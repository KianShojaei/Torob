import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://ai.boxapi.ir/ai/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("BOXAPI_API_KEY", ""))
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-5.4-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    SQLITE_DB_PATH: Path = Path(os.getenv("SQLITE_DB_PATH", "./data/torob_assistant.db"))
    SNAPSHOT_DATE: str = os.getenv("SNAPSHOT_DATE", "2026-10-13")
    DEMO_TIME_SCALE: float = float(os.getenv("DEMO_TIME_SCALE", "20.0"))
    CONTACT_TIMEOUT_SECONDS: int = int(os.getenv("CONTACT_TIMEOUT_SECONDS", "12"))

    # Default location in Tehran (Maidan-e Ferdowsi / Sheikh Hadi cluster center)
    DEFAULT_LAT: float = 35.6961
    DEFAULT_LON: float = 51.4078
    DEFAULT_NEIGHBORHOOD: str = "فردوسی"

settings = Settings()
