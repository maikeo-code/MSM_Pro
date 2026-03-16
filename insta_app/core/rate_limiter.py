import random
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console

from insta_app.config import Settings

console = Console()

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "rate_limiter.db"


def _get_db() -> sqlite3.Connection:
    """Retorna conexao SQLite para o banco de rate limiting."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_action_ts ON action_log(action, timestamp)"
    )
    conn.commit()
    return conn


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db = _get_db()
        # Circuit breaker state (FIX 6)
        self._consecutive_errors: int = 0
        self._circuit_breaker_threshold: int = 3
        self._circuit_breaker_pause: float = 900.0  # 15 minutes in seconds
        # Cleanup old records on init
        self._cleanup_old_records()

    # ------------------------------------------------------------------
    # SQLite persistence (FIX 2)
    # ------------------------------------------------------------------

    def _cleanup_old_records(self) -> None:
        """Remove registros com mais de 48h do banco."""
        cutoff = time.time() - 172800  # 48h in seconds
        self._db.execute("DELETE FROM action_log WHERE timestamp < ?", (cutoff,))
        self._db.commit()

    def _count_in_window(self, action: str, window_seconds: float) -> int:
        """Conta acoes dentro de uma janela de tempo."""
        cutoff = time.time() - window_seconds
        cursor = self._db.execute(
            "SELECT COUNT(*) FROM action_log WHERE action = ? AND timestamp >= ?",
            (action, cutoff),
        )
        return cursor.fetchone()[0]

    def _count_last_hour(self, action: str) -> int:
        """Conta acoes realizadas na ultima hora."""
        return self._count_in_window(action, 3600)

    def _count_last_day(self, action: str) -> int:
        """Conta acoes realizadas nas ultimas 24h."""
        return self._count_in_window(action, 86400)

    # ------------------------------------------------------------------
    # Warm-up gradual (FIX 3)
    # ------------------------------------------------------------------

    def _get_first_login_date(self) -> datetime:
        """Recupera ou define a data do primeiro login."""
        cursor = self._db.execute(
            "SELECT value FROM meta WHERE key = 'first_login_date'"
        )
        row = cursor.fetchone()
        if row:
            return datetime.fromisoformat(row[0])
        # Primeiro uso: salvar data atual
        now = datetime.now()
        self._db.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('first_login_date', ?)",
            (now.isoformat(),),
        )
        self._db.commit()
        return now

    def get_warmup_multiplier(self) -> float:
        """
        Retorna multiplicador de warm-up (0.15 a 1.0).
        Dia 1 = 15%, dia N = min(100%, 15% + 85% * N / warmup_days).
        Retorna 1.0 se warm-up desabilitado.
        """
        if not self._settings.warmup_enabled:
            return 1.0

        first_login = self._get_first_login_date()
        days_active = (datetime.now() - first_login).days

        if days_active >= self._settings.warmup_days:
            return 1.0

        multiplier = 0.15 + 0.85 * (days_active / self._settings.warmup_days)
        return min(1.0, max(0.15, multiplier))

    def get_warmup_status(self) -> dict:
        """Retorna info do warmup para exibicao no status."""
        if not self._settings.warmup_enabled:
            return {"enabled": False, "multiplier": 1.0, "days_active": 0, "days_total": 0}

        first_login = self._get_first_login_date()
        days_active = (datetime.now() - first_login).days
        multiplier = self.get_warmup_multiplier()
        completed = days_active >= self._settings.warmup_days

        return {
            "enabled": True,
            "multiplier": multiplier,
            "percentage": int(multiplier * 100),
            "days_active": days_active,
            "days_total": self._settings.warmup_days,
            "completed": completed,
            "first_login": first_login.isoformat(),
        }

    def _get_effective_limits(self, action: str) -> tuple[int, int]:
        """Retorna (per_hour, per_day) ajustados pelo warmup multiplier."""
        limits = self._settings.rate_limits[action]
        multiplier = self.get_warmup_multiplier()
        effective_hour = max(1, int(limits.per_hour * multiplier))
        effective_day = max(1, int(limits.per_day * multiplier))
        return effective_hour, effective_day

    # ------------------------------------------------------------------
    # Core rate limiting
    # ------------------------------------------------------------------

    def can_perform(self, action: str) -> bool:
        """Verifica se pode executar a acao baseado nos limites configurados."""
        if action not in self._settings.rate_limits:
            console.print(f"[yellow]Acao desconhecida:[/yellow] {action}")
            return False

        effective_hour, effective_day = self._get_effective_limits(action)
        hourly_count = self._count_last_hour(action)
        daily_count = self._count_last_day(action)

        if hourly_count >= effective_hour:
            console.print(
                f"[yellow]Limite por hora atingido para '{action}':[/yellow] "
                f"{hourly_count}/{effective_hour}"
            )
            return False

        if daily_count >= effective_day:
            console.print(
                f"[yellow]Limite diario atingido para '{action}':[/yellow] "
                f"{daily_count}/{effective_day}"
            )
            return False

        return True

    def record_action(self, action: str) -> None:
        """Registra que uma acao foi executada (INSERT no SQLite)."""
        self._db.execute(
            "INSERT INTO action_log (action, timestamp) VALUES (?, ?)",
            (action, time.time()),
        )
        self._db.commit()

    def wait_for_action(self, action: str) -> None:
        """
        Aguarda delay gaussiano antes da acao (FIX 4).
        5% de chance de micro-pausa longa (60-180s) simulando distracao humana.
        """
        if action not in self._settings.rate_limits:
            return
        limits = self._settings.rate_limits[action]

        # FIX 4: Gaussian delay com clamp
        mean = (limits.delay_min + limits.delay_max) / 2
        std_dev = (limits.delay_max - limits.delay_min) / 4
        delay = random.gauss(mean, std_dev)
        delay = max(limits.delay_min, min(limits.delay_max, delay))

        # FIX 4: 5% chance de micro-pausa longa
        if random.random() < 0.05:
            micro_pause = random.uniform(60.0, 180.0)
            console.print(
                f"[dim]Micro-pausa humana: {micro_pause:.0f}s "
                f"(simulando distracao)...[/dim]"
            )
            time.sleep(micro_pause)

        console.print(f"[dim]Aguardando {delay:.1f}s antes de '{action}'...[/dim]")
        time.sleep(delay)

    def get_remaining(self, action: str) -> dict[str, int]:
        """Retorna quantas acoes restam na hora e no dia."""
        if action not in self._settings.rate_limits:
            return {"hour": 0, "day": 0}
        effective_hour, effective_day = self._get_effective_limits(action)
        hourly_used = self._count_last_hour(action)
        daily_used = self._count_last_day(action)
        return {
            "hour": max(0, effective_hour - hourly_used),
            "day": max(0, effective_day - daily_used),
        }

    def is_within_schedule(self) -> bool:
        """Verifica se o horario atual esta dentro da janela de funcionamento."""
        start_hour, end_hour = self._settings.schedule_hours
        current_hour = datetime.now().hour
        return start_hour <= current_hour < end_hour

    def reset_daily(self) -> None:
        """Reseta os contadores diarios removendo registros do dia."""
        cutoff = time.time() - 86400
        self._db.execute("DELETE FROM action_log WHERE timestamp < ?", (cutoff,))
        self._db.commit()
        console.print("[green]Contadores diarios resetados.[/green]")

    # ------------------------------------------------------------------
    # Circuit breaker (FIX 6)
    # ------------------------------------------------------------------

    def record_error(self, action: str) -> None:
        """
        Registra erro consecutivo. Se >= 3, pausa por 15 minutos e reseta.
        """
        self._consecutive_errors += 1
        console.print(
            f"[yellow]Erro consecutivo #{self._consecutive_errors} "
            f"para '{action}'.[/yellow]"
        )

        if self._consecutive_errors >= self._circuit_breaker_threshold:
            pause_minutes = int(self._circuit_breaker_pause / 60)
            console.print(
                f"[bold red]Circuit breaker ativado! "
                f"{self._consecutive_errors} erros seguidos. "
                f"Pausando por {pause_minutes} minutos...[/bold red]"
            )
            time.sleep(self._circuit_breaker_pause)
            self._consecutive_errors = 0
            console.print("[green]Circuit breaker resetado. Retomando acoes.[/green]")

    def record_success(self, action: str) -> None:
        """Reseta contador de erros consecutivos apos sucesso."""
        self._consecutive_errors = 0
