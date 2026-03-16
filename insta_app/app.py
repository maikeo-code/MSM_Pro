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

    return sorted(set(indices))


def _load_settings() -> Settings:
    return Settings.load_from_file(str(_CONFIG_FILE)) if _CONFIG_FILE.exists() else Settings()


@click.group()
@click.option("--dry-run", is_flag=True, default=False, help="Simula acoes sem executar de verdade.")
@click.pass_context
def insta(ctx: click.Context, dry_run: bool) -> None:
    """InstaApp — Automacao segura do Instagram."""
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = dry_run
    if dry_run:
        console.print(Panel("[bold yellow]MODO DRY-RUN ATIVO[/bold yellow] — Nenhuma acao sera executada de verdade.", title="Dry-Run"))


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

    # FIX 3: Warmup status
    warmup = rate_limiter.get_warmup_status()
    if warmup["enabled"]:
        if warmup["completed"]:
            warmup_text = "[green]Concluido (100%)[/green]"
        else:
            warmup_text = (
                f"[yellow]Dia {warmup['days_active']}/{warmup['days_total']} "
                f"({warmup['percentage']}%)[/yellow]"
            )
    else:
        warmup_text = "[dim]Desabilitado[/dim]"

    console.print(
        Panel(
            f"Usuario: [bold]{username}[/bold]\n"
            f"Sessao: {status_text}\n"
            f"Horario: {schedule_text} "
            f"({settings.schedule_hours[0]}h - {settings.schedule_hours[1]}h)\n"
            f"Warm-up: {warmup_text}",
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
@click.pass_context
def cmd_not_following_back(ctx: click.Context) -> None:
    """Lista quem nao te segue de volta e oferece opcao de unfollow."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

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

    unfollow_mgr = UnfollowManager(client, rate_limiter, data_dir="data", dry_run=dry_run, settings=settings)
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
@click.pass_context
def cmd_unfollow_queue(ctx: click.Context, execute: bool, cancel: bool) -> None:
    """Gerencia a fila de unfollows pendentes."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.unfollow import UnfollowManager

    unfollow_mgr = UnfollowManager(client, rate_limiter, data_dir="data", dry_run=dry_run, settings=settings)

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
@click.pass_context
def cmd_like_new(ctx: click.Context, max_posts: int) -> None:
    """Curte posts dos novos seguidores."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter, dry_run=dry_run, settings=settings)

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
@click.pass_context
def cmd_like_user(ctx: click.Context, username: str, amount: int) -> None:
    """Curte posts de um usuario especifico. USERNAME pode conter @ ou nao."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter, dry_run=dry_run, settings=settings)
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
@click.pass_context
def cmd_like_commenters(ctx: click.Context) -> None:
    """Curte posts de quem comentou nos seus posts recentes."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.likes import LikeManager

    like_mgr = LikeManager(client, rate_limiter, dry_run=dry_run, settings=settings)

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
@click.pass_context
def cmd_stories(ctx: click.Context, react: bool, emoji: str) -> None:
    """Visualiza (e opcionalmente reage a) stories de novos seguidores."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.stories import StoryManager

    story_mgr = StoryManager(client, rate_limiter, dry_run=dry_run, settings=settings)

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
@click.pass_context
def cmd_stories_user(ctx: click.Context, username: str, react: bool, emoji: str) -> None:
    """Visualiza (e opcionalmente reage a) stories de um usuario especifico. USERNAME pode conter @ ou nao."""
    settings, manager, client = _get_logged_client()
    rate_limiter = RateLimiter(settings)
    dry_run = ctx.obj.get("dry_run", False)

    from insta_app.features.stories import StoryManager

    story_mgr = StoryManager(client, rate_limiter, dry_run=dry_run, settings=settings)
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


@insta.command("report")
@click.option("--days", default=7, show_default=True, help="Periodo do relatorio em dias.")
def cmd_report(days: int) -> None:
    """Mostra relatorio de atividade dos ultimos N dias."""
    import sqlite3
    from datetime import datetime, timedelta
    from pathlib import Path

    db_path = Path("data/actions.db")
    if not db_path.exists():
        console.print(
            Panel(
                "[yellow]Nenhum registro de acoes encontrado.[/yellow]\n"
                "Execute algumas acoes primeiro (like-new, stories, etc.).",
                title="Relatorio",
            )
        )
        return

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT action_type, status, COUNT(*) as cnt
        FROM actions
        WHERE timestamp >= ?
        GROUP BY action_type, status
        ORDER BY action_type, status
        """,
        (cutoff,),
    ).fetchall()
    conn.close()

    if not rows:
        console.print(
            Panel(
                f"[yellow]Nenhuma acao registrada nos ultimos {days} dias.[/yellow]",
                title="Relatorio",
            )
        )
        return

    # Agrupa por action_type
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        action_type = row["action_type"]
        status = row["status"]
        count = row["cnt"]
        if action_type not in summary:
            summary[action_type] = {}
        summary[action_type][status] = count

    table = Table(title=f"Relatorio de Atividade - Ultimos {days} dias")
    table.add_column("Acao", style="cyan")
    table.add_column("Sucesso", style="green", justify="right")
    table.add_column("Falha", style="red", justify="right")
    table.add_column("Total", style="bold", justify="right")

    for action_type, counts in sorted(summary.items()):
        ok_count = counts.get("ok", 0)
        error_count = counts.get("error", 0)
        table.add_row(
            action_type,
            str(ok_count),
            str(error_count),
            str(ok_count + error_count),
        )

    console.print(table)


@insta.command("commit-snapshot")
def cmd_commit_snapshot() -> None:
    """Salva o snapshot atual de seguidores, marcando-os como processados."""
    settings, manager, client = _get_logged_client()

    from insta_app.features.monitoring import FollowerMonitor

    monitor = FollowerMonitor(client, data_dir="data")

    console.print(Panel("[bold cyan]Atualizando snapshot de seguidores...[/bold cyan]", title="Snapshot"))

    monitor.commit_snapshot()

    console.print(
        Panel(
            "[bold green]Snapshot atualizado com sucesso.[/bold green]\n"
            "Novos seguidores serao calculados a partir deste ponto.",
            title="Resultado",
        )
    )


# ---------------------------------------------------------------------------
# Comandos de configuracao: presets, whitelist/blacklist, proxy
# ---------------------------------------------------------------------------


@insta.command("preset")
@click.argument("name", type=click.Choice(["conservador", "moderado", "agressivo"]))
def cmd_preset(name: str) -> None:
    """Aplica um preset de comportamento (conservador, moderado, agressivo)."""
    settings = _load_settings()
    settings.apply_preset(name)
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(
        Panel(
            f"Preset [bold]{name}[/bold] aplicado com sucesso!\n"
            f"Os novos limites de taxa estao ativos.",
            title="Preset Aplicado",
        )
    )

    # Mostra os novos limites
    table = Table(title=f"Limites do preset '{name}'", show_header=True, header_style="bold cyan")
    table.add_column("Acao", style="dim", width=16)
    table.add_column("Por hora", justify="center")
    table.add_column("Por dia", justify="center")
    table.add_column("Delay min (s)", justify="center")
    table.add_column("Delay max (s)", justify="center")

    for action, limits in settings.rate_limits.items():
        table.add_row(
            action,
            str(limits.per_hour),
            str(limits.per_day),
            f"{limits.delay_min:.0f}",
            f"{limits.delay_max:.0f}",
        )

    console.print(table)


@insta.command("whitelist-add")
@click.argument("username")
def cmd_whitelist_add(username: str) -> None:
    """Adiciona username a whitelist (nunca dar unfollow)."""
    username = username.lstrip("@")
    settings = _load_settings()
    if username in settings.whitelist:
        console.print(f"[yellow]@{username} ja esta na whitelist.[/yellow]")
        return
    settings.whitelist.append(username)
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(f"[green]@{username} adicionado a whitelist.[/green]")


@insta.command("whitelist-remove")
@click.argument("username")
def cmd_whitelist_remove(username: str) -> None:
    """Remove username da whitelist."""
    username = username.lstrip("@")
    settings = _load_settings()
    if username not in settings.whitelist:
        console.print(f"[yellow]@{username} nao esta na whitelist.[/yellow]")
        return
    settings.whitelist.remove(username)
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(f"[green]@{username} removido da whitelist.[/green]")


@insta.command("whitelist-show")
def cmd_whitelist_show() -> None:
    """Exibe a whitelist atual (usernames que nunca serao unfollowed)."""
    settings = _load_settings()
    if not settings.whitelist:
        console.print("[dim]Whitelist vazia.[/dim]")
        return

    table = Table(title=f"Whitelist ({len(settings.whitelist)} usuarios)", show_header=True, header_style="bold green")
    table.add_column("#", justify="right", width=5)
    table.add_column("Username", style="bold")

    for i, username in enumerate(settings.whitelist, start=1):
        table.add_row(str(i), f"@{username}")

    console.print(table)


@insta.command("blacklist-add")
@click.argument("username")
def cmd_blacklist_add(username: str) -> None:
    """Adiciona username a blacklist (nunca interagir)."""
    username = username.lstrip("@")
    settings = _load_settings()
    if username in settings.blacklist:
        console.print(f"[yellow]@{username} ja esta na blacklist.[/yellow]")
        return
    settings.blacklist.append(username)
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(f"[green]@{username} adicionado a blacklist.[/green]")


@insta.command("blacklist-remove")
@click.argument("username")
def cmd_blacklist_remove(username: str) -> None:
    """Remove username da blacklist."""
    username = username.lstrip("@")
    settings = _load_settings()
    if username not in settings.blacklist:
        console.print(f"[yellow]@{username} nao esta na blacklist.[/yellow]")
        return
    settings.blacklist.remove(username)
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(f"[green]@{username} removido da blacklist.[/green]")


@insta.command("blacklist-show")
def cmd_blacklist_show() -> None:
    """Exibe a blacklist atual (usernames que nunca serao interagidos)."""
    settings = _load_settings()
    if not settings.blacklist:
        console.print("[dim]Blacklist vazia.[/dim]")
        return

    table = Table(title=f"Blacklist ({len(settings.blacklist)} usuarios)", show_header=True, header_style="bold red")
    table.add_column("#", justify="right", width=5)
    table.add_column("Username", style="bold")

    for i, username in enumerate(settings.blacklist, start=1):
        table.add_row(str(i), f"@{username}")

    console.print(table)


@insta.command("set-proxy")
@click.argument("proxy_url")
def cmd_set_proxy(proxy_url: str) -> None:
    """Configura proxy para conexao (ex: http://user:pass@host:port ou socks5://...)."""
    settings = _load_settings()
    settings.proxy = proxy_url
    settings.save_to_file(str(_CONFIG_FILE))
    console.print(f"[green]Proxy configurado:[/green] {proxy_url}")
    console.print("[dim]O proxy sera usado na proxima sessao de login.[/dim]")


@insta.command("remove-proxy")
def cmd_remove_proxy() -> None:
    """Remove a configuracao de proxy."""
    settings = _load_settings()
    if settings.proxy is None:
        console.print("[yellow]Nenhum proxy configurado.[/yellow]")
        return
    settings.proxy = None
    settings.save_to_file(str(_CONFIG_FILE))
    console.print("[green]Proxy removido.[/green]")


if __name__ == "__main__":
    insta()
