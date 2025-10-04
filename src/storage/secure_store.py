from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
import sys
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.wallet_manager import WalletInfo


APP_DIR_NAME = "XianWallet"
STORE_FILE = "wallet_store.bin"
MAGIC = b"XWAL1\0"       # Windows DPAPI format (existing)
MAGIC_PW = b"XWAL2\0"     # Cross-platform password-based format
MAGIC_KR = b"XWAL3\0"     # Cross-platform keyring-managed AES-GCM


def _app_data_dir() -> str:
    if os.name == 'nt':
        base = os.getenv('APPDATA') or os.path.expanduser('~')
    else:
        base = os.path.expanduser('~/.local/share')
    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _store_path() -> str:
    return os.path.join(_app_data_dir(), STORE_FILE)


def _is_windows() -> bool:
    return os.name == 'nt' or sys.platform.startswith('win')


def _keyring_available() -> bool:
    try:
        import keyring  # type: ignore
        return True
    except Exception:
        return False


def requires_password() -> bool:
    # If Windows DPAPI or system keyring is available, no password required
    if _is_windows():
        return False
    return not _keyring_available()


def store_exists() -> bool:
    return os.path.exists(_store_path())


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _to_blob(data: bytes) -> _DATA_BLOB:
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))


def _from_blob(blob: _DATA_BLOB) -> bytes:
    size = int(blob.cbData)
    ptr = ctypes.cast(blob.pbData, ctypes.POINTER(ctypes.c_ubyte))
    out = bytes(bytearray(ptr[i] for i in range(size)))
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return out


def _dpapi_encrypt(data: bytes) -> bytes:
    in_blob = _to_blob(data)
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return _from_blob(out_blob)
    finally:
        pass


def _dpapi_decrypt(data: bytes) -> bytes:
    in_blob = _to_blob(data)
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return _from_blob(out_blob)
    finally:
        pass


def _encrypt(data: bytes) -> bytes:
    if not _is_windows():
        raise RuntimeError("DPAPI only available on Windows")
    enc = _dpapi_encrypt(data)
    return MAGIC + base64.b64encode(enc)


def _decrypt(payload: bytes) -> bytes:
    if not payload.startswith(MAGIC):
        raise ValueError("Invalid file format")
    raw = base64.b64decode(payload[len(MAGIC):])
    if not _is_windows():
        raise RuntimeError("DPAPI only available on Windows")
    return _dpapi_decrypt(raw)


# ----- Password-based (non-Windows): scrypt + AESGCM -----
def _encrypt_pw(data: bytes, password: str) -> bytes:
    import os as _os
    import json as _json
    import base64 as _b64
    import hashlib
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency for AES-GCM encryption. Install with: pip install cryptography") from e

    salt = _os.urandom(16)
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    aesgcm = AESGCM(key)
    nonce = _os.urandom(12)
    ct = aesgcm.encrypt(nonce, data, None)
    meta = {
        "v": 2,
        "alg": "AESGCM",
        "kdf": "scrypt",
        "params": {"n": 16384, "r": 8, "p": 1},
        "salt": _b64.b64encode(salt).decode('ascii'),
        "nonce": _b64.b64encode(nonce).decode('ascii'),
        "ct": _b64.b64encode(ct).decode('ascii'),
    }
    blob = _json.dumps(meta, ensure_ascii=False).encode('utf-8')
    return MAGIC_PW + blob


def _decrypt_pw(payload: bytes, password: str) -> bytes:
    import json as _json
    import base64 as _b64
    import hashlib
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency for AES-GCM encryption. Install with: pip install cryptography") from e

    meta = _json.loads(payload[len(MAGIC_PW):].decode('utf-8'))
    if meta.get("alg") != "AESGCM" or meta.get("kdf") != "scrypt":
        raise ValueError("Unsupported encryption format")
    params = meta.get("params") or {}
    n, r, p = int(params.get("n", 16384)), int(params.get("r", 8)), int(params.get("p", 1))
    salt = _b64.b64decode(meta["salt"])  # type: ignore
    nonce = _b64.b64decode(meta["nonce"])  # type: ignore
    ct = _b64.b64decode(meta["ct"])  # type: ignore
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=n, r=r, p=p, dklen=32)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ----- Keyring-based cross-platform AESGCM -----
_KR_SERVICE = "XianWallet"
_KR_USER = "wallet-key"


def _get_keyring_key(create: bool = False) -> Optional[bytes]:
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    val = keyring.get_password(_KR_SERVICE, _KR_USER)
    if val:
        try:
            return base64.b64decode(val)
        except Exception:
            return None
    if create:
        import os as _os
        key = _os.urandom(32)
        try:
            keyring.set_password(_KR_SERVICE, _KR_USER, base64.b64encode(key).decode('ascii'))
            return key
        except Exception:
            return None
    return None


def _encrypt_keyring(data: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency for AES-GCM encryption. Install with: pip install cryptography") from e
    key = _get_keyring_key(create=True)
    if not key:
        raise RuntimeError("Could not access the system keyring")
    import os as _os, json as _json, base64 as _b64
    nonce = _os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, data, None)
    meta = {
        "v": 3,
        "mode": "keyring",
        "nonce": _b64.b64encode(nonce).decode('ascii'),
        "ct": _b64.b64encode(ct).decode('ascii'),
    }
    blob = _json.dumps(meta, ensure_ascii=False).encode('utf-8')
    return MAGIC_KR + blob


def _decrypt_keyring(payload: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency for AES-GCM encryption. Install with: pip install cryptography") from e
    import json as _json, base64 as _b64
    meta = _json.loads(payload[len(MAGIC_KR):].decode('utf-8'))
    key = _get_keyring_key(create=False)
    if not key:
        raise RuntimeError("Could not access the system keyring")
    aesgcm = AESGCM(key)
    nonce = _b64.b64decode(meta["nonce"])  # type: ignore
    ct = _b64.b64decode(meta["ct"])  # type: ignore
    return aesgcm.decrypt(nonce, ct, None)


def save_wallet(info: "WalletInfo", *, node_url: Optional[str] = None, password: Optional[str] = None) -> None:
    from src.core.wallet_manager import WalletInfo
    obj: Dict[str, Any] = {
        "private_key": info.private_key,
        "public_key": info.public_key,
        "mnemonic": info.mnemonic,
        "node_url": node_url or "",
    }
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    # Prefer keyring on all platforms if available
    if _keyring_available():
        enc = _encrypt_keyring(data)
    elif _is_windows():
        enc = _encrypt(data)
    else:
        if not password:
            raise RuntimeError("A password is required to save the wallet on this system")
        enc = _encrypt_pw(data, password)
    with open(_store_path(), "wb") as f:
        f.write(enc)


def load_wallet(password: Optional[str] = None) -> Tuple[Optional["WalletInfo"], Optional[str]]:
    from src.core.wallet_manager import WalletInfo
    path = _store_path()
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, "rb") as f:
            payload = f.read()
        if payload.startswith(MAGIC_KR):
            plain = _decrypt_keyring(payload)
        elif payload.startswith(MAGIC):
            plain = _decrypt(payload)
        elif payload.startswith(MAGIC_PW):
            if not password:
                raise RuntimeError("A password is required to load the wallet on this system")
            plain = _decrypt_pw(payload, password)
        else:
            raise ValueError("Unknown wallet format")
        obj = json.loads(plain.decode("utf-8"))
        info = WalletInfo(
            private_key=obj.get("private_key", ""),
            public_key=obj.get("public_key", ""),
            mnemonic=obj.get("mnemonic") or None,
        )
        node_url = obj.get("node_url") or None
        return info, node_url
    except Exception:
        return None, None


def clear_wallet() -> None:
    path = _store_path()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ----- Portable encrypted JSON backup (password-based) -----
def create_portable_backup(info: "WalletInfo", *, node_url: Optional[str], password: str) -> str:
    from src.core.wallet_manager import WalletInfo
    """Create a portable encrypted JSON backup using scrypt + AES-GCM.
    Returns a JSON string that can be saved as a file and restored on any OS.
    """
    obj: Dict[str, Any] = {
        "private_key": info.private_key,
        "public_key": info.public_key,
        "mnemonic": info.mnemonic,
        "node_url": node_url or "",
    }
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    # Reuse password-based path for portability
    import os as _os, json as _json, base64 as _b64, hashlib
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency to export encrypted backup. Install with: pip install cryptography") from e
    salt = _os.urandom(16)
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    nonce = _os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, data, None)
    meta = {
        "v": 2,
        "type": "portable",
        "alg": "AESGCM",
        "kdf": "scrypt",
        "params": {"n": 16384, "r": 8, "p": 1},
        "salt": _b64.b64encode(salt).decode('ascii'),
        "nonce": _b64.b64encode(nonce).decode('ascii'),
        "ct": _b64.b64encode(ct).decode('ascii'),
    }
    return _json.dumps(meta, ensure_ascii=False)


def restore_portable_backup(blob: str, *, password: str) -> Tuple["WalletInfo", Optional[str]]:
    from src.core.wallet_manager import WalletInfo
    """Restore from a portable encrypted JSON backup created above."""
    import json as _json, base64 as _b64, hashlib
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing 'cryptography' dependency to import encrypted backup. Install with: pip install cryptography") from e
    meta = _json.loads(blob)
    if meta.get("kdf") != "scrypt" or meta.get("alg") != "AESGCM":
        raise ValueError("Unsupported backup format")
    params = meta.get("params") or {}
    n, r, p = int(params.get("n", 16384)), int(params.get("r", 8)), int(params.get("p", 1))
    salt = _b64.b64decode(meta["salt"])  # type: ignore
    nonce = _b64.b64decode(meta["nonce"])  # type: ignore
    ct = _b64.b64decode(meta["ct"])  # type: ignore
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=n, r=r, p=p, dklen=32)
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(nonce, ct, None)
    obj = json.loads(plain.decode("utf-8"))
    info = WalletInfo(
        private_key=obj.get("private_key", ""),
        public_key=obj.get("public_key", ""),
        mnemonic=obj.get("mnemonic") or None,
    )
    node_url = obj.get("node_url") or None
    return info, node_url
