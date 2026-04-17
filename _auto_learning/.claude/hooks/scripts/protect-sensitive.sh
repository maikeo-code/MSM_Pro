#!/bin/bash
# Hook: Protege bancos SQLite, .env e arquivos criticos do SWARM GENESIS

FILE_PATH="${CLAUDE_FILE_PATH:-}"

case "$FILE_PATH" in
    *.env|*.env.*|*/.env)
        echo '{"decision": "deny", "reason": "Arquivo .env protegido (EKAS). Edite manualmente."}'
        exit 0
        ;;
    *.db|*.sqlite|*.sqlite3)
        echo '{"decision": "deny", "reason": "Banco SQLite protegido. Use loop_runner.py para modificar."}'
        exit 0
        ;;
    *schema.sql)
        echo '{"decision": "deny", "reason": "Schema protegido. Modificar apenas com migracao planejada."}'
        exit 0
        ;;
    *.pem|*.key|*.p12|*.pfx)
        echo '{"decision": "deny", "reason": "Certificado/chave protegido."}'
        exit 0
        ;;
esac

echo '{"decision": "allow"}'
