from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

from insta_app.core.rate_limiter import RateLimiter
from insta_app.core.utils import atomic_write_json

try:
    from instagrapi import Client
    from instagrapi.exceptions import ChallengeRequired, LoginRequired
except ImportError:
    Console().print(
        "[bold red]Erro:[/bold red] instagrapi nao instalado. "
        "Execute: pip install instagrapi"
    )
    raise

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from insta_app.config import Settings
    from insta_app.core.action_log import ActionLog

console = Console()

_ACTION = "unfollow"


class UnfollowManager:
    def __init__(
        self,
        client: Client,
        rate_limiter: RateLimiter,
        data_dir: str = "data",
        action_log: ActionLog | None = None,
        dry_run: bool = False,
        settings: "Settings | None" = None,
    ) -> None:
        """
        Gerencia unfollows de forma segura e com rate limiting.

        Args:
            client: instagrapi.Client ja autenticado.
            rate_limiter: instancia de RateLimiter para controlar cadencia.
            data_dir: pasta onde a fila e arquivos de dados sao salvos.
            action_log: instancia opcional de ActionLog para registrar acoes.
            dry_run: se True, simula acoes sem executar de verdade.
            settings: instancia opcional de Settings para leitura de configuracao (whitelist).
        """
        self._client = client
        self._rate_limiter = rate_limiter
        self._action_log = action_log
        self._dry_run = dry_run
        self._settings = settings
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._queue_path = self._data_dir / "unfollow_queue.json"

    # ------------------------------------------------------------------
    # Sugestoes de unfollow
    # ------------------------------------------------------------------

    def get_unfollow_suggestions(self) -> list[dict]:
        """
        Busca quem nao te segue de volta e enriquece com info do perfil.

        Retorna lista ordenada por followers_count crescente
        (menos seguidores = menos relevante = melhor candidato a unfollow).
        """
        user_id = self._client.user_id
        console.print("[dim]Buscando seguidores...[/dim]")
        try:
            followers: dict = self._client.user_followers(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)

        console.print("[dim]Buscando seguindo...[/dim]")

        try:
            following: dict = self._client.user_following(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)

        follower_ids: set[int] = set(followers.keys())
        not_following_back = {uid: user for uid, user in following.items() if uid not in follower_ids}

        console.print(
            f"[dim]Enriquecendo info de {len(not_following_back)} perfis "
            "(pode demorar por causa do rate limit)...[/dim]"
        )

        suggestions: list[dict] = []
        for uid, user_short in not_following_back.items():
            try:
                import random
                time.sleep(random.uniform(0.5, 1.5))  # delay simples entre chamadas API
                info = self._client.user_info(uid)
                suggestions.append(
                    {
                        "user_id": uid,
                        "username": info.username,
                        "full_name": info.full_name or "",
                        "followers_count": info.follower_count,
                        "media_count": info.media_count,
                        "is_private": info.is_private,
                    }
                )
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(f"[yellow]Nao foi possivel buscar info de {user_short.username}: {exc}[/yellow]")
                suggestions.append(
                    {
                        "user_id": uid,
                        "username": user_short.username,
                        "full_name": user_short.full_name or "",
                        "followers_count": 0,
                        "media_count": 0,
                        "is_private": user_short.is_private,
                    }
                )

        # Ordena: menos seguidores primeiro (candidatos mais fracos)
        suggestions.sort(key=lambda x: x["followers_count"])
        return suggestions

    # ------------------------------------------------------------------
    # Fila de unfollow
    # ------------------------------------------------------------------

    def schedule_unfollow(
        self,
        user_ids: list[int],
        delay_between: float | None = None,
    ) -> dict:
        """
        Salva lista de unfollows pendentes em data/unfollow_queue.json.

        Args:
            user_ids: lista de user IDs para dar unfollow.
            delay_between: delay medio entre unfollows em segundos (None usa o configurado).

        Returns:
            {"total": int, "estimated_time": str}
        """
        if not user_ids:
            return {"total": 0, "estimated_time": "0s"}

        queue_data = {
            "created_at": datetime.now().isoformat(),
            "pending": list(user_ids),
            "completed": [],
            "failed": [],
        }

        atomic_write_json(self._queue_path, queue_data)

        # Calcula tempo estimado
        if delay_between is None:
            # Usa a media dos delays configurados para unfollow
            try:
                if self._settings is not None:
                    limits = self._settings.rate_limits.get(_ACTION)
                else:
                    from insta_app.config import Settings
                    limits = Settings().rate_limits.get(_ACTION)
                delay_between = (limits.delay_min + limits.delay_max) / 2 if limits else 60.0
            except Exception:
                delay_between = 60.0

        total_seconds = int(len(user_ids) * delay_between)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            estimated = f"{hours}h {minutes}min"
        elif minutes > 0:
            estimated = f"{minutes}min {seconds}s"
        else:
            estimated = f"{seconds}s"

        console.print(
            f"[green]Fila criada:[/green] {len(user_ids)} unfollows agendados. "
            f"Tempo estimado: {estimated}"
        )
        return {"total": len(user_ids), "estimated_time": estimated}

    def execute_unfollow_queue(self) -> dict:
        """
        Le data/unfollow_queue.json e executa unfollows respeitando rate_limiter.
        Move user_ids de 'pending' para 'completed' ou 'failed'.
        Salva progresso a cada acao (para poder retomar).

        Returns:
            {"completed": int, "failed": int, "remaining": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"completed": 0, "failed": 0, "remaining": 0, "message": "Fora do horario"}

        queue = self._load_queue()
        if queue is None:
            console.print("[yellow]Nenhuma fila de unfollow encontrada.[/yellow]")
            return {"completed": 0, "failed": 0, "remaining": 0}

        pending: list[int] = queue.get("pending", [])
        completed: list[int] = queue.get("completed", [])
        failed: list[int] = queue.get("failed", [])

        if not pending:
            console.print("[yellow]Fila ja esta vazia.[/yellow]")
            return {"completed": len(completed), "failed": len(failed), "remaining": 0}

        console.print(f"[cyan]Iniciando execucao da fila:[/cyan] {len(pending)} unfollows pendentes.")

        # Build a username lookup for whitelist checking
        whitelist: list[str] = []
        if self._settings:
            whitelist = self._settings.whitelist

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Executando unfollows...", total=len(pending))

            for user_id in list(pending):
                if not self._rate_limiter.can_perform(_ACTION):
                    console.print("[yellow]Limite de unfollow atingido. Pausando execucao.[/yellow]")
                    break

                # Whitelist check: try to resolve username for the user_id
                if whitelist:
                    try:
                        user_info = self._client.user_info(user_id)
                        username = user_info.username
                        if username in whitelist:
                            console.print(f"[dim]@{username} na whitelist. Pulando.[/dim]")
                            pending.remove(user_id)
                            progress.advance(task)
                            continue
                    except Exception:
                        pass  # If we can't resolve username, proceed with unfollow

                if not self._dry_run:
                    self._rate_limiter.wait_for_action(_ACTION)

                try:
                    if self._dry_run:
                        console.print(f"[dim][DRY-RUN] Unfollow user_id={user_id}[/dim]")
                    else:
                        self._client.user_unfollow(user_id)
                    if not self._dry_run:
                        self._rate_limiter.record_action(_ACTION)
                        self._rate_limiter.record_success(_ACTION)
                    completed.append(user_id)
                    pending.remove(user_id)
                    if not self._dry_run:
                        console.print(f"[green]Unfollow realizado:[/green] user_id={user_id}")
                    if self._action_log and not self._dry_run:
                        self._action_log.log(_ACTION, str(user_id), "", "ok")
                except ChallengeRequired:
                    console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                    console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                    # Salva progresso antes de sair
                    queue["pending"] = pending
                    queue["completed"] = completed
                    queue["failed"] = failed
                    self._save_queue(queue)
                    raise SystemExit(2)
                except LoginRequired:
                    console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                    queue["pending"] = pending
                    queue["completed"] = completed
                    queue["failed"] = failed
                    self._save_queue(queue)
                    raise SystemExit(2)
                except Exception as exc:
                    console.print(f"[red]Erro ao dar unfollow em {user_id}:[/red] {exc}")
                    self._rate_limiter.record_error(_ACTION)
                    failed.append(user_id)
                    pending.remove(user_id)
                    if self._action_log:
                        self._action_log.log(_ACTION, str(user_id), "", "error", str(exc))

                # Salva progresso apos cada acao
                queue["pending"] = pending
                queue["completed"] = completed
                queue["failed"] = failed
                self._save_queue(queue)
                progress.advance(task)

        return {
            "completed": len(completed),
            "failed": len(failed),
            "remaining": len(pending),
        }

    def cancel_unfollow_queue(self) -> None:
        """Remove o arquivo de fila de unfollow."""
        if self._queue_path.exists():
            self._queue_path.unlink()
            console.print("[green]Fila de unfollow cancelada.[/green]")
        else:
            console.print("[yellow]Nenhuma fila encontrada para cancelar.[/yellow]")

    def get_queue_status(self) -> dict | None:
        """
        Retorna status da fila atual (se existir).
        Retorna None se nao houver fila.
        """
        queue = self._load_queue()
        if queue is None:
            return None
        return {
            "created_at": queue.get("created_at", ""),
            "pending": len(queue.get("pending", [])),
            "completed": len(queue.get("completed", [])),
            "failed": len(queue.get("failed", [])),
        }

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _load_queue(self) -> dict | None:
        """Carrega fila de unfollow do arquivo JSON."""
        if not self._queue_path.exists():
            return None
        try:
            with open(self._queue_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            console.print(f"[yellow]Erro ao carregar fila:[/yellow] {exc}")
            return None

    def _save_queue(self, queue: dict) -> None:
        """Salva fila de unfollow no arquivo JSON de forma atomica."""
        atomic_write_json(self._queue_path, queue)
