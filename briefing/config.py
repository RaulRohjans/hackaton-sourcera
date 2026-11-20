import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
load_dotenv(ROOT / ".env")


class Settings:
    def __init__(self):
        self.data_dir = Path(os.getenv("BRIEFING_DATA_DIR", ROOT / "liquid-briefing-data"))
        self.state_dir = Path(os.getenv("BRIEFING_STATE_DIR", ROOT / ".runtime"))
        self.database = self.state_dir / "briefing.sqlite3"
        self.audio_dir = self.state_dir / "audio"
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        self.elevenlabs_model = os.getenv("ELEVENLABS_MODEL", "").strip() or "eleven_v4"

    @staticmethod
    def voice_id(language: str, voice: str) -> str:
        default = {
            "feminine": "EXAVITQu4vr4xnSDxMaL",
            "masculine": "JBFqnCBsd6RMkjVDRZzb",
        }
        return os.getenv(f"ELEVENLABS_VOICE_{language.upper()}_{voice.upper()}", "").strip() or default[voice]
