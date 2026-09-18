import difflib
import json
import webbrowser

from ..userdata import get_data_dir
from . import tool

_LIBRARY_PATH = get_data_dir() / "musiclibrary.json"


def _load_library() -> dict:
    if not _LIBRARY_PATH.exists():
        _LIBRARY_PATH.write_text("{}", encoding="utf-8")
        return {}
    try:
        return json.loads(_LIBRARY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


@tool(
    name="play_music",
    description="Play a song from the user's local music library on YouTube.",
    parameters={
        "type": "object",
        "properties": {
            "song": {
                "type": "string",
                "description": "The name of the song to play.",
            }
        },
        "required": ["song"],
    },
)
def play_music(song: str) -> str:
    library = _load_library()
    if not library:
        return "Your music library is empty. Add songs to musiclibrary.json in the Jarvis app data folder."

    if song in library:
        webbrowser.open(library[song])
        return f"Playing {song}."

    matches = difflib.get_close_matches(song, library.keys(), n=1, cutoff=0.5)
    if matches:
        match = matches[0]
        webbrowser.open(library[match])
        return f"Playing {match}."

    return f"I couldn't find {song} in your library."
