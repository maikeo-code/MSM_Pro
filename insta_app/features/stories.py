from __future__ import annotations

from rich.console import Console

from insta_app.core.rate_limiter import RateLimiter

try:
    from instagrapi import Client
    from instagrapi.exceptions import ChallengeRequired, LoginRequired
except ImportError:
    Console().print(
        "[bold red]Erro:[/bold red] instagrapi nao instalado. "
        "Execute: pip install instagrapi"
    )
    raise

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from insta_app.core.action_log import ActionLog

console = Console()

_ACTION_VIEW = "story_view"
_ACTION_REACT = "story_react"


class StoryManager:
    def __init__(
        self,
        client: Client,
        rate_limiter: RateLimiter,
        action_log: ActionLog | None = None,
    ) -> None:
        """
        Gerencia visualizacoes e reacoes a stories com rate limiting.

        Args:
            client: instagrapi.Client ja autenticado.
            rate_limiter: instancia de RateLimiter para controlar cadencia.
            action_log: instancia opcional de ActionLog para registrar acoes.
        """
        self._client = client
        self._rate_limiter = rate_limiter
        self._action_log = action_log

    # ------------------------------------------------------------------
    # Metodos publicos
    # ------------------------------------------------------------------

    def view_user_stories(self, user_id: int) -> int:
        """
        Visualiza todos os stories de um usuario.

        Args:
            user_id: ID numerico do usuario no Instagram.

        Returns:
            Numero de stories visualizados.
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return 0

        stories_viewed = 0

        try:
            stories = self._client.user_stories(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            console.print("Faca login novamente com: python -m insta_app.app login")
            raise SystemExit(2)
        except Exception as exc:
            console.print(f"[yellow]Erro ao buscar stories do user_id={user_id}:[/yellow] {exc}")
            self._rate_limiter.record_error(_ACTION_VIEW)
            return 0

        if not stories:
            console.print(f"[dim]Nenhum story ativo para user_id={user_id}.[/dim]")
            return 0

        for story in stories:
            # FIX 9: verificar duplicata antes de visualizar
            if self._action_log and self._action_log.already_acted(_ACTION_VIEW, str(story.pk), hours=24):
                console.print(f"[dim]Story {story.pk} ja visto recentemente. Pulando.[/dim]")
                continue

            if not self._rate_limiter.can_perform(_ACTION_VIEW):
                console.print("[yellow]Limite de story_view atingido. Pausando.[/yellow]")
                break

            self._rate_limiter.wait_for_action(_ACTION_VIEW)

            try:
                self._client.story_seen([story.pk])
                self._rate_limiter.record_action(_ACTION_VIEW)
                self._rate_limiter.record_success(_ACTION_VIEW)
                stories_viewed += 1
                console.print(f"[green]Story visto:[/green] {story.pk}")
                if self._action_log:
                    self._action_log.log(_ACTION_VIEW, str(story.pk), str(user_id), "ok")
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(f"[red]Erro ao marcar story {story.pk} como visto:[/red] {exc}")
                self._rate_limiter.record_error(_ACTION_VIEW)
                if self._action_log:
                    self._action_log.log(_ACTION_VIEW, str(story.pk), str(user_id), "error", str(exc))

        return stories_viewed

    def view_new_followers_stories(self) -> dict:
        """
        Busca novos seguidores e visualiza os stories de cada um.

        Returns:
            {"users_checked": int, "stories_viewed": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"users_checked": 0, "stories_viewed": 0, "errors": 0, "message": "Fora do horario"}

        from insta_app.features.monitoring import FollowerMonitor

        monitor = FollowerMonitor(self._client, data_dir="data")
        new_followers = monitor.get_new_followers(update_snapshot=False)

        users_checked = 0
        stories_viewed = 0
        errors = 0

        if not new_followers:
            console.print("[yellow]Nenhum novo seguidor encontrado para ver stories.[/yellow]")
            return {"users_checked": 0, "stories_viewed": 0, "errors": 0}

        console.print(
            f"[cyan]Verificando stories de {len(new_followers)} novo(s) seguidor(es)...[/cyan]"
        )

        for user in new_followers:
            user_id = int(user.pk)
            username = user.username

            users_checked += 1
            console.print(f"[dim]Verificando stories de @{username}...[/dim]")

            try:
                viewed = self.view_user_stories(user_id)
                stories_viewed += viewed
            except SystemExit:
                raise
            except Exception as exc:
                console.print(f"[red]Erro ao ver stories de @{username}:[/red] {exc}")
                errors += 1

        return {
            "users_checked": users_checked,
            "stories_viewed": stories_viewed,
            "errors": errors,
        }

    def view_list_stories(self, usernames: list[str]) -> dict:
        """
        Visualiza stories de uma lista de usernames.

        Args:
            usernames: lista de nomes de usuario (com ou sem @).

        Returns:
            {"users_checked": int, "stories_viewed": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"users_checked": 0, "stories_viewed": 0, "errors": 0, "message": "Fora do horario"}

        users_checked = 0
        stories_viewed = 0
        errors = 0

        console.print(
            f"[cyan]Verificando stories de {len(usernames)} usuario(s)...[/cyan]"
        )

        for username in usernames:
            username = username.lstrip("@")
            users_checked += 1

            try:
                user_info = self._client.user_info_by_username(username)
                user_id = int(user_info.pk)
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(f"[red]Erro ao buscar usuario @{username}:[/red] {exc}")
                errors += 1
                continue

            console.print(f"[dim]Verificando stories de @{username}...[/dim]")

            try:
                viewed = self.view_user_stories(user_id)
                stories_viewed += viewed
            except SystemExit:
                raise
            except Exception as exc:
                console.print(f"[red]Erro ao ver stories de @{username}:[/red] {exc}")
                errors += 1

        return {
            "users_checked": users_checked,
            "stories_viewed": stories_viewed,
            "errors": errors,
        }

    def react_to_stories(self, user_id: int, emoji: str = "\U0001f525") -> int:
        """
        Reage aos stories de um usuario usando a API nativa de reacao a stories.

        Args:
            user_id: ID numerico do usuario no Instagram.
            emoji: emoji para enviar como reacao.

        Returns:
            Numero de reacoes enviadas.
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return 0

        reactions_sent = 0

        try:
            stories = self._client.user_stories(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)
        except Exception as exc:
            console.print(f"[yellow]Erro ao buscar stories do user_id={user_id}:[/yellow] {exc}")
            self._rate_limiter.record_error(_ACTION_REACT)
            return 0

        if not stories:
            console.print(f"[dim]Nenhum story ativo para reagir (user_id={user_id}).[/dim]")
            return 0

        for story in stories:
            # FIX 9: verificar duplicata antes de reagir
            if self._action_log and self._action_log.already_acted(_ACTION_REACT, str(story.pk), hours=48):
                console.print(f"[dim]Story {story.pk} ja reagido recentemente. Pulando.[/dim]")
                continue

            if not self._rate_limiter.can_perform(_ACTION_REACT):
                console.print("[yellow]Limite de story_react atingido. Pausando.[/yellow]")
                break

            self._rate_limiter.wait_for_action(_ACTION_REACT)

            try:
                # FIX 1: Usar API nativa de reacao a stories em vez de direct_send (DM spam)
                self._client.story_send_reaction(story.pk, emoji)
                self._rate_limiter.record_action(_ACTION_REACT)
                self._rate_limiter.record_success(_ACTION_REACT)
                reactions_sent += 1
                console.print(f"[green]Reacao enviada:[/green] {emoji} para story {story.pk}")
                if self._action_log:
                    self._action_log.log(_ACTION_REACT, str(story.pk), str(user_id), "ok", f"emoji={emoji}")
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(
                    f"[red]Erro ao reagir ao story {story.pk}:[/red] {exc}"
                )
                self._rate_limiter.record_error(_ACTION_REACT)
                if self._action_log:
                    self._action_log.log(_ACTION_REACT, str(story.pk), str(user_id), "error", str(exc))

        return reactions_sent

    def react_new_followers_stories(self, emoji: str = "\U0001f525") -> dict:
        """
        Busca novos seguidores, ve stories e reage a eles.
        FIX 1: Stories sao buscados UMA unica vez por usuario (view + react no mesmo loop).

        Args:
            emoji: emoji para usar como reacao.

        Returns:
            {"users_checked": int, "stories_viewed": int, "reactions_sent": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"users_checked": 0, "stories_viewed": 0, "reactions_sent": 0, "errors": 0, "message": "Fora do horario"}

        from insta_app.features.monitoring import FollowerMonitor

        monitor = FollowerMonitor(self._client, data_dir="data")
        new_followers = monitor.get_new_followers(update_snapshot=False)

        users_checked = 0
        stories_viewed = 0
        reactions_sent = 0
        errors = 0

        if not new_followers:
            console.print("[yellow]Nenhum novo seguidor encontrado para reagir a stories.[/yellow]")
            return {"users_checked": 0, "stories_viewed": 0, "reactions_sent": 0, "errors": 0}

        console.print(
            f"[cyan]Visualizando e reagindo a stories de {len(new_followers)} novo(s) seguidor(es)...[/cyan]"
        )

        for user in new_followers:
            user_id = int(user.pk)
            username = user.username

            users_checked += 1
            console.print(f"[dim]Verificando stories de @{username}...[/dim]")

            try:
                # FIX 1: Buscar stories UMA unica vez e fazer view + react no mesmo loop
                stories = self._client.user_stories(user_id)
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(f"[red]Erro ao buscar stories de @{username}:[/red] {exc}")
                errors += 1
                continue

            if not stories:
                console.print(f"[dim]Nenhum story ativo para @{username}.[/dim]")
                continue

            for story in stories:
                # VIEW
                # FIX 9: verificar duplicata antes de visualizar
                view_skipped = False
                if self._action_log and self._action_log.already_acted(_ACTION_VIEW, str(story.pk), hours=24):
                    console.print(f"[dim]Story {story.pk} ja visto recentemente. Pulando view.[/dim]")
                    view_skipped = True

                if not view_skipped and self._rate_limiter.can_perform(_ACTION_VIEW):
                    self._rate_limiter.wait_for_action(_ACTION_VIEW)
                    try:
                        self._client.story_seen([story.pk])
                        self._rate_limiter.record_action(_ACTION_VIEW)
                        self._rate_limiter.record_success(_ACTION_VIEW)
                        stories_viewed += 1
                        console.print(f"[green]Story visto:[/green] {story.pk} de @{username}")
                        if self._action_log:
                            self._action_log.log(_ACTION_VIEW, str(story.pk), username, "ok")
                    except ChallengeRequired:
                        console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                        console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                        raise SystemExit(2)
                    except LoginRequired:
                        console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                        raise SystemExit(2)
                    except Exception as exc:
                        console.print(f"[red]Erro ao ver story {story.pk}:[/red] {exc}")
                        self._rate_limiter.record_error(_ACTION_VIEW)
                        if self._action_log:
                            self._action_log.log(_ACTION_VIEW, str(story.pk), username, "error", str(exc))
                        errors += 1

                # REACT (usando API nativa, nao DM)
                # FIX 9: verificar duplicata antes de reagir
                if self._action_log and self._action_log.already_acted(_ACTION_REACT, str(story.pk), hours=48):
                    console.print(f"[dim]Story {story.pk} ja reagido recentemente. Pulando react.[/dim]")
                    continue

                if self._rate_limiter.can_perform(_ACTION_REACT):
                    self._rate_limiter.wait_for_action(_ACTION_REACT)
                    try:
                        self._client.story_send_reaction(story.pk, emoji)
                        self._rate_limiter.record_action(_ACTION_REACT)
                        self._rate_limiter.record_success(_ACTION_REACT)
                        reactions_sent += 1
                        console.print(f"[green]Reacao enviada:[/green] {emoji} para story {story.pk} de @{username}")
                        if self._action_log:
                            self._action_log.log(_ACTION_REACT, str(story.pk), username, "ok", f"emoji={emoji}")
                    except ChallengeRequired:
                        console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                        console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                        raise SystemExit(2)
                    except LoginRequired:
                        console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                        raise SystemExit(2)
                    except Exception as exc:
                        console.print(f"[red]Erro ao reagir ao story {story.pk}:[/red] {exc}")
                        self._rate_limiter.record_error(_ACTION_REACT)
                        if self._action_log:
                            self._action_log.log(_ACTION_REACT, str(story.pk), username, "error", str(exc))
                        errors += 1

        return {
            "users_checked": users_checked,
            "stories_viewed": stories_viewed,
            "reactions_sent": reactions_sent,
            "errors": errors,
        }
