import json
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

from insta_app.core.rate_limiter import RateLimiter

try:
    from instagrapi import Client
except ImportError:
    Console().print(
        "[bold red]Erro:[/bold red] instagrapi nao instalado. "
        "Execute: pip install instagrapi"
    )
    raise

console = Console()

_ACTION = "unfollow"


class UnfollowManager:
    def __init__(
        self,
        client: Client,
        rate_limiter: RateLimiter,
        data_dir: str = "data",
    ) -> None:
        """
        Gerencia unfollows de forma segura e com rate limiting.

        Args:
            client: instagrapi.Client ja autenticado.
            rate_limiter: instancia de RateLimiter para controlar cadencia.
            data_dir: pasta onde a fila e arquivos de dados sao salvos.
        """
        self._client = client
        self._rate_limiter = rate_limiter
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
        followers: dict = self._client.user_followers(user_id)
        console.print("[dim]Buscando seguindo...[/dim]")
        following: dict = self._client.user_following(user_id)

        follower_ids: set[int] = set(followers.keys())
        not_following_back = {uid: user for uid, user in following.items() if uid not in follower_ids}

        console.print(
            f"[dim]Enriquecendo info de {len(not_following_back)} perfis "
            "(pode demorar por causa do rate limit)...[/dim]"
        )

        suggestions: list[dict] = []
        for uid, user_short in not_following_back.items():
            try:
                self._rate_limiter.wait_for_action("story_view")  # delay leve entre chamadas
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

        with open(self._queue_path, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)

        # Calcula tempo estimado
        if delay_between is None:
            from insta_app.config import Settings
            # Usa a media dos delays configurados para unfollow
            try:
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

        for user_id in list(pending):
            if not self._rate_limiter.can_perform(_ACTION):
                console.print("[yellow]Limite de unfollow atingido. Pausando execucao.[/yellow]")
                break

            self._rate_limiter.wait_for_action(_ACTION)

            try:
                self._client.user_unfollow(user_id)
                self._rate_limiter.record_action(_ACTION)
                completed.append(user_id)
                pending.remove(user_id)
                console.print(f"[green]Unfollow realizado:[/green] user_id={user_id}")
            except Exception as exc:
                console.print(f"[red]Erro ao dar unfollow em {user_id}:[/red] {exc}")
                failed.append(user_id)
                pending.remove(user_id)

            # Salva progresso apos cada acao
            queue["pending"] = pending
            queue["completed"] = completed
            queue["failed"] = failed
            self._save_queue(queue)

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
        """Salva fila de unfollow no arquivo JSON."""
        with open(self._queue_path, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2, ensure_ascii=False)
