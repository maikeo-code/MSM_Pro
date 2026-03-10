#!/bin/bash
# Exibe resumo do projeto ao iniciar a sessão

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"

echo "" >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "  MSM_Pro — Sessão iniciada" >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2

# Mostra sprint atual do CLAUDE.md
if [[ -f "$CLAUDE_MD" ]]; then
  SPRINT=$(grep -A 5 "### Sprint" "$CLAUDE_MD" | grep "\[ \]" | head -3 || true)
  if [[ -n "$SPRINT" ]]; then
    echo "  📋 Próximas tarefas:" >&2
    echo "$SPRINT" | sed 's/^/     /' >&2
  fi
fi

# Verifica se Docker está rodando
if command -v docker &>/dev/null; then
  if docker info &>/dev/null 2>&1; then
    CONTAINERS=$(docker ps --format "{{.Names}}" 2>/dev/null | grep -i "msm\|postgres\|redis" || true)
    if [[ -n "$CONTAINERS" ]]; then
      echo "  🐳 Containers ativos: $(echo $CONTAINERS | tr '\n' ' ')" >&2
    else
      echo "  🐳 Docker ativo — containers MSM_Pro não iniciados" >&2
    fi
  fi
fi

# Conta arquivos Python/TS do projeto
PY_FILES=$(find "$PROJECT_DIR/backend" -name "*.py" 2>/dev/null | grep -v __pycache__ | wc -l | tr -d ' ')
TS_FILES=$(find "$PROJECT_DIR/frontend/src" -name "*.ts" -o -name "*.tsx" 2>/dev/null | wc -l | tr -d ' ')
echo "  📁 Backend: ${PY_FILES} .py | Frontend: ${TS_FILES} .ts/.tsx" >&2
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >&2
echo "" >&2

exit 0
