import shutil
import subprocess

_FALLBACK_PATH = r"C:\Program Files\Tailscale\tailscale.exe"


def _tailscale_exe():
    return shutil.which("tailscale") or _FALLBACK_PATH


def get_tailscale_ip() -> str | None:
    """Returns this machine's Tailscale IPv4 address, or None if Tailscale
    isn't installed, isn't running, or isn't logged in."""
    try:
        result = subprocess.run(
            [_tailscale_exe(), "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    first_line = result.stdout.strip().splitlines()
    return first_line[0].strip() if first_line else None
