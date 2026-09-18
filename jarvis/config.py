import os

from dotenv import load_dotenv

from .userdata import get_data_dir

_PROJECT_ENV = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
_USER_ENV = get_data_dir() / ".env"

# Prefer a project-local .env for development; otherwise use the per-user one
# (this is where the first-run setup wizard writes for installed/frozen apps).
if os.path.exists(_PROJECT_ENV):
    load_dotenv(_PROJECT_ENV)
else:
    load_dotenv(_USER_ENV)


def _reload():
    global GROQ_API_KEY, GROQ_MODEL
    load_dotenv(_USER_ENV, override=True)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

TTS_VOICE = os.getenv("TTS_VOICE", "en-GB-RyanNeural")


def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def save_user_key(api_key: str, model: str = "openai/gpt-oss-20b"):
    """Writes the Groq key to the per-user .env (used by the setup wizard),
    then reloads this module's config from it."""
    lines = [
        f"GROQ_API_KEY={api_key}\n",
        f"GROQ_MODEL={model}\n",
    ]
    _USER_ENV.write_text("".join(lines), encoding="utf-8")
    _reload()
