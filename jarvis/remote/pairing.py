import socket

import qrcode

from .. import config
from .tailscale import get_tailscale_ip


def build_pairing_info() -> dict:
    """Assembles everything the tray/overlay pairing window needs to show.
    Only ever called locally by the tray UI - never exposed over the API,
    since being at the laptop to view it is the trust bootstrap for pairing."""
    ip = get_tailscale_ip()
    warning = None
    if ip is None:
        ip = socket.gethostbyname(socket.gethostname())
        warning = (
            "Tailscale not detected - showing your local network address "
            "instead. Install and sign in to Tailscale on both this PC and "
            "your phone for secure access from anywhere."
        )

    port = config.REMOTE_PORT
    token = config.get_or_create_remote_token()
    url = f"http://{ip}:{port}/?token={token}"

    return {
        "ip": ip,
        "port": port,
        "token": token,
        "url": url,
        "warning": warning,
        "qr_image": qrcode.make(url),
    }
