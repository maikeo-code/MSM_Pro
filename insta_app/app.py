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


if __name__ == "__main__":
    insta()
