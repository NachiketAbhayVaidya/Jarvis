import math
import queue
import tkinter as tk
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText

from PIL import ImageTk

from ..remote import broadcaster

# -- fixed window footprint; the notch pill animates its HEIGHT inside it.
# Width never changes - flush against the top edge, it only grows downward. --
_MAX_W = 460
_SIDE_PAD = 20  # horizontal margin reserved for the glow bleed either side
_FIXED_W = _MAX_W - 2 * _SIDE_PAD  # the notch's width, constant in every state

_THIN_H = 6  # resting "bezel" height - just a slim glowing line
_EXPANDED_H = 46  # full pill height once listening/speaking
_WIN_H = _EXPANDED_H + 24  # window/canvas footprint, with room for glow bleed
_TOP_MARGIN = 0  # flush against the very top edge of the screen

_BOTTOM_RADIUS = 20  # only the bottom corners are rounded, like a real notch
_ARC_STEPS = 10

_EASE = 0.28  # how fast the pill eases toward its target height

_PAD_X = 14
_ICON_D = 18
_GAP_SM = 7
_GAP_MD = 10
_CLOSE_D = 16

_BAR_COUNT = 5
_BAR_WIDTH = 3
_BAR_GAP = 6
_BAR_MAX_H = 16
_BAR_SPEED = 0.22

_ANIMATION_INTERVAL_MS = 40
_CAPTION_TIMEOUT_MS = 6000
# Black, not magenta: anti-aliased edges blend toward the key color, and a
# blend-toward-black reads as a faint natural shadow instead of a color
# fringe against the glass pill.
_TRANSPARENT_KEY = "#000000"
_TAP_WINDOW_MS = 400  # time to wait for additional taps before acting

_GLASS_FILL = "#14172c"
_GLOW_LAYERS = (8, 4, 0)  # extra padding per ambient-glow layer, outer to inner

# (waveform/edge gradient start, end, status text color) per state
_PALETTE = {
    "idle": ("#4f6bd8", "#8a5cf6", "#9aa0c8"),
    "listening": ("#38d9c4", "#4f8cff", "#cfeee8"),
    "speaking": ("#4f8cff", "#ff5cf0", "#e4d6ff"),
}

_LABELS = {
    "idle": "Idle",
    "listening": "Listening...",
    "speaking": "Speaking...",
}


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _darken(color, t):
    """Blend `color` toward black by fraction `t` (0 = unchanged, 1 = black)."""
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex((r * (1 - t), g * (1 - t), b * (1 - t)))


def _lerp_color(c1, c2, t):
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def _notch_points(x1, y1, x2, y2, r, arc_steps=_ARC_STEPS):
    """A pill hanging from a flat top edge: square top corners, rounded
    bottom corners - the actual shape of a screen notch, not a full capsule.
    """
    pts = [(x1, y1), (x2, y1)]
    cx, cy = x2 - r, y2 - r
    for i in range(arc_steps + 1):
        ang = math.radians(90 * i / arc_steps)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    cx, cy = x1 + r, y2 - r
    for i in range(arc_steps + 1):
        ang = math.radians(90 + 90 * i / arc_steps)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


class FloatingOverlay:
    """A dark-glass "dynamic island" style notch hanging from the top-center
    of the screen. At rest it's just a thin glowing bezel line; the moment
    the wake word is heard it eases open downward into a full pill - a small
    gradient orb, the "Jarvis" label, a live status/caption line, a colorful
    animated waveform, a glowing gradient edge, and a close button - then
    eases shut again once idle. Its width never changes, only its height. A
    full transcript is kept and can be opened on demand (e.g. from the tray
    menu) without blocking the screen.

    Tap gestures anywhere on the pill: double-tap stops whatever Jarvis is
    currently doing without ending the program; triple-tap quits. The close
    button is a one-click shortcut for stop.
    """

    def __init__(self, on_stop, on_quit):
        self._queue = queue.Queue()
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._caption_after_id = None
        self._caption_persistent = False
        self._caption_text = ""
        self._log_lines = []
        self._log_window = None
        self._log_text = None
        self._remote_window = None
        self._remote_qr_photo = None
        self._bar_phase = 0.0
        self._status = "idle"
        self._tap_count = 0
        self._tap_after_id = None
        self._cur_h = float(_THIN_H)
        self._target_h = float(_THIN_H)

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=_TRANSPARENT_KEY)
        try:
            self.root.attributes("-transparentcolor", _TRANSPARENT_KEY)
            self.root.attributes("-alpha", 0.96)
        except tk.TclError:
            pass  # older Tk builds without per-pixel transparency support
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._on_quit())

        self._label_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self._status_font = tkfont.Font(family="Segoe UI", size=9)

        screen_w = self.root.winfo_screenwidth()
        self._anchor_x = screen_w // 2
        self.root.geometry(
            f"{_MAX_W}x{_WIN_H}+{self._anchor_x - _MAX_W // 2}+{_TOP_MARGIN}"
        )

        # The notch's left/right edges are fixed for good - only its bottom
        # edge (height) ever moves.
        cx = _MAX_W / 2
        self._x1, self._x2 = cx - _FIXED_W / 2, cx + _FIXED_W / 2

        self.canvas = tk.Canvas(
            self.root,
            width=_MAX_W,
            height=_WIN_H,
            bg=_TRANSPARENT_KEY,
            highlightthickness=0,
        )
        self.canvas.pack()

        # Ambient glow behind the pill: padded, dimmed copies of the same
        # notch shape, outer (dimmest) to inner.
        self._glow_shapes = [
            self.canvas.create_polygon(0, 0, 0, 0, fill="black", outline="")
            for _ in _GLOW_LAYERS
        ]
        self._glass = self.canvas.create_polygon(0, 0, 0, 0, fill=_GLASS_FILL, outline="")
        self._edge_segments = []  # gradient border, built lazily to match point count

        # Icon: a tiny gradient orb, outer to inner.
        self._icon_rings = [self.canvas.create_oval(0, 0, 0, 0, outline="") for _ in range(3)]

        self._label_item = self.canvas.create_text(
            0, 0, text="Jarvis", fill="#f2f3ff", font=self._label_font, anchor="w"
        )
        self._sep_item = self.canvas.create_text(
            0, 0, text="·", fill="#5a5e82", font=self._status_font, anchor="w"
        )
        self._status_item = self.canvas.create_text(
            0, 0, text="", fill="#9aa0c8", font=self._status_font, anchor="w"
        )
        self._bars = [
            self.canvas.create_line(0, 0, 0, 0, width=_BAR_WIDTH, capstyle=tk.ROUND)
            for _ in range(_BAR_COUNT)
        ]
        for bar in self._bars:
            self.canvas.itemconfig(bar, state="hidden")

        self._close_bg = self.canvas.create_oval(0, 0, 0, 0, fill="#22254a", outline="")
        self._close_x1 = self.canvas.create_line(0, 0, 0, 0, fill="#c7c9e6", width=1.6)
        self._close_x2 = self.canvas.create_line(0, 0, 0, 0, fill="#c7c9e6", width=1.6)
        for item in (self._close_bg, self._close_x1, self._close_x2):
            self.canvas.addtag_withtag("close_btn", item)
        self.canvas.tag_bind("close_btn", "<ButtonPress-1>", self._on_close_click)

        self.canvas.bind("<ButtonPress-1>", self._on_press)

        self._animate()
        self.root.after(100, self._drain_queue)

    # -- tap gestures / close button ---------------------------------------
    def _on_press(self, event):
        self._tap_count += 1
        if self._tap_after_id is not None:
            self.root.after_cancel(self._tap_after_id)
        self._tap_after_id = self.root.after(_TAP_WINDOW_MS, self._resolve_taps)

    def _resolve_taps(self):
        count = self._tap_count
        self._tap_count = 0
        self._tap_after_id = None
        if count == 2:
            if self._on_stop:
                self._on_stop()
        elif count >= 3:
            if self._on_quit:
                self._on_quit()

    def _on_close_click(self, event):
        if self._on_stop:
            self._on_stop()
        return "break"

    # -- public, thread-safe API ----------------------------------------
    def show(self):
        self._queue.put(("show_log", None))

    def show_remote_info(self, **pairing_info):
        self._queue.put(("show_remote_info", pairing_info))

    def set_status(self, status: str):
        self._queue.put(("status", status))
        broadcaster.publish({"type": "status", "status": status})

    def log(self, line: str):
        self._queue.put(("log", line))
        broadcaster.publish({"type": "log", "line": line})

    def close(self):
        self._queue.put(("destroy", None))

    def run(self):
        self.root.mainloop()

    # -- content / sizing ----------------------------------------------------
    def _status_text(self):
        text = self._caption_text or _LABELS.get(self._status, "")
        for prefix in ("Jarvis:", "You:"):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        max_w = 220
        if self._status_font.measure(text) <= max_w:
            return text
        while text and self._status_font.measure(text + "...") > max_w:
            text = text[:-1]
        return text + "..."

    # -- animation -----------------------------------------------------------
    def _animate(self):
        self._bar_phase += _BAR_SPEED
        show_bars = self._status in ("listening", "speaking")
        status_text = self._status_text()

        self._target_h = _THIN_H if self._status == "idle" else _EXPANDED_H
        self._cur_h += (self._target_h - self._cur_h) * _EASE
        h = self._cur_h
        # Only draw the label/icon/waveform/close button once the pill has
        # opened up enough to actually fit them - otherwise they'd render
        # clipped (or overflowing) against a still-thin bezel.
        show_content = h > (_THIN_H + _EXPANDED_H) / 2

        edge_a, edge_b, status_color = _PALETTE.get(self._status, _PALETTE["idle"])

        x1, x2 = self._x1, self._x2
        y1, y2 = 0, h
        r = min(_BOTTOM_RADIUS, _FIXED_W / 2, h)

        pts = _notch_points(x1, y1, x2, y2, r)
        flat = [c for p in pts for c in p]

        for layer_id, pad in zip(self._glow_shapes, _GLOW_LAYERS):
            gp = _notch_points(x1 - pad, y1, x2 + pad, y2 + pad, r + pad)
            self.canvas.coords(layer_id, *[c for p in gp for c in p])
            self.canvas.itemconfig(layer_id, fill=_darken(edge_b, 0.8 if pad else 0.55))

        self.canvas.coords(self._glass, *flat)

        # Gradient edge: recolor a running set of short segments along the
        # boundary, blue-to-pink (or state equivalent) left to right.
        n = len(pts)
        if len(self._edge_segments) != n:
            for seg in self._edge_segments:
                self.canvas.delete(seg)
            self._edge_segments = [
                self.canvas.create_line(0, 0, 0, 0, width=2) for _ in range(n)
            ]
        for i in range(n):
            x_a, y_a = pts[i]
            x_b, y_b = pts[(i + 1) % n]
            t = max(0.0, min(1.0, ((x_a + x_b) / 2 - x1) / max(1.0, (x2 - x1))))
            color = _lerp_color(edge_a, edge_b, t)
            self.canvas.coords(self._edge_segments[i], x_a, y_a, x_b, y_b)
            self.canvas.itemconfig(self._edge_segments[i], fill=color)

        if not show_content:
            for ring in self._icon_rings:
                self.canvas.itemconfig(ring, state="hidden")
            for item in (self._label_item, self._sep_item, self._status_item):
                self.canvas.itemconfig(item, state="hidden")
            for bar in self._bars:
                self.canvas.itemconfig(bar, state="hidden")
            for item in (self._close_bg, self._close_x1, self._close_x2):
                self.canvas.itemconfig(item, state="hidden")
            self.root.after(_ANIMATION_INTERVAL_MS, self._animate)
            return

        # -- icon --
        icon_cx = x1 + _PAD_X + _ICON_D / 2
        icon_cy = _EXPANDED_H / 2
        for ring, frac, t in zip(self._icon_rings, (1.0, 0.66, 0.36), (0.0, 0.5, 1.0)):
            rr = _ICON_D / 2 * frac
            self.canvas.coords(
                ring, icon_cx - rr, icon_cy - rr, icon_cx + rr, icon_cy + rr
            )
            self.canvas.itemconfig(ring, fill=_lerp_color(edge_a, edge_b, t), state="normal")

        # -- label / separator / status --
        for item in (self._label_item, self._sep_item, self._status_item):
            self.canvas.itemconfig(item, state="normal")

        label_x = icon_cx + _ICON_D / 2 + _GAP_SM
        self.canvas.coords(self._label_item, label_x, icon_cy)
        label_w = self._label_font.measure("Jarvis")

        sep_x = label_x + label_w + _GAP_SM
        self.canvas.coords(self._sep_item, sep_x, icon_cy)
        sep_w = self._status_font.measure("·")

        status_x = sep_x + sep_w + _GAP_SM
        self.canvas.coords(self._status_item, status_x, icon_cy)
        self.canvas.itemconfig(self._status_item, text=status_text, fill=status_color)
        status_w = self._status_font.measure(status_text)

        # -- waveform --
        bars_x = status_x + status_w + _GAP_MD
        if show_bars:
            for i, bar in enumerate(self._bars):
                amp = math.sin(self._bar_phase * 1.6 + i * 1.3) * 0.5 + 0.5
                bar_h = 3 + amp * (_BAR_MAX_H - 3)
                bx = bars_x + i * (_BAR_WIDTH + _BAR_GAP)
                self.canvas.coords(bar, bx, icon_cy - bar_h / 2, bx, icon_cy + bar_h / 2)
                color = _lerp_color(edge_a, edge_b, i / max(1, _BAR_COUNT - 1))
                self.canvas.itemconfig(bar, fill=color, state="normal")
        else:
            for bar in self._bars:
                self.canvas.itemconfig(bar, state="hidden")

        # -- close button --
        close_cx = x2 - _PAD_X - _CLOSE_D / 2
        close_cy = icon_cy
        cr = _CLOSE_D / 2
        self.canvas.coords(
            self._close_bg, close_cx - cr, close_cy - cr, close_cx + cr, close_cy + cr
        )
        d = cr * 0.45
        self.canvas.coords(
            self._close_x1, close_cx - d, close_cy - d, close_cx + d, close_cy + d
        )
        self.canvas.coords(
            self._close_x2, close_cx - d, close_cy + d, close_cx + d, close_cy - d
        )
        for item in (self._close_bg, self._close_x1, self._close_x2):
            self.canvas.itemconfig(item, state="normal")

        self.root.after(_ANIMATION_INTERVAL_MS, self._animate)

    # -- internal queue handling (runs on the Tk main thread) ------------
    def _show_caption(self, text: str):
        self._caption_text = text
        if self._caption_after_id:
            self.root.after_cancel(self._caption_after_id)
            self._caption_after_id = None

        if text.startswith("Jarvis:"):
            # Stays up for as long as the reply is being spoken; hidden when
            # the status leaves "speaking" (see _drain_queue).
            self._caption_persistent = True
        else:
            self._caption_persistent = False
            self._caption_after_id = self.root.after(
                _CAPTION_TIMEOUT_MS, self._clear_caption
            )

    def _clear_caption(self):
        self._caption_after_id = None
        self._caption_persistent = False
        self._caption_text = ""

    def _ensure_log_window(self):
        if self._log_window is not None:
            return
        self._log_window = tk.Toplevel(self.root)
        self._log_window.title("Jarvis - Transcript")
        self._log_window.geometry("420x320")
        self._log_window.protocol("WM_DELETE_WINDOW", self._log_window.withdraw)
        self._log_text = ScrolledText(self._log_window, state="disabled", wrap="word")
        self._log_text.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_log_text()

    def _ensure_remote_info_window(self, info):
        if self._remote_window is not None:
            self._remote_window.destroy()

        self._remote_window = tk.Toplevel(self.root)
        self._remote_window.title("Jarvis - Remote Access")
        self._remote_window.resizable(False, False)
        pad = {"padx": 12, "pady": 6}

        if info.get("warning"):
            tk.Label(
                self._remote_window, text=info["warning"], fg="#a00", wraplength=320,
                justify="left",
            ).pack(**pad)

        tk.Label(
            self._remote_window,
            text=f"Scan this QR code on your phone, or open:",
            justify="left",
        ).pack(**pad)

        self._remote_qr_photo = ImageTk.PhotoImage(info["qr_image"].get_image())
        tk.Label(self._remote_window, image=self._remote_qr_photo).pack(padx=12, pady=6)

        url_entry = tk.Entry(self._remote_window, width=48)
        url_entry.insert(0, info["url"])
        url_entry.config(state="readonly")
        url_entry.pack(**pad)

        def copy_url():
            self.root.clipboard_clear()
            self.root.clipboard_append(info["url"])

        tk.Button(self._remote_window, text="Copy Link", command=copy_url).pack(pady=(0, 12))

        self._remote_window.protocol("WM_DELETE_WINDOW", self._remote_window.destroy)

    def _refresh_log_text(self):
        if self._log_text is None:
            return
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.insert("end", "\n".join(self._log_lines))
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "status":
                    previous_status = self._status
                    self._status = payload
                    if (
                        previous_status == "speaking"
                        and payload != "speaking"
                        and self._caption_persistent
                    ):
                        self._clear_caption()
                elif kind == "log":
                    self._log_lines.append(payload)
                    self._show_caption(payload)
                    if self._log_window is not None:
                        self._log_text.config(state="normal")
                        self._log_text.insert("end", payload + "\n")
                        self._log_text.see("end")
                        self._log_text.config(state="disabled")
                elif kind == "show_log":
                    self._ensure_log_window()
                    self._log_window.deiconify()
                    self._log_window.lift()
                elif kind == "show_remote_info":
                    self._ensure_remote_info_window(payload)
                    self._remote_window.deiconify()
                    self._remote_window.lift()
                elif kind == "destroy":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)
