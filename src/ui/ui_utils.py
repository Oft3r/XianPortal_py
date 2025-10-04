import tkinter as tk


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
    def h2i(h: str) -> int:
        return int(h, 16)

    r1, g1, b1 = h2i(c1[1:3]), h2i(c1[3:5]), h2i(c1[5:7])
    r2, g2, b2 = h2i(c2[1:3]), h2i(c2[3:5]), h2i(c2[5:7])
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"