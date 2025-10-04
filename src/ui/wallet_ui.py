import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import threading
from typing import Optional, List, Dict, TypedDict, Union

from src.storage import config_store, secure_store
from src.core.wallet_manager import WalletManager
from xian_py import Xian


# Simple rounded rectangle helper using arcs + rectangles
def create_round_rect(canvas, x1, y1, x2, y2, r=12, fill="#1b2228", outline="#1b2228", width=1):
    if r <= 0:
        return canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
    items = []
    # Four arcs
    items.append(canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style=tk.PIESLICE, outline=outline, width=width, fill=fill))
    items.append(canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style=tk.PIESLICE, outline=outline, width=width, fill=fill))
    items.append(canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style=tk.PIESLICE, outline=outline, width=width, fill=fill))
    items.append(canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style=tk.PIESLICE, outline=outline, width=width, fill=fill))
    # Center rectangles to stitch corners
    items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill))
    items.append(canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=fill))
    # Outline path (approximate) for nicer border
    if outline and width:
        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width)
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style=tk.ARC, outline=outline, width=width)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style=tk.ARC, outline=outline, width=width)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style=tk.ARC, outline=outline, width=width)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style=tk.ARC, outline=outline, width=width)
    return items


def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linear interpolate between two hex colors like #RRGGBB."""
    def h2i(h: str) -> int:
        return int(h, 16)
    r1, g1, b1 = h2i(c1[1:3]), h2i(c1[3:5]), h2i(c1[5:7])
    r2, g2, b2 = h2i(c2[1:3]), h2i(c2[3:5]), h2i(c2[5:7])
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class TokenRow(TypedDict):
    name: str
    symbol: str
    contract: str
    balance: Optional[Union[int, float]]
    icon: str


class Rect(TypedDict):
    x1: int
    y1: int
    x2: int
    y2: int


class HitArea(Rect, total=False):
    idx: int


class HoverState(TypedDict):
    tab: Optional[int]
    token: Optional[int]
    bottom: Optional[int]
    addr: bool
    copy: bool
    edit: bool


class PressedState(TypedDict):
    tab: Optional[int]
    bottom: Optional[int]
    edit: bool


class WalletUI(tk.Tk):
    WIDTH = 360
    HEIGHT = 640

    def __init__(self):
        super().__init__()
        self.title("Wallet UI - Tkinter")
        self.resizable(False, False)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.configure(bg="#0b1417")

        self.active_tab = tk.StringVar(value="Tokens")
        self.address = "d53f0b...a21dcf"
        self.wallet_manager = WalletManager()
        self.current_wallet = None  # WalletInfo
        self.node_url: Optional[str] = None
        self._store_password: Optional[str] = None  # session-only, not persisted
        # Pressed feedback state
        self.pressed_state: PressedState = {
            'tab': None,     # index or None
            'bottom': None,  # index or None
            'edit': False,   # pressed state for edit button
        }

        self.loading_balances = False
        self.scroll_offset: int = 0
        self.total_balance_xian: float = 0.0

        self.tokens: List[TokenRow] = [
            {"name": "XIAN Currency", "symbol": "XIAN", "contract": "currency", "balance": None, "icon": "XN"},
            {"name": "XIAN Wallet Token", "symbol": "XWT", "contract": "con_xwt", "balance": None, "icon": "XWT"},
        ]
        # Hover and hit testing state
        self.hover_state: HoverState = {
            'tab': None,        # index 0..2 or None
            'token': None,      # index 0..n or None
            'bottom': None,     # index 0..4 or None
            'addr': False,
            'copy': False,
            'edit': False,
        }

        self.hit_areas: Dict[str, List[HitArea]] = {
            'tabs': [],
            'tokens': [],
            'bottom': [],
            'addr': [],
            'copy': [],
            'edit': [],
        }

        # Single canvas for custom drawing
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg="#0b1417", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind shortcuts
        self.bind_all("<Control-n>", self._create_wallet)
        self.bind_all("<Control-i>", self._import_wallet)
        self.bind_all("<Control-u>", self._set_node_url)
        self.bind_all("<F5>", self._refresh_balances)

        # Try to load stored wallet securely
        loaded_info, loaded_node = (None, None)
        try:
            if secure_store.store_exists():
                if secure_store.requires_password():
                    pwd = simpledialog.askstring("Security", "Enter the wallet password", show='*')
                    if pwd:
                        self._store_password = pwd
                        loaded_info, loaded_node = secure_store.load_wallet(password=pwd)
                else:
                    loaded_info, loaded_node = secure_store.load_wallet()
        except Exception as e:
            messagebox.showwarning("Secure load", f"Could not load stored wallet: {e}")
        if loaded_info is not None:
            self.current_wallet = loaded_info
            self.address = f"{loaded_info.public_key[:6]}...{loaded_info.public_key[-6:]}"
            if loaded_node:
                self.node_url = loaded_node

        # Load tokens from config before first draw
        try:
            self._load_tokens_from_config()
        except Exception:
            pass

        # Draw once
        self.draw_ui()

        # Auto refresh balances if possible
        try:
            self.after(10, self._refresh_balances)
        except Exception:
            pass

        # Redraw on resize
        self.canvas.bind("<Configure>", lambda e: self.draw_ui())
        # Hover and click handling
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._clear_hover())
        self.canvas.bind("<Button-1>", self._on_click)
        # Scroll wheel support
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)   # Windows/macOS
        self.canvas.bind("<Button-4>", self._on_scroll_up)      # Linux up
        self.canvas.bind("<Button-5>", self._on_scroll_down)    # Linux down
        # Initial setup dialog on startup (skips if wallet already loaded)
        self.after(200, self._initial_setup)

    def draw_ui(self):
        c = self.canvas
        c.delete("all")
        # reset hit areas for fresh hover targeting
        self.hit_areas['tabs'] = []
        self.hit_areas['tokens'] = []
        self.hit_areas['bottom'] = []
        self.hit_areas['addr'] = []
        self.hit_areas['copy'] = []
        self.hit_areas['edit'] = []

        # Background subtle vignette
        self._draw_vignette(c)

        # Top bar
        self._draw_topbar(c)

        # Balance card
        self._draw_balance_card(c)

        # Tabs
        self._draw_tabs(c)

        # Token list
        self._draw_token_list2(c)

        # Bottom nav
        self._draw_bottom_nav(c)

    def _draw_vignette(self, c):
        # Simple vertical gradient by drawing horizontal lines
        top = "#0a1617"
        bottom = "#0a1012"
        for i in range(self.HEIGHT):
            t = i / self.HEIGHT
            color = lerp_color(top, bottom, t)
            c.create_line(0, i, self.WIDTH, i, fill=color)

    def _draw_topbar(self, c):
        # PRO pill with OFF switch and a lock icon, with depth
        pad = 14
        pill_h = 28
        pill_w = 120
        x1, y1 = pad, pad
        x2, y2 = x1 + pill_w, y1 + pill_h
        # Shadow
        create_round_rect(c, x1+1, y1+2, x2+1, y2+2, r=14, fill="#0a1215", outline="#0a1215")
        # Main pill
        create_round_rect(c, x1, y1, x2, y2, r=14, fill="#0f1b1f", outline="#1a2a2f")
        # Top highlight
        c.create_line(x1+8, y1+1, x2-8, y1+1, fill="#1f3339")
        c.create_text(x1 + 28, y1 + pill_h / 2, text="PRO", fill="#9ac6cc", font=("Segoe UI", 9, "bold"))

        # Small switch UI inside pill
        c.create_text(x1 + 60, y1 + pill_h / 2, text="OFF", fill="#718086", font=("Segoe UI", 8))
        # Switch track and knob
        track_x1, track_y1 = x2 - 46, y1 + 6
        track_x2, track_y2 = x2 - 16, y1 + pill_h - 6
        create_round_rect(c, track_x1, track_y1, track_x2, track_y2, r=10, fill="#0e181b", outline="#1a2a2f")
        # knob with subtle shadow
        create_round_rect(c, track_x1+2, track_y1+2, track_x1+18, track_y2-2, r=8, fill="#16252a", outline="#22343a")

        # Lock icon on right
        lock = "\U0001F512"  # 🔒
        c.create_text(self.WIDTH - pad, y1 + pill_h / 2, text=lock, fill="#9ac6cc", font=("Segoe UI Emoji", 12), anchor="e")

    def _draw_balance_card(self, c):
        pad = 16
        top = 60
        w = self.WIDTH - 2 * pad
        h = 190
        x1, y1, x2, y2 = pad, top, pad + w, top + h

        # Shadow + outer ring
        create_round_rect(c, x1+2, y1+3, x2+2, y2+3, r=18, fill="#0a1215", outline="#0a1215")
        create_round_rect(c, x1 - 2, y1 - 2, x2 + 2, y2 + 2, r=18, fill="#0e181b", outline="#0e181b")
        create_round_rect(c, x1 - 4, y1 - 4, x2 + 4, y2 + 4, r=20, fill="", outline="#1b3b3f", width=2)

        # Main card body + subtle vertical gradient lines
        create_round_rect(c, x1, y1, x2, y2, r=16, fill="#0f1b1f", outline="#1b2b30")
        for i in range(8):
            t = i/8
            y = y1 + 4 + i * 2
            c.create_line(x1+12, y, x2-12, y, fill=lerp_color("#16252a", "#0f1b1f", t))

        # Header row: TOTAL BALANCE + eye
        c.create_text(x1 + 18, y1 + 18, text="TOTAL BALANCE", anchor="w", fill="#8aa4aa", font=("Segoe UI", 9, "bold"))
        c.create_text(x2 - 18, y1 + 18, text="\U0001F441", anchor="e", fill="#8aa4aa", font=("Segoe UI Emoji", 12))

        # Amount
        amount_text = f"{self.total_balance_xian:,.3f}" if self.total_balance_xian else "0.000"
        c.create_text(x1 + 22, y1 + 70, text=amount_text, anchor="w", fill="#e8f6f7", font=("Segoe UI", 28, "bold"))
        c.create_text(x1 + 160, y1 + 70, text="XIAN", anchor="w", fill="#9ac6cc", font=("Segoe UI", 11, "bold"))

        # Fiat amount
        c.create_text(x1 + 22, y1 + 100, text="~ $0.00", anchor="w", fill="#86979b", font=("Segoe UI", 10))

        # Address + copy icon (hoverable)
        addr_hover = self.hover_state['addr']
        addr_color = "#cfe6ea" if addr_hover else "#8aa4aa"
        c.create_text(x1 + 22, y2 - 24, text=self.address, anchor="w", fill=addr_color, font=("Segoe UI", 9, "underline" if addr_hover else "normal"))
        # handled via canvas-wide click handler
        copy_hover = self.hover_state['copy']
        copy_color = "#cfe6ea" if copy_hover else "#8aa4aa"
        c.create_text(x2 - 24, y2 - 24, text="\U0001F4CB", fill=copy_color, font=("Segoe UI Emoji", 12))
        # store hit areas
        self.hit_areas['addr'] = [{'x1': int(x1+12), 'y1': int(y2-36), 'x2': int(x1+180), 'y2': int(y2-14)}]
        self.hit_areas['copy'] = [{'x1': int(x2-36), 'y1': int(y2-36), 'x2': int(x2-12), 'y2': int(y2-12)}]

    def _draw_tabs(self, c):
        pad = 16
        top = 264
        w = self.WIDTH - 2 * pad
        h = 42
        # reserve space for edit button at right
        edit_gap = 8
        edit_w = 34
        x1, y1 = pad, top
        container_w = w - (edit_w + edit_gap)
        x2, y2 = x1 + container_w, top + h
        create_round_rect(c, x1+1, y1+2, x2+1, y2+2, r=20, fill="#0a1215", outline="#0a1215")
        create_round_rect(c, x1, y1, x2, y2, r=20, fill="#0f1b1f", outline="#1a2a2f")

        # Three segments
        labels = ["Tokens", "Items", "Activity"]
        self.hit_areas['tabs'] = []
        for i, label in enumerate(labels):
            seg_w = container_w / 3
            sx1 = x1 + i * seg_w
            sx2 = sx1 + seg_w
            active = (self.active_tab.get() == label)
            hovered = (self.hover_state['tab'] == i)
            pressed = (self.pressed_state.get('tab') == i)
            if active:
                create_round_rect(c, sx1 + 4, y1 + 4, sx2 - 4, y2 - 4, r=16, fill="#17262b", outline="#22383e")
                c.create_line(sx1+12, y1+6, sx2-12, y1+6, fill="#223a41")
                color = "#e8f6f7"
                weight = "bold"
            else:
                if hovered:
                    create_round_rect(c, sx1 + 6, y1 + 6, sx2 - 6, y2 - 6, r=14, fill="#142127", outline="#22343a")
                    color = "#cfe6ea"
                    weight = "bold"
                else:
                    color = "#9ab0b5"
                    weight = "normal"
            ty = (y1 + y2) / 2 + (1 if pressed else 0)
            c.create_text((sx1 + sx2) / 2, ty, text=label, fill=color, font=("Segoe UI", 10, weight))
            # handled via canvas-wide click handler
            self.hit_areas['tabs'].append({'x1': int(sx1), 'y1': int(y1), 'x2': int(sx2), 'y2': int(y2)})

        # Edit pencil button to the right of the tabs container
        bx1 = x1 + container_w + edit_gap
        bx2 = bx1 + edit_w
        by1, by2 = y1, y2
        # shadow
        create_round_rect(c, bx1+1, by1+2, bx2+1, by2+2, r=14, fill="#0a1215", outline="#0a1215")
        hovered_edit = self.hover_state.get('edit', False)
        pressed_edit = self.pressed_state.get('edit', False)
        fill = "#142127" if hovered_edit else "#0f1b1f"
        outline = "#22343a" if hovered_edit else "#1a2a2f"
        create_round_rect(c, bx1, by1, bx2, by2, r=14, fill=fill, outline=outline)
        # icon
        py = (by1 + by2) / 2 + (1 if pressed_edit else 0)
        c.create_text((bx1 + bx2)/2, py, text="\u270F\ufe0f", fill="#cfe6ea", font=("Segoe UI Emoji", 12))
        # store hit area
        self.hit_areas['edit'] = [{'x1': int(bx1), 'y1': int(by1), 'x2': int(bx2), 'y2': int(by2)}]

    def _draw_token_list2(self, c):
        pad = 16
        start_y = 318
        row_h = 66
        spacing = 12
        item_full = row_h + spacing
        # Visible viewport (token list area)
        visible_top = start_y
        visible_bottom = self.HEIGHT - 80
        # Clamp scroll_offset to content bounds
        visible_height = max(0, visible_bottom - visible_top)
        n_items = len(self.tokens) if getattr(self, 'tokens', None) else 0
        content_height = max(0, n_items * item_full - (spacing if n_items > 0 else 0))
        max_offset = max(0, content_height - visible_height)
        if getattr(self, 'scroll_offset', 0) > max_offset:
            self.scroll_offset = max_offset
        if self.scroll_offset < 0:
            self.scroll_offset = 0
        self.hit_areas['tokens'] = []

        for i, row in enumerate(self.tokens):
            y1 = start_y - getattr(self, 'scroll_offset', 0) + i * item_full
            y2 = y1 + row_h
            # Cull items outside viewport
            if y2 < visible_top - 40 or y1 > visible_bottom + 40:
                continue
            hovered = (self.hover_state['token'] == i)
            # shadow and card body
            create_round_rect(c, pad+1, y1+2, self.WIDTH - pad+1, y2+2, r=14, fill="#0a1215", outline="#0a1215")
            fill = "#132127" if hovered else "#0f1b1f"
            outline = "#2a3d43" if hovered else "#1a2a2f"
            create_round_rect(c, pad, y1, self.WIDTH - pad, y2, r=14, fill=fill, outline=outline)

            # Left logo box
            create_round_rect(c, pad + 10, y1 + 10, pad + 10 + 44, y1 + 10 + 44, r=10, fill="#101b1f", outline="#22343a")
            # Logo text
            c.create_text(pad + 10 + 22, y1 + 10 + 22, text=row.get("icon",""), fill="#e8f6f7", font=("Segoe UI", 9, "bold"))

            # Name and ticker
            c.create_text(pad + 70, y1 + 20, text=row["name"], anchor="w", fill="#dbe9ea", font=("Segoe UI", 10, "bold"))
            c.create_text(pad + 70, y1 + 40, text=row["symbol"], anchor="w", fill="#8aa4aa", font=("Segoe UI", 9))

            # Right amount
            bal = row.get("balance")
            bal_text = "loading..." if self.loading_balances else ("?" if bal is None else str(bal))
            c.create_text(self.WIDTH - pad - 28, y1 + 22, text=bal_text, anchor="e", fill="#cbd9db", font=("Segoe UI", 10, "bold"))
            c.create_text(self.WIDTH - pad - 28, y1 + 42, text="~ $0.00", anchor="e", fill="#8aa4aa", font=("Segoe UI", 9))

            # little dot icon on far right
            c.create_text(self.WIDTH - pad - 10, y1 + row_h / 2, text="\u2022", fill="#8aa4aa", font=("Segoe UI", 18))

            # store hit area for hover/click aligned to drawn position
            self.hit_areas['tokens'].append({'x1': pad, 'y1': int(y1), 'x2': self.WIDTH - pad, 'y2': int(y2), 'idx': i})

    def _draw_bottom_nav(self, c):
        pad = 16
        h = 64
        y2 = self.HEIGHT - pad
        y1 = y2 - h
        create_round_rect(c, pad+1, y1+2, self.WIDTH - pad+1, y2+2, r=16, fill="#0a1215", outline="#0a1215")
        create_round_rect(c, pad, y1, self.WIDTH - pad, y2, r=16, fill="#0f1b1f", outline="#1a2a2f")

        # bag, refresh, globe, magnifier, gear
        icons = ["\U0001F45B", "\U0001F504", "\U0001F310", "\U0001F50D", "\u2699\ufe0f"]
        count = len(icons)
        spacing = (self.WIDTH - 2 * pad) / count
        self.hit_areas['bottom'] = []
        for i, ch in enumerate(icons):
            x = pad + spacing * (i + 0.5)
            y = (y1 + y2) / 2
            active = (i == 0)
            hovered = (self.hover_state['bottom'] == i)
            pressed = (self.pressed_state.get('bottom') == i)
            if active:
                # Active gets a subtle greenish pill
                create_round_rect(c, x - 18, y - 14, x + 18, y + 14, r=10, fill="#0f2a21", outline="#1e3e35")
                color = "#7ee1a6"
            else:
                if hovered:
                    create_round_rect(c, x - 16, y - 12, x + 16, y + 12, r=10, fill="#122027", outline="#22343a")
                    color = "#cfe6ea"
                else:
                    color = "#9ab0b5"
            ty = y + (1 if pressed else 0)
            c.create_text(x, ty, text=ch, fill=color, font=("Segoe UI Emoji", 13))
            # store hit areas
            self.hit_areas['bottom'].append({'x1': int(x-18), 'y1': int(y-16), 'x2': int(x+18), 'y2': int(y+16)})

    def _copy_address(self, _):
        self.clipboard_clear()
        self.clipboard_append(self.address)
        self.update()  # keep after app closes
        messagebox.showinfo("Copied", f"Address copied to clipboard:\n{self.address}")

    def _set_tab(self, val):
        self.active_tab.set(val)
        self.draw_ui()

    # ---- Hover and click helpers on canvas ----
    def _on_motion(self, e):
        x, y = e.x, e.y
        changed = False
        # Tabs
        new_tab = None
        for idx, r in enumerate(self.hit_areas.get('tabs', [])):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                new_tab = idx
                break
        if new_tab != self.hover_state.get('tab'):
            self.hover_state['tab'] = new_tab
            changed = True

        # Tokens
        new_token = None
        for r in self.hit_areas.get('tokens', []):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                new_token = r.get('idx')
                break
        if new_token != self.hover_state.get('token'):
            self.hover_state['token'] = new_token
            changed = True

        # Bottom
        new_bottom = None
        for idx, r in enumerate(self.hit_areas.get('bottom', [])):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                new_bottom = idx
                break
        if new_bottom != self.hover_state.get('bottom'):
            self.hover_state['bottom'] = new_bottom
            changed = True

        # Address, copy and edit button
        addr_rects = self.hit_areas.get('addr', [])
        copy_rects = self.hit_areas.get('copy', [])
        edit_rects = self.hit_areas.get('edit', [])
        addr_hover = any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in addr_rects)
        copy_hover = any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in copy_rects)
        edit_hover = any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in edit_rects)
        if addr_hover != self.hover_state.get('addr'):
            self.hover_state['addr'] = addr_hover
            changed = True
        if copy_hover != self.hover_state.get('copy'):
            self.hover_state['copy'] = copy_hover
            changed = True
        if edit_hover != self.hover_state.get('edit'):
            self.hover_state['edit'] = edit_hover
            changed = True
        if changed:
            self.draw_ui()

    def _clear_hover(self):
        if any([self.hover_state.get('tab'), self.hover_state.get('token'), self.hover_state.get('bottom'),
                self.hover_state.get('addr'), self.hover_state.get('copy'), self.hover_state.get('edit')]):
            self.hover_state.update({'tab': None, 'token': None, 'bottom': None, 'addr': False, 'copy': False, 'edit': False})
            self.draw_ui()

    # ---- Scroll handlers ----
    def _adjust_scroll(self, delta_pixels: int) -> None:
        # Token list layout constants
        start_y = 318
        row_h = 66
        spacing = 12
        item_full = row_h + spacing
        # Visible viewport: from token list start to top of bottom nav (HEIGHT - 80)
        visible_top = start_y
        visible_bottom = self.HEIGHT - 80
        visible_height = max(0, visible_bottom - visible_top)
        # Content height
        n = len(self.tokens) if getattr(self, 'tokens', None) else 0
        content_height = max(0, n * item_full - (spacing if n > 0 else 0))
        max_offset = max(0, content_height - visible_height)
        # Update and clamp
        self.scroll_offset = max(0, min(max_offset, self.scroll_offset + delta_pixels))
        self.draw_ui()

    def _on_mousewheel(self, e):
        # Windows/macOS: e.delta typically ±120 per notch; use ~30 px step per notch
        step = 30
        delta = 0
        try:
            if e.delta > 0:
                delta = -step
            elif e.delta < 0:
                delta = step
        except Exception:
            delta = 0
        if delta != 0:
            self._adjust_scroll(delta)

    def _on_scroll_up(self, _e):
        # Linux scroll up
        self._adjust_scroll(-30)

    def _on_scroll_down(self, _e):
        # Linux scroll down
        self._adjust_scroll(30)

    def _on_click(self, e):
        x, y = e.x, e.y
        # Show pressed feedback briefly
        pressed_any = False
        for idx, r in enumerate(self.hit_areas.get('tabs', [])):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                self.pressed_state['tab'] = idx
                pressed_any = True
                break
        if not pressed_any:
            for idx, r in enumerate(self.hit_areas.get('bottom', [])):
                if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                    self.pressed_state['bottom'] = idx
                    pressed_any = True
                    break
        if pressed_any:
            self.draw_ui()
            def _clear_press():
                self.pressed_state.update({'tab': None, 'bottom': None})
                self.draw_ui()
            self.after(120, _clear_press)

        # Edit button press
        if any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in self.hit_areas.get('edit', [])):
            self.pressed_state['edit'] = True
            self.draw_ui()
            def _clear_press_edit():
                self.pressed_state.update({'edit': False})
                self.draw_ui()
            self.after(120, _clear_press_edit)
            self._open_token_manager_dialog()
            return

        # Tabs click
        for idx, r in enumerate(self.hit_areas.get('tabs', [])):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                self._set_tab(["Tokens", "Items", "Activity"][idx])
                return

        # Bottom actions
        for idx, r in enumerate(self.hit_areas.get('bottom', [])):
            if r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2']:
                if idx == 1:
                    self._refresh_balances()
                if idx == 2:
                    self._set_node_url()
                if idx == 4:
                    self._open_settings_dialog()
                return

        # Address + copy
        if any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in self.hit_areas.get('addr', [])):
            self._show_keys()
            return

        if any(r['x1'] <= x <= r['x2'] and r['y1'] <= y <= r['y2'] for r in self.hit_areas.get('copy', [])):
            self._copy_address(None)
            return

    def _open_settings_dialog(self, _evt=None):
        WalletSettingsDialog(self)

    def _load_tokens_from_config(self) -> None:
        try:
            cfg_tokens = config_store.get_tokens()
        except Exception:
            cfg_tokens = []
        old_by = {t["contract"]: t for t in (self.tokens or [])}
        new_list: List[TokenRow] = []
        for t in cfg_tokens:
            try:
                name = str(t.get("name", ""))
                symbol = str(t.get("symbol", ""))
                contract = str(t.get("contract", ""))
                icon = str(t.get("icon", ""))
                row: TokenRow = {"name": name, "symbol": symbol, "contract": contract, "balance": None, "icon": icon}
                if contract in old_by:
                    row["balance"] = old_by[contract].get("balance")
                new_list.append(row)
            except Exception:
                continue
        self.tokens = new_list

    def _save_tokens_to_config(self) -> None:
        try:
            config_store.set_tokens([
                {"name": t["name"], "symbol": t["symbol"], "contract": t["contract"], "icon": t.get("icon", "")}
                for t in (self.tokens or [])
            ])
        except Exception:
            pass

    def _open_token_manager_dialog(self, _evt=None):
        win = tk.Toplevel(self)
        win.title("Token Manager")
        win.configure(bg="#0b1417")
        win.transient(self)
        win.grab_set()

        pad = 12
        root = tk.Frame(win, bg="#0b1417")
        root.pack(padx=pad, pady=pad, fill='both', expand=True)

        # Token list
        list_frame = tk.Frame(root, bg="#0b1417")
        list_frame.pack(fill='both', expand=True)

        lb = tk.Listbox(list_frame, activestyle='none', selectmode='browse',
                        bg="#0f1b1f", fg="#e8f6f7", highlightthickness=1, relief='flat')
        sb = tk.Scrollbar(list_frame, orient='vertical', command=lb.yview)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        btns = tk.Frame(root, bg="#0b1417")
        btns.pack(fill='x', pady=(10,0))

        tokens = []

        def refresh_list():
            nonlocal tokens
            try:
                tokens = config_store.get_tokens()
            except Exception:
                tokens = []
            lb.delete(0, 'end')
            for t in tokens:
                name = t.get('name', '')
                sym = t.get('symbol', '')
                con = t.get('contract', '')
                lb.insert('end', f"{name} ({sym}) - {con}")

        def ensure_selection():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Tokens", "Select a token", parent=win)
                return None
            return sel[0]

        def edit_dialog(initial: Dict[str, str] | None, title: str) -> Dict[str, str] | None:
            d = tk.Toplevel(win)
            d.title(title)
            d.configure(bg="#0b1417")
            d.transient(win)
            d.grab_set()

            frm = tk.Frame(d, bg="#0b1417")
            frm.pack(padx=pad, pady=pad, fill='both', expand=True)

            tk.Label(frm, text="Name", fg="#9ac6cc", bg="#0b1417").grid(row=0, column=0, sticky='w')
            name_var = tk.StringVar(value=(initial.get("name","") if initial else ""))
            tk.Entry(frm, textvariable=name_var, width=40, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat').grid(row=1, column=0, sticky='we', pady=(2,8))

            tk.Label(frm, text="Symbol", fg="#9ac6cc", bg="#0b1417").grid(row=2, column=0, sticky='w')
            symbol_var = tk.StringVar(value=(initial.get("symbol","") if initial else ""))
            tk.Entry(frm, textvariable=symbol_var, width=40, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat').grid(row=3, column=0, sticky='we', pady=(2,8))

            tk.Label(frm, text="Contract", fg="#9ac6cc", bg="#0b1417").grid(row=4, column=0, sticky='w')
            contract_var = tk.StringVar(value=(initial.get("contract","") if initial else ""))
            tk.Entry(frm, textvariable=contract_var, width=40, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat').grid(row=5, column=0, sticky='we', pady=(2,8))

            tk.Label(frm, text="Icon (optional short text)", fg="#9ac6cc", bg="#0b1417").grid(row=6, column=0, sticky='w')
            icon_var = tk.StringVar(value=(initial.get("icon","") if initial else ""))
            tk.Entry(frm, textvariable=icon_var, width=40, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat').grid(row=7, column=0, sticky='we', pady=(2,8))

            btnrow = tk.Frame(frm, bg="#0b1417")
            btnrow.grid(row=8, column=0, sticky='e', pady=(10,0))

            res = {"ok": False}
            def on_ok():
                n = name_var.get().strip()
                s = symbol_var.get().strip()
                c = contract_var.get().strip()
                if not n or not s or not c:
                    messagebox.showerror("Token", "Please fill in name, symbol and contract", parent=d)
                    return
                res["ok"] = True
                d.destroy()

            tk.Button(btnrow, text="Cancel", command=d.destroy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right', padx=6)
            tk.Button(btnrow, text="OK", command=on_ok, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right')

            try:
                frm.grid_columnconfigure(0, weight=1)
            except Exception:
                pass

            d.wait_window(d)

            if not res["ok"]:
                return None
            return {
                "name": name_var.get().strip(),
                "symbol": symbol_var.get().strip(),
                "contract": contract_var.get().strip(),
                "icon": icon_var.get().strip(),
            }

        def on_add():
            data = edit_dialog(None, "Add token")
            if not data:
                return
            try:
                added = config_store.add_token(data["name"], data["symbol"], data["contract"], data.get("icon",""))
            except Exception as e:
                messagebox.showerror("Token", str(e), parent=win)
                return
            if not added:
                messagebox.showinfo("Token", "This contract already exists in the list", parent=win)
                return
            try:
                self._load_tokens_from_config()
            except Exception:
                pass
            self.draw_ui()
            try:
                self._refresh_balances()
            except Exception:
                pass
            refresh_list()

        def on_edit():
            idx = ensure_selection()
            if idx is None:
                return
            t = tokens[idx]
            data = edit_dialog(t, "Edit token")
            if not data:
                return
            # If contract changed, validate duplicate
            new_c = data["contract"]
            old_c = t.get("contract","")
            if new_c != old_c and any(x.get("contract","") == new_c for x in tokens):
                messagebox.showerror("Token", "A token with that contract already exists", parent=win)
                return
            try:
                config_store.upsert_token(data["name"], data["symbol"], data["contract"], data.get("icon",""))
            except Exception as e:
                messagebox.showerror("Token", str(e), parent=win)
                return
            try:
                self._load_tokens_from_config()
            except Exception:
                pass
            self.draw_ui()
            try:
                self._refresh_balances()
            except Exception:
                pass
            refresh_list()

        def on_remove():
            idx = ensure_selection()
            if idx is None:
                return
            t = tokens[idx]
            c = t.get("contract","")
            try:
                if config_store.is_default_contract(c):
                    messagebox.showinfo("Token", "You cannot remove default tokens", parent=win)
                    return
            except Exception:
                pass
            if not messagebox.askyesno("Delete", "Remove this token from the list?", parent=win):
                return
            try:
                ok = config_store.remove_token(c)
            except Exception as e:
                messagebox.showerror("Token", str(e), parent=win)
                return
            if not ok:
                messagebox.showinfo("Token", "Could not remove (does it no longer exist?)", parent=win)
                return
            try:
                self._load_tokens_from_config()
            except Exception:
                pass
            self.draw_ui()
            try:
                self._refresh_balances()
            except Exception:
                pass
            refresh_list()

        tk.Button(btns, text="Add", command=on_add, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left')
        tk.Button(btns, text="Edit", command=on_edit, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left', padx=6)
        tk.Button(btns, text="Remove", command=on_remove, relief='raised', borderwidth=2, activebackground="#3a1a1a", bg="#1c1010", fg="#ffdede").pack(side='left', padx=6)
        tk.Button(btns, text="Close", command=win.destroy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right')

        def on_double_click(_evt):
            on_edit()
        lb.bind("<Double-Button-1>", on_double_click)

        refresh_list()

    # --- Wallet actions ---

    def _create_wallet(self, _evt=None):
        info = self.wallet_manager.create_hd_wallet()
        self.current_wallet = info
        # Display public key truncated as address placeholder
        self.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
        self.draw_ui()
        # Persist securely
        try:
            if secure_store.requires_password():
                if not self._store_password:
                    p1 = simpledialog.askstring("Protect your wallet", "Create a password for this device", show='*')
                    p2 = simpledialog.askstring("Confirm", "Repeat the password", show='*')
                    if not p1 or p1 != p2:
                        messagebox.showerror("Password", "Passwords do not match")
                        return
                    self._store_password = p1
                secure_store.save_wallet(info, node_url=self.node_url, password=self._store_password)
            else:
                secure_store.save_wallet(info, node_url=self.node_url)
        except Exception as e:
            messagebox.showwarning("Local save", f"Could not securely save the wallet: {e}")
        messagebox.showinfo("Wallet created", "A new wallet was generated. Save your phrase:")
        # Show mnemonic in a simple dialog for copy (read-only)
        try:
            self.clipboard_clear()
            self.clipboard_append(info.mnemonic or "")
        except Exception:
            pass
        messagebox.showinfo("Mnemonic", info.mnemonic or "")
        self._refresh_balances()

    def _import_wallet(self, _evt=None):
        choice = messagebox.askquestion(
            "Import Wallet",
            "Import using mnemonic? Click 'Yes'.\nFor private key, click 'No'."
        )
        try:
            if choice == 'yes':
                m = simpledialog.askstring("Mnemonic", "Paste your mnemonic (24 words)")
                if not m:
                    return
                info = self.wallet_manager.import_hd_wallet(m)
            else:
                k = simpledialog.askstring("Private Key", "Paste your private key (hex 64)")
                if not k:
                    return
                info = self.wallet_manager.import_private_key(k.strip())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.current_wallet = info
        self.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
        self.draw_ui()
        # Persist securely
        try:
            if secure_store.requires_password():
                if not self._store_password:
                    p1 = simpledialog.askstring("Protect your wallet", "Create a password for this device", show='*')
                    p2 = simpledialog.askstring("Confirm", "Repeat the password", show='*')
                    if not p1 or p1 != p2:
                        messagebox.showerror("Password", "Passwords do not match")
                        return
                    self._store_password = p1
                secure_store.save_wallet(info, node_url=self.node_url, password=self._store_password)
            else:
                secure_store.save_wallet(info, node_url=self.node_url)
        except Exception as e:
            messagebox.showwarning("Local save", f"Could not securely save the wallet: {e}")
        self._refresh_balances()

    def _show_keys(self, _evt=None):
        if not self.current_wallet:
            messagebox.showinfo("No wallet", "Create or import a wallet first (Ctrl+N / Ctrl+I)")
            return
        info = self.current_wallet
        msg = f"Public key:\n{info.public_key}\n\nPrivate key:\n{info.private_key}\n\nMnemonic:\n{info.mnemonic or '(not available)'}"
        try:
            self.clipboard_clear()
            self.clipboard_append(msg)
        except Exception:
            pass
        messagebox.showinfo("Keys", msg)

    def _set_node_url(self, _evt=None):
        default = self.node_url or "http://127.0.0.1:26657"
        url = simpledialog.askstring("Xian Node", "Node URL (http://host:port)", initialvalue=default)
        if url:
            self.node_url = url.strip().rstrip('/')
            # update persisted store if wallet exists
            if self.current_wallet is not None:
                try:
                    if secure_store.requires_password():
                        if not self._store_password:
                            self._store_password = simpledialog.askstring("Security", "Enter the password to update the saved wallet", show='*')
                        if self._store_password:
                            secure_store.save_wallet(self.current_wallet, node_url=self.node_url, password=self._store_password)
                    else:
                        secure_store.save_wallet(self.current_wallet, node_url=self.node_url)
                except Exception:
                    pass
            self._refresh_balances()

    def _refresh_balances(self, _evt=None):
        try:
            self._load_tokens_from_config()
        except Exception:
            pass
        if self.loading_balances:
            return

        node_url = self.node_url
        wallet = self.current_wallet
        if node_url is None or wallet is None:
            # Nothing to fetch
            self.total_balance_xian = 0.0
            for t in self.tokens:
                t["balance"] = None
            self.draw_ui()
            return

        self.loading_balances = True
        self.draw_ui()

        def worker(node_url=node_url, addr=wallet.public_key):
            total_xian = 0.0
            try:
                client = Xian(node_url)
                for t in self.tokens:
                    try:
                        bal = client.get_balance(address=addr, contract=t["contract"])
                        t["balance"] = bal
                        if t["contract"] == "currency":
                            total_xian = float(bal)
                    except Exception:
                        t["balance"] = None
            finally:
                def done():
                    self.total_balance_xian = total_xian
                    self.loading_balances = False
                    self.draw_ui()
                self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    # ---- Initial setup dialog ----
    def _initial_setup(self):
        # Try loading again if needed
        if self.current_wallet is None and secure_store.store_exists():
            if secure_store.requires_password():
                pwd = simpledialog.askstring("Security", "Enter the wallet password", show='*')
                if pwd:
                    self._store_password = pwd
                    info, node = secure_store.load_wallet(password=pwd)
                else:
                    info, node = (None, None)
            else:
                info, node = secure_store.load_wallet()
            if info is not None:
                self.current_wallet = info
                self.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
                if node:
                    self.node_url = node
                self.draw_ui()
                self._refresh_balances()
                return
        if self.current_wallet is not None:
            return
        dlg = SetupDialog(self, default_node=self.node_url or "http://127.0.0.1:26657")
        self.wait_window(dlg.window)
        if not getattr(dlg, 'ok', False):
            return
        self.node_url = dlg.node_url
        try:
            if dlg.mode == 'create':
                info = self.wallet_manager.create_hd_wallet()
                # Show mnemonic to the user
                try:
                    self.clipboard_clear()
                    self.clipboard_append(info.mnemonic or "")
                except Exception:
                    pass
                messagebox.showinfo("Mnemonic", info.mnemonic or "")
            elif dlg.mode == 'mnemonic':
                info = self.wallet_manager.import_hd_wallet(dlg.mnemonic)
            else:  # 'priv'
                info = self.wallet_manager.import_private_key(dlg.private_key)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        # Set wallet and refresh
        self.current_wallet = info
        self.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
        # Persist securely
        try:
            secure_store.save_wallet(info, node_url=self.node_url)
        except Exception as e:
            messagebox.showwarning("Local save", f"Could not securely save the wallet: {e}")
        self.draw_ui()
        self._refresh_balances()


class SetupDialog:
    def __init__(self, master, default_node: str):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("Configure Wallet")
        self.window.configure(bg="#0b1417")
        self.window.transient(master)
        self.window.grab_set()

        # State
        self.ok = False
        # Initialize variables
        self.mode: str = 'create'
        self.node_url: str = default_node
        self.mnemonic: str = ''
        self.private_key: str = ''
        self.mode_var = tk.StringVar(value='create')
        self.node_var = tk.StringVar(value=default_node)
        self.mnemonic_text: tk.Text
        self.priv_var = tk.StringVar()

        # Layout
        pad = 10
        frm = tk.Frame(self.window, bg="#0b1417")
        frm.pack(padx=pad, pady=pad)

        tk.Label(frm, text="Node (http://host:port)", fg="#9ac6cc", bg="#0b1417").grid(row=0, column=0, sticky='w')
        tk.Entry(frm, textvariable=self.node_var, width=34, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat').grid(row=1, column=0, columnspan=3, sticky='we', pady=(0,10))

        tk.Label(frm, text="Choose a method", fg="#9ac6cc", bg="#0b1417").grid(row=2, column=0, sticky='w')
        tk.Radiobutton(frm, text="Create new", variable=self.mode_var, value='create', command=self._update_mode, bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").grid(row=3, column=0, sticky='w')
        tk.Radiobutton(frm, text="Import mnemonic", variable=self.mode_var, value='mnemonic', command=self._update_mode, bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").grid(row=3, column=1, sticky='w')
        tk.Radiobutton(frm, text="Import private key", variable=self.mode_var, value='priv', command=self._update_mode, bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").grid(row=3, column=2, sticky='w')

        self.mnemonic_text = tk.Text(frm, height=4, width=44, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat', wrap='word')
        self.mnemonic_text.grid(row=4, column=0, columnspan=3, pady=(6,6))
        self.mnemonic_text.insert('1.0', "Paste your mnemonic here (24 words)")
        self.mnemonic_text.config(state='disabled')

        self.priv_entry = tk.Entry(frm, textvariable=self.priv_var, width=44, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat')
        self.priv_entry.grid(row=5, column=0, columnspan=3, pady=(0,6))

        btns = tk.Frame(frm, bg="#0b1417")
        btns.grid(row=6, column=0, columnspan=3, pady=(8,0))
        tk.Button(btns, text="Cancel", command=self.window.destroy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right', padx=6)
        tk.Button(btns, text="OK", command=self._accept, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right')

        self._update_mode()

    def _update_mode(self):
        mode = self.mode_var.get()
        self.mnemonic_text.config(state='normal' if mode == 'mnemonic' else 'disabled')
        self.priv_entry.config(state='normal' if mode == 'priv' else 'disabled')

    def _accept(self):
        self.mode = self.mode_var.get()
        self.node_url = self.node_var.get().strip()
        self.mnemonic = ''
        self.private_key = ''
        if self.mode == 'mnemonic':
            self.mnemonic = self.mnemonic_text.get('1.0', 'end').strip()
            if not self.mnemonic:
                messagebox.showerror("Missing mnemonic", "Paste your mnemonic to continue")
                return
        elif self.mode == 'priv':
            self.private_key = self.priv_var.get().strip()
            if not self.private_key:
                messagebox.showerror("Missing key", "Paste your private key to continue")
                return
        if not self.node_url:
            messagebox.showerror("Missing node", "Enter the node URL")
            return
        self.ok = True
        self.window.destroy()


class WalletSettingsDialog:
    def __init__(self, master: 'WalletUI'):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.title("Wallet Settings")
        self.window.configure(bg="#0b1417")
        self.window.transient(master)
        self.window.grab_set()

        pad = 12
        root = tk.Frame(self.window, bg="#0b1417")
        root.pack(padx=pad, pady=pad)

        # Node section
        sec1 = tk.LabelFrame(root, text="Node", fg="#9ac6cc", bg="#0b1417", labelanchor='n')
        sec1.configure(highlightbackground="#1a2a2f", highlightcolor="#1a2a2f")
        sec1.pack(fill='x', pady=(0,10))
        self.node_var = tk.StringVar(value=master.node_url or "http://127.0.0.1:26657")
        tk.Label(sec1, text="URL (http://host:port)", fg="#9ac6cc", bg="#0b1417").pack(anchor='w')
        node_entry = tk.Entry(sec1, textvariable=self.node_var, width=40, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat')
        node_entry.pack(fill='x', pady=(2,6))
        tk.Button(sec1, text="Save Node", command=self._save_node, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(anchor='e')

        # Current wallet section
        sec2 = tk.LabelFrame(root, text="Current wallet", fg="#9ac6cc", bg="#0b1417", labelanchor='n')
        sec2.configure(highlightbackground="#1a2a2f", highlightcolor="#1a2a2f")
        sec2.pack(fill='x', pady=(0,10))
        addr = master.address if master.current_wallet else "(no wallet)"
        tk.Label(sec2, text=f"Address: {addr}", fg="#dbe9ea", bg="#0b1417").pack(anchor='w', pady=(0,6))
        tk.Button(sec2, text="Remove wallet from this device", command=self._clear_wallet, relief='raised', borderwidth=2, activebackground="#3a1a1a", bg="#1c1010", fg="#ffdede").pack(anchor='w')

        # Create/import section
        sec3 = tk.LabelFrame(root, text="Create / Import", fg="#9ac6cc", bg="#0b1417", labelanchor='n')
        sec3.configure(highlightbackground="#1a2a2f", highlightcolor="#1a2a2f")
        sec3.pack(fill='x', pady=(0,4))
        self.mode_var = tk.StringVar(value='create')
        row = tk.Frame(sec3, bg="#0b1417")
        row.pack(fill='x')
        tk.Radiobutton(row, text="Create new", variable=self.mode_var, value='create', bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").pack(side='left')
        tk.Radiobutton(row, text="Import mnemonic", variable=self.mode_var, value='mnemonic', bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").pack(side='left', padx=(14,0))
        tk.Radiobutton(row, text="Import private key", variable=self.mode_var, value='priv', bg="#0b1417", fg="#dbe9ea", selectcolor="#0f1b1f", activebackground="#0b1417").pack(side='left', padx=(14,0))

        self.mnemonic_text = tk.Text(sec3, height=4, width=48, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat', wrap='word')
        self.mnemonic_text.pack(fill='x', pady=(6,6))
        self.mnemonic_text.insert('1.0', "Paste your mnemonic here (24 words)")
        self.priv_var = tk.StringVar()
        self.priv_entry = tk.Entry(sec3, textvariable=self.priv_var, width=48, bg="#0f1b1f", fg="#e8f6f7", insertbackground="#e8f6f7", relief='flat')
        self.priv_entry.pack(fill='x', pady=(0,6))

        self._update_fields()
        self.mode_var.trace_add('write', lambda *_: self._update_fields())

        # Backup section
        sec4 = tk.LabelFrame(root, text="Backup", fg="#9ac6cc", bg="#0b1417", labelanchor='n')
        sec4.configure(highlightbackground="#1a2a2f", highlightcolor="#1a2a2f")
        sec4.pack(fill='x', pady=(6,0))
        tk.Label(sec4, text="Back up private key or mnemonic", fg="#9ac6cc", bg="#0b1417").pack(anchor='w')
        btnrow = tk.Frame(sec4, bg="#0b1417")
        btnrow.pack(fill='x', pady=(4,2))
        tk.Button(btnrow, text="Show private key", command=self._backup_private, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left')
        tk.Button(btnrow, text="Show mnemonic", command=self._backup_mnemonic, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left', padx=8)
        tk.Button(btnrow, text="Export encrypted JSON", command=self._export_json_encrypted, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left', padx=8)
        tk.Button(btnrow, text="Import encrypted JSON", command=self._import_json_encrypted, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left')

        # Footer buttons
        foot = tk.Frame(root, bg="#0b1417")
        foot.pack(fill='x', pady=(8,0))
        tk.Button(foot, text="Cancel", command=self.window.destroy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right', padx=6)
        tk.Button(foot, text="Apply", command=self._apply, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right')

    def _update_fields(self):
        mode = self.mode_var.get()
        self.mnemonic_text.config(state='normal' if mode == 'mnemonic' else 'disabled')
        self.priv_entry.config(state='normal' if mode == 'priv' else 'disabled')

    def _save_node(self):
        val = (self.node_var.get() or '').strip().rstrip('/')
        if not val:
            messagebox.showerror("Node", "Enter a valid URL")
            return
        self.master.node_url = val
        # persist if wallet exists
        if self.master.current_wallet is not None:
            try:
                if secure_store.requires_password():
                    if not self.master._store_password:
                        self.master._store_password = simpledialog.askstring("Security", "Wallet password", show='*')
                    if self.master._store_password:
                        secure_store.save_wallet(self.master.current_wallet, node_url=self.master.node_url, password=self.master._store_password)
                else:
                    secure_store.save_wallet(self.master.current_wallet, node_url=self.master.node_url)
            except Exception:
                pass
        self.master.draw_ui()
        self.master._refresh_balances()

    def _clear_wallet(self):
        if not self.master.current_wallet and not secure_store.store_exists():
            return
        if not messagebox.askyesno("Delete", "Delete the stored wallet from this device? This does not delete anything on-chain, only this computer."):
            return
        try:
            secure_store.clear_wallet()
        except Exception:
            pass
        self.master.current_wallet = None
        self.master.address = "d53f0b...a21dcf"
        self.master.total_balance_xian = 0.0
        for t in self.master.tokens:
            t["balance"] = None
        self.master.draw_ui()
        messagebox.showinfo("Done", "The wallet was removed from this device. You can now create or import another.")

    def _apply(self):
        mode = self.mode_var.get()
        # Ensure node from entry is saved to master before actions
        self._save_node()
        try:
            if mode == 'create':
                info = self.master.wallet_manager.create_hd_wallet()
                # show mnemonic
                try:
                    self.master.clipboard_clear()
                    self.master.clipboard_append(info.mnemonic or "")
                except Exception:
                    pass
                messagebox.showinfo("Mnemonic", info.mnemonic or "")
            elif mode == 'mnemonic':
                m = self.mnemonic_text.get('1.0', 'end').strip()
                if not m:
                    messagebox.showerror("Mnemonic", "Paste your mnemonic (24 words)")
                    return
                info = self.master.wallet_manager.import_hd_wallet(m)
            else:
                k = self.priv_var.get().strip()
                if not k:
                    messagebox.showerror("Private key", "Paste your private key (hex 64)")
                    return
                info = self.master.wallet_manager.import_private_key(k)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # Persist securely
        try:
            if secure_store.requires_password():
                if not self.master._store_password:
                    p1 = simpledialog.askstring("Protect your wallet", "Create a password for this device", show='*')
                    p2 = simpledialog.askstring("Confirm", "Repeat the password", show='*')
                    if not p1 or p1 != p2:
                        messagebox.showerror("Password", "Passwords do not match")
                        return
                    self.master._store_password = p1
                secure_store.save_wallet(info, node_url=self.master.node_url, password=self.master._store_password)
            else:
                secure_store.save_wallet(info, node_url=self.master.node_url)
        except Exception as e:
            messagebox.showwarning("Local save", f"Could not securely save the wallet: {e}")

        # Update master state
        self.master.current_wallet = info
        self.master.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
        self.master.draw_ui()
        self.master._refresh_balances()
        self.window.destroy()

    # ---- Backup helpers ----
    def _require_auth(self) -> bool:
        if not messagebox.askyesno("Warning", "You are about to display sensitive data (key/seed). Do you want to continue?"):
            return False
        # If session password exists, request it
        if getattr(self.master, '_store_password', None):
            pwd = simpledialog.askstring("Security", "Enter your password", parent=self.window, show='*')
            if pwd != self.master._store_password:
                messagebox.showerror("Password", "Incorrect password")
                return False
        return True

    def _backup_private(self):
        if not self.master.current_wallet:
            messagebox.showinfo("No wallet", "No wallet loaded")
            return
        if not self._require_auth():
            return
        pk = self.master.current_wallet.private_key
        self._show_export("Private Key", pk)

    def _backup_mnemonic(self):
        if not self.master.current_wallet or not self.master.current_wallet.mnemonic:
            messagebox.showinfo("No mnemonic", "No mnemonic available for this wallet")
            return
        if not self._require_auth():
            return
        self._show_export("Mnemonic (seed)", self.master.current_wallet.mnemonic)

    def _show_export(self, title: str, content: str):
        win = tk.Toplevel(self.window)
        win.title(title)
        win.configure(bg="#0b1417")
        win.transient(self.window)
        pad = 10
        frm = tk.Frame(win, bg="#0b1417")
        frm.pack(padx=pad, pady=pad)
        tk.Label(frm, text="Save this information in a secure place.", fg="#ffd7a1", bg="#0b1417").pack(anchor='w', pady=(0,6))
        txt = tk.Text(frm, height=6, width=56, bg="#0f1b1f", fg="#e8f6f7", relief='flat', wrap='word')
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', content)
        txt.config(state='disabled')
        row = tk.Frame(frm, bg="#0b1417")
        row.pack(fill='x', pady=(8,0))
        def _copy():
            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(content)
                messagebox.showinfo("Copied", "Content copied to clipboard")
                # Clear clipboard after 30s as a safety measure
                try:
                    self.master.after(30000, self.master.clipboard_clear)
                except Exception:
                    pass
            except Exception:
                pass
        def _save_file():
            path = filedialog.asksaveasfilename(title="Save backup", defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    messagebox.showinfo("Saved", "Backup saved successfully")
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        tk.Button(row, text="Copy", command=_copy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right')
        tk.Button(row, text="Save as...", command=_save_file, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='right', padx=6)
        tk.Button(row, text="Close", command=win.destroy, relief='raised', borderwidth=2, activebackground="#16252a", bg="#101b1f", fg="#dbe9ea").pack(side='left')

    def _export_json_encrypted(self):
        if not self.master.current_wallet:
            messagebox.showinfo("No wallet", "No wallet loaded")
            return
        p1 = simpledialog.askstring("Export JSON", "Create a password for the backup", parent=self.window, show='*')
        p2 = simpledialog.askstring("Confirm", "Repeat the password", parent=self.window, show='*')
        if not p1 or p1 != p2:
            messagebox.showerror("Password", "Passwords do not match")
            return
        try:
            blob = secure_store.create_portable_backup(self.master.current_wallet, node_url=self.master.node_url, password=p1)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        path = filedialog.asksaveasfilename(title="Save encrypted backup", defaultextension=".xwbackup", filetypes=[("Xian Wallet Backup","*.xwbackup"), ("JSON","*.json"), ("All","*.*")])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(blob)
                messagebox.showinfo("Saved", "Encrypted backup saved successfully")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _import_json_encrypted(self):
        path = filedialog.askopenfilename(title="Import encrypted backup", filetypes=[("Xian Wallet Backup","*.xwbackup"), ("JSON","*.json"), ("All","*.*")])
        if not path:
            return
        pwd = simpledialog.askstring("Import JSON", "Enter the backup password", parent=self.window, show='*')
        if not pwd:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                blob = f.read()
            info, node = secure_store.restore_portable_backup(blob, password=pwd)
        except Exception as e:
            messagebox.showerror("Error", f"Could not import: {e}")
            return
        try:
            if secure_store.requires_password():
                if not self.master._store_password:
                    dp1 = simpledialog.askstring("Protect your device", "Create a password for this device", parent=self.window, show='*')
                    dp2 = simpledialog.askstring("Confirm", "Repeat the password", parent=self.window, show='*')
                    if not dp1 or dp1 != dp2:
                        messagebox.showerror("Password", "Passwords do not match")
                        return
                    self.master._store_password = dp1
                secure_store.save_wallet(info, node_url=node or self.master.node_url, password=self.master._store_password)
            else:
                secure_store.save_wallet(info, node_url=node or self.master.node_url)
        except Exception as e:
            messagebox.showwarning("Local save", f"Could not securely save the wallet: {e}")
        self.master.current_wallet = info
        if node:
            self.master.node_url = node
        self.master.address = f"{info.public_key[:6]}...{info.public_key[-6:]}"
        self.master.draw_ui()
        self.master._refresh_balances()


if __name__ == "__main__":
    app = WalletUI()
    app.mainloop()
