import difflib
import os
from pathlib import Path

from . import tool

_START_MENU_DIRS = [
    Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
    Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
]

_index = None


def _build_index():
    index = {}
    for base in _START_MENU_DIRS:
        if not base.exists():
            continue
        for path in list(base.rglob("*.lnk")) + list(base.rglob("*.url")):
            index[path.stem.lower()] = path
    return index


def _get_index():
    global _index
    if _index is None:
        _index = _build_index()
    return _index


@tool(
    name="open_application",
    description=(
        "Open a desktop application installed on this PC by name, e.g. Spotify, "
        "Notepad, Claude, Chrome, Steam. Matches against Start Menu shortcuts."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the application to open.",
            }
        },
        "required": ["name"],
    },
)
def open_application(name: str) -> str:
    index = _get_index()
    key = name.strip().lower()

    path = index.get(key)
    if path is None:
        matches = difflib.get_close_matches(key, index.keys(), n=1, cutoff=0.4)
        if matches:
            path = index[matches[0]]
            name = matches[0]

    if path is None:
        return f"I couldn't find an application called {name} installed on this PC."

    os.startfile(path)
    return f"Opening {name}."
