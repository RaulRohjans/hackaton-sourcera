from dataclasses import dataclass
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock

import httpx

from .config import Settings
from .models import Briefing

LOG = logging.getLogger(__name__)
FORMAT = "mp3_44100_64"
SPEED = {"calm": 0.9, "professional": 1.0, "conversational": 1.04}
LOCKS = tuple(Lock() for _ in range(16))


class AudioError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AudioAsset:
    filename: str
    provider: str


def elevenlabs(settings: Settings, briefing: Briefing, voice: str, output: Path) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", voice):
        raise AudioError("Check the ElevenLabs voice ID in the server configuration.")
    profile = briefing.profile
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=5.0)) as client:
            response = client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                headers={"xi-api-key": settings.elevenlabs_key, "Accept": "audio/mpeg"},
                params={"output_format": FORMAT},
                json={
                    "text": briefing.script,
                    "model_id": settings.elevenlabs_model,
                    "language_code": profile.language,
                    "voice_settings": {
                        "stability": 0.62 if profile.tone == "calm" else 0.5,
                        "similarity_boost": 0.75,
                        "speed": SPEED[profile.tone],
                    },
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        LOG.warning("ElevenLabs synthesis unavailable (%s, status=%s)", type(exc).__name__, status)
        raise AudioError("ElevenLabs could not generate audio. Check the API key, voice and quota, or use local narration.",
                         502) from exc

    if not response.content or not response.headers.get("content-type", "").startswith("audio/"):
        raise AudioError("ElevenLabs returned an invalid audio file. Try local narration.", 502)
    output.write_bytes(response.content)


def local_speech(briefing: Briefing, directory: Path, output: Path) -> None:
    profile = briefing.profile
    rate = round(153 * SPEED[profile.tone])
    script_file = directory / "script.txt"
    script_file.write_text(briefing.script, encoding="utf-8")
    mac_voice = {
        ("en", "feminine"): "Flo (English (US))",
        ("en", "masculine"): "Reed (English (US))",
        ("nl", "masculine"): "Xander",
        ("nl", "feminine"): "Ellen",
    }
    if espeak := shutil.which("espeak-ng"):
        source = directory / "speech.wav"
        variant = "+f3" if profile.voice == "feminine" else "+m3"
        speak = [espeak, "-v", profile.language + variant, "-s", str(rate),
                 "-w", str(source), "-f", str(script_file)]
    elif sys.platform == "darwin" and (say := shutil.which("say")):
        source = directory / "speech.aiff"
        speak = [say, "-v", mac_voice[profile.language, profile.voice], "-r", str(rate),
                 "-o", str(source), "-f", str(script_file)]
    else:
        raise AudioError("Local narration requires espeak-ng or macOS speech.")
    if lame := shutil.which("lame"):
        encode = [lame, "--quiet", "-b", "64", str(source), str(output)]
    elif ffmpeg := shutil.which("ffmpeg"):
        encode = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source),
                  "-ar", "44100", "-b:a", "64k", str(output)]
    else:
        raise AudioError("Install LAME or FFmpeg, or set an ElevenLabs API key to generate an MP3.")

    try:
        result = subprocess.run(speak, check=False, capture_output=True, timeout=25)
        if result.returncode and sys.platform == "darwin" and speak[0] == shutil.which("say"):
            # Installable macOS voices vary. Xander and Samantha ship with the system.
            speak[2] = {"en": "Samantha", "nl": "Xander"}[profile.language]
            result = subprocess.run(speak, check=False, capture_output=True, timeout=25)
        if result.returncode:
            raise AudioError("The local speech engine could not read this briefing.")
        subprocess.run(encode, check=True, capture_output=True, timeout=25)
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("Local narration unavailable (%s)", type(exc).__name__)
        raise AudioError("The local speech engine could not create an MP3.") from exc


def synthesize(settings: Settings, briefing: Briefing, local: bool) -> AudioAsset:
    if not briefing.script:
        raise AudioError("This briefing has no stories to narrate.", 409)
    provider = "elevenlabs" if settings.elevenlabs_key and not local else "local"
    profile = briefing.profile
    voice = settings.voice_id(profile.language, profile.voice) if provider == "elevenlabs" else profile.voice
    model = settings.elevenlabs_model if provider == "elevenlabs" else f"local-v2-{sys.platform}"
    key = sha256(json.dumps([
        briefing.script, provider, model, voice, profile.language, profile.tone, FORMAT,
    ], ensure_ascii=False).encode()).hexdigest()
    asset = AudioAsset(f"{key}.mp3", provider)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    final_path = settings.audio_dir / asset.filename

    with LOCKS[int(key[0], 16)]:
        if final_path.is_file():
            return asset
        with TemporaryDirectory(dir=settings.audio_dir) as temp:
            directory = Path(temp)
            output = directory / "briefing.mp3"
            if provider == "elevenlabs":
                elevenlabs(settings, briefing, voice, output)
            else:
                local_speech(briefing, directory, output)
            if not output.is_file() or output.stat().st_size == 0:
                raise AudioError("The narration provider did not create an audio file.", 502)
            output.replace(final_path)
    return asset
