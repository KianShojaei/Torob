"""Environment contract (master prompt §7). All values overridable via env."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    # --- data ---
    data_dir: str = str(ROOT / "data")
    db_path: str = str(ROOT / "backend" / "var" / "app.db")
    snapshot_date: str = "2026-10-13"

    # --- llm (provider agnostic) ---
    llm_provider: str = "none"          # none | anthropic | openai
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5"
    llm_base_url: str = ""
    llm_timeout_seconds: float = 30.0

    # --- demo / contact simulation ---
    demo_mode: bool = True
    demo_time_scale: float = 20.0        # 1 simulated minute = 60/scale seconds
    contact_timeout_seconds: float = 45.0
    no_reply_rate: float = 0.33

    # --- geo / map ---
    default_lat: float = 35.6949
    default_lon: float = 51.4071
    map_tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    map_attribution: str = "© OpenStreetMap"

    # --- misc ---
    cors_origins: str = "*"
    log_level: str = "INFO"

    @property
    def snapshot(self) -> date:
        return date.fromisoformat(self.snapshot_date)

    @property
    def now_tehran(self) -> datetime:
        from app.services.hours import TEHRAN
        return datetime.now(TEHRAN)

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider in ("anthropic", "openai") and bool(self.llm_api_key)


settings = Settings()
