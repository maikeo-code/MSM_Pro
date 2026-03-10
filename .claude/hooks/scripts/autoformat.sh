#!/bin/bash
# Formata automaticamente arquivos Python (.py) e TypeScript/React (.ts .tsx) após edição

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
params = data.get('tool_input', {})
path = params.get('file_path', params.get('path', ''))
print(path)
" 2>/dev/null || echo "")

if [[ -z "$FILE_PATH" ]] || [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"

# Python: roda black (formatador) + flake8 (linter rápido)
if [[ "$EXT" == "py" ]]; then
  if command -v black &>/dev/null; then
    black --quiet "$FILE_PATH" 2>/dev/null || true
  fi
  if command -v flake8 &>/dev/null; then
    RESULT=$(flake8 --max-line-length=100 "$FILE_PATH" 2>&1 || true)
    if [[ -n "$RESULT" ]]; then
      echo "⚠️  flake8 — $FILE_PATH:" >&2
      echo "$RESULT" >&2
    fi
  fi
fi

# TypeScript/React: roda prettier
if [[ "$EXT" == "ts" ]] || [[ "$EXT" == "tsx" ]]; then
  if command -v prettier &>/dev/null; then
    prettier --write --log-level silent "$FILE_PATH" 2>/dev/null || true
  fi
fi

exit 0
