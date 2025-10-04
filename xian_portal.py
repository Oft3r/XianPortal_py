#!/usr/bin/env python3
"""
Xian Portal - Main Entry Point
A professional wallet manager for the Xian blockchain network.

This is the main script that launches the Xian Portal application.
Simply run this file to start the wallet interface.

Usage:
    python xian_portal.py
"""



import sys
import os

# Add the project root to Python path to enable imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.wallet_ui import WalletUI



def main():

    try:
        app = WalletUI()
        app.mainloop()
    except KeyboardInterrupt:
        print("\n\nXian Portal closed by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
