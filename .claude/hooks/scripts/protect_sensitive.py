"""
Hook PreToolUse — protege arquivos sensiveis contra edicao acidental.

Le o payload JSON do stdin (tool_input.file_path) e bloqueia Write/Edit em
.env, credenciais, chaves/certificados e no banco SQLite principal.

Substitui o antigo protect-sensitive.sh, que lia a env var CLAUDE_FILE_PATH
(inexistente no protocolo de hooks) e por isso liberava tudo silenciosamente.

Regra de ouro: em caso de erro, NUNCA travar a sessao — exit 0 sem decisao.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from datetime import datetime
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[3]

# (padrao_glob_no_nome, motivo)
PADROES_BLOQUEADOS: list[tuple[str, str]] = [
    (".env", "Arquivo .env contem segredos. Edite manualmente."),
    (".env.*", "Arquivo .env contem segredos. Edite manualmente."),
    ("*.pem", "Certificado/chave privada protegido."),
    ("*.key", "Certificado/chave privada protegido."),
    ("*.p12", "Certificado/chave privada protegido."),
    ("*.pfx", "Certificado/chave privada protegido."),
    ("ia_geral.db", "Banco SQLite principal protegido. Use scripts Python para modificar."),
    ("learning.db", "Banco do auto-learning protegido."),
    ("credentials.json", "Credenciais do Google protegidas."),
    ("drive_token.json", "Token do Google Drive protegido."),
]

# Padrões no NOME do arquivo (não no caminho inteiro): um path que por acaso contenha
# "tokens" — como .venv/Lib/site-packages/yaml/tokens.py — não pode travar a edição.
PADROES_NOME_SENSIVEL: list[tuple[str, str]] = [
    ("*token*.json", "Arquivo de tokens protegido."),
    ("*credential*.json", "Arquivo de credenciais protegido."),
    ("*secret*.json", "Arquivo de secrets protegido."),
    ("*secret*.yaml", "Arquivo de secrets protegido."),
    ("*secret*.yml", "Arquivo de secrets protegido."),
]

# Diretórios cujo nome declara que o conteúdo é segredo (nome exato, não substring:
# "meus_tokens" não conta, senão voltaríamos a bloquear libs de terceiros).
DIRS_SENSIVEIS = {"secrets", "credentials", "tokens", ".secrets"}

# Dependências de terceiros: fora do escopo de proteção (e de edição manual).
DIRS_IGNORADOS = {".venv", ".venv_backup_py314", "node_modules", "site-packages"}


def _log(msg: str) -> None:
    try:
        log_dir = PROJETO / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} | protect-sensitive | {msg}\n"
        with open(log_dir / "hooks_saude.log", "a", encoding="utf-8") as f:
            f.write(linha)
    except OSError:
        pass


def _motivo_bloqueio(file_path: str) -> str | None:
    if not file_path:
        return None

    alvo = Path(file_path)
    partes = {p.lower() for p in alvo.parts}

    if partes & DIRS_IGNORADOS:
        return None  # dependência de terceiros, não é segredo do projeto

    nome = alvo.name.lower()

    for padrao, motivo in (*PADROES_BLOQUEADOS, *PADROES_NOME_SENSIVEL):
        if fnmatch.fnmatch(nome, padrao):
            return motivo

    # Diretório pai declara segredo (ex.: config/secrets/qualquer_coisa.txt)
    if partes & DIRS_SENSIVEIS:
        return "Arquivo dentro de diretório de segredos protegido."

    return None


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            return 0

        file_path = str(payload.get("tool_input", {}).get("file_path", ""))
        motivo = _motivo_bloqueio(file_path)

        if motivo:
            _log(f"deny | {file_path} | {motivo}")
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"{motivo} ({Path(file_path).name})",
                        }
                    },
                    ensure_ascii=False,
                )
            )
        return 0

    except Exception as exc:  # noqa: BLE001 — hook nunca pode derrubar a sessao
        _log(f"erro | {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
