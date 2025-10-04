"""
Xian Portal - A professional wallet manager for the Xian blockchain network.

This package provides a complete desktop application for managing Xian wallets
with enterprise-grade security features, including cross-platform encrypted storage,
HD wallet support, and an intuitive GUI interface.

Modules:
    ui: User interface components built with Tkinter
    core: Core business logic and wallet management
    storage: Secure data persistence and configuration management

Usage:
    from src.ui.wallet_ui import WalletUI

    app = WalletUI()
    app.mainloop()
"""

__version__ = "1.0.0"
__author__ = "Xian Portal Team"
__license__ = "MIT"

# Package metadata
__all__ = [
    "__version__",
    "__author__",
    "__license__",
]

# Note: Individual modules should be imported directly as needed
# Example: from src.ui.wallet_ui import WalletUI
# Example: from src.core.wallet_manager import WalletManager
