"""Two-step confirmation for risky skills.

A risky tool doesn't act; it registers a pending action via request(). The
action only runs when confirm_action is called in a *later* user turn, so the
model can't approve its own action within the same request.
"""

import contextvars
import re
import threading
import unicodedata

from . import tool

_session = contextvars.ContextVar("jarvis_session", default="default")
_lock = threading.Lock()
_turns = {}
_pending = {}


def begin_turn(session_id: str):
    """Called once per user message (voice, phone chat, or phone skill tap)."""
    with _lock:
        _turns[session_id] = _turns.get(session_id, 0) + 1
    _session.set(session_id)


def request(description: str, action) -> str:
    sid = _session.get()
    with _lock:
        pending = _pending.get(sid)
        if pending and pending["turn"] == _turns.get(sid, 0):
            return (
                f"CONFIRMATION ALREADY NEEDED to {pending['desc']}. Do not request "
                "another confirmation or action. Ask the user to confirm this action."
            )
        _pending[sid] = {"turn": _turns.get(sid, 0), "desc": description, "action": action}
    return (
        f"CONFIRMATION NEEDED to {description}. Nothing has been done yet. Tell the "
        "user exactly what will happen and ask them one yes-or-no question. Stop "
        "after asking; do not ask for confirmation again."
    )


def has_pending(session_id: str) -> bool:
    with _lock:
        return session_id in _pending


def cancel_pending(session_id: str) -> bool:
    with _lock:
        return _pending.pop(session_id, None) is not None


def resolve_response(response: str, session_id: str) -> str | None:
    """Resolve a clear spoken yes/no; cancel safely if it is unclear."""
    normalized = " ".join(
        "".join(
            character
            if unicodedata.category(character)[0] in {"L", "M", "N"}
            else " "
            for character in response.casefold()
        ).split()
    )
    negative_tokens = {
        "no", "nope", "not", "never", "dont", "don't", "didnt", "didn't",
        "cannot", "cant", "can't", "wouldnt", "wouldn't", "cancel", "stop",
        "nahi", "nahin",
        "नहीं", "नही", "मत", "रद्द",
    }
    tokens = normalized.split()
    is_negative = any(token in negative_tokens for token in tokens) or bool(
        re.search(r"\b(?:didn['’]?t|don['’]?t|can['’]?t|cannot|wouldn['’]?t)\b", response.casefold())
    )
    affirmative_tokens = {
        "yeah", "yep", "yup", "sure", "absolutely", "definitely",
        "okay", "ok", "proceed", "confirm", "haan", "han", "हाँ", "हां", "जी",
    }
    has_yes = any(re.fullmatch(r"ye+s+", token) for token in tokens)
    is_affirmative = (
        (has_yes or any(token in affirmative_tokens for token in tokens)
         or "go ahead" in normalized or "do it" in normalized)
        and not is_negative
    )

    with _lock:
        pending = _pending.pop(session_id, None)
    if pending is None:
        return None
    if is_negative:
        return "Okay, cancelled."
    if not is_affirmative:
        heard = response.strip()
        return (
            f"I heard '{heard}', but couldn't identify a clear yes or no, "
            "so I cancelled it. No change was made."
        )
    return pending["action"]()


@tool(
    name="confirm_action",
    description=(
        "Carry out the action the user was just asked to confirm. Call this ONLY "
        "after the user replied yes to a confirmation question."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def confirm_action() -> str:
    sid = _session.get()
    with _lock:
        pending = _pending.get(sid)
        turn = _turns.get(sid, 0)
        if pending is None:
            return "Nothing is waiting for confirmation."
        if turn <= pending["turn"]:
            return "The user hasn't answered yet. Ask them to confirm and wait for their reply."
        _pending.pop(sid, None)
        if turn > pending["turn"] + 1:
            return "That request expired. Ask the user again if they still want it."
    return pending["action"]()


@tool(
    name="cancel_action",
    description="Discard the pending action when the user says no or changes their mind.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def cancel_action() -> str:
    with _lock:
        _pending.pop(_session.get(), None)
    return "Okay, cancelled."
