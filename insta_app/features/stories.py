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

_ACTION_VIEW = "story_view"
_ACTION_REACT = "story_react"


class StoryManager:
    def __init__(self, client: Client, rate_limiter: RateLimiter) -> None:
        """
        Gerencia visualizacoes e reacoes a stories com rate limiting.

        Args:
            client: instagrapi.Client ja autenticado.
            rate_limiter: instancia de RateLimiter para controlar cadencia.
        """
        self._client = client
        self._rate_limiter = rate_limiter

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
        stories_viewed = 0

        try:
            stories = self._client.user_stories(user_id)
        except Exception as exc:
            console.print(f"[yellow]Erro ao buscar stories do user_id={user_id}:[/yellow] {exc}")
            return 0

        if not stories:
            console.print(f"[dim]Nenhum story ativo para user_id={user_id}.[/dim]")
            return 0

        for story in stories:
            if not self._rate_limiter.can_perform(_ACTION_VIEW):
                console.print("[yellow]Limite de story_view atingido. Pausando.[/yellow]")
                break

            self._rate_limiter.wait_for_action(_ACTION_VIEW)

            try:
                self._client.story_seen([story.pk])
                self._rate_limiter.record_action(_ACTION_VIEW)
                stories_viewed += 1
                console.print(f"[green]Story visto:[/green] {story.pk}")
            except Exception as exc:
                console.print(f"[red]Erro ao marcar story {story.pk} como visto:[/red] {exc}")

        return stories_viewed

    def view_new_followers_stories(self) -> dict:
        """
        Busca novos seguidores e visualiza os stories de cada um.

        Returns:
            {"users_checked": int, "stories_viewed": int, "errors": int}
        """
        from insta_app.features.monitoring import FollowerMonitor

        monitor = FollowerMonitor(self._client, data_dir="data")
        new_followers = monitor.get_new_followers()

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
            except Exception as exc:
                console.print(f"[red]Erro ao buscar usuario @{username}:[/red] {exc}")
                errors += 1
                continue

            console.print(f"[dim]Verificando stories de @{username}...[/dim]")

            try:
                viewed = self.view_user_stories(user_id)
                stories_viewed += viewed
            except Exception as exc:
                console.print(f"[red]Erro ao ver stories de @{username}:[/red] {exc}")
                errors += 1

        return {
            "users_checked": users_checked,
            "stories_viewed": stories_viewed,
            "errors": errors,
        }

    def react_to_stories(self, user_id: int, emoji: str = "🔥") -> int:
        """
        Reage aos stories de um usuario com emoji via DM.

        Args:
            user_id: ID numerico do usuario no Instagram.
            emoji: emoji para enviar como reacao.

        Returns:
            Numero de reacoes enviadas.
        """
        reactions_sent = 0

        try:
            stories = self._client.user_stories(user_id)
        except Exception as exc:
            console.print(f"[yellow]Erro ao buscar stories do user_id={user_id}:[/yellow] {exc}")
            return 0

        if not stories:
            console.print(f"[dim]Nenhum story ativo para reagir (user_id={user_id}).[/dim]")
            return 0

        for story in stories:
            if not self._rate_limiter.can_perform(_ACTION_REACT):
                console.print("[yellow]Limite de story_react atingido. Pausando.[/yellow]")
                break

            self._rate_limiter.wait_for_action(_ACTION_REACT)

            try:
                self._client.direct_send(emoji, [user_id])
                self._rate_limiter.record_action(_ACTION_REACT)
                reactions_sent += 1
                console.print(f"[green]Reacao enviada:[/green] {emoji} para story {story.pk}")
            except Exception as exc:
                console.print(
                    f"[red]Erro ao reagir ao story {story.pk}:[/red] {exc}"
                )

        return reactions_sent

    def react_new_followers_stories(self, emoji: str = "🔥") -> dict:
        """
        Busca novos seguidores, ve stories e reage a eles.

        Args:
            emoji: emoji para usar como reacao.

        Returns:
            {"users_checked": int, "reactions_sent": int, "errors": int}
        """
        from insta_app.features.monitoring import FollowerMonitor

        monitor = FollowerMonitor(self._client, data_dir="data")
        new_followers = monitor.get_new_followers()

        users_checked = 0
        reactions_sent = 0
        errors = 0

        if not new_followers:
            console.print("[yellow]Nenhum novo seguidor encontrado para reagir a stories.[/yellow]")
            return {"users_checked": 0, "reactions_sent": 0, "errors": 0}

        console.print(
            f"[cyan]Reagindo a stories de {len(new_followers)} novo(s) seguidor(es)...[/cyan]"
        )

        for user in new_followers:
            user_id = int(user.pk)
            username = user.username

            users_checked += 1
            console.print(f"[dim]Verificando stories de @{username} para reagir...[/dim]")

            try:
                # Primeiro visualiza, depois reage
                self.view_user_stories(user_id)
                sent = self.react_to_stories(user_id, emoji=emoji)
                reactions_sent += sent
            except Exception as exc:
                console.print(f"[red]Erro ao reagir a stories de @{username}:[/red] {exc}")
                errors += 1

        return {
            "users_checked": users_checked,
            "reactions_sent": reactions_sent,
            "errors": errors,
        }
