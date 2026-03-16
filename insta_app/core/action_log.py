"""
Registro persistente de acoes executadas em SQLite.

Permite verificar duplicatas, gerar resumos e limpar registros antigos.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


class ActionLog:
    """Gerencia log de acoes em banco SQLite local."""

    def __init__(self, db_path: str | Path = "data/actions.db") -> None:
        """
        Inicializa o ActionLog com banco SQLite.

        Args:
            db_path: caminho para o arquivo SQLite. O diretorio pai sera
                     criado automaticamente se nao existir.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self) -> None:
        """Cria a tabela de acoes se nao existir."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_username TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ok',
                details TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Indice para consultas de duplicata (action_type + target_id + timestamp)
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_actions_lookup
            ON actions (action_type, target_id, timestamp)
            """
        )
        self._conn.commit()

    def log(
        self,
        action_type: str,
        target_id: str,
        target_username: str = "",
        status: str = "ok",
        details: str = "",
    ) -> None:
        """
        Registra uma acao executada.

        Args:
            action_type: tipo da acao (ex: 'like', 'story_view', 'story_react', 'unfollow').
            target_id: identificador do alvo (media_pk, user_id, story_pk).
            target_username: username do alvo (para leitura humana).
            status: resultado da acao ('ok', 'error', etc).
            details: detalhes adicionais opcionais.
        """
        self._conn.execute(
            """
            INSERT INTO actions (timestamp, action_type, target_id, target_username, status, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                action_type,
                str(target_id),
                target_username,
                status,
                details,
            ),
        )
        self._conn.commit()

    def already_acted(self, action_type: str, target_id: str, hours: int = 24) -> bool:
        """
        Verifica se uma acao do mesmo tipo ja foi realizada no alvo dentro de N horas.

        Args:
            action_type: tipo da acao.
            target_id: identificador do alvo.
            hours: janela de tempo em horas para considerar duplicata.

        Returns:
            True se a acao ja foi executada com status 'ok' dentro da janela.
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        row = self._conn.execute(
            """
            SELECT COUNT(*) as cnt FROM actions
            WHERE action_type = ? AND target_id = ? AND status = 'ok' AND timestamp >= ?
            """,
            (action_type, str(target_id), cutoff),
        ).fetchone()
        return row["cnt"] > 0

    def get_summary(self, days: int = 7) -> dict[str, int]:
        """
        Retorna contagens de acoes por tipo nos ultimos N dias.

        Args:
            days: numero de dias para incluir no resumo.

        Returns:
            Dicionario {action_type: contagem}.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """
            SELECT action_type, COUNT(*) as cnt FROM actions
            WHERE timestamp >= ? AND status = 'ok'
            GROUP BY action_type
            """,
            (cutoff,),
        ).fetchall()
        return {row["action_type"]: row["cnt"] for row in rows}

    def cleanup(self, days: int = 30) -> int:
        """
        Remove registros mais antigos que N dias.

        Args:
            days: idade maxima em dias dos registros a manter.

        Returns:
            Numero de registros removidos.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "DELETE FROM actions WHERE timestamp < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Fecha a conexao com o banco."""
        self._conn.close()
