from PIL import Image, ImageDraw
import pystray

_COLORS = {
    "idle": "#606060",
    "listening": "#2ecc71",
    "speaking": "#3498db",
}


def _make_icon(color: str) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=color)
    return image


class TrayIcon:
    def __init__(self, on_show_log, on_show_remote, on_quit):
        self._on_quit = on_quit
        self.icon = pystray.Icon(
            "jarvis",
            _make_icon(_COLORS["idle"]),
            "Jarvis: idle",
            menu=pystray.Menu(
                pystray.MenuItem("Show Log", lambda: on_show_log()),
                pystray.MenuItem("Remote Access...", lambda: on_show_remote()),
                pystray.MenuItem("Quit", lambda: self._on_quit()),
            ),
        )

    def set_status(self, status: str):
        color = _COLORS.get(status, _COLORS["idle"])
        self.icon.icon = _make_icon(color)
        self.icon.title = f"Jarvis: {status}"

    def run_detached(self):
        self.icon.run_detached()

    def stop(self):
        self.icon.stop()
