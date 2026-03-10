#!/bin/bash
# Bloqueia edição de arquivos sensíveis: .env, tokens ML, .git

set -euo pipefail

# Lê o input JSON do PreToolUse via stdin
INPUT=$(cat)

# Extrai o file_path do input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
params = data.get('tool_input', {})
path = params.get('file_path', params.get('path', ''))
print(path)
" 2>/dev/null || echo "")

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Lista de padrões bloqueados
BLOCKED_PATTERNS=(
  ".env"
  "dados/tokens"
  "ml_token.json"
  ".git/"
  "*.pem"
  "*.key"
  "secrets"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "{\"decision\": \"deny\", \"reason\": \"Arquivo sensível protegido: $FILE_PATH — edite manualmente se necessário.\"}" >&2
    exit 2
  fi
done

exit 0
