import tkinter as tk
import threading
from typing import Optional, Callable, Any

from PIL import Image, ImageDraw, ImageFont
import pystray


class SystemTray:


    def __init__(
        self,
        window: tk.Tk,
        on_show: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):

        self.window = window
        self.on_show = on_show
        self.on_quit = on_quit
        self.icon = None  # Deliberately untyped to avoid strict external types
        self.is_visible = True
        self._icon_running = False

    def create_icon_image(self, size=(64, 64)):

        image = Image.new("RGBA", size, color=(35, 150, 200, 255))
        draw = ImageDraw.Draw(image)

        # Circle
        draw.ellipse(
            [2, 2, size[0] - 2, size[1] - 2],
            fill=(35, 150, 200, 255),
            outline=(255, 255, 255, 255),
            width=2,
        )

        # Letter X
        text = "X"
        font_size = int(min(size) * 0.5)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Compute text bounds with robust fallbacks for Pillow versions
        try:
            # Preferred (Pillow >= 8.0)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            offset_x, offset_y = bbox[0], bbox[1]
        except Exception:
            # Fallback 1: font.getbbox (may exist on many versions)
            try:
                bbox2 = font.getbbox(text)  # type: ignore[attr-defined]
                text_width = bbox2[2] - bbox2[0]
                text_height = bbox2[3] - bbox2[1]
                offset_x, offset_y = bbox2[0], bbox2[1]
            except Exception:
                # Fallback 2: font.getmask provides raster size
                try:
                    mask = font.getmask(text)
                    text_width, text_height = mask.size
                    offset_x = offset_y = 0
                except Exception:
                    # Last resort: approximate with font size
                    text_width = text_height = font_size
                    offset_x = offset_y = 0

        text_x = (size[0] - text_width) // 2 - offset_x
        text_y = (size[1] - text_height) // 2 - offset_y
        draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
        return image

    def show_window(self, icon=None, item=None):
        self.window.after(0, self._show_window_impl)

    def _show_window_impl(self):
        self.window.deiconify()
        self.window.lift()
        try:
            self.window.focus_force()
        except Exception:
            pass
        self.is_visible = True
        if self.on_show:
            try:
                self.on_show()
            except Exception as e:
                print(f"Error in on_show callback: {e}")

    def _on_unmap(self, _event):
        try:
            if self.window.state() == "iconic":
                self.minimize_to_tray()
        except Exception as e:
            print(f"Error handling minimize: {e}")

    def minimize_to_tray(self):
        if not self._icon_running:
            self._start_tray_icon()
            # Give the icon time to initialize
            self.window.after(200, self._hide_window)
        else:
            self._hide_window()

    def _hide_window(self):
        self.window.withdraw()
        self.is_visible = False

    def _start_tray_icon(self):
        if self._icon_running:
            return
        try:
            icon_image = self.create_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem("Show Wallet", self.show_window, default=True),
                pystray.MenuItem("Quit", self.quit_application),
            )
            self.icon = pystray.Icon("xian_portal", icon_image, "Xian Portal Wallet", menu)
            self._icon_running = True

            # Run the tray icon in a dedicated thread
            t = threading.Thread(target=self._run_icon, daemon=False, name="SystemTrayThread")
            t.start()
        except Exception as e:
            print(f"ERROR starting tray icon: {e}")
            try:
                import traceback

                traceback.print_exc()
            except Exception:
                pass
            self._icon_running = False

    def _run_icon(self):
        try:
            if self.icon:
                self.icon.run()
        except Exception as e:
            print(f"ERROR in tray icon thread: {e}")
            try:
                import traceback

                traceback.print_exc()
            except Exception:
                pass
        finally:
            self._icon_running = False

    def quit_application(self, icon=None, item=None):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        if self.on_quit:
            self.window.after(0, self.on_quit)
        else:
            self.window.after(0, self.window.quit)

    def destroy(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
        self._icon_running = False
