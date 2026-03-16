import json
from datetime import datetime
from pathlib import Path

from rich.console import Console

from insta_app.core.utils import atomic_write_json

try:
    from instagrapi import Client
    from instagrapi.exceptions import ChallengeRequired, LoginRequired
    from instagrapi.types import UserShort
except ImportError:
    Console().print(
        "[bold red]Erro:[/bold red] instagrapi nao instalado. "
        "Execute: pip install instagrapi"
    )
    raise

console = Console()


class FollowerMonitor:
    def __init__(self, client: Client, data_dir: str = "data") -> None:
        """
        Monitora seguidores do usuario logado.

        Args:
            client: instagrapi.Client ja autenticado.
            data_dir: pasta onde o historico e snapshots sao salvos.
        """
        self._client = client
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_path = self._data_dir / "followers_snapshot.json"
        self._history_path = self._data_dir / "followers_history.json"

    # ------------------------------------------------------------------
    # Metodos publicos de consulta
    # ------------------------------------------------------------------

    def get_followers(self) -> dict[int, UserShort]:
        """Busca todos os seguidores do usuario logado."""
        user_id = self._client.user_id
        console.print(f"[dim]Buscando seguidores de user_id={user_id}...[/dim]")
        try:
            followers: dict[int, UserShort] = self._client.user_followers(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)
        console.print(f"[dim]Total de seguidores: {len(followers)}[/dim]")
        return followers

    def get_following(self) -> dict[int, UserShort]:
        """Busca todos que o usuario segue."""
        user_id = self._client.user_id
        console.print(f"[dim]Buscando seguindo de user_id={user_id}...[/dim]")
        try:
            following: dict[int, UserShort] = self._client.user_following(user_id)
        except ChallengeRequired:
            console.print("[bold red]CHECKPOINT DETECTADO! Parando TODAS as acoes.[/bold red]")
            console.print("Resolva o desafio no app/site do Instagram e faca login novamente.")
            raise SystemExit(2)
        except LoginRequired:
            console.print("[bold red]LOGIN NECESSARIO! Sessao expirada.[/bold red]")
            raise SystemExit(2)
        console.print(f"[dim]Total seguindo: {len(following)}[/dim]")
        return following

    def get_new_followers(self, update_snapshot: bool = True) -> list[UserShort]:
        """
        Compara seguidores atuais com snapshot anterior.
        Retorna lista de NOVOS seguidores desde o ultimo snapshot.

        Args:
            update_snapshot: Se True, atualiza o snapshot apos a comparacao.
                            Se False, mantem o snapshot intacto para uso posterior.
        """
        current = self.get_followers()
        snapshot = self._load_snapshot()

        if snapshot is None:
            # Primeiro snapshot — todos sao "novos" na perspectiva de dados,
            # mas retornamos lista vazia pois nao ha baseline anterior.
            console.print("[yellow]Primeiro snapshot criado. Nenhum dado anterior para comparar.[/yellow]")
            self._save_snapshot(current)
            return []

        previous_ids: set[int] = {int(uid) for uid in snapshot["followers"]}
        new_followers = [user for uid, user in current.items() if uid not in previous_ids]

        # Atualiza snapshot com lista atual (se solicitado)
        if update_snapshot:
            self._save_snapshot(current)
        return new_followers

    def commit_snapshot(self) -> None:
        """
        Salva o snapshot atual de seguidores explicitamente.
        Use apos processar novos seguidores com update_snapshot=False
        para marcar o snapshot como "processado".
        """
        current = self.get_followers()
        self._save_snapshot(current)

    def get_unfollowers(self) -> list[dict]:
        """
        Compara snapshot anterior com seguidores atuais.
        Retorna lista de quem DEIXOU de seguir.
        Formato: [{"user_id": int, "username": str}]
        """
        snapshot = self._load_snapshot()
        if snapshot is None:
            console.print("[yellow]Nenhum snapshot anterior. Faca uma consulta de seguidores primeiro.[/yellow]")
            return []

        current = self.get_followers()
        current_ids: set[int] = set(current.keys())
        previous_ids_map: dict[int, dict] = {
            int(uid): data for uid, data in snapshot["followers"].items()
        }

        unfollowers = [
            {"user_id": uid, "username": data.get("username", "")}
            for uid, data in previous_ids_map.items()
            if uid not in current_ids
        ]

        # Atualiza snapshot com lista atual
        self._save_snapshot(current)
        return unfollowers

    def get_not_following_back(self) -> list[UserShort]:
        """
        Quem voce segue MAS nao te segue de volta.
        Retorna lista de UserShort.
        """
        followers = self.get_followers()
        following = self.get_following()

        follower_ids: set[int] = set(followers.keys())
        not_following_back = [
            user for uid, user in following.items() if uid not in follower_ids
        ]
        return not_following_back

    def get_fans(self) -> list[UserShort]:
        """
        Quem te segue MAS voce nao segue de volta.
        Retorna lista de UserShort.
        """
        followers = self.get_followers()
        following = self.get_following()

        following_ids: set[int] = set(following.keys())
        fans = [
            user for uid, user in followers.items() if uid not in following_ids
        ]
        return fans

    def get_stats(self) -> dict:
        """
        Retorna estatisticas consolidadas do usuario.

        Returns:
            dict com chaves: followers, following, new_followers,
            unfollowers, not_following_back, fans.
        """
        followers = self.get_followers()
        following = self.get_following()

        snapshot = self._load_snapshot()
        new_followers_count = 0
        unfollowers_count = 0

        if snapshot is not None:
            previous_ids: set[int] = {int(uid) for uid in snapshot["followers"]}
            current_ids: set[int] = set(followers.keys())
            new_followers_count = len(current_ids - previous_ids)
            unfollowers_count = len(previous_ids - current_ids)

        follower_ids: set[int] = set(followers.keys())
        following_ids: set[int] = set(following.keys())
        not_following_back_count = len(following_ids - follower_ids)
        fans_count = len(follower_ids - following_ids)

        return {
            "followers": len(followers),
            "following": len(following),
            "new_followers": new_followers_count,
            "unfollowers": unfollowers_count,
            "not_following_back": not_following_back_count,
            "fans": fans_count,
        }

    # ------------------------------------------------------------------
    # Snapshot e historico
    # ------------------------------------------------------------------

    def _save_snapshot(self, followers: dict[int, UserShort]) -> None:
        """
        Salva snapshot atual em data/followers_snapshot.json.
        Formato: {"timestamp": "ISO", "followers": {user_id: {"username": str, "full_name": str}}}
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "followers": {
                str(uid): {
                    "username": user.username,
                    "full_name": user.full_name,
                }
                for uid, user in followers.items()
            },
        }
        atomic_write_json(self._snapshot_path, data)
        console.print(f"[dim]Snapshot salvo em: {self._snapshot_path}[/dim]")

    def _load_snapshot(self) -> dict | None:
        """
        Carrega snapshot anterior de data/followers_snapshot.json.
        Retorna None se nao existir.
        """
        if not self._snapshot_path.exists():
            return None
        try:
            with open(self._snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            console.print(f"[yellow]Erro ao carregar snapshot:[/yellow] {exc}")
            return None

    def save_history(self, stats: dict) -> None:
        """
        Appenda stats em data/followers_history.json (array de entries com timestamp).
        Para futuro grafico de crescimento.
        """
        entry = {"timestamp": datetime.now().isoformat(), **stats}

        history: list[dict] = []
        if self._history_path.exists():
            try:
                with open(self._history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, OSError):
                history = []

        history.append(entry)

        atomic_write_json(self._history_path, history)
        console.print(f"[dim]Historico salvo em: {self._history_path}[/dim]")
