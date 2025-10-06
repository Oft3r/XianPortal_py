import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Callable, Optional
import re

if TYPE_CHECKING:
    from .wallet_ui import WalletUI, TokenRow

from src.ui.ui_utils import create_round_rect, lerp_color


class SendScreen:

    def __init__(self, master: 'WalletUI', parent, token_data: 'TokenRow', on_send: Optional[Callable] = None, on_back: Optional[Callable] = None):
        self.master = master
        self.parent = parent
        self.token_data = token_data
        self.on_send = on_send
        self.on_back = on_back

        # Create main frame for the send screen
        self.frame = tk.Frame(parent, bg="#0b1417")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Create scrollable canvas
        self.canvas = tk.Canvas(self.frame, bg="#0b1417", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#0b1417")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Keep inner frame width in sync with canvas to avoid horizontal overflow
        self.scroll_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.scroll_window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Main container with minimal padding
        self.main_frame = tk.Frame(self.scrollable_frame, bg="#0b1417")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # Build UI sections
        self._create_header()
        self._create_balance_section()
        self._create_recipient_section()
        self._create_amount_section()
        self._create_memo_section()
        self._create_transaction_summary()
        self._create_action_buttons()

        # Focus on recipient field
        self.recipient_entry.focus_set()

        # Bind mousewheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _create_header(self):
        header_frame = tk.Frame(self.main_frame, bg="#0b1417")
        header_frame.pack(fill=tk.X, pady=(0, 8))

        # Token icon (small circle with symbol)
        icon_frame = tk.Canvas(header_frame, width=40, height=40, bg="#0b1417",
                              highlightthickness=0)
        icon_frame.pack(side=tk.LEFT, padx=(0, 10))

        # Draw icon circle with gradient effect
        create_round_rect(icon_frame, 2, 2, 38, 38, r=19, fill="#0a1215", outline="#0a1215")
        create_round_rect(icon_frame, 0, 0, 36, 36, r=18, fill="#0f1b1f", outline="#1a2a2f")

        # Icon text
        icon_frame.create_text(19, 19, text=self.token_data.get("icon", "T"),
                              fill="#7ee1a6", font=("Segoe UI", 13, "bold"))

        # Header text
        text_frame = tk.Frame(header_frame, bg="#0b1417")
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        title = tk.Label(text_frame, text=f"Send {self.token_data['symbol']}",
                        font=("Segoe UI", 13, "bold"), fg="#e8f6f7", bg="#0b1417")
        title.pack(anchor="w")

        subtitle = tk.Label(text_frame, text=self.token_data['name'],
                           font=("Segoe UI", 9), fg="#8aa4aa", bg="#0b1417")
        subtitle.pack(anchor="w")

        # Back button (←)
        back_btn = tk.Label(header_frame, text="←", font=("Segoe UI", 14),
                           fg="#9ab0b5", bg="#0b1417", cursor="hand2")
        back_btn.pack(side=tk.RIGHT)
        back_btn.bind("<Button-1>", lambda e: self._handle_back())
        back_btn.bind("<Enter>", lambda e: back_btn.config(fg="#e8f6f7"))
        back_btn.bind("<Leave>", lambda e: back_btn.config(fg="#9ab0b5"))

    def _create_balance_section(self):
        # Container for balance card
        container = tk.Frame(self.main_frame, bg="#0b1417")
        container.pack(fill=tk.X, pady=(0, 8))

        balance_frame = tk.Canvas(container, height=50, bg="#0b1417",
                                 highlightthickness=0)
        balance_frame.pack(fill=tk.X)

        # Schedule drawing after widget is sized
        balance_frame.update_idletasks()
        width = balance_frame.winfo_width()
        if width < 10:
            width = 350

        # Card with gradient
        create_round_rect(balance_frame, 1, 1, width-1, 49, r=8, fill="#0a1215", outline="#0a1215")
        create_round_rect(balance_frame, 0, 0, width-2, 48, r=8, fill="#0f1b1f", outline="#1a2a2f")

        # Text
        balance_frame.create_text(10, 10, text="Available Balance",
                                 anchor="w", fill="#8aa4aa", font=("Segoe UI", 8))

        balance = self.token_data.get("balance")
        balance_text = "0.000" if balance is None else f"{balance:,.6f}".rstrip('0').rstrip('.')
        balance_frame.create_text(10, 32, text=f"{balance_text} {self.token_data['symbol']}",
                                 anchor="w", fill="#e8f6f7", font=("Segoe UI", 12, "bold"))

    def _create_recipient_section(self):
        """Create recipient address input"""
        section_frame = tk.Frame(self.main_frame, bg="#0b1417")
        section_frame.pack(fill=tk.X, pady=(0, 8))

        # Label with icon
        label_frame = tk.Frame(section_frame, bg="#0b1417")
        label_frame.pack(fill=tk.X, pady=(0, 4))

        label = tk.Label(label_frame, text="📬  Recipient Address",
                        font=("Segoe UI", 9, "bold"), fg="#dbe9ea", bg="#0b1417")
        label.pack(side=tk.LEFT)

        required = tk.Label(label_frame, text="*", font=("Segoe UI", 9, "bold"),
                          fg="#e85555", bg="#0b1417")
        required.pack(side=tk.LEFT, padx=(2, 0))

        # Paste button (moved to label line)
        paste_btn = tk.Button(label_frame, text="📋",
                            command=self._paste_address,
                            font=("Segoe UI", 8), bg="#142127", fg="#9ac6cc",
                            relief="flat", cursor="hand2",
                            activebackground="#1a2f35", activeforeground="#cfe6ea")
        paste_btn.pack(side=tk.RIGHT)

        # Input field with custom styling
        input_frame = tk.Frame(section_frame, bg="#1a2a2f", relief="solid", bd=1)
        input_frame.pack(fill=tk.X)

        self.recipient_entry = tk.Entry(input_frame, font=("Courier New", 9),
                                       bg="#0e181b", fg="#dbe9ea", relief="flat",
                                       insertbackground="#7ee1a6", bd=0)
        self.recipient_entry.pack(fill=tk.BOTH, padx=2, pady=2, ipady=6, ipadx=6)

        # Validation hint (smaller)
        self.recipient_hint = tk.Label(section_frame, text="Enter wallet address",
                                      font=("Segoe UI", 7), fg="#6a7a7e", bg="#0b1417")
        self.recipient_hint.pack(anchor="w", pady=(2, 0))

    def _create_amount_section(self):
        section_frame = tk.Frame(self.main_frame, bg="#0b1417")
        section_frame.pack(fill=tk.X, pady=(0, 8))

        # Label
        label_frame = tk.Frame(section_frame, bg="#0b1417")
        label_frame.pack(fill=tk.X, pady=(0, 4))

        label = tk.Label(label_frame, text="💰  Amount",
                        font=("Segoe UI", 9, "bold"), fg="#dbe9ea", bg="#0b1417")
        label.pack(side=tk.LEFT)

        required = tk.Label(label_frame, text="*", font=("Segoe UI", 9, "bold"),
                          fg="#e85555", bg="#0b1417")
        required.pack(side=tk.LEFT, padx=(2, 0))

        # Input container
        input_container = tk.Frame(section_frame, bg="#0b1417")
        input_container.pack(fill=tk.X)

        # Input field
        input_frame = tk.Frame(input_container, bg="#1a2a2f", relief="solid", bd=1)
        input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.amount_entry = tk.Entry(input_frame, font=("Segoe UI", 10),
                                    bg="#0e181b", fg="#e8f6f7", relief="flat",
                                    insertbackground="#7ee1a6", bd=0)
        self.amount_entry.pack(fill=tk.BOTH, padx=2, pady=2, ipady=6, ipadx=6)
        self.amount_entry.bind("<KeyRelease>", self._validate_amount)

        # MAX button
        max_btn = tk.Button(input_container, text="MAX",
                          command=self._set_max_amount,
                          font=("Segoe UI", 8, "bold"), bg="#7ee1a6", fg="#0f2a21",
                          relief="flat", cursor="hand2", width=5,
                          activebackground="#6bd090", activeforeground="#0f2a21")
        max_btn.pack(side=tk.LEFT, padx=(6, 0), ipady=6)

        # Validation hint
        self.amount_hint = tk.Label(section_frame, text="Enter amount",
                                   font=("Segoe UI", 7), fg="#6a7a7e", bg="#0b1417")
        self.amount_hint.pack(anchor="w", pady=(2, 0))

    def _create_memo_section(self):
        section_frame = tk.Frame(self.main_frame, bg="#0b1417")
        section_frame.pack(fill=tk.X, pady=(0, 8))

        # Label
        label_frame = tk.Frame(section_frame, bg="#0b1417")
        label_frame.pack(fill=tk.X, pady=(0, 4))

        label = tk.Label(label_frame, text="📝  Memo (Optional)",
                        font=("Segoe UI", 9, "bold"), fg="#dbe9ea", bg="#0b1417")
        label.pack(side=tk.LEFT)

        # Input field
        input_frame = tk.Frame(section_frame, bg="#1a2a2f", relief="solid", bd=1)
        input_frame.pack(fill=tk.X)

        self.memo_entry = tk.Entry(input_frame, font=("Segoe UI", 9),
                                  bg="#0e181b", fg="#dbe9ea", relief="flat",
                                  insertbackground="#7ee1a6", bd=0)
        self.memo_entry.pack(fill=tk.BOTH, padx=2, pady=2, ipady=6, ipadx=6)

    def _create_transaction_summary(self):
        # Container for summary card
        container = tk.Frame(self.main_frame, bg="#0b1417")
        container.pack(fill=tk.X, pady=(0, 8))

        summary_frame = tk.Canvas(container, height=60, bg="#0b1417",
                                 highlightthickness=0)
        summary_frame.pack(fill=tk.X)

        # Schedule drawing after widget is sized
        summary_frame.update_idletasks()
        width = summary_frame.winfo_width()
        if width < 10:  # Not sized yet, use default
            width = 350

        # Card background
        create_round_rect(summary_frame, 1, 1, width-1, 59, r=8, fill="#0a1215", outline="#0a1215")
        create_round_rect(summary_frame, 0, 0, width-2, 58, r=8, fill="#0f1b1f", outline="#1a2a2f")

        # Title
        summary_frame.create_text(10, 10, text="Summary",
                                 anchor="w", fill="#8aa4aa", font=("Segoe UI", 8, "bold"))

        # Fee estimate
        summary_frame.create_text(10, 28, text="Fee:",
                                 anchor="w", fill="#9ab0b5", font=("Segoe UI", 8))
        self.fee_text = summary_frame.create_text(width-10, 28, text="~0.001 XIAN",
                                 anchor="e", fill="#dbe9ea", font=("Segoe UI", 8))

        # Total
        summary_frame.create_line(10, 38, width-10, 38, fill="#1a2a2f", width=1)
        summary_frame.create_text(10, 48, text="Total:",
                                 anchor="w", fill="#7ee1a6", font=("Segoe UI", 9, "bold"))
        self.total_text = summary_frame.create_text(width-10, 48, text="0.000",
                                                    anchor="e", fill="#7ee1a6",
                                                    font=("Segoe UI", 9, "bold"))

    def _create_action_buttons(self):
        btn_frame = tk.Frame(self.main_frame, bg="#0b1417")
        btn_frame.pack(fill=tk.X, pady=(0, 0))

        # Cancel button
        cancel_btn = tk.Button(btn_frame, text="Cancel",
                              command=self._handle_back,
                              font=("Segoe UI", 10, "bold"), bg="#142127", fg="#9ab0b5",
                              relief="flat", cursor="hand2",
                              activebackground="#1a2f35", activeforeground="#cfe6ea")
        cancel_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6), ipady=8)

        # Send button (prominent)
        self.send_btn = tk.Button(btn_frame, text="🚀  Send",
                                  command=self._handle_send,
                                  font=("Segoe UI", 10, "bold"), bg="#7ee1a6", fg="#0f2a21",
                                  relief="flat", cursor="hand2",
                                  activebackground="#6bd090", activeforeground="#0f2a21")
        self.send_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), ipady=8)

    def _paste_address(self):
        try:
            clipboard_text = self.master.clipboard_get()
            self.recipient_entry.delete(0, tk.END)
            self.recipient_entry.insert(0, clipboard_text.strip())
            self._validate_recipient()
        except tk.TclError:
            messagebox.showwarning("Paste Error", "Clipboard is empty or unavailable.")

    def _set_max_amount(self):
        balance = self.token_data.get("balance")
        if balance is not None and balance > 0:
            # Leave small amount for fees (0.001)
            max_amount = max(0, balance - 0.001)
            self.amount_entry.delete(0, tk.END)
            self.amount_entry.insert(0, f"{max_amount:.6f}".rstrip('0').rstrip('.'))
            self._validate_amount()

    def _validate_amount(self, event=None):
        amount_text = self.amount_entry.get().strip()

        if not amount_text:
            self.amount_hint.config(text="Enter amount", fg="#6a7a7e")
            self._update_total("0.000")
            return

        # Check if valid number
        try:
            amount = float(amount_text)

            if amount <= 0:
                self.amount_hint.config(text="⚠️ Must be > 0", fg="#e85555")
                self._update_total("0.000")
                return

            balance = self.token_data.get("balance")
            if balance is not None and amount > balance:
                self.amount_hint.config(
                    text=f"⚠️ Insufficient ({balance:.6f})",
                    fg="#e85555"
                )
                self._update_total(f"{amount + 0.001:.6f}")
                return

            # Valid amount
            self.amount_hint.config(text="✓ Valid", fg="#7ee1a6")
            self._update_total(f"{amount + 0.001:.6f}")

        except ValueError:
            self.amount_hint.config(text="⚠️ Invalid number", fg="#e85555")
            self._update_total("0.000")

    def _update_total(self, total: str):
        # Find the canvas and update the text
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, tk.Canvas):
                try:
                    widget.itemconfig(self.total_text, text=f"{total} {self.token_data['symbol']}")
                except:
                    pass

    def _validate_recipient(self):
        address = self.recipient_entry.get().strip()

        if not address:
            self.recipient_hint.config(text="Enter wallet address", fg="#6a7a7e")
            return False

        # Basic validation (64 hex characters)
        if len(address) == 64 and re.match(r'^[a-fA-F0-9]{64}$', address):
            self.recipient_hint.config(text="✓ Valid", fg="#7ee1a6")
            return True
        else:
            self.recipient_hint.config(text="⚠️ Invalid (64 hex chars)", fg="#e85555")
            return False

    def _handle_send(self):
        # Validate all fields
        recipient = self.recipient_entry.get().strip()
        amount_text = self.amount_entry.get().strip()
        memo = self.memo_entry.get().strip()

        # Validate recipient
        if not recipient:
            messagebox.showwarning("Missing Recipient", "Please enter a recipient address.")
            self.recipient_entry.focus_set()
            return

        if not self._validate_recipient():
            messagebox.showwarning("Invalid Recipient", "Please enter a valid wallet address.")
            self.recipient_entry.focus_set()
            return

        # Validate amount
        if not amount_text:
            messagebox.showwarning("Missing Amount", "Please enter an amount to send.")
            self.amount_entry.focus_set()
            return

        try:
            amount = float(amount_text)

            if amount <= 0:
                messagebox.showwarning("Invalid Amount", "Amount must be greater than zero.")
                self.amount_entry.focus_set()
                return

            balance = self.token_data.get("balance")
            if balance is not None and amount > balance:
                messagebox.showwarning("Insufficient Balance",
                                      f"You don't have enough {self.token_data['symbol']}.\n"
                                      f"Available: {balance:.6f}\n"
                                      f"Requested: {amount:.6f}")
                self.amount_entry.focus_set()
                return

        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid number for the amount.")
            self.amount_entry.focus_set()
            return

        # Confirm transaction
        confirm_msg = (
            f"Review Transaction Details:\n\n"
            f"Token: {self.token_data['symbol']}\n"
            f"To: {recipient[:16]}...{recipient[-16:]}\n"
            f"Amount: {amount:.6f} {self.token_data['symbol']}\n"
            f"Fee: ~0.001 XIAN\n"
            f"Total: ~{amount + 0.001:.6f}\n"
        )

        if memo:
            confirm_msg += f"Memo: {memo}\n"

        confirm_msg += "\nDo you want to proceed with this transaction?"

        if messagebox.askyesno("Confirm Transaction", confirm_msg):
            # Prepare transaction data
            transaction_data = {
                'recipient': recipient,
                'amount': amount,
                'token': self.token_data['contract'],
                'symbol': self.token_data['symbol'],
                'memo': memo if memo else None
            }

            # Call callback if provided
            if self.on_send:
                self.on_send(transaction_data)
            else:
                # Default behavior - show success message
                messagebox.showinfo("Transaction Submitted",
                                   f"Transaction of {amount:.6f} {self.token_data['symbol']} "
                                   f"to {recipient[:16]}... has been submitted!")

            # Go back after successful send
            self._handle_back()

    def _handle_back(self):
        if self.on_back:
            self.on_back()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
