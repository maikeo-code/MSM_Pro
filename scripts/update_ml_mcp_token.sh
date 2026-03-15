#!/bin/bash
# =============================================================================
# update_ml_mcp_token.sh
# Busca o access_token ML e atualiza o .mcp.json para o MCP Server do ML
#
# Uso:
#   ./scripts/update_ml_mcp_token.sh                    # busca via API producao
#   ./scripts/update_ml_mcp_token.sh TOKEN_AQUI         # token manual
#   ./scripts/update_ml_mcp_token.sh --db               # busca do banco local
#
# Requer: python3, curl
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MCP_JSON="$PROJECT_DIR/.mcp.json"
API_URL="${MSM_API_URL:-https://msmpro-production.up.railway.app}"

# Se token passado como argumento direto
if [ -n "${1:-}" ] && [ "${1:-}" != "--db" ]; then
    TOKEN="$1"
    echo "[OK] Usando token passado por argumento"

# Busca do banco local (--db flag)
elif [ "${1:-}" = "--db" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        for envfile in "$PROJECT_DIR/.env" "$PROJECT_DIR/backend/.env"; do
            if [ -f "$envfile" ]; then
                DB_URL_RAW=$(grep -E "^DATABASE_URL=" "$envfile" 2>/dev/null | head -1 | cut -d= -f2-)
                if [ -n "$DB_URL_RAW" ]; then
                    DATABASE_URL="$DB_URL_RAW"
                    break
                fi
            fi
        done
    fi
    DB_URL="${DATABASE_URL:-postgresql://msm:msm@localhost:5432/msm_pro}"
    DB_URL=$(echo "$DB_URL" | sed 's/postgresql+asyncpg/postgresql/')
    echo "[INFO] Buscando token do banco..."
    TOKEN=$(psql "$DB_URL" -t -A -c "
        SELECT access_token FROM ml_accounts
        WHERE is_active = true AND access_token IS NOT NULL AND access_token != ''
        ORDER BY token_expires_at DESC NULLS LAST LIMIT 1;
    " 2>/dev/null) || true
    if [ -z "$TOKEN" ]; then
        echo "[ERRO] Nao conseguiu conectar ao banco ou nenhum token encontrado."
        exit 1
    fi

# Busca via API de producao (default)
else
    echo "[INFO] Buscando token ML via API de producao..."
    echo -n "Email MSM_Pro: "
    read -r EMAIL
    echo -n "Senha: "
    read -rs PASSWORD
    echo ""

    # Login para pegar JWT
    JWT=$(curl -s -X POST "$API_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | \
        python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

    if [ -z "$JWT" ]; then
        echo "[ERRO] Login falhou. Verifique email/senha."
        exit 1
    fi
    echo "[OK] Login OK"

    # Lista contas ML
    ACCOUNTS=$(curl -s "$API_URL/api/v1/auth/ml/accounts" \
        -H "Authorization: Bearer $JWT")

    ACCOUNT_ID=$(echo "$ACCOUNTS" | python3 -c "
import json,sys
data = json.load(sys.stdin)
if isinstance(data, list) and len(data) > 0:
    print(data[0]['id'])
" 2>/dev/null)

    if [ -z "$ACCOUNT_ID" ]; then
        echo "[ERRO] Nenhuma conta ML encontrada."
        exit 1
    fi

    # Busca token da conta
    TOKEN_DATA=$(curl -s "$API_URL/api/v1/auth/ml/accounts/$ACCOUNT_ID/token" \
        -H "Authorization: Bearer $JWT")

    TOKEN=$(echo "$TOKEN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
    EXPIRES=$(echo "$TOKEN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('expires_at',''))" 2>/dev/null)
    NICKNAME=$(echo "$TOKEN_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('nickname',''))" 2>/dev/null)

    if [ -z "$TOKEN" ]; then
        echo "[ERRO] Token ML nao disponivel. Reconecte a conta ML."
        echo "[DEBUG] $TOKEN_DATA"
        exit 1
    fi

    echo "[OK] Conta: $NICKNAME"
    if [ -n "$EXPIRES" ]; then
        echo "[INFO] Token expira em: $EXPIRES"
    fi
fi

# Mostra preview do token
TOKEN_LEN=${#TOKEN}
if [ "$TOKEN_LEN" -gt 16 ]; then
    TOKEN_PREVIEW="${TOKEN:0:8}...${TOKEN: -8}"
else
    TOKEN_PREVIEW="(${TOKEN_LEN} chars)"
fi
echo "[OK] Token (${TOKEN_LEN} chars): $TOKEN_PREVIEW"

# Atualiza .mcp.json usando python3
python3 << PYEOF
import json
import os
import sys

mcp_path = "$MCP_JSON"
token = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
if not token:
    token = """$TOKEN"""

# Le o .mcp.json existente ou cria novo
if os.path.exists(mcp_path):
    with open(mcp_path, 'r') as f:
        config = json.load(f)
else:
    config = {"mcpServers": {}}

if "mcpServers" not in config:
    config["mcpServers"] = {}

# Adiciona/atualiza o server do ML
config["mcpServers"]["mercadolibre-docs"] = {
    "command": "npx",
    "args": [
        "-y", "mcp-remote",
        "https://mcp.mercadolibre.com/mcp",
        "--header",
        f"Authorization:Bearer {token}"
    ]
}

with open(mcp_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write("\n")

print("[OK] .mcp.json atualizado!")
PYEOF

echo ""
echo "=== MCP Servers configurados ==="
python3 -c "
import json
with open('$MCP_JSON') as f:
    data = json.load(f)
for name in data.get('mcpServers', {}):
    print(f'  - {name}')
"
echo ""
echo "[PROXIMO PASSO] Reinicie o Claude Code para carregar o novo MCP server."
echo "[INFO] O token ML expira em ~6h. Rode este script novamente quando expirar."
