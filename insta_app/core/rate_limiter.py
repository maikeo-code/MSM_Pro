import random
import time
from collections import deque
from datetime import datetime, timedelta

from rich.console import Console

from insta_app.config import Settings

console = Console()


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Armazena timestamps de cada acao (deque com maxlen para eficiencia)
        self._actions: dict[str, deque[float]] = {
            action: deque(maxlen=limits.per_day * 2)
            for action, limits in settings.rate_limits.items()
        }

    def _clean_old_timestamps(self, action: str) -> None:
        """Remove timestamps mais antigos que 24h."""
        now = time.time()
        cutoff_day = now - 86400  # 24 horas em segundos
        queue = self._actions[action]
        while queue and queue[0] < cutoff_day:
            queue.popleft()

    def _count_last_hour(self, action: str) -> int:
        """Conta acoes realizadas na ultima hora."""
        now = time.time()
        cutoff_hour = now - 3600
        return sum(1 for ts in self._actions[action] if ts >= cutoff_hour)

    def _count_last_day(self, action: str) -> int:
        """Conta acoes realizadas nas ultimas 24h."""
        self._clean_old_timestamps(action)
        return len(self._actions[action])

    def can_perform(self, action: str) -> bool:
        """Verifica se pode executar a acao baseado nos limites configurados."""
        if action not in self._settings.rate_limits:
            console.print(f"[yellow]Acao desconhecida:[/yellow] {action}")
            return False

        limits = self._settings.rate_limits[action]
        hourly_count = self._count_last_hour(action)
        daily_count = self._count_last_day(action)

        if hourly_count >= limits.per_hour:
            console.print(
                f"[yellow]Limite por hora atingido para '{action}':[/yellow] "
                f"{hourly_count}/{limits.per_hour}"
            )
            return False

        if daily_count >= limits.per_day:
            console.print(
                f"[yellow]Limite diario atingido para '{action}':[/yellow] "
                f"{daily_count}/{limits.per_day}"
            )
            return False

        return True

    def record_action(self, action: str) -> None:
        """Registra que uma acao foi executada (salva timestamp atual)."""
        if action not in self._actions:
            self._actions[action] = deque()
        self._actions[action].append(time.time())

    def wait_for_action(self, action: str) -> None:
        """Aguarda o delay aleatorio configurado para a acao."""
        if action not in self._settings.rate_limits:
            return
        limits = self._settings.rate_limits[action]
        delay = random.uniform(limits.delay_min, limits.delay_max)
        console.print(f"[dim]Aguardando {delay:.1f}s antes de '{action}'...[/dim]")
        time.sleep(delay)

    def get_remaining(self, action: str) -> dict[str, int]:
        """Retorna quantas acoes restam na hora e no dia."""
        if action not in self._settings.rate_limits:
            return {"hour": 0, "day": 0}
        limits = self._settings.rate_limits[action]
        hourly_used = self._count_last_hour(action)
        daily_used = self._count_last_day(action)
        return {
            "hour": max(0, limits.per_hour - hourly_used),
            "day": max(0, limits.per_day - daily_used),
        }

    def is_within_schedule(self) -> bool:
        """Verifica se o horario atual esta dentro da janela de funcionamento."""
        start_hour, end_hour = self._settings.schedule_hours
        current_hour = datetime.now().hour
        return start_hour <= current_hour < end_hour

    def reset_daily(self) -> None:
        """Reseta os contadores diarios removendo todos os timestamps."""
        for action in self._actions:
            self._actions[action].clear()
        console.print("[green]Contadores diarios resetados.[/green]")
