"""
Hook PreToolUse (Write|Edit) do MSM_Pro — avisa antes de editar o cliente da API do Mercado Livre.

Lê o payload JSON do stdin (protocolo de hooks do Claude Code; $CLAUDE_TOOL_INPUT não existe).
Nunca bloqueia: em qualquer erro sai com 0. O aviso vai ao usuário (systemMessage) e ao modelo
(additionalContext).
"""

from __future__ import annotations

import json
import sys

ALVOS = ("mercadolivre/client.py",)
AVISO = ("AVISO: você está editando o cliente da API do Mercado Livre ({arquivo}). Antes de prosseguir, "
         "valide o endpoint com o agente ml-api / MCP mercadolibre-official e confira docs/ml_api_reference.md "
         "(se o arquivo não existir, avise o Maikeo em vez de assumir o contrato). "
         "A API é api.mercadolibre.com (libre).")


def _rotulo(caminho: str) -> str:
    partes = [p for p in caminho.split("/") if p]
    return "/".join(partes[-2:]) if partes else caminho


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    bruto = tool_input.get("file_path")
    if bruto is None:
        return 0
    caminho = str(bruto).replace("\\", "/")
    if any(caminho == a or caminho.endswith("/" + a) for a in ALVOS):
        msg = AVISO.format(arquivo=_rotulo(caminho))
        print(json.dumps({
            "systemMessage": msg,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": msg,
            },
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BaseException:  # noqa: BLE001 — hook nunca derruba a sessão
        sys.exit(0)
