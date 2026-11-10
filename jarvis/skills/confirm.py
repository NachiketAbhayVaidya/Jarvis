"""Two-step confirmation for risky skills.

A risky tool doesn't act; it registers a pending action via request(). The
action only runs when confirm_action is called in a *later* user turn, so the
model can't approve its own action within the same request.
"""

import contextvars
import threading

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
        _pending[sid] = {"turn": _turns.get(sid, 0), "desc": description, "action": action}
    return (
        f"CONFIRMATION NEEDED to {description}. Nothing has been done yet. Tell the "
        "user exactly what will happen and ask them to say yes or no. Only call "
        "confirm_action after they answer yes in their next message."
    )


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
