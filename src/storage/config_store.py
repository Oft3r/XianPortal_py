# JSON-based config store for custom tokens (English version)

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional, TypedDict, NotRequired


APP_DIR_NAME = "XianWallet"
CONFIG_FILE = "config.json"
_LOCK = threading.RLock()


class TokenConfig(TypedDict):
    """
    Token structure in the configuration.
    - name: human-readable token name (e.g., "XIAN Currency")
    - symbol: ticker (e.g., "XIAN")
    - contract: on-chain identifier/contract (e.g., "currency" or "con_xwt")
    - icon: short text or icon alias (e.g., "XN", "XWT")
    - pinned: reserved for future use (e.g., highlight in UI)
    """
    name: str
    symbol: str
    contract: str
    icon: NotRequired[str]
    pinned: NotRequired[bool]


def _app_data_dir() -> str:
    """
    Return the app data directory (creating it if it doesn't exist).
    Windows: %APPDATA%/XianWallet
    macOS/Linux: ~/.local/share/XianWallet
    """
    if os.name == "nt":
        base = os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~/.local/share")
    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_config_path() -> str:
    """Absolute path to the JSON configuration file."""
    return os.path.join(_app_data_dir(), CONFIG_FILE)


def _default_tokens() -> List[TokenConfig]:
    """
    Default tokens that the UI already shows.
    Note: keep in sync with the UI.
    """
    return [
        {
            "name": "XIAN Currency",
            "symbol": "XIAN",
            "contract": "currency",
            "icon": "XN",
        },
        {
            "name": "XIAN Wallet Token",
            "symbol": "XWT",
            "contract": "con_xwt",
            "icon": "XWT",
        },
    ]


def _default_config() -> Dict[str, Any]:
    return {
        "version": 1,
        "tokens": _default_tokens(),
        "ui": {},  # reserved for future UI settings (theme, layout, etc.)
    }


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """
    Atomic write: write to a temporary file and replace the destination.
    """
    tmp = path + ".tmp"
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    # os.replace is atomic on Windows/Unix
    os.replace(tmp, path)


def _normalize_token(t: Dict[str, Any]) -> Optional[TokenConfig]:
    """
    Validate/sanitize a token dictionary. Return None if invalid.
    Minimum rules:
      - name, symbol, contract: non-empty str
      - reasonable lengths (<= 128)
    """
    try:
        name = str(t.get("name", "")).strip()
        symbol = str(t.get("symbol", "")).strip()
        contract = str(t.get("contract", "")).strip()
        icon = str(t.get("icon", "")).strip()
        pinned = bool(t.get("pinned", False))
        if not name or not symbol or not contract:
            return None
        if (
            len(name) > 128
            or len(symbol) > 128
            or len(contract) > 128
            or len(icon) > 128
        ):
            return None
        return TokenConfig(
            name=name, symbol=symbol, contract=contract, icon=icon, pinned=pinned
        )
    except Exception:
        return None


def _ensure_unique_contracts(tokens: List[TokenConfig]) -> List[TokenConfig]:
    seen: set[str] = set()
    unique: List[TokenConfig] = []
    for t in tokens:
        c = t.get("contract", "")
        if c and c not in seen:
            unique.append(t)
            seen.add(c)
    return unique


def _merge_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure default tokens exist if they're not already present.
    """
    tokens: List[TokenConfig] = [
        t for t in map(_normalize_token, cfg.get("tokens", [])) if t
    ]
    present = {t["contract"] for t in tokens}
    for d in _default_tokens():
        if d["contract"] not in present:
            tokens.append(d)
    cfg["tokens"] = _ensure_unique_contracts(tokens)
    return cfg


def load_config() -> Dict[str, Any]:
    """
    Load configuration from disk.
    - If it doesn't exist: create and return defaults.
    - If corrupted/invalid: return defaults without overwriting the broken file.
    - Always ensure defaults are included.
    """
    path = get_config_path()
    with _LOCK:
        raw = _read_file(path)
        if raw is None:
            cfg = _default_config()
            # Save immediately to create the file if missing
            try:
                _atomic_write_json(path, cfg)
            except Exception:
                pass
            return cfg
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Config root is not a JSON object")
        except Exception:
            # Recovery: return defaults without overwriting the broken file
            return _default_config()

        # Normalize minimal structure
        if "version" not in data or not isinstance(data.get("version"), int):
            data["version"] = 1
        if "tokens" not in data or not isinstance(data.get("tokens"), list):
            data["tokens"] = []
        if "ui" not in data or not isinstance(data.get("ui"), dict):
            data["ui"] = {}
        # Clean invalid tokens and merge defaults
        data["tokens"] = [t for t in map(_normalize_token, data["tokens"]) if t]
        data = _merge_defaults(data)
        return data


def save_config(cfg: Dict[str, Any]) -> None:
    """
    Save configuration to disk atomically.
    - Normalize structure and avoid duplicates by 'contract'.
    """
    path = get_config_path()
    with _LOCK:
        norm: Dict[str, Any] = {
            "version": int(cfg.get("version", 1)),
            "ui": cfg.get("ui", {}) if isinstance(cfg.get("ui"), dict) else {},
        }
        tokens_raw = cfg.get("tokens", [])
        if not isinstance(tokens_raw, list):
            tokens_raw = []
        tokens: List[TokenConfig] = [t for t in map(_normalize_token, tokens_raw) if t]
        norm["tokens"] = _ensure_unique_contracts(tokens)
        norm = _merge_defaults(norm)
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _atomic_write_json(path, norm)


def get_tokens() -> List[TokenConfig]:
    """Return the list of tokens (includes defaults)."""
    cfg = load_config()
    tokens = cfg.get("tokens", [])
    # Defensive copy
    return [TokenConfig(**t) for t in tokens]


def set_tokens(tokens: List[Dict[str, Any]]) -> None:
    """
    Replace the token list with the given one (defaults will be merged).
    """
    cfg = load_config()
    cfg["tokens"] = [t for t in map(_normalize_token, tokens) if t]
    save_config(cfg)


def add_token(
    name: str, symbol: str, contract: str, icon: str = "", pinned: bool = False
) -> bool:
    """
    Add a custom token. Return True if it was added, False if a token with that
    contract already existed.
    """
    new_tok = _normalize_token(
        {
            "name": name,
            "symbol": symbol,
            "contract": contract,
            "icon": icon,
            "pinned": pinned,
        }
    )
    if not new_tok:
        raise ValueError("Invalid token data")
    cfg = load_config()
    tokens: List[TokenConfig] = cfg.get("tokens", [])
    if any(t.get("contract") == new_tok["contract"] for t in tokens):
        return False
    tokens.append(new_tok)
    cfg["tokens"] = tokens
    save_config(cfg)
    return True


def upsert_token(
    name: str, symbol: str, contract: str, icon: str = "", pinned: bool = False
) -> None:
    """
    Insert or update a token identified by its 'contract'.
    """
    upd = _normalize_token(
        {
            "name": name,
            "symbol": symbol,
            "contract": contract,
            "icon": icon,
            "pinned": pinned,
        }
    )
    if not upd:
        raise ValueError("Invalid token data")
    cfg = load_config()
    tokens: List[TokenConfig] = cfg.get("tokens", [])
    replaced = False
    for i, t in enumerate(tokens):
        if t.get("contract") == contract:
            tokens[i] = upd
            replaced = True
            break
    if not replaced:
        tokens.append(upd)
    cfg["tokens"] = tokens
    save_config(cfg)


def remove_token(contract: str) -> bool:
    """
    Remove a token by its 'contract'.
    Returns True if it was removed; False if it didn't exist or if it's a default token.
    """
    contract = (contract or "").strip()
    if not contract:
        return False
    # Do not allow deleting defaults
    default_contracts = {t["contract"] for t in _default_tokens()}
    if contract in default_contracts:
        return False
    cfg = load_config()
    tokens: List[TokenConfig] = cfg.get("tokens", [])
    new_tokens = [t for t in tokens if t.get("contract") != contract]
    if len(new_tokens) == len(tokens):
        return False
    cfg["tokens"] = new_tokens
    save_config(cfg)
    return True


def is_default_contract(contract: str) -> bool:
    """Return True if the contract belongs to the default tokens."""
    c = (contract or "").strip()
    return any(t["contract"] == c for t in _default_tokens())


__all__ = [
    "TokenConfig",
    "get_config_path",
    "load_config",
    "save_config",
    "get_tokens",
    "set_tokens",
    "add_token",
    "upsert_token",
    "remove_token",
    "is_default_contract",
]
