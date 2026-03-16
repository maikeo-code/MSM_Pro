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

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from insta_app.core.action_log import ActionLog
    from insta_app.config import Settings

console = Console()

_ACTION = "like"


class LikeManager:
    def __init__(
        self,
        client: Client,
        rate_limiter: RateLimiter,
        action_log: ActionLog | None = None,
        dry_run: bool = False,
        settings: Settings | None = None,
    ) -> None:
        """
        Gerencia curtidas de forma segura e com rate limiting.

        Args:
            client: instagrapi.Client ja autenticado.
            rate_limiter: instancia de RateLimiter para controlar cadencia.
            action_log: instancia opcional de ActionLog para registrar acoes.
            dry_run: se True, simula acoes sem executar de verdade.
            settings: instancia de Settings para acesso a blacklist.
        """
        self._client = client
        self._rate_limiter = rate_limiter
        self._action_log = action_log
        self._dry_run = dry_run
        self._settings = settings

    # ------------------------------------------------------------------
    # Metodos publicos
    # ------------------------------------------------------------------

    def like_new_followers_posts(self, max_posts_per_user: int = 3) -> dict:
        """
        Busca novos seguidores e curte os ultimos N posts de cada um.

        Args:
            max_posts_per_user: numero maximo de posts para curtir por usuario.

        Returns:
            {"users_processed": int, "likes_given": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"users_processed": 0, "likes_given": 0, "errors": 0, "message": "Fora do horario"}

        from insta_app.features.monitoring import FollowerMonitor

        monitor = FollowerMonitor(self._client, data_dir="data")
        new_followers = monitor.get_new_followers(update_snapshot=False)

        users_processed = 0
        likes_given = 0
        errors = 0

        if not new_followers:
            console.print("[yellow]Nenhum novo seguidor encontrado para curtir posts.[/yellow]")
            return {"users_processed": 0, "likes_given": 0, "errors": 0}

        console.print(
            f"[cyan]Curtindo posts de {len(new_followers)} novo(s) seguidor(es)...[/cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Curtindo posts de novos seguidores...", total=len(new_followers))

            for user in new_followers:
                user_id = int(user.pk)
                username = user.username

                # Blacklist check
                if self._settings and username in self._settings.blacklist:
                    console.print(f"[dim]@{username} na blacklist. Pulando.[/dim]")
                    progress.advance(task)
                    continue

                if user.is_private:
                    console.print(f"[dim]@{username} tem perfil privado -- pulando.[/dim]")
                    progress.advance(task)
                    continue

                try:
                    medias = self._client.user_medias(user_id, amount=max_posts_per_user)
                except ChallengeRequired:
                    console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                    console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                    raise SystemExit(2)
                except LoginRequired:
                    console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                    raise SystemExit(2)
                except Exception as exc:
                    console.print(f"[yellow]Erro ao buscar posts de @{username}:[/yellow] {exc}")
                    self._rate_limiter.record_error(_ACTION)
                    errors += 1
                    progress.advance(task)
                    continue

                user_likes = 0
                for media in medias:
                    # Verificar duplicata antes de curtir
                    if self._action_log and self._action_log.already_acted(_ACTION, str(media.pk), hours=48):
                        console.print(f"[dim]Post {media.pk} ja curtido recentemente. Pulando.[/dim]")
                        continue

                    if not self._rate_limiter.can_perform(_ACTION):
                        console.print("[yellow]Limite de curtidas atingido. Pausando.[/yellow]")
                        break

                    if not self._dry_run:
                        self._rate_limiter.wait_for_action(_ACTION)

                    try:
                        if self._dry_run:
                            console.print(f"[dim][DRY-RUN] Curtindo post {media.pk} de @{username}[/dim]")
                        else:
                            self._client.media_like(media.pk)
                        if not self._dry_run:
                            self._rate_limiter.record_action(_ACTION)
                            self._rate_limiter.record_success(_ACTION)
                        user_likes += 1
                        likes_given += 1
                        if not self._dry_run:
                            console.print(
                                f"[green]Curtida:[/green] post {media.pk} de @{username}"
                            )
                        if self._action_log and not self._dry_run:
                            self._action_log.log(_ACTION, str(media.pk), username, "ok")
                    except ChallengeRequired:
                        console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                        console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                        raise SystemExit(2)
                    except LoginRequired:
                        console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                        raise SystemExit(2)
                    except Exception as exc:
                        console.print(
                            f"[red]Erro ao curtir post {media.pk} de @{username}:[/red] {exc}"
                        )
                        self._rate_limiter.record_error(_ACTION)
                        errors += 1
                        if self._action_log:
                            self._action_log.log(_ACTION, str(media.pk), username, "error", str(exc))

                if user_likes > 0:
                    users_processed += 1

                progress.advance(task)

        return {
            "users_processed": users_processed,
            "likes_given": likes_given,
            "errors": errors,
        }

    def like_user_posts(self, username: str, amount: int = 3) -> dict:
        """
        Curte os ultimos N posts de um usuario especifico.

        Args:
            username: nome de usuario do Instagram (sem @).
            amount: numero de posts para curtir.

        Returns:
            {"username": str, "likes_given": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"username": username, "likes_given": 0, "errors": 0, "message": "Fora do horario"}

        username = username.lstrip("@")
        likes_given = 0
        errors = 0

        # Blacklist check
        if self._settings and username in self._settings.blacklist:
            console.print(f"[dim]@{username} na blacklist. Pulando.[/dim]")
            return {"username": username, "likes_given": 0, "errors": 0}

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
            return {"username": username, "likes_given": 0, "errors": 1}

        if user_info.is_private:
            console.print(f"[yellow]@{username} tem perfil privado -- impossivel ver posts.[/yellow]")
            return {"username": username, "likes_given": 0, "errors": 0}

        try:
            medias = self._client.user_medias(user_id, amount=amount)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)
        except Exception as exc:
            console.print(f"[red]Erro ao buscar posts de @{username}:[/red] {exc}")
            return {"username": username, "likes_given": 0, "errors": 1}

        console.print(
            f"[cyan]Curtindo {len(medias)} post(s) de @{username}...[/cyan]"
        )

        for media in medias:
            # Verificar duplicata antes de curtir
            if self._action_log and self._action_log.already_acted(_ACTION, str(media.pk), hours=48):
                console.print(f"[dim]Post {media.pk} ja curtido recentemente. Pulando.[/dim]")
                continue

            if not self._rate_limiter.can_perform(_ACTION):
                console.print("[yellow]Limite de curtidas atingido. Pausando.[/yellow]")
                break

            if not self._dry_run:
                self._rate_limiter.wait_for_action(_ACTION)

            try:
                if self._dry_run:
                    console.print(f"[dim][DRY-RUN] Curtindo post {media.pk} de @{username}[/dim]")
                else:
                    self._client.media_like(media.pk)
                if not self._dry_run:
                    self._rate_limiter.record_action(_ACTION)
                    self._rate_limiter.record_success(_ACTION)
                likes_given += 1
                if not self._dry_run:
                    console.print(f"[green]Curtida:[/green] post {media.pk} de @{username}")
                if self._action_log and not self._dry_run:
                    self._action_log.log(_ACTION, str(media.pk), username, "ok")
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(
                    f"[red]Erro ao curtir post {media.pk} de @{username}:[/red] {exc}"
                )
                self._rate_limiter.record_error(_ACTION)
                errors += 1
                if self._action_log:
                    self._action_log.log(_ACTION, str(media.pk), username, "error", str(exc))

        return {"username": username, "likes_given": likes_given, "errors": errors}

    def like_list_posts(self, usernames: list[str], max_posts_per_user: int = 3) -> dict:
        """
        Curte posts de uma lista de usernames.

        Args:
            usernames: lista de nomes de usuario (com ou sem @).
            max_posts_per_user: numero maximo de posts por usuario.

        Returns:
            {"users_processed": int, "likes_given": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"users_processed": 0, "likes_given": 0, "errors": 0, "message": "Fora do horario"}

        users_processed = 0
        total_likes = 0
        total_errors = 0

        console.print(
            f"[cyan]Curtindo posts de {len(usernames)} usuario(s)...[/cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Curtindo posts da lista...", total=len(usernames))

            for username in usernames:
                result = self.like_user_posts(username, amount=max_posts_per_user)
                if result["likes_given"] > 0:
                    users_processed += 1
                total_likes += result["likes_given"]
                total_errors += result["errors"]
                progress.advance(task)

        return {
            "users_processed": users_processed,
            "likes_given": total_likes,
            "errors": total_errors,
        }

    def like_commenters_posts(self, amount: int = 3) -> dict:
        """
        Busca seus posts recentes, identifica comentaristas e curte posts deles.

        Args:
            amount: numero de posts para curtir por comentarista.

        Returns:
            {"commenters_found": int, "likes_given": int, "errors": int}
        """
        # FIX 7: Verificar horario permitido
        if not self._rate_limiter.is_within_schedule():
            console.print("[yellow]Fora do horario permitido. Acoes suspensas.[/yellow]")
            return {"commenters_found": 0, "likes_given": 0, "errors": 0, "message": "Fora do horario"}

        commenters_found = 0
        likes_given = 0
        errors = 0

        console.print("[dim]Buscando seus posts recentes...[/dim]")

        try:
            my_medias = self._client.user_medias(self._client.user_id, amount=10)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)
        except Exception as exc:
            console.print(f"[red]Erro ao buscar seus posts:[/red] {exc}")
            return {"commenters_found": 0, "likes_given": 0, "errors": 1}

        seen_commenter_ids: set[int] = set()

        # First pass: collect all unique commenters
        all_commenters: list[tuple[int, str]] = []

        for media in my_medias:
            console.print(f"[dim]Buscando comentaristas do post {media.pk}...[/dim]")
            try:
                comments = self._client.media_comments(media.pk)
            except ChallengeRequired:
                console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
                console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
                raise SystemExit(2)
            except LoginRequired:
                console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
                raise SystemExit(2)
            except Exception as exc:
                console.print(f"[yellow]Erro ao buscar comentarios do post {media.pk}:[/yellow] {exc}")
                self._rate_limiter.record_error(_ACTION)
                errors += 1
                continue

            for comment in comments:
                commenter_id = int(comment.user.pk)
                commenter_username = comment.user.username

                if commenter_id == int(self._client.user_id):
                    continue
                if commenter_id in seen_commenter_ids:
                    continue

                seen_commenter_ids.add(commenter_id)
                all_commenters.append((commenter_id, commenter_username))

        # Second pass: like posts with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Curtindo posts de comentaristas...", total=len(all_commenters))

            for commenter_id, commenter_username in all_commenters:
                # Blacklist check
                if self._settings and commenter_username in self._settings.blacklist:
                    console.print(f"[dim]@{commenter_username} na blacklist. Pulando.[/dim]")
                    progress.advance(task)
                    continue

                commenters_found += 1
                console.print(f"[cyan]Curtindo posts de comentarista @{commenter_username}...[/cyan]")

                result = self.like_user_posts(commenter_username, amount=amount)
                likes_given += result["likes_given"]
                errors += result["errors"]
                progress.advance(task)

        return {
            "commenters_found": commenters_found,
            "likes_given": likes_given,
            "errors": errors,
        }
