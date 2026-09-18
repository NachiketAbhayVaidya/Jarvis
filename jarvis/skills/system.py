import time
from datetime import datetime

import psutil

from .. import control
from . import tool


@tool(
    name="get_current_time",
    description="Get the current local time.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_current_time() -> str:
    return datetime.now().strftime("%I:%M %p")


@tool(
    name="list_processes",
    description=(
        "List what's currently running on this PC, like checking Task Manager. "
        "Returns the total process count plus the top ones by CPU or memory usage."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sort_by": {
                "type": "string",
                "enum": ["cpu", "memory", "name"],
                "description": "What to rank processes by. Defaults to cpu.",
            },
            "limit": {
                "type": "integer",
                "description": "How many top processes to include. Defaults to 8.",
            },
        },
        "required": [],
    },
)
def list_processes(sort_by: str = "cpu", limit: int = 8) -> str:
    if sort_by not in ("cpu", "memory", "name"):
        sort_by = "cpu"
    limit = max(1, min(limit, 25))

    procs = [
        p
        for p in psutil.process_iter(["name"])
        if (p.info["name"] or "").lower() != "system idle process"
    ]
    for p in procs:
        try:
            p.cpu_percent(None)  # first call primes the measurement
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.3)

    rows = []
    for p in procs:
        try:
            rows.append(
                {
                    "name": p.info["name"] or "unknown",
                    "cpu": p.cpu_percent(None),
                    "memory": p.memory_percent(),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "name":
        rows.sort(key=lambda r: r["name"].lower())
    else:
        rows.sort(key=lambda r: r[sort_by], reverse=True)

    top = rows[:limit]
    listing = "; ".join(f"{r['name']} ({r['cpu']:.0f}% CPU, {r['memory']:.0f}% RAM)" for r in top)
    return f"{len(rows)} processes running. Top {len(top)} by {sort_by}: {listing}"


@tool(
    name="exit_app",
    description="Shut down the Jarvis assistant. Use this when the user asks to stop, exit, or quit.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def exit_app() -> str:
    control.shutdown_event.set()
    return "Goodbye!"
