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
ELEVENLABS_FORMAT = "mp3_44100_128"
SPEED = {"calm": 0.9, "professional": 1.0, "conversational": 1.04}
MAC_VOICES = {
    "en": {"feminine": ("Flo (English (US))", "Samantha"), "masculine": ("Reed (English (US))", "Alex")},
    "nl": {"feminine": ("Ellen",), "masculine": ("Xander",)},
    "de": {"feminine": ("Petra", "Anna"), "masculine": ("Markus",)},
}
LOCKS = tuple(Lock() for _ in range(16))


class AudioError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AudioAsset:
    filename: str
    provider: str


def elevenlabs_payload(settings: Settings, briefing: Briefing) -> dict:
    profile = briefing.profile
    model = settings.elevenlabs_model
    voice_settings = {
        "stability": 0.62 if profile.tone == "calm" else 0.5,
        "similarity_boost": 0.75,
    }
    if model not in {"eleven_v3", "eleven_v4", "eleven_v4_turbo"}:
        voice_settings["speed"] = SPEED[profile.tone]
    payload = {
        "text": briefing.script,
        "model_id": model,
        "voice_settings": voice_settings,
    }
    if model != "eleven_multilingual_v2":
        payload["language_code"] = profile.language
    return payload


def elevenlabs(settings: Settings, voice: str, payload: dict, output: Path) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", voice):
        raise AudioError("Check the ElevenLabs voice ID in the server configuration.", 502)
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=5.0)) as client:
            response = client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                headers={"xi-api-key": settings.elevenlabs_key, "Accept": "audio/mpeg"},
                params={"output_format": ELEVENLABS_FORMAT},
                json=payload,
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
    if espeak := shutil.which("espeak-ng"):
        source = directory / "speech.wav"
        variant = "+f3" if profile.voice == "feminine" else "+m3"
        speak = [espeak, "-v", profile.language + variant, "-b", "1", "-s", str(rate),
                 "-w", str(source), "-f", str(script_file)]
    elif sys.platform == "darwin" and (say := shutil.which("say")):
        source = directory / "speech.aiff"
        voices = iter(MAC_VOICES[profile.language][profile.voice])
        speak = [say, "-v", next(voices), "-r", str(rate),
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
        if result.returncode and source.suffix == ".aiff":
            for voice in voices:
                speak[2] = voice
                result = subprocess.run(speak, check=False, capture_output=True, timeout=25)
                if result.returncode == 0:
                    break
            if result.returncode:
                raise AudioError("Install the selected voice in macOS speech settings or use eSpeak NG.")
        if result.returncode:
            raise AudioError("The local speech engine could not read this briefing.")
        subprocess.run(encode, check=True, capture_output=True, timeout=25)
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("Local narration unavailable (%s)", type(exc).__name__)
        raise AudioError("The local speech engine could not create an MP3.") from exc


def synthesize(settings: Settings, briefing: Briefing, local: bool) -> AudioAsset:
    if not briefing.script:
        raise AudioError("This briefing has no stories to narrate.", 409)
    profile = briefing.profile
    if settings.elevenlabs_key and not local:
        provider = "elevenlabs"
        voice = settings.voice_id(profile.language, profile.voice)
        payload = elevenlabs_payload(settings, briefing)
        cache_input = [provider, voice, ELEVENLABS_FORMAT, payload]
    else:
        provider = "local"
        payload = None
        version = "v4" if sys.platform == "darwin" else "v3"
        cache_input = [
            briefing.script, provider, f"local-{version}-{sys.platform}", profile.voice,
            profile.language, profile.tone, "mp3_44100_64",
        ]
    key = sha256(json.dumps(cache_input, ensure_ascii=False).encode()).hexdigest()
    asset = AudioAsset(f"{key}.mp3", provider)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    final_path = settings.audio_dir / asset.filename

    with LOCKS[int(key[0], 16)]:
        if final_path.is_file():
            return asset
        with TemporaryDirectory(dir=settings.audio_dir) as temp:
            directory = Path(temp)
            output = directory / "briefing.mp3"
            if payload is not None:
                elevenlabs(settings, voice, payload, output)
            else:
                local_speech(briefing, directory, output)
            if not output.is_file() or output.stat().st_size == 0:
                raise AudioError("The narration provider did not create an audio file.", 502)
            output.replace(final_path)
    return asset
