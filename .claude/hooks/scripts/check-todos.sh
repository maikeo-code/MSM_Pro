#!/bin/bash
# Verifica TODOs críticos antes de encerrar a sessão
# Se encontrar TODO/FIXME/HACK em arquivos editados, avisa o usuário

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

# Busca TODOs críticos apenas no backend e frontend (ignora node_modules, .venv, etc.)
TODOS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  --exclude-dir=dist \
  --exclude-dir=.git \
  "$PROJECT_DIR/backend" "$PROJECT_DIR/frontend" 2>/dev/null || true)

if [[ -n "$TODOS" ]]; then
  COUNT=$(echo "$TODOS" | wc -l | tr -d ' ')
  echo "" >&2
  echo "⚠️  $COUNT TODO(s)/FIXME(s) pendentes no projeto:" >&2
  echo "$TODOS" | head -10 >&2
  if [[ "$COUNT" -gt 10 ]]; then
    echo "  ... e mais $((COUNT - 10)) ocorrências." >&2
  fi
  echo "" >&2
fi

exit 0
