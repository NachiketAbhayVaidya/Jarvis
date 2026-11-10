"""Gnani Inya Shield (armour365) voice-biometric client."""
import os
from dataclasses import dataclass
from typing import Any

import requests

from . import config
from .audio.capture import record_wav


@dataclass(frozen=True)
class BiometricResult:
    verified: bool
    message: str
    score: float | None = None


def _headers() -> dict[str, str]:
    return {
        "product": "voice-biometric",
        "token": config.GNANI_BIOMETRIC_TOKEN or "",
        "accesskey": config.GNANI_BIOMETRIC_ACCESS_KEY or "",
        "userid": config.GNANI_BIOMETRIC_USER_ID or "",
    }


def _post(url: str, audio_path: str | None = None) -> dict[str, Any]:
    files = None
    handle = None
    try:
        if audio_path:
            handle = open(audio_path, "rb")
            files = {"audio_file": handle}
        response = requests.post(
            url, headers=_headers(), data={"speaker": config.GNANI_BIOMETRIC_SPEAKER},
            files=files, timeout=20,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if handle:
            handle.close()


def enroll_from_microphone(duration_seconds: float = 8) -> BiometricResult:
    """Create/update the remote encrypted voiceprint from a consented sample."""
    if not config.biometrics_configured():
        return BiometricResult(False, "Voice biometrics credentials are not configured.")
    path = record_wav(max(7, duration_seconds))  # Gnani enrollment minimum
    try:
        data = _post(config.GNANI_BIOMETRIC_ENROLL_URL, path)
    except (requests.RequestException, ValueError) as exc:
        return BiometricResult(False, f"Enrollment request failed: {exc}")
    finally:
        _delete_audio(path)
    ok = data.get("status_code") == 0 and data.get("decision_code") == 0
    return BiometricResult(ok, data.get("message", "Enrollment failed."), data.get("score"))


def verify_audio(audio_path: str) -> BiometricResult:
    """Verify one temporary command recording against the remote voiceprint."""
    if not config.GNANI_BIOMETRICS_ENABLED:
        return BiometricResult(True, "Voice biometrics disabled.")
    if not config.biometrics_configured():
        return BiometricResult(False, "Voice biometrics is enabled but not configured.")
    try:
        data = _post(config.GNANI_BIOMETRIC_VERIFY_URL, audio_path)
    except (requests.RequestException, ValueError) as exc:
        return BiometricResult(False, f"Verification request failed: {exc}")
    ok = data.get("status_code") == 0 and data.get("decision_code") == 0 and data.get("spoof", 0) == 0
    return BiometricResult(ok, data.get("message", "Voice verification failed."), data.get("score"))


def delete_enrollment() -> BiometricResult:
    if not config.biometrics_configured():
        return BiometricResult(False, "Voice biometrics credentials are not configured.")
    try:
        data = _post(config.GNANI_BIOMETRIC_DELETE_URL)
    except (requests.RequestException, ValueError) as exc:
        return BiometricResult(False, f"Delete request failed: {exc}")
    return BiometricResult(data.get("status_code") == 0, data.get("message", "Delete failed."))


def _delete_audio(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
