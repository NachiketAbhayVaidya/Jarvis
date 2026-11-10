import json
import threading
from collections import deque

from openai import OpenAI

from .. import config
from ..skills import call_tool, confirm, get_tool_schemas

_client = None


def _get_client():
    # Built lazily: config.GROQ_API_KEY may not be set yet at import time if
    # the first-run setup wizard hasn't written it out.
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
    return _client


_SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Jarvis, a smart voice assistant. Be concise, since your replies are "
        "spoken aloud. Use the available tools when the user asks you to open sites, "
        "search the web, play music, check the time, open a desktop application "
        "installed on the PC, check what's running (processes/Task Manager style "
        "questions), or exit. Prefer open_application for local desktop apps (e.g. "
        "Spotify, Claude, Steam, Notepad) and open_website/web_search only for things "
        "meant to happen in a browser. When summarizing list_processes results, keep "
        "it brief since it's spoken aloud. You can also explore the PC: list_drives, "
        "list_directory, search_files, read_file, open_path (open a file or folder), "
        "create_folder, write_file and edit_file (to change files), and "
        "close_application. To edit a file, read_file it first, then edit_file with "
        "exact text. To create a file, call write_file directly; it creates missing "
        "parent folders, so don't call create_folder first. Ask for only one "
        "confirmation per action. write_file, edit_file and close_application don't act "
        "immediately: they return CONFIRMATION NEEDED. Then briefly tell the user what "
        "will happen, ask one yes-or-no question, and STOP. Only call confirm_action "
        "after the user says yes in their next message; call cancel_action if they say "
        "no. Never claim a change was made until confirmation reports it. Keep file "
        "listings and search results short when spoken. Otherwise, just answer directly."
    ),
}

# Rolling conversation memory, kept per session so the local voice loop and
# remote (phone) commands don't interleave into the same conversation. All
# remote commands share one "remote" session regardless of which paired
# device sent them, since this is a single-user personal app.
_sessions = {}
_sessions_lock = threading.Lock()


def _get_session(session_id: str):
    with _sessions_lock:
        if session_id not in _sessions:
            _sessions[session_id] = {
                "history": deque(maxlen=20),
                "lock": threading.Lock(),
            }
        return _sessions[session_id]


_MAX_TOOL_ROUNDS = 5


def process(command: str, session_id: str = "local") -> str:
    session = _get_session(session_id)
    with session["lock"]:
        confirm.begin_turn(session_id)
        history = session["history"]
        history.append({"role": "user", "content": command})

        if confirm.has_pending(session_id):
            reply = confirm.resolve_response(command, session_id)
            history.append({"role": "assistant", "content": reply})
            return reply

        client = _get_client()
        for _ in range(_MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[_SYSTEM_PROMPT, *history],
                tools=get_tool_schemas(),
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                history.append({"role": "assistant", "content": message.content})
                return message.content

            history.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [tc.model_dump() for tc in message.tool_calls],
                }
            )

            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments or "{}")
                result = call_tool(tool_call.function.name, args)
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    }
                )

        return "Sorry, I got stuck trying to handle that."
