import json
import shutil
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
        self._configure_device_fingerprint()
        self._configure_proxy()

    def _configure_device_fingerprint(self) -> None:
        """Configura device fingerprint fixo para manter consistencia entre sessoes."""
        self._client.set_device(
            {
                "app_version": "269.0.0.18.75",
                "android_version": 31,
                "android_release": "12.0",
                "dpi": "480dpi",
                "resolution": "1080x2220",
                "manufacturer": "samsung",
                "device": "star2lte",
                "model": "SM-G965F",
                "cpu": "exynos9810",
                "version_code": "314665256",
            }
        )

    def _configure_proxy(self) -> None:
        """Configura proxy se definido nas settings."""
        if self._settings.proxy:
            self._client.set_proxy(self._settings.proxy)
            console.print(f"[dim]Proxy configurado: {self._settings.proxy}[/dim]")

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
        """
        Tenta carregar sessao salva do arquivo. Retorna True se sessao valida.
        Se o arquivo principal falhar, tenta carregar do backup mais recente.
        """
        session_path = Path(self._settings.session_file)

        # Tentar arquivo principal primeiro
        if session_path.exists():
            result = self._try_load_session(session_path)
            if result:
                return True

        # Tentar backups em ordem (1 = mais recente)
        for i in range(1, 4):
            backup_path = session_path.with_suffix(f".backup.{i}.json")
            if backup_path.exists():
                console.print(f"[yellow]Tentando carregar backup {i}...[/yellow]")
                result = self._try_load_session(backup_path)
                if result:
                    # Restaurar backup como sessao principal
                    shutil.copy2(backup_path, session_path)
                    console.print(f"[green]Backup {i} restaurado como sessao principal.[/green]")
                    return True

        console.print("[yellow]Nenhuma sessao valida encontrada. Faca login novamente.[/yellow]")
        return False

    def _try_load_session(self, path: Path) -> bool:
        """Tenta carregar sessao de um caminho especifico. Retorna True se valida."""
        try:
            self._client.load_settings(str(path))
            self._client.account_info()
            self._logged_in = True
            console.print(f"[green]Sessao carregada com sucesso de: {path}[/green]")
            return True
        except LoginRequired:
            console.print(f"[yellow]Sessao expirada em {path}.[/yellow]")
            self._logged_in = False
            return False
        except Exception as exc:
            console.print(f"[yellow]Nao foi possivel carregar sessao de {path}:[/yellow] {exc}")
            self._logged_in = False
            return False

    def _backup_session(self) -> None:
        """Cria backup rotativo da sessao atual (mantem ultimos 3)."""
        session_path = Path(self._settings.session_file)
        if not session_path.exists():
            return
        # Rotacionar: 2->3, 1->2
        for i in range(3, 1, -1):
            old = session_path.with_suffix(f".backup.{i - 1}.json")
            new = session_path.with_suffix(f".backup.{i}.json")
            if old.exists():
                old.rename(new)
        # Copiar atual para backup.1
        shutil.copy2(session_path, session_path.with_suffix(".backup.1.json"))
        console.print("[dim]Backup de sessao criado.[/dim]")

    def save_session(self) -> None:
        """Salva cookies/session do instagrapi para arquivo JSON com backup rotativo."""
        session_path = Path(self._settings.session_file)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_session()
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
