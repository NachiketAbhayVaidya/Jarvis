import os
import secrets

from dotenv import get_key, load_dotenv, set_key

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
    global GROQ_API_KEY, GROQ_MODEL, REMOTE_TOKEN, REMOTE_PORT
    load_dotenv(_USER_ENV, override=True)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    REMOTE_TOKEN = os.getenv("REMOTE_TOKEN")
    REMOTE_PORT = int(os.getenv("REMOTE_PORT", "8765"))


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))

TTS_VOICE = os.getenv("TTS_VOICE", "en-GB-RyanNeural")

GNANI_API_KEY = os.getenv("GNANI_API_KEY")
GNANI_LANGUAGE_CODE = os.getenv("GNANI_LANGUAGE_CODE", "hi-IN")
GNANI_PREFERRED_LANGUAGE = os.getenv("GNANI_PREFERRED_LANGUAGE", GNANI_LANGUAGE_CODE)
GNANI_STT_URL = os.getenv("GNANI_STT_URL", "https://api.vachana.ai/stt/v3")
GNANI_TTS_URL = os.getenv("GNANI_TTS_URL", "https://api.vachana.ai/api/v1/tts/sse")
GNANI_TTS_VOICE = os.getenv("GNANI_TTS_VOICE", "Pranav")

GNANI_BIOMETRICS_ENABLED = os.getenv("GNANI_BIOMETRICS_ENABLED", "false").lower() == "true"
GNANI_BIOMETRIC_TOKEN = os.getenv("GNANI_BIOMETRIC_TOKEN")
GNANI_BIOMETRIC_ACCESS_KEY = os.getenv("GNANI_BIOMETRIC_ACCESS_KEY")
GNANI_BIOMETRIC_USER_ID = os.getenv("GNANI_BIOMETRIC_USER_ID")
GNANI_BIOMETRIC_SPEAKER = os.getenv("GNANI_BIOMETRIC_SPEAKER", "jarvis-owner")
GNANI_BIOMETRIC_ENROLL_URL = os.getenv("GNANI_BIOMETRIC_ENROLL_URL", "https://armour365.gnani.ai/api/enrollment")
GNANI_BIOMETRIC_VERIFY_URL = os.getenv("GNANI_BIOMETRIC_VERIFY_URL", "https://armour365.gnani.ai/api/verification")
GNANI_BIOMETRIC_DELETE_URL = os.getenv("GNANI_BIOMETRIC_DELETE_URL", "https://armour365.gnani.ai/api/delete_enrollment")


def biometrics_configured() -> bool:
    return all((GNANI_BIOMETRIC_TOKEN, GNANI_BIOMETRIC_ACCESS_KEY, GNANI_BIOMETRIC_USER_ID))

REMOTE_TOKEN = os.getenv("REMOTE_TOKEN")
REMOTE_PORT = int(os.getenv("REMOTE_PORT", "8765"))


def is_configured() -> bool:
    return bool(GROQ_API_KEY)


def save_user_key(api_key: str, model: str = "openai/gpt-oss-20b"):
    """Writes the Groq key to the per-user .env (used by the setup wizard),
    then reloads this module's config from it."""
    _USER_ENV.touch(exist_ok=True)
    set_key(str(_USER_ENV), "GROQ_API_KEY", api_key)
    set_key(str(_USER_ENV), "GROQ_MODEL", model)
    _reload()


def get_or_create_remote_token() -> str:
    """Returns the persisted remote-control pairing token, generating and
    saving one on first use (same per-user .env as the Groq key).

    Always checks the per-user .env file directly (not just the in-memory
    REMOTE_TOKEN global), since in dev mode a project-local .env is loaded
    at import time instead - which would otherwise make this look unset on
    every restart and mint a fresh token each time.
    """
    _USER_ENV.touch(exist_ok=True)
    existing = get_key(str(_USER_ENV), "REMOTE_TOKEN")
    if existing:
        global REMOTE_TOKEN
        REMOTE_TOKEN = existing
        return existing

    token = secrets.token_urlsafe(32)
    set_key(str(_USER_ENV), "REMOTE_TOKEN", token)
    _reload()
    return REMOTE_TOKEN
