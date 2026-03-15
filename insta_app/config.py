import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ActionLimits(BaseModel):
    per_hour: int
    per_day: int
    delay_min: float  # seconds
    delay_max: float  # seconds

    @model_validator(mode="after")
    def check_values(self) -> "ActionLimits":
        if self.delay_min > self.delay_max:
            raise ValueError("delay_min nao pode ser maior que delay_max")
        if self.per_hour < 0 or self.per_day < 0:
            raise ValueError("Limites nao podem ser negativos")
        return self


class Settings(BaseModel):
    username: str = ""
    session_file: str = "session.json"
    rate_limits: dict[str, ActionLimits] = Field(
        default_factory=lambda: {
            "follow": ActionLimits(per_hour=15, per_day=150, delay_min=30.0, delay_max=90.0),
            "unfollow": ActionLimits(per_hour=15, per_day=150, delay_min=30.0, delay_max=90.0),
            "like": ActionLimits(per_hour=40, per_day=500, delay_min=15.0, delay_max=45.0),
            "story_view": ActionLimits(per_hour=50, per_day=500, delay_min=5.0, delay_max=15.0),
            "story_react": ActionLimits(per_hour=10, per_day=100, delay_min=30.0, delay_max=90.0),
        }
    )
    schedule_hours: tuple[int, int] = (8, 23)
    warmup_enabled: bool = True
    warmup_days: int = 14
    ignore_business_accounts: bool = True

    @classmethod
    def load_from_file(cls, path: str) -> "Settings":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(config_path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return cls(**data)

    def save_to_file(self, path: str) -> None:
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)


_CONFIG_FILE = Path(__file__).parent / "config.json"

if _CONFIG_FILE.exists():
    settings = Settings.load_from_file(str(_CONFIG_FILE))
else:
    settings = Settings()
