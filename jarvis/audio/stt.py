import os
import tempfile

import requests
import speech_recognition as sr

from .. import config

_recognizer = sr.Recognizer()
_recognizer.energy_threshold = 300
_recognizer.pause_threshold = 1.5
_recognizer.dynamic_energy_threshold = True


def listen_for_command_with_audio(timeout=5):
    """Capture a command and return ``(transcript, temporary_wav_path)``.

    The caller owns the temporary file and must delete it. Keeping this one
    capture lets Prisma transcribe and Inya Shield verify the exact same voice
    sample; there is no second, confusing authentication prompt.
    """
    with sr.Microphone() as source:
        try:
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = _recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            return None, None

    fd, audio_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as wav:
            wav.write(audio.get_wav_data(convert_rate=16_000, convert_width=2))
        transcript = _transcribe_gnani(audio_path) if config.GNANI_API_KEY else _transcribe_google(audio)
        return transcript, audio_path
    except Exception:
        try:
            os.remove(audio_path)
        except FileNotFoundError:
            pass
        return None, None


def listen_for_command(timeout=5):
    """Compatibility wrapper for callers that do not need biometric audio."""
    transcript, audio_path = listen_for_command_with_audio(timeout)
    if audio_path:
        os.remove(audio_path)
    return transcript


def _transcribe_gnani(audio_path: str):
    with open(audio_path, "rb") as audio_file:
        response = requests.post(
            config.GNANI_STT_URL,
            headers={"X-API-Key-ID": config.GNANI_API_KEY},
            data={
                "language_code": config.GNANI_LANGUAGE_CODE,
                "preferred_language": config.GNANI_PREFERRED_LANGUAGE,
                "format": "transcribe",
                "itn_native_numerals": "false",
            },
            files={"audio_file": ("command.wav", audio_file, "audio/wav")},
            timeout=20,
        )
    response.raise_for_status()
    return response.json().get("transcript") or None


def _transcribe_google(audio):
    """Development fallback; production challenge runs use Prisma above."""
    try:
        return _recognizer.recognize_google(audio)
    except (sr.UnknownValueError, sr.RequestError):
        return None
