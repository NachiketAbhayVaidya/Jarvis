import os
from pathlib import Path


def get_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    data_dir = Path(base) / "Jarvis"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
