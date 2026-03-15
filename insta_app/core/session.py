import json
from pathlib import Path

from rich.console import Console

from insta_app.config import Settings

console = Console()

try:
    from instagrapi import Client
    from instagrapi.exceptions import (
        BadPassword,
        ChallengeRequired,
        LoginRequired,
        TwoFactorRequired,
    )
except ImportError:
    console.print(
        "[bold red]Erro:[/bold red] instagrapi nao instalado. "
        "Execute: pip install instagrapi"
    )
    raise


class SessionManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Client = Client()
        self._logged_in: bool = False

    def login(self, username: str, password: str) -> bool:
        """Realiza login no Instagram. Trata 2FA e challenges."""
        try:
            self._client.login(username, password)
            self._logged_in = True
            self.save_session()
            console.print(f"[bold green]Login realizado com sucesso:[/bold green] {username}")
            return True

        except TwoFactorRequired as e:
            console.print("[yellow]Autenticacao de dois fatores necessaria.[/yellow]")
            code = input("Digite o codigo 2FA: ").strip()
            try:
                two_factor_id = getattr(e, "two_factor_identifier", None)
                self._client.two_factor_login(code, two_factor_identifier=two_factor_id)
                self._logged_in = True
                self.save_session()
                console.print(f"[bold green]Login com 2FA realizado:[/bold green] {username}")
                return True
            except Exception as exc:
                console.print(f"[bold red]Erro no login com 2FA:[/bold red] {exc}")
                return False

        except ChallengeRequired:
            console.print(
                "[bold yellow]Challenge requerido pelo Instagram.[/bold yellow] "
                "Resolva o desafio pelo app/site e tente novamente."
            )
            return False

        except BadPassword:
            console.print("[bold red]Senha incorreta.[/bold red]")
            return False

        except LoginRequired:
            console.print("[bold red]Login necessario — sessao expirada.[/bold red]")
            return False

        except Exception as exc:
            console.print(f"[bold red]Erro inesperado no login:[/bold red] {exc}")
            return False

    def load_session(self) -> bool:
        """Tenta carregar sessao salva do arquivo. Retorna True se sessao valida."""
        session_path = Path(self._settings.session_file)
        if not session_path.exists():
            return False
        try:
            self._client.load_settings(str(session_path))
            # Testa se sessao ainda e valida
            self._client.account_info()
            self._logged_in = True
            console.print("[green]Sessao carregada com sucesso.[/green]")
            return True
        except LoginRequired:
            console.print("[yellow]Sessao expirada. Faca login novamente.[/yellow]")
            self._logged_in = False
            return False
        except Exception as exc:
            console.print(f"[yellow]Nao foi possivel carregar a sessao:[/yellow] {exc}")
            self._logged_in = False
            return False

    def save_session(self) -> None:
        """Salva cookies/session do instagrapi para arquivo JSON."""
        session_path = Path(self._settings.session_file)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._client.dump_settings(str(session_path))
        console.print(f"[dim]Sessao salva em:[/dim] {session_path}")

    def is_logged_in(self) -> bool:
        """Retorna True se o usuario esta autenticado."""
        return self._logged_in

    def get_client(self) -> Client:
        """Retorna o cliente instagrapi autenticado."""
        if not self._logged_in:
            raise RuntimeError("Cliente nao autenticado. Faca login primeiro.")
        return self._client

    def logout(self) -> None:
        """Encerra a sessao e remove o arquivo de sessao."""
        try:
            self._client.logout()
        except Exception:
            pass  # Logout pode falhar se sessao ja expirou
        self._logged_in = False
        session_path = Path(self._settings.session_file)
        if session_path.exists():
            session_path.unlink()
            console.print(f"[dim]Arquivo de sessao removido:[/dim] {session_path}")
        console.print("[green]Logout realizado.[/green]")
