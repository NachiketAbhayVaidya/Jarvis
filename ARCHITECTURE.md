# Jarvis — Technical Overview

A voice assistant for Windows: wake-word activated, LLM-driven command routing
with a tool/skill system, an animated floating overlay UI, and packaged for
distribution as a standalone `.exe`.

This document describes the system as it exists now, and *why* each piece was
chosen, for anyone reading the codebase cold.

---

## 1. High-level architecture

```
main.py                      Entry point: wiring, main loop, gesture handling
jarvis/
  config.py                  Loads settings from .env (per-user or dev-local)
  control.py                 Shared threading.Event flags (shutdown, cancel)
  userdata.py                Resolves %APPDATA%\Jarvis for per-user files
  audio/
    wakeword.py               "Hey Jarvis" detection (openWakeWord + sounddevice)
    stt.py                     Speech-to-text for the actual command (SpeechRecognition)
    tts.py                     Text-to-speech playback (edge-tts + pygame)
  brain/
    llm.py                     Groq LLM call, tool-calling loop, conversation memory
  skills/
    __init__.py                 @tool decorator + registry (schema + function)
    web.py                      open_website, web_search
    music.py                    play_music (per-user JSON library)
    apps.py                     open_application (Start Menu shortcut index)
    system.py                   get_current_time, list_processes, exit_app
  ui/
    overlay.py                  Floating pulsing "orb" (Tkinter), tap gestures
    tray.py                     System tray icon (pystray)
    setup_wizard.py              First-run API key entry dialog
```

**Why this shape:** the original script was one 130-line file with an
`if/elif` chain matching substrings in the transcribed command. That doesn't
scale past a handful of commands and can't hold a conversation. Splitting into
`audio` (I/O) / `brain` (decides what to do) / `skills` (what it can actually
do) / `ui` (what the user sees) means each piece can change independently —
e.g. swapping the wake-word engine never touches the LLM code.

---

## 2. Request flow

1. `wakeword.wait_for_wakeword()` streams microphone audio through openWakeWord
   until it hears "Hey Jarvis".
2. `stt.listen_for_command()` records and transcribes the next thing said.
3. `brain.llm.process(command)` sends the transcript (plus rolling
   conversation history) to the LLM **with the full skill list as tool
   definitions**. The model decides on its own whether to call a tool
   (`open_application`, `play_music`, etc.) or just answer in plain text.
4. If it calls a tool, `skills.call_tool()` runs the matching Python function,
   the result is fed back to the model, and it produces a final spoken reply
   (looped up to 5 rounds, in case it chains multiple tool calls).
5. `tts.speak()` synthesizes and plays the reply. The floating overlay shows
   the text as a caption for exactly as long as the audio plays.

Two `threading.Event`s in `control.py` cut across this whole flow:
`shutdown_event` (triple-tap the bubble, or the `exit_app` tool, or the tray's
Quit) and `cancel_event` (double-tap the bubble) — checked inside the LLM
call's polling loop and inside the TTS playback loop so either can be
interrupted mid-flight without killing the process.

---

## 3. Why each model/service was picked

| Concern | Choice | Why |
|---|---|---|
| **LLM + tool-calling** | Groq API, model `openai/gpt-oss-20b` | Started on OpenAI's `gpt-4o-mini`, but that requires a paid, billed API key. Groq's free tier needs no credit card, is fast (purpose-built inference hardware), and exposes an **OpenAI-compatible** `/chat/completions` endpoint — so the existing `openai` Python client works unmodified, just pointed at a different `base_url`. `openai/gpt-oss-20b` is one of Groq's hosted open-weight models with solid tool-calling support and good free-tier throughput; picked over the 120B variant for speed, since replies are spoken aloud and latency matters more than maximum reasoning depth for short commands. |
| **Wake word** | openWakeWord, bundled `hey_jarvis` pretrained model | The original approach polled Google's speech API every few seconds and string-matched the word "jarvis" — slow, rate-limit-prone, and needs network for something that should be instant and local. openWakeWord runs a small model **fully offline**, continuously, with no account/API key, and ships a ready-made "hey jarvis" model, so no custom training was needed. |
| **Command transcription** | Google Web Speech API via `SpeechRecognition` | Kept from the original project — free, no API key, good accuracy for short commands. Only used *after* the wake word fires (not continuously), so its slowness/network dependency doesn't matter as much as it would for wake-word detection. |
| **Text-to-speech** | `edge-tts` (Microsoft neural voices) + `pygame` for playback | Originally `pyttsx3`, which sounds robotic (SAPI voices). `edge-tts` uses the same neural voices behind Microsoft Edge's "Read aloud" feature — free, no API key, far more natural — at the cost of needing internet per reply. `pygame.mixer` just plays the resulting MP3; chosen over `playsound` because `playsound` has known reliability issues with file paths on Windows. |
| **UI toolkit** | Tkinter | No extra dependency (ships with Python), sufficient for a borderless, always-on-top, per-pixel-transparent overlay window plus a couple of dialogs. Wrapping a heavier UI framework (Qt, etc.) around a two-widget floating bubble would be disproportionate. |
| **Tray icon** | `pystray` + `Pillow` | Standard, lightweight way to get a native system tray icon with a right-click menu on Windows without hand-rolling Win32 API calls. |
| **Process listing** | `psutil` | Cross-platform process/CPU/memory introspection; the standard library has no equivalent. |
| **Packaging** | PyInstaller, `--onedir` | Turns the app into something with no Python install required. `--onedir` (a folder) rather than `--onefile` (single .exe) specifically because onefile re-extracts its entire bundle into a temp directory on *every launch* — with this dependency set (onnxruntime, scipy, sklearn are pulled in transitively by openWakeWord) that's 30-40 seconds of nothing visibly happening, which reads as "broken" to someone who didn't build it themselves. Onedir extracts once, at build time. |

---

## 4. Skills (tools the LLM can call)

Each is a plain Python function registered via a `@tool(name, description,
parameters)` decorator (`jarvis/skills/__init__.py`) that builds the
OpenAI-style function-calling schema automatically. The model sees all of
these on every turn and decides for itself whether/which to call — there is
no keyword matching anywhere in this path.

| Skill | What it does |
|---|---|
| `open_website` | Opens a known site (Google, YouTube, Facebook, LinkedIn, Claude, ChatGPT) or an arbitrary URL in the default browser. |
| `web_search` | Builds a search URL for Google/YouTube/Claude/ChatGPT and opens it. |
| `play_music` | Looks up a song in the user's personal library (`%APPDATA%\Jarvis\musiclibrary.json`), with fuzzy name matching (`difflib`) so exact wording isn't required. |
| `open_application` | Opens any installed desktop app by name (Spotify, Chrome, Steam, etc.) by indexing `.lnk`/`.url` shortcuts from both Start Menu folders and fuzzy-matching against that index — no per-app hardcoding needed. |
| `get_current_time` | Returns the local time. |
| `list_processes` | Task-Manager-style: total process count plus the top N by CPU, memory, or name (via `psutil`), with the CPU measurement "primed" first since `psutil` needs two samples to report a real percentage. |
| `exit_app` | Sets `shutdown_event`, ending the program (also reachable via a triple-tap gesture or the tray menu). |

Adding a new ability means writing one function and decorating it — nothing
else in the routing logic needs to change.

---

## 5. Conversation memory & tool-calling loop

`brain/llm.py` keeps a rolling `deque(maxlen=20)` of the last N messages
(user/assistant/tool roles — the system prompt is prepended fresh each call,
not stored in the deque). Each call passes the full tool schema list with
`tool_choice="auto"`; if the model responds with tool calls, they're executed
and their results appended as `role: "tool"` messages, then the loop calls
the model again — up to 5 rounds — until it returns a plain-text answer. This
loop (rather than a single "call once, then call again for the final answer"
shape) was needed because Groq's hosted `gpt-oss` model will still attempt a
tool call on the follow-up turn if the `tools` parameter isn't included again,
so the tools list is always resent and the loop just keeps going until the
model stops asking for tools.

---

## 6. UI: the floating overlay

`jarvis/ui/overlay.py` is a borderless, always-on-top Tkinter window using
`-transparentcolor` (per-pixel transparency — only the drawn circle is
opaque, corners are see-through to the desktop) combined with `-alpha`
(whole-window translucency), so it renders as a soft glassy floating orb
rather than a flat colored square. Two concentric ovals (a glow + a core)
are redrawn every 40ms with a sine-wave-driven radius to give it a gentle
"breathing" pulse, colored per status (grey-blue idle, green listening,
blue-purple speaking).

**Gestures**, implemented as a tap-counter with a short window (400ms) to
distinguish single/double/triple clicks rather than relying on the OS's
native double-click event:
- **Double-tap** → sets `cancel_event`, interrupting whatever's in flight
  (an in-progress LLM call is abandoned via a daemon thread so the UI doesn't
  block waiting for the network; in-progress speech is stopped immediately
  via `pygame.mixer.music.stop()`) — Jarvis goes back to listening for the
  wake word, the process keeps running.
- **Triple-tap** → full shutdown.

The caption bubble above the orb shows the latest line of conversation.
Replies (prefixed `"Jarvis:"`) stay visible for exactly as long as speech is
playing (tied to the `speaking` → non-`speaking` status transition) rather
than a fixed timer, so it never cuts off mid-sentence or lingers after
Jarvis has gone quiet; other log lines (like the transcribed command) use a
short fixed auto-fade instead, since there's no "speech duration" to tie them
to.

---

## 7. Security & configuration

- The original code had a **live OpenAI API key hardcoded in plaintext** in
  `main.py`. This was removed; the key now comes from environment
  configuration only, never from source.
- `.env` (with the real key) is git-ignored; `.env.example` is the checked-in
  template.
- `jarvis/config.py` looks for a project-local `.env` first (developer
  workflow — running from source), and falls back to
  `%APPDATA%\Jarvis\.env` (used by the packaged `.exe`, and where the
  first-run setup wizard writes to). This means the dev environment and an
  installed copy on someone else's machine never collide.
- The music library and other per-user state also live under
  `%APPDATA%\Jarvis\`, not in the installed program's own folder — needed
  because a real install location (e.g. `Program Files`) is often read-only,
  and because it keeps "the program" and "this person's data" separate.

---

## 8. Distribution

Packaged with **PyInstaller** (`Jarvis.spec`, documented in `BUILD.md`) into
`dist\Jarvis\` — a folder containing `Jarvis.exe` and its `_internal`
dependencies (~280MB, mostly `onnxruntime` + `scipy`/`scikit-learn`, both
pulled in transitively by openWakeWord). `--collect-all` is used for several
packages (`openwakeword`, `sounddevice`, `edge_tts`, `pystray`,
`onnxruntime`, `pyaudio`) whose data files or dynamically-loaded submodules
PyInstaller's default hooks don't always catch — trading bundle size for a
build that works on the first try on someone else's machine.

A first-run **setup wizard** (`jarvis/ui/setup_wizard.py`) replaces manual
`.env` editing for end users: if no Groq key is found, a small Tkinter dialog
asks for one (with a button linking to the free signup page), saves it to
`%APPDATA%\Jarvis\.env`, and the app proceeds normally — no text editor, no
terminal, needed only once per machine.

The whole `dist\Jarvis\` folder must be distributed together (zipped) — the
`.exe` alone is not runnable, since it depends on the sibling `_internal`
folder for its Python runtime and libraries.

---

## 9. Full dependency list

| Package | Role |
|---|---|
| `openai` | HTTP client for the LLM (pointed at Groq's OpenAI-compatible endpoint) |
| `python-dotenv` | Loads `.env` files into environment variables |
| `SpeechRecognition` | Wraps Google's free speech-to-text API for command transcription |
| `PyAudio` | Microphone capture backend used by `SpeechRecognition` |
| `openwakeword` | Offline wake-word detection |
| `sounddevice` | Microphone audio streaming for the wake-word detector |
| `numpy` | Array plumbing required by openWakeWord/onnxruntime |
| `edge-tts` | Neural text-to-speech synthesis |
| `pygame` | Audio playback for synthesized speech |
| `pystray` | System tray icon |
| `Pillow` | Generates the tray icon image |
| `psutil` | Process/CPU/memory introspection for `list_processes` |
| `pyinstaller` *(build-time only)* | Packages the app into a standalone `.exe` |
