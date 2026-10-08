import os
import re

from dotenv import load_dotenv

load_dotenv()

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def pg_schema() -> str:
    s = os.environ.get("DB_SCHEMA", "public")
    if not _IDENT.match(s):
        raise ValueError(
            f'Invalid DB_SCHEMA "{s}" - must be a bare SQL identifier '
            r"([A-Za-z_][A-Za-z0-9_]*)."
        )
    return s


class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DATABASE_SSL = os.environ.get("DATABASE_SSL")
    SQLITE_PATH = os.environ.get("SQLITE_PATH", "mental_health.db")
    PGPOOL_MAX = int(os.environ.get("PGPOOL_MAX", "3"))
    USE_POSTGRES = bool(DATABASE_URL)
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    TETHER_MODEL = os.environ.get("TETHER_MODEL", "claude-opus-5-5")
    TETHER_EFFORT = os.environ.get("TETHER_EFFORT", "medium")  # low | medium | high | xhigh | max
    TETHER_PROMPT_FILE = os.environ.get("TETHER_PROMPT_FILE")  # unset -> app/tether/prompts/clinician.md
    TETHER_PATIENT_ID = os.environ.get("TETHER_PATIENT_ID")  # unset -> first patient on file
    ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
