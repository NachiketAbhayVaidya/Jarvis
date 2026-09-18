import json
from collections import deque

from openai import OpenAI

from .. import config
from ..skills import call_tool, get_tool_schemas

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
        "it brief since it's spoken aloud. Otherwise, just answer directly."
    ),
}

# Rolling conversation memory (user/assistant/tool messages only; system prompt is
# always prepended separately).
_history = deque(maxlen=20)


_MAX_TOOL_ROUNDS = 5


def process(command: str) -> str:
    _history.append({"role": "user", "content": command})

    client = _get_client()
    for _ in range(_MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[_SYSTEM_PROMPT, *_history],
            tools=get_tool_schemas(),
            tool_choice="auto",
        )
        message = response.choices[0].message

        if not message.tool_calls:
            _history.append({"role": "assistant", "content": message.content})
            return message.content

        _history.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            result = call_tool(tool_call.function.name, args)
            _history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

    return "Sorry, I got stuck trying to handle that."
