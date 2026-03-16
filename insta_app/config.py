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


PRESETS: dict[str, dict[str, ActionLimits]] = {
    "conservador": {
        "like": ActionLimits(per_hour=10, per_day=100, delay_min=45, delay_max=120),
        "follow": ActionLimits(per_hour=5, per_day=50, delay_min=60, delay_max=180),
        "unfollow": ActionLimits(per_hour=5, per_day=50, delay_min=60, delay_max=180),
        "story_view": ActionLimits(per_hour=15, per_day=150, delay_min=8, delay_max=25),
        "story_react": ActionLimits(per_hour=5, per_day=30, delay_min=30, delay_max=90),
    },
    "moderado": {
        "like": ActionLimits(per_hour=40, per_day=500, delay_min=15, delay_max=45),
        "follow": ActionLimits(per_hour=15, per_day=150, delay_min=30, delay_max=90),
        "unfollow": ActionLimits(per_hour=15, per_day=150, delay_min=30, delay_max=90),
        "story_view": ActionLimits(per_hour=50, per_day=500, delay_min=5, delay_max=15),
        "story_react": ActionLimits(per_hour=10, per_day=100, delay_min=30, delay_max=90),
    },
    "agressivo": {
        "like": ActionLimits(per_hour=55, per_day=700, delay_min=8, delay_max=25),
        "follow": ActionLimits(per_hour=25, per_day=300, delay_min=20, delay_max=60),
        "unfollow": ActionLimits(per_hour=25, per_day=300, delay_min=20, delay_max=60),
        "story_view": ActionLimits(per_hour=50, per_day=500, delay_min=3, delay_max=10),
        "story_react": ActionLimits(per_hour=20, per_day=150, delay_min=10, delay_max=30),
    },
}


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
    whitelist: list[str] = Field(default_factory=list)
    blacklist: list[str] = Field(default_factory=list)
    proxy: str | None = None

    def apply_preset(self, name: str) -> None:
        """
        Aplica um preset de comportamento, substituindo os rate_limits atuais.

        Args:
            name: nome do preset ('conservador', 'moderado', 'agressivo').

        Raises:
            ValueError: se o nome do preset nao existir.
        """
        if name not in PRESETS:
            raise ValueError(f"Preset '{name}' nao encontrado. Opcoes: {list(PRESETS.keys())}")
        self.rate_limits = {k: v.model_copy() for k, v in PRESETS[name].items()}

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
