# Xian Portal

A desktop wallet manager for the Xian blockchain network.

## Features

- Create HD wallets with 24-word mnemonic phrases
- Import wallets from mnemonic or private key
- View token balances (XIAN and custom tokens)
- Secure encrypted storage (Windows DPAPI, macOS Keychain, Linux Secret Service)
- Clean Tkinter interface with modern design

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the main script:

```bash
python xian_portal.py
```

**Note for Windows users**: If you use `py` command, run:
```bash
python xian_portal.py
```
Or simply double-click `run.bat` in the project folder.

### First Time

1. Configure your node URL (or use default)
2. Create a new wallet or import an existing one
3. **Save your mnemonic phrase securely!**

### Keyboard Shortcuts

- `Ctrl+N` - Create wallet
- `Ctrl+I` - Import wallet
- `Ctrl+U` - Set node URL
- `F5` - Refresh balances

## Security

Your wallet is encrypted using:
- **XWAL3** (Recommended): System keyring + AES-256-GCM
- **XWAL1** (Windows): DPAPI encryption
- **XWAL2** (Fallback): Password-based encryption

Storage location:
- Windows: `%APPDATA%\XianWallet\wallet_store.bin`
- macOS/Linux: `~/.local/share/XianWallet/wallet_store.bin`

## Project Structure

```
XianPortal_py/
├── xian_portal.py          # Main entry point - Run this!
├── src/
│   ├── ui/                 # User interface
│   ├── core/               # Wallet operations
│   └── storage/            # Encrypted storage
└── scripts/                # Utility scripts
```

## Dependencies

- Python 3.10+
- xian-py (Xian network client)
- keyring (recommended for cross-platform security)
- cryptography (for AES-GCM encryption)

## License

MIT License - See LICENSE file for details.

---

**⚠️ Important**: Always backup your mnemonic phrase. Store it securely offline.