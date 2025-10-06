# Xian Portal

A desktop wallet manager for the Xian blockchain network.

## Features

- Create HD wallets with 24-word mnemonic phrases
- Import wallets from mnemonic or private key
- View token balances (XIAN and custom tokens)
- **Send Tokens** - Beautiful modal with real-time validation, balance checking, and fee estimation
- **Receive Tokens** - QR code generation and address sharing
- Manage custom tokens (add, edit, remove via Token Manager dialog)
- Secure encrypted storage (Windows DPAPI, macOS Keychain, Linux Secret Service)
- Clean Tkinter interface with modern design
- **System Tray Support** - Minimize wallet to system tray icon

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

### System Tray

The wallet can be minimized to the system tray to keep it running in the background:

1. Click the **Settings** icon (gear) in the bottom navigation
2. In the "Window" section, click **Minimize to Tray**
3. The wallet will minimize to your system tray
4. **Right-click** the tray icon to see options:
   - **Show Wallet** - Restore the wallet window
   - **Quit** - Close the wallet completely

**Note**: When minimized to tray, the wallet continues to run in the background. You can restore it anytime by clicking the tray icon.

### Sending Tokens 🚀

The wallet includes a beautiful Send modal for secure token transfers:

1. Navigate to any token in your wallet
2. Click the **Send** button
3. Enter recipient address (or paste from clipboard)
4. Enter amount (or click **MAX** for full balance)
5. Add optional memo/note
6. Review transaction summary with fees
7. Confirm and send!

**Features:**
- ✅ Real-time input validation
- ✅ Balance checking (prevents overspending)
- ✅ Address format verification
- ✅ Fee estimation (~0.001 XIAN)
- ✅ MAX button for sending full balance
- ✅ Paste button for quick address entry
- ✅ Optional transaction memo
- ✅ Confirmation dialog before sending

**Try the demo:**
```bash
python demo_send_modal.py
```

For detailed documentation, see [SEND_MODAL_README.md](SEND_MODAL_README.md) or [Quick Start Guide](SEND_MODAL_QUICKSTART.md).

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
├── demo_send_modal.py      # Demo for Send modal UI
├── src/
│   ├── ui/
│   │   ├── wallet_ui.py           # Main wallet interface (Tkinter-based)
│   │   ├── send_modal.py          # Send transaction modal dialog
│   │   ├── token_details_screen.py # Token details view
│   │   ├── system_tray.py         # System tray functionality
│   │   └── ui_utils.py            # Shared UI utilities
│   ├── core/
│   │   └── wallet_manager.py      # Wallet creation/import/balances
│   └── storage/
│       ├── config_store.py        # Token and configuration storage
│       └── secure_store.py        # Encrypted wallet storage
└── scripts/                       # Utility scripts
```

## Dependencies

- Python 3.10+
- xian-py (Xian network client)
- keyring (recommended for cross-platform security)
- cryptography (for AES-GCM encryption)
- pystray (system tray icon support)
- Pillow (image processing for tray icons)

## License

MIT License - See LICENSE file for details.

---

**⚠️ Important**: Always backup your mnemonic phrase. Store it securely offline.