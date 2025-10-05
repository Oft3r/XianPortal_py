import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import TYPE_CHECKING, Any
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageTk

if TYPE_CHECKING:
    from .wallet_ui import WalletUI, TokenRow

from src.ui.ui_utils import create_round_rect, lerp_color


class TokenDetailsScreen:
    def __init__(self, master: 'WalletUI', parent, token_data: 'TokenRow', on_back=None):
        self.master = master
        self.parent = parent
        self.token_data = token_data
        self.on_back = on_back

        # Frame for the details
        self.frame = tk.Frame(parent, bg="#0b1417")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Window size - similar to main app
        self.WIDTH = 360
        self.HEIGHT = 500

        # Canvas for custom drawing
        self.canvas = tk.Canvas(self.frame, width=self.WIDTH, height=self.HEIGHT,
                                bg="#0b1417", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Hit areas for buttons
        self.hit_areas = {'send': [], 'receive': [], 'swap': []}

        # Draw the UI
        self.draw_ui()

        # Bind events
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._clear_hover())
        self.canvas.bind("<Button-1>", self._on_click)

    def draw_ui(self):
        c = self.canvas
        c.delete("all")

        # Reset hit areas
        for key in self.hit_areas:
            self.hit_areas[key] = []

        # Background vignette
        self._draw_vignette(c)

        # Header with token icon and name
        self._draw_header(c)

        # Token details card
        self._draw_details_card(c)

        # Action buttons
        self._draw_action_buttons(c)

    def _draw_vignette(self, c):
        # Simple vertical gradient
        top = "#0a1617"
        bottom = "#0a1012"
        for i in range(self.HEIGHT):
            t = i / self.HEIGHT
            color = lerp_color(top, bottom, t)
            c.create_line(0, i, self.WIDTH, i, fill=color)

    def _draw_header(self, c):
        pad = 16
        top = 20

        # Back button (simple arrow)
        c.create_text(pad, top + 20, text="←", fill="#9ac6cc", font=("Segoe UI", 16), anchor="w")
        # Store hit area for back button
        self.hit_areas['back'] = [{'x1': pad-5, 'y1': top+5, 'x2': pad+25, 'y2': top+35}]

        # Token icon in center
        icon_size = 40
        icon_x = self.WIDTH // 2
        icon_y = top + 30
        create_round_rect(c, icon_x - icon_size//2, icon_y - icon_size//2,
                         icon_x + icon_size//2, icon_y + icon_size//2,
                         r=8, fill="#101b1f", outline="#22343a")
        c.create_text(icon_x, icon_y, text=self.token_data.get("icon", "T"),
                     fill="#e8f6f7", font=("Segoe UI", 12, "bold"))

        # Token name and symbol
        c.create_text(icon_x, icon_y + 35, text=self.token_data["name"],
                     fill="#dbe9ea", font=("Segoe UI", 14, "bold"), anchor="center")
        c.create_text(icon_x, icon_y + 55, text=self.token_data["symbol"],
                     fill="#8aa4aa", font=("Segoe UI", 11), anchor="center")

    def _draw_details_card(self, c):
        pad = 16
        top = 120
        w = self.WIDTH - 2 * pad
        h = 160
        x1, y1, x2, y2 = pad, top, pad + w, top + h

        # Shadow + outer ring
        create_round_rect(c, x1+2, y1+3, x2+2, y2+3, r=18, fill="#0a1215", outline="#0a1215")
        create_round_rect(c, x1 - 2, y1 - 2, x2 + 2, y2 + 2, r=18, fill="#0e181b", outline="#0e181b")
        create_round_rect(c, x1 - 4, y1 - 4, x2 + 4, y2 + 4, r=20, fill="", outline="#1b3b3f", width=2)

        # Main card body
        create_round_rect(c, x1, y1, x2, y2, r=16, fill="#0f1b1f", outline="#1b2b30")

        # Contract address
        c.create_text(x1 + 18, y1 + 20, text="Contract", anchor="w", fill="#8aa4aa", font=("Segoe UI", 9, "bold"))
        contract = self.token_data.get("contract", "")
        c.create_text(x1 + 18, y1 + 40, text=contract, anchor="w", fill="#dbe9ea", font=("Segoe UI", 10))

        # Balance
        c.create_text(x1 + 18, y1 + 70, text="Balance", anchor="w", fill="#8aa4aa", font=("Segoe UI", 9, "bold"))
        balance = self.token_data.get("balance")
        balance_text = "0.000" if balance is None else str(balance)
        c.create_text(x1 + 18, y1 + 90, text=balance_text, anchor="w", fill="#e8f6f7", font=("Segoe UI", 16, "bold"))

        # Fiat value (placeholder)
        c.create_text(x1 + 18, y1 + 120, text="~ $0.00", anchor="w", fill="#86979b", font=("Segoe UI", 10))

        # Copy contract button
        copy_x = x2 - 30
        copy_y = y1 + 30
        c.create_text(copy_x, copy_y, text="\U0001F4CB", fill="#8aa4aa", font=("Segoe UI Emoji", 12))
        self.hit_areas['copy_contract'] = [{'x1': copy_x-15, 'y1': copy_y-15, 'x2': copy_x+15, 'y2': copy_y+15}]

    def _draw_action_buttons(self, c):
        pad = 16
        top = 320
        button_h = 50
        button_w = (self.WIDTH - 2 * pad - 20) // 3  # 3 buttons with spacing
        spacing = 10

        buttons = [
            ("Send", "#7ee1a6", "#0f2a21"),
            ("Receive", "#6bb6e8", "#0f1f2a"),
            ("Swap", "#e8a76b", "#2a1f0f")
        ]

        for i, (label, active_color, bg_color) in enumerate(buttons):
            x1 = pad + i * (button_w + spacing)
            y1 = top
            x2 = x1 + button_w
            y2 = y1 + button_h

            # Shadow
            create_round_rect(c, x1+1, y1+2, x2+1, y2+2, r=12, fill="#0a1215", outline="#0a1215")

            # Main button
            create_round_rect(c, x1, y1, x2, y2, r=10, fill=bg_color, outline="#1a2a2f")

            # Button text
            c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label,
                         fill=active_color, font=("Segoe UI", 11, "bold"))

            # Store hit area
            key = label.lower()
            self.hit_areas[key] = [{'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}]

    def _on_motion(self, e):
        x, y = e.x, e.y
        # Check button hover (simplified - just redraw on any motion for now)
        self.draw_ui()

    def _clear_hover(self):
        self.draw_ui()

    def _on_click(self, e):
        x, y = e.x, e.y

        # Check back button
        for rect in self.hit_areas.get('back', []):
            if rect['x1'] <= x <= rect['x2'] and rect['y1'] <= y <= rect['y2']:
                self._handle_action('back')
                return

        # Check action buttons
        for action in ['send', 'receive', 'swap']:
            for rect in self.hit_areas.get(action, []):
                if rect['x1'] <= x <= rect['x2'] and rect['y1'] <= y <= rect['y2']:
                    self._handle_action(action)
                    return

        # Check copy contract
        for rect in self.hit_areas.get('copy_contract', []):
            if rect['x1'] <= x <= rect['x2'] and rect['y1'] <= y <= rect['y2']:
                self._copy_contract()
                return

    def _handle_action(self, action: str):
        if action == 'back':
            if self.on_back:
                self.on_back()
        elif action == 'send':
            self._send_token()
        elif action == 'receive':
            self._receive_token()
        elif action == 'swap':
            self._swap_token()

    def _send_token(self):
        # Placeholder for send functionality
        messagebox.showinfo("Send", f"Send {self.token_data['symbol']} functionality not yet implemented.")

    def _receive_token(self):
        # Show receiving address with QR code
        if self.master.current_wallet:
            address = self.master.current_wallet.public_key

            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(address)
            except Exception:
                pass

            # Create QR code popup
            popup = tk.Toplevel(self.master)
            popup.title("Receive Token")
            # Window size will be set dynamically after QR is generated
            popup.update_idletasks()
            popup.configure(bg="#0b1417")
            popup.resizable(False, False)

            # Center the popup
            popup.transient(self.master)
            popup.grab_set()

            # Header with token info
            header_frame = tk.Frame(popup, bg="#0b1417")
            header_frame.pack(fill=tk.X, pady=(20, 10))

            token_icon = tk.Label(header_frame, text=self.token_data.get("icon", "T"),
                                 font=("Segoe UI", 20, "bold"), fg="#e8f6f7", bg="#0b1417")
            token_icon.pack(side=tk.LEFT, padx=(20, 10))

            header_text = tk.Frame(header_frame, bg="#0b1417")
            header_text.pack(side=tk.LEFT)
            token_name = tk.Label(header_text, text=f"Receive {self.token_data['symbol']}",
                                 font=("Segoe UI", 14, "bold"), fg="#dbe9ea", bg="#0b1417")
            token_name.pack(anchor="w")
            subtitle = tk.Label(header_text, text="Scan QR code or copy address",
                               font=("Segoe UI", 9), fg="#8aa4aa", bg="#0b1417")
            subtitle.pack(anchor="w")

            # QR Code section with maximum contrast (compact sizing)
            qr_frame = tk.Frame(popup, bg="#ffffff", relief="solid", bd=2)  # White background for contrast
            qr_frame.pack(pady=(8, 16), padx=12)

            # Generate QR code with high contrast (black/white)
            # Smaller box_size and a standard quiet zone (border=4) keep it compact and scannable
            qr = qrcode.QRCode(
                version=1,
                box_size=6,   # Reduced size per module
                border=4,     # Standard quiet zone
                error_correction=ERROR_CORRECT_H
            )
            qr.add_data(address)
            qr.make(fit=True)

            # Create QR image with maximum contrast
            qr_image = qr.make_image(fill_color="black", back_color="white")
            # Ensure we have a PIL Image for Tk
            pil_img = qr_image.convert("RGB") if hasattr(qr_image, "convert") else qr_image  # type: ignore[assignment]

            # Convert to PhotoImage
            qr_photo: ImageTk.PhotoImage = ImageTk.PhotoImage(pil_img)  # type: ignore

            # Display QR code (keep reference on the instance to avoid GC)
            qr_label = tk.Label(qr_frame, image=qr_photo, bg="white")  # type: ignore
            self._qr_photo_ref = qr_photo
            qr_label.pack(padx=8, pady=8)

            # After rendering QR, adjust popup size to fit content exactly
            popup.update_idletasks()
            # Compute desired width/height based on frame plus padding (more compact)
            total_width = max(320, qr_frame.winfo_reqwidth() + 40)
            total_height = qr_frame.winfo_reqheight() + 220  # header + address + buttons
            popup.geometry(f"{total_width}x{total_height}")

            # Address section - show full address clearly
            addr_frame = tk.Frame(popup, bg="#0b1417")
            addr_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            addr_title = tk.Label(addr_frame, text="Wallet Address",
                                 font=("Segoe UI", 12, "bold"), fg="#dbe9ea", bg="#0b1417")
            addr_title.pack(anchor="w", pady=(0, 5))

            addr_subtitle = tk.Label(addr_frame, text="Click to copy • Right-click for options",
                                    font=("Segoe UI", 9), fg="#8aa4aa", bg="#0b1417")
            addr_subtitle.pack(anchor="w", pady=(0, 10))

            # Address display in a single-line entry for easy copying
            addr_var = tk.StringVar(value=address)
            addr_entry = tk.Entry(addr_frame, textvariable=addr_var, font=("Courier New", 10),
                                   bg="#0e181b", fg="#dbe9ea", relief="solid", bd=1,
                                   insertbackground="#dbe9ea")
            addr_entry.pack(fill=tk.X, ipady=8)
            # Select-all on focus for quick copy
            def on_focus_in(_):
                addr_entry.selection_range(0, tk.END)
            addr_entry.bind("<FocusIn>", on_focus_in)
            # Right-click context menu
            def show_context_menu(event):
                menu = tk.Menu(popup, tearoff=0, bg="#0f1b1f", fg="#dbe9ea",
                               activebackground="#6bb6e8", activeforeground="#0f1f2a")
                menu.add_command(label="Copy Address",
                                 command=lambda: self._copy_address(address, popup=None))
                menu.add_command(label="Select All",
                                 command=lambda: addr_entry.selection_range(0, tk.END))
                menu.post(event.x_root, event.y_root)
            addr_entry.bind("<Button-3>", show_context_menu)
            # Double-click to copy
            addr_entry.bind("<Double-Button-1>", lambda _e: self._copy_address(address, popup=None))

            # Copy button
            copy_frame = tk.Frame(popup, bg="#0b1417")
            copy_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

            copy_btn = tk.Button(copy_frame, text="📋 Copy Address",
                                command=lambda: self._copy_address(address, popup),
                                font=("Segoe UI", 12, "bold"), bg="#6bb6e8",
                                fg="#0f1f2a", relief="flat", height=2,
                                activebackground="#5ba0d0", activeforeground="#0f1f2a")
            copy_btn.pack(fill=tk.X)

        else:
            messagebox.showwarning("No Wallet", "No wallet loaded.")

    def _swap_token(self):
        # Placeholder for swap functionality
        messagebox.showinfo("Swap", f"Swap {self.token_data['symbol']} functionality not yet implemented.")

    def _copy_address(self, address: str, popup: tk.Toplevel | None):
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(address)
            messagebox.showinfo("Copied", "Address copied to clipboard!")
        except Exception:
            messagebox.showerror("Error", "Failed to copy address to clipboard.")
        if popup is not None:
            popup.destroy()

    def _copy_contract(self):
        contract = self.token_data.get("contract", "")
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(contract)
        except Exception:
            pass
        messagebox.showinfo("Copied", f"Contract address copied:\n{contract}")