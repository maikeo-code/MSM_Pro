import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from insta_app.config import Settings, _CONFIG_FILE
from insta_app.core.rate_limiter import RateLimiter
from insta_app.core.session import SessionManager

console = Console()


# ---------------------------------------------------------------------------
# Helpers compartilhados pelos novos comandos
# ---------------------------------------------------------------------------

def _get_logged_client():
    """
    Carrega sessao e retorna (settings, manager, client).
    Encerra o processo se a sessao nao for valida.
    """
    settings = _load_settings()
    manager = SessionManager(settings)
    if not manager.load_session():
        console.print(
            Panel(
                "[bold red]Sessao nao encontrada ou expirada.[/bold red]\n"
                "Execute [bold]python -m insta_app.app login[/bold] primeiro.",
                title="Erro de Autenticacao",
            )
        )
        raise SystemExit(1)
    return settings, manager, manager.get_client()


def _parse_selection(selection: str, max_index: int) -> list[int]:
    """
    Converte string de selecao em lista de indices (1-based).
    Aceita: "todos", "nenhum", "1,3,5-10", etc.
    Retorna lista de indices 0-based para acesso em lista.
    """
    selection = selection.strip().lower()

    if selection in ("nenhum", "n", ""):
        return []

    if selection in ("todos", "t", "all", "a"):
        return list(range(max_index))

    indices: list[int] = []
    parts = [p.strip() for p in selection.split(",")]
    for part in parts:
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start = int(bounds[0])
                end = int(bounds[1])
                for i in range(start, end + 1):
                    if 1 <= i <= max_index:
                        indices.append(i - 1)
            except ValueError:
                console.print(f"[yellow]Intervalo invalido ignorado: {part}[/yellow]")
        else:
            try:
                i = int(part)
                if 1 <= i <= max_index:
                    indices.append(i - 1)
                else:
                    console.print(f"[yellow]Numero fora do intervalo ignorado: {i}[/yellow]")
            except ValueError:
                console.print(f"[yellow]Valor invalido ignorado: {part}[/yellow]")

    return indices


def _load_settings() -> Settings:
    return Settings.load_from_file(str(_CONFIG_FILE)) if _CONFIG_FILE.exists() else Settings()


@click.group()
def insta() -> None:
    """InstaApp — Automacao segura do Instagram."""
    pass


@insta.command()
@click.option("--username", "-u", prompt="Usuario do Instagram", help="Seu usuario do Instagram")
@click.option(
    "--password",
    "-p",
    prompt="Senha",
    hide_input=True,
    help="Sua senha do Instagram",
)
def login(username: str, password: str) -> None:
    """Faz login no Instagram e salva a sessao."""
    settings = _load_settings()
    settings.username = username
    manager = SessionManager(settings)

    console.print(Panel(f"Realizando login como [bold]{username}[/bold]", title="Login"))

    # Tenta carregar sessao existente primeiro
    if manager.load_session():
        console.print("[green]Sessao existente valida. Nao e necessario novo login.[/green]")
        return

    success = manager.login(username, password)
    if success:
        # Salva username nas configuracoes
        settings.save_to_file(str(_CONFIG_FILE))
        console.print(Panel("[bold green]Login realizado com sucesso![/bold green]", title="Sucesso"))
    else:
        console.print(Panel("[bold red]Falha no login.[/bold red]", title="Erro"))
        raise SystemExit(1)


@insta.command()
def status() -> None:
    """Exibe status da sessao e limites de acoes restantes."""
    settings = _load_settings()
    manager = SessionManager(settings)
    rate_limiter = RateLimiter(settings)

    # Verifica sessao
    logged_in = manager.load_session()
    username = settings.username or "Desconhecido"

    # Painel de status da sessao
    status_text = "[bold green]Conectado[/bold green]" if logged_in else "[bold red]Desconectado[/bold red]"
    schedule_ok = rate_limiter.is_within_schedule()
    schedule_text = "[green]Dentro do horario[/green]" if schedule_ok else "[yellow]Fora do horario[/yellow]"

    console.print(
        Panel(
            f"Usuario: [bold]{username}[/bold]\n"
            f"Sessao: {status_text}\n"
            f"Horario: {schedule_text} "
            f"({settings.schedule_hours[0]}h - {settings.schedule_hours[1]}h)",
            title="Status da Sessao",
        )
    )

    # Tabela de limites restantes
    table = Table(title="Limites de Acoes Restantes", show_header=True, header_style="bold cyan")
    table.add_column("Acao", style="dim", width=16)
    table.add_column("Restam (hora)", justify="center")
    table.add_column("Restam (dia)", justify="center")
    table.add_column("Limite/hora", justify="center")
    table.add_column("Limite/dia", justify="center")

    for action, limits in settings.rate_limits.items():
        remaining = rate_limiter.get_remaining(action)
        hour_color = "green" if remaining["hour"] > 0 else "red"
        day_color = "green" if remaining["day"] > 0 else "red"
        table.add_row(
            action,
            f"[{hour_color}]{remaining['hour']}[/{hour_color}]",
            f"[{day_color}]{remaining['day']}[/{day_color}]",
            str(limits.per_hour),
            str(limits.per_day),
        )

    console.print(table)


@insta.command()
def logout() -> None:
    """Encerra a sessao do Instagram."""
    settings = _load_settings()
    manager = SessionManager(settings)

    console.print(Panel("Encerrando sessao...", title="Logout"))

    session_loaded = manager.load_session()
    if session_loaded:
        manager.logout()
    else:
        # Remove arquivo de sessao mesmo se nao conseguiu carregar
        from pathlib import Path
        session_path = Path(settings.session_file)
        if session_path.exists():
            session_path.unlink()
            console.print("[dim]Arquivo de sessao removido.[/dim]")
        else:
            console.print("[yellow]Nenhuma sessao ativa encontrada.[/yellow]")
            return

    console.print(Panel("[bold green]Sessao encerrada com sucesso.[/bold green]", title="Logout"))


@insta.command("followers")
def cmd_followers() -> None:
    """Exibe stats de seguidores: novos, unfollowers, nao seguem de volta e fas."""
    settings, manager, client = _get_logged_client()

    from insta_app.features.monitoring import FollowerMonitor

    monitor = FollowerMonitor(client, data_dir="data")

    console.print(Panel("[bold cyan]Buscando dados de seguidores...[/bold cyan]", title="Monitoramento"))

    stats = monitor.get_stats()
    monitor.save_history(stats)

    # Painel de estatisticas gerais
    console.print(
        Panel(
            f"Seguidores:          [bold green]{stats['followers']}[/bold green]\n"
            f"Seguindo:            [bold blue]{stats['following']}[/bold blue]\n"
            f"Novos seguidores:    [bold yellow]{stats['new_followers']}[/bold yellow]\n"
            f"Deixaram de seguir:  [bold red]{stats['unfollowers']}[/bold red]\n"
            f"Nao seguem de volta: [bold magenta]{stats['not_following_back']}[/bold magenta]\n"
            f"Fas (seguem voce):   [bold cyan]{stats['fans']}[/bold cyan]",
            title="Resumo de Seguidores",
        )
    )

    # Tabela de detalhes
    table = Table(title="Detalhes", show_header=True, header_style="bold cyan")
    table.add_column("Metrica", style="dim", width=28)
    table.add_column("Quantidade", justify="center")

    rows = [
        ("Seguidores totais", str(stats["followers"]), "green"),
        ("Seguindo totais", str(stats["following"]), "blue"),
        ("Novos seguidores (vs snapshot)", str(stats["new_followers"]), "yellow"),
        ("Deixaram de seguir", str(stats["unfollowers"]), "red"),
        ("Nao seguem de volta", str(stats["not_following_back"]), "magenta"),
        ("Fas (voce nao segue)", str(stats["fans"]), "cyan"),
    ]
    for label, value, color in rows:
        table.add_row(label, f"[{color}]{value}[/{color}]")

    console.print(table)


@insta.command("not-following-back")
def cmd_not_following_back() -> None:
    """Lista quem nao te segue de volta e oferece opcao de unfollow."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.monitoring import FollowerMonitor
    from insta_app.features.unfollow import UnfollowManager

    monitor = FollowerMonitor(client, data_dir="data")

    console.print(Panel("[bold cyan]Buscando quem nao te segue de volta...[/bold cyan]", title="Analise"))

    not_following_back = monitor.get_not_following_back()

    if not not_following_back:
        console.print(Panel("[bold green]Todos que voce segue te seguem de volta![/bold green]", title="Resultado"))
        return

    table = Table(title=f"Nao seguem de volta ({len(not_following_back)})", show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", width=5)
    table.add_column("Username", style="bold")
    table.add_column("Nome Completo")

    for i, user in enumerate(not_following_back, start=1):
        table.add_row(str(i), f"@{user.username}", user.full_name or "")

    console.print(table)

    # Pergunta se quer selecionar para unfollow
    selection = Prompt.ask(
        '\nSelecione para unfollow ("todos", numeros como "1,3,5-10", ou "nenhum")',
        default="nenhum",
    )

    chosen_indices = _parse_selection(selection, len(not_following_back))
    if not chosen_indices:
        console.print("[dim]Nenhum usuario selecionado. Saindo.[/dim]")
        return

    chosen_users = [not_following_back[i] for i in chosen_indices]
    chosen_ids = [int(u.pk) for u in chosen_users]

    console.print(f"[yellow]{len(chosen_ids)} usuario(s) selecionado(s).[/yellow]")
    for u in chosen_users:
        console.print(f"  - @{u.username}")

    when = Prompt.ask(
        '\nQuando executar? ("agora" ou horario no formato HH:MM)',
        default="agora",
    )

    unfollow_mgr = UnfollowManager(client, rate_limiter, data_dir="data")
    result = unfollow_mgr.schedule_unfollow(chosen_ids)

    if when.strip().lower() == "agora":
        console.print(Panel("[bold cyan]Executando unfollows agora...[/bold cyan]", title="Unfollow"))
        exec_result = unfollow_mgr.execute_unfollow_queue()
        console.print(
            Panel(
                f"Concluidos: [green]{exec_result['completed']}[/green]\n"
                f"Falhos:     [red]{exec_result['failed']}[/red]\n"
                f"Pendentes:  [yellow]{exec_result['remaining']}[/yellow]",
                title="Resultado",
            )
        )
    else:
        console.print(
            Panel(
                f"[green]{result['total']}[/green] unfollows agendados.\n"
                f"Tempo estimado: [cyan]{result['estimated_time']}[/cyan]\n"
                f"Horario solicitado: [yellow]{when}[/yellow]\n\n"
                "Execute [bold]python -m insta_app.app unfollow-queue --execute[/bold] para iniciar.",
                title="Agendado",
            )
        )


@insta.command("unfollow-queue")
@click.option("--execute", is_flag=True, default=False, help="Executa a fila de unfollows pendentes.")
@click.option("--cancel", is_flag=True, default=False, help="Cancela a fila de unfollows.")
def cmd_unfollow_queue(execute: bool, cancel: bool) -> None:
    """Gerencia a fila de unfollows pendentes."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.unfollow import UnfollowManager

    unfollow_mgr = UnfollowManager(client, rate_limiter, data_dir="data")

    if cancel:
        unfollow_mgr.cancel_unfollow_queue()
        return

    if execute:
        status_info = unfollow_mgr.get_queue_status()
        if status_info is None:
            console.print(Panel("[yellow]Nenhuma fila de unfollow encontrada.[/yellow]", title="Fila"))
            return

        console.print(
            Panel(
                f"Pendentes:  [yellow]{status_info['pending']}[/yellow]\n"
                f"Concluidos: [green]{status_info['completed']}[/green]\n"
                f"Falhos:     [red]{status_info['failed']}[/red]\n"
                f"Criada em:  [dim]{status_info['created_at']}[/dim]",
                title="Fila Atual",
            )
        )
        console.print(Panel("[bold cyan]Executando fila de unfollows...[/bold cyan]", title="Unfollow"))
        result = unfollow_mgr.execute_unfollow_queue()
        console.print(
            Panel(
                f"Concluidos: [green]{result['completed']}[/green]\n"
                f"Falhos:     [red]{result['failed']}[/red]\n"
                f"Pendentes:  [yellow]{result['remaining']}[/yellow]",
                title="Resultado",
            )
        )
        return

    # Apenas exibe o status
    status_info = unfollow_mgr.get_queue_status()
    if status_info is None:
        console.print(Panel("[yellow]Nenhuma fila de unfollow encontrada.[/yellow]", title="Fila"))
        return

    table = Table(title="Status da Fila de Unfollow", show_header=True, header_style="bold cyan")
    table.add_column("Campo", style="dim", width=16)
    table.add_column("Valor", justify="center")

    table.add_row("Criada em", status_info["created_at"])
    table.add_row("Pendentes", f"[yellow]{status_info['pending']}[/yellow]")
    table.add_row("Concluidos", f"[green]{status_info['completed']}[/green]")
    table.add_row("Falhos", f"[red]{status_info['failed']}[/red]")

    console.print(table)
    console.print(
        "\nUse [bold]--execute[/bold] para processar a fila ou [bold]--cancel[/bold] para cancelar."
    )


@insta.command("unfollowers")
def cmd_unfollowers() -> None:
    """Lista quem parou de te seguir recentemente (comparado ao ultimo snapshot)."""
    settings, manager, client = _get_logged_client()

    from insta_app.features.monitoring import FollowerMonitor

    monitor = FollowerMonitor(client, data_dir="data")

    console.print(Panel("[bold cyan]Verificando quem deixou de te seguir...[/bold cyan]", title="Unfollowers"))

    unfollowers = monitor.get_unfollowers()

    if not unfollowers:
        console.print(Panel("[bold green]Ninguem deixou de te seguir desde o ultimo snapshot.[/bold green]", title="Resultado"))
        return

    table = Table(title=f"Deixaram de seguir ({len(unfollowers)})", show_header=True, header_style="bold red")
    table.add_column("#", justify="right", width=5)
    table.add_column("User ID", style="dim", width=14)
    table.add_column("Username", style="bold")

    for i, entry in enumerate(unfollowers, start=1):
        table.add_row(str(i), str(entry["user_id"]), f"@{entry['username']}")

    console.print(table)


@insta.command("like-new")
@click.option(
    "--max-posts",
    default=3,
    show_default=True,
    help="Numero maximo de posts para curtir por usuario.",
)
def cmd_like_new(max_posts: int) -> None:
    """Curte posts dos novos seguidores."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter)

    console.print(
        Panel(
            f"[bold cyan]Curtindo ate {max_posts} post(s) de cada novo seguidor...[/bold cyan]",
            title="Like — Novos Seguidores",
        )
    )

    result = like_mgr.like_new_followers_posts(max_posts_per_user=max_posts)

    console.print(
        Panel(
            f"Usuarios processados: [green]{result['users_processed']}[/green]\n"
            f"Curtidas dadas:       [green]{result['likes_given']}[/green]\n"
            f"Erros:                [red]{result['errors']}[/red]",
            title="Resultado",
        )
    )


@insta.command("like-user")
@click.argument("username")
@click.option(
    "--amount",
    default=3,
    show_default=True,
    help="Numero de posts para curtir.",
)
def cmd_like_user(username: str, amount: int) -> None:
    """Curte posts de um usuario especifico. USERNAME pode conter @ ou nao."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter)
    clean_username = username.lstrip("@")

    console.print(
        Panel(
            f"[bold cyan]Curtindo {amount} post(s) de @{clean_username}...[/bold cyan]",
            title="Like — Usuario Especifico",
        )
    )

    result = like_mgr.like_user_posts(clean_username, amount=amount)

    console.print(
        Panel(
            f"Usuario:        [bold]@{result['username']}[/bold]\n"
            f"Curtidas dadas: [green]{result['likes_given']}[/green]\n"
            f"Erros:          [red]{result['errors']}[/red]",
            title="Resultado",
        )
    )


@insta.command("like-commenters")
def cmd_like_commenters() -> None:
    """Curte posts de quem comentou nos seus posts recentes."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter)

    console.print(
        Panel(
            "[bold cyan]Identificando comentaristas e curtindo seus posts...[/bold cyan]",
            title="Like — Comentaristas",
        )
    )

    result = like_mgr.like_commenters_posts()

    console.print(
        Panel(
            f"Comentaristas encontrados: [cyan]{result['commenters_found']}[/cyan]\n"
            f"Curtidas dadas:            [green]{result['likes_given']}[/green]\n"
            f"Erros:                     [red]{result['errors']}[/red]",
            title="Resultado",
        )
    )


@insta.command("stories")
@click.option(
    "--react/--no-react",
    default=True,
    show_default=True,
    help="Reagir aos stories alem de visualizar.",
)
@click.option(
    "--emoji",
    default="🔥",
    show_default=True,
    help="Emoji usado como reacao.",
)
def cmd_stories(react: bool, emoji: str) -> None:
    """Visualiza (e opcionalmente reage a) stories de novos seguidores."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.stories import StoryManager

    story_mgr = StoryManager(client, rate_limiter)

    if react:
        console.print(
            Panel(
                f"[bold cyan]Visualizando e reagindo com {emoji} a stories de novos seguidores...[/bold cyan]",
                title="Stories — Novos Seguidores",
            )
        )
        result = story_mgr.react_new_followers_stories(emoji=emoji)
        console.print(
            Panel(
                f"Usuarios verificados: [cyan]{result['users_checked']}[/cyan]\n"
                f"Reacoes enviadas:     [green]{result['reactions_sent']}[/green]\n"
                f"Erros:                [red]{result['errors']}[/red]",
                title="Resultado",
            )
        )
    else:
        console.print(
            Panel(
                "[bold cyan]Visualizando stories de novos seguidores...[/bold cyan]",
                title="Stories — Novos Seguidores",
            )
        )
        result = story_mgr.view_new_followers_stories()
        console.print(
            Panel(
                f"Usuarios verificados: [cyan]{result['users_checked']}[/cyan]\n"
                f"Stories vistos:       [green]{result['stories_viewed']}[/green]\n"
                f"Erros:                [red]{result['errors']}[/red]",
                title="Resultado",
            )
        )


@insta.command("stories-user")
@click.argument("username")
@click.option(
    "--react/--no-react",
    default=True,
    show_default=True,
    help="Reagir aos stories alem de visualizar.",
)
@click.option(
    "--emoji",
    default="🔥",
    show_default=True,
    help="Emoji usado como reacao.",
)
def cmd_stories_user(username: str, react: bool, emoji: str) -> None:
    """Visualiza (e opcionalmente reage a) stories de um usuario especifico. USERNAME pode conter @ ou nao."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)

    from insta_app.features.stories import StoryManager

    story_mgr = StoryManager(client, rate_limiter)
    clean_username = username.lstrip("@")

    try:
        user_info = client.user_info_by_username(clean_username)
        user_id = int(user_info.pk)
    except Exception as exc:
        console.print(
            Panel(
                f"[bold red]Erro ao buscar usuario @{clean_username}:[/bold red] {exc}",
                title="Erro",
            )
        )
        raise SystemExit(1)

    if react:
        console.print(
            Panel(
                f"[bold cyan]Visualizando stories de @{clean_username} e reagindo com {emoji}...[/bold cyan]",
                title="Stories — Usuario Especifico",
            )
        )
        viewed = story_mgr.view_user_stories(user_id)
        reactions = story_mgr.react_to_stories(user_id, emoji=emoji)
        console.print(
            Panel(
                f"Stories vistos:   [green]{viewed}[/green]\n"
                f"Reacoes enviadas: [green]{reactions}[/green]",
                title="Resultado",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold cyan]Visualizando stories de @{clean_username}...[/bold cyan]",
                title="Stories — Usuario Especifico",
            )
        )
        viewed = story_mgr.view_user_stories(user_id)
        console.print(
            Panel(
                f"Stories vistos: [green]{viewed}[/green]",
                title="Resultado",
            )
        )


if __name__ == "__main__":
    insta()
