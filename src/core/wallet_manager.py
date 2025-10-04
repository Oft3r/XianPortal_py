

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

try:
    # Installed via: pip install git+https://github.com/xian-network/xian-py.git
    from xian_py import wallet as xw
except Exception as e:  # pragma: no cover
    raise ImportError("xian-py is required. Install with pip.") from e


# Default BIP44-like path hardened internally by xian-py HDWallet.get_wallet
# This becomes effectively m/44'/0'/0'/0'/0'
DEFAULT_DERIVATION_PATH: List[int] = [44, 0, 0, 0, 0]


@dataclass
class WalletInfo:
    private_key: str
    public_key: str
    mnemonic: Optional[str] = None


class WalletManager:
    def __init__(self, derivation_path: Optional[List[int]] = None):
        self.derivation_path = derivation_path or DEFAULT_DERIVATION_PATH

    # --- HD Wallets ---
    def create_hd_wallet(self) -> WalletInfo:
        hd = xw.HDWallet()  # generates a 24-word mnemonic
        w = hd.get_wallet(self.derivation_path)
        return WalletInfo(
            private_key=w.private_key,
            public_key=w.public_key,
            mnemonic=hd.mnemonic_str,
        )

    def import_hd_wallet(self, mnemonic: str) -> WalletInfo:
        hd = xw.HDWallet(mnemonic)
        w = hd.get_wallet(self.derivation_path)
        return WalletInfo(
            private_key=w.private_key,
            public_key=w.public_key,
            mnemonic=hd.mnemonic_str,
        )

    # --- Raw key wallets ---
    def import_private_key(self, private_key_hex: str) -> WalletInfo:
        if not xw.Wallet.is_valid_key(private_key_hex):
            raise ValueError("Invalid private key: must be 64-char hex")
        w = xw.Wallet(private_key_hex)
        return WalletInfo(private_key=w.private_key, public_key=w.public_key)

    # --- Utilities ---
    def sign_message(self, private_key_hex: str, message: str) -> str:
        w = xw.Wallet(private_key_hex)
        return w.sign_msg(message)

    def verify_message(self, public_or_private_key_hex: str, message: str, signature_hex: str) -> bool:
        # xian-py Wallet takes a private key for SigningKey. If we receive a
        # public key, verification will fail; users should pass the same
        # private used to sign or wrap verification separately with VerifyKey
        try:
            w = xw.Wallet(public_or_private_key_hex)
        except Exception:
            # When a public key is passed, construct VerifyKey path using wallet module
            try:
                from xian_py.wallet import VerifyKey  # type: ignore
                vk = VerifyKey(bytes.fromhex(public_or_private_key_hex))
                try:
                    vk.verify(message.encode(), bytes.fromhex(signature_hex))
                    return True
                except Exception:
                    return False
            except Exception:
                return False
        return w.verify_msg(message, signature_hex)
