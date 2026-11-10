import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil

from ..userdata import get_data_dir
from . import confirm, tool

_HOME = os.path.realpath(os.path.expanduser("~"))
_MAX_READ_BYTES = 2_000_000
_MAX_WRITE_CHARS = 500_000
_SKIP_DIRS = {"node_modules", ".git", "venv", ".venv", "__pycache__", "$recycle.bin"}
_BLOCKED_NAMES = {".ssh", ".aws", ".gnupg", ".azure", "$recycle.bin", "system volume information"}
_PROTECTED_PROCESSES = {
    "system", "smss", "csrss", "wininit", "winlogon", "services", "lsass",
    "svchost", "dwm", "explorer", "fontdrvhost", "registry", "memcompression",
}


def _norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(p))


def _blocked_roots() -> list:
    roots = []
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        if os.environ.get(var):
            roots.append(_norm(os.environ[var]))
    if os.environ.get("APPDATA"):
        roots.append(_norm(os.path.dirname(os.environ["APPDATA"])))  # whole AppData
    roots.append(_norm(str(get_data_dir())))
    return roots


_ROOTS = _blocked_roots()


def _is_blocked(path: str) -> bool:
    np = _norm(path)
    for root in _ROOTS:
        if np == root or np.startswith(root + os.sep):
            return True
    if set(np.split(os.sep)) & _BLOCKED_NAMES:
        return True
    return os.path.basename(np).startswith(".env")


def _resolve(path: str) -> str:
    path = os.path.expandvars(os.path.expanduser((path or "").strip().strip('"')))
    if not os.path.isabs(path):
        path = os.path.join(_HOME, path)
    return os.path.abspath(path)


def _check(path: str):
    """Returns (resolved_path, error). error is None when the path is allowed."""
    resolved = _resolve(path)
    if _is_blocked(resolved):
        return resolved, "That location is protected (system folders, app data, keys and .env files)."
    return resolved, None


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _backup(path: str) -> str:
    backup_dir = get_data_dir() / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{stamp}_{os.path.basename(path)}"
    shutil.copy2(path, dest)
    return str(dest)


def _read_text(path: str):
    if os.path.getsize(path) > _MAX_READ_BYTES:
        return None, "That file is too large to read."
    try:
        return Path(path).read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "That doesn't look like a text file."


@tool(
    name="list_drives",
    description="List the drives on this PC (C:, D:, ...) with free space.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def list_drives() -> str:
    rows = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            rows.append(f"{part.mountpoint} ({_size(usage.free)} free of {_size(usage.total)})")
        except OSError:
            continue
    return "Drives: " + "; ".join(rows)


@tool(
    name="list_directory",
    description=(
        "List the files and folders inside a directory on this PC. Paths can be "
        "absolute (D:\\MyProjects) or relative to the user's home folder (Documents, Desktop)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Folder to list."},
            "limit": {"type": "integer", "description": "Max entries to show. Defaults to 40."},
        },
        "required": ["path"],
    },
)
def list_directory(path: str, limit: int = 40) -> str:
    resolved, error = _check(path)
    if error:
        return error
    if not os.path.isdir(resolved):
        return f"{resolved} is not a folder."
    limit = max(1, min(limit, 100))
    try:
        names = sorted(os.listdir(resolved), key=str.lower)
    except OSError as exc:
        return f"Couldn't open that folder: {exc}"

    rows = []
    for name in names:
        full = os.path.join(resolved, name)
        if _is_blocked(full):
            continue
        try:
            rows.append(f"[folder] {name}" if os.path.isdir(full) else f"{name} ({_size(os.path.getsize(full))})")
        except OSError:
            rows.append(name)
    shown = rows[:limit]
    more = f" (+{len(rows) - limit} more)" if len(rows) > limit else ""
    return f"{resolved} has {len(rows)} items: " + "; ".join(shown) + more if rows else f"{resolved} is empty."


@tool(
    name="search_files",
    description=(
        "Find files or folders by name (partial, case-insensitive). Searches the "
        "user's home folder by default; pass a folder or a drive like D:\\ to search elsewhere."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Part of the file or folder name."},
            "folder": {"type": "string", "description": "Where to search. Defaults to the home folder."},
            "limit": {"type": "integer", "description": "Max results. Defaults to 15."},
        },
        "required": ["query"],
    },
)
def search_files(query: str, folder: str = "", limit: int = 15) -> str:
    root, error = _check(folder or _HOME)
    if error:
        return error
    if not os.path.isdir(root):
        return f"{root} is not a folder."
    needle = query.lower().strip()
    limit = max(1, min(limit, 40))
    found, deadline = [], time.monotonic() + 10

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS and not _is_blocked(os.path.join(dirpath, d))]
        for name in dirnames + filenames:
            if needle in name.lower():
                found.append(os.path.join(dirpath, name))
                if len(found) >= limit:
                    break
        if len(found) >= limit or time.monotonic() > deadline:
            break

    if not found:
        return f"No matches for '{query}' in {root}."
    timed_out = " (search stopped early, results may be incomplete)" if time.monotonic() > deadline else ""
    return f"Found {len(found)}: " + "; ".join(found) + timed_out


@tool(
    name="read_file",
    description="Read the text contents of a file (code, notes, config, etc.).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to read."},
            "max_chars": {"type": "integer", "description": "Max characters to return. Defaults to 4000."},
        },
        "required": ["path"],
    },
)
def read_file(path: str, max_chars: int = 4000) -> str:
    resolved, error = _check(path)
    if error:
        return error
    if not os.path.isfile(resolved):
        return f"{resolved} isn't a file."
    text, error = _read_text(resolved)
    if error:
        return error
    max_chars = max(100, min(max_chars, 20000))
    if len(text) > max_chars:
        return text[:max_chars] + f"\n...[truncated, {len(text)} characters total]"
    return text or "(the file is empty)"


@tool(
    name="open_path",
    description="Open a file or folder with its default program (a folder opens in File Explorer).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File or folder to open."}},
        "required": ["path"],
    },
)
def open_path(path: str) -> str:
    resolved, error = _check(path)
    if error:
        return error
    if not os.path.exists(resolved):
        return f"{resolved} doesn't exist."
    os.startfile(resolved)
    return f"Opened {resolved}."


@tool(
    name="create_folder",
    description="Create a new folder (and any missing parent folders).",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Folder to create."}},
        "required": ["path"],
    },
)
def create_folder(path: str) -> str:
    resolved, error = _check(path)
    if error:
        return error
    os.makedirs(resolved, exist_ok=True)
    return f"Folder ready: {resolved}"


@tool(
    name="write_file",
    description=(
        "Create a text file, or completely overwrite an existing one, with the given "
        "content. Asks the user to confirm first; existing files are backed up. For "
        "small changes to an existing file use edit_file instead."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to write."},
            "content": {"type": "string", "description": "The full new contents."},
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    resolved, error = _check(path)
    if error:
        return error
    if len(content) > _MAX_WRITE_CHARS:
        return "That's too much text to write in one go."
    if os.path.isdir(resolved):
        return f"{resolved} is a folder."

    exists = os.path.isfile(resolved)

    def action():
        note = ""
        if exists:
            note = f" Backup: {_backup(resolved)}"
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        Path(resolved).write_text(content, encoding="utf-8")
        return f"Saved {resolved}.{note}"

    verb = "overwrite" if exists else "create"
    return confirm.request(f"{verb} {resolved} ({len(content)} characters)", action)


@tool(
    name="edit_file",
    description=(
        "Change part of an existing text file by replacing some exact text with new "
        "text. Read the file first so 'find' matches exactly. Asks the user to "
        "confirm first; the original is backed up."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to edit."},
            "find": {"type": "string", "description": "Exact existing text to replace."},
            "replace": {"type": "string", "description": "Text to put in its place."},
            "replace_all": {"type": "boolean", "description": "Replace every occurrence. Defaults to false."},
        },
        "required": ["path", "find", "replace"],
    },
)
def edit_file(path: str, find: str, replace: str, replace_all: bool = False) -> str:
    resolved, error = _check(path)
    if error:
        return error
    if not os.path.isfile(resolved):
        return f"{resolved} isn't a file."
    if not find:
        return "Nothing to find."
    text, error = _read_text(resolved)
    if error:
        return error
    count = text.count(find)
    if count == 0:
        return "That text wasn't found in the file. Read the file again and use the exact text."
    if count > 1 and not replace_all:
        return f"That text appears {count} times. Use a longer, unique snippet, or set replace_all."

    def action():
        current, err = _read_text(resolved)
        if err:
            return err
        if find not in current:
            return "The file changed in the meantime; nothing was edited."
        backup = _backup(resolved)
        Path(resolved).write_text(
            current.replace(find, replace) if replace_all else current.replace(find, replace, 1),
            encoding="utf-8",
        )
        return f"Edited {resolved}. Backup: {backup}"

    preview = f"replace '{find[:40]}' with '{replace[:40]}'"
    times = f" ({count} places)" if replace_all and count > 1 else ""
    return confirm.request(f"edit {resolved}: {preview}{times}", action)


@tool(
    name="close_application",
    description=(
        "Close a running application by name (e.g. Notepad, Spotify, Chrome). Asks "
        "the user to confirm first. Closes politely by default so the app can offer "
        "to save; use force only if the user asks to force close."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "App or process name."},
            "force": {"type": "boolean", "description": "Kill it immediately (unsaved work is lost)."},
        },
        "required": ["name"],
    },
)
def close_application(name: str, force: bool = False) -> str:
    needle = name.lower().replace(".exe", "").strip()
    if not needle:
        return "Which application?"

    own = {os.getpid()}
    try:
        own.update(p.pid for p in psutil.Process().parents())
    except psutil.Error:
        pass

    exes = {}
    for proc in psutil.process_iter(["pid", "name"]):
        exe = proc.info["name"] or ""
        stem = exe.lower().removesuffix(".exe")
        if proc.info["pid"] in own or stem in _PROTECTED_PROCESSES or stem == "jarvis":
            continue
        if needle == stem or needle in stem:
            exes.setdefault(exe, 0)
            exes[exe] += 1

    if not exes:
        return f"I couldn't find a running app matching '{name}'."

    def action():
        results = []
        for exe in exes:
            cmd = ["taskkill", "/IM", exe] + (["/F"] if force else [])
            out = subprocess.run(
                cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            results.append(f"{exe}: {'closed' if out.returncode == 0 else 'could not close (' + out.stderr.strip()[:80] + ')'}")
        return "; ".join(results)

    how = "force close (unsaved work will be lost)" if force else "close"
    return confirm.request(f"{how} {', '.join(exes)}", action)
