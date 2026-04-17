#!/bin/bash
# Hook: Mostra status do SWARM GENESIS ao iniciar sessao

PROJETO_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"

echo ""
echo "======================================"
echo "  SWARM GENESIS v7.0 - Status"
echo "======================================"

# Status via loop_runner
if [ -f "$PROJETO_DIR/loop_runner.py" ]; then
    echo ""
    cd "$PROJETO_DIR" && python loop_runner.py status 2>/dev/null || echo "  (loop_runner indisponivel)"
fi

# Bancos de dados
echo ""
echo "--- Bancos de Dados ---"
for db in "$PROJETO_DIR/db/"*.db "$PROJETO_DIR/ekas/db/"*.db; do
    if [ -f "$db" ]; then
        SIZE=$(stat --printf="%s" "$db" 2>/dev/null || stat -f%z "$db" 2>/dev/null || echo "?")
        echo "  $(basename "$db"): $SIZE bytes"
    fi
done

# Ultimo checkpoint
echo ""
echo "--- Ultimo Checkpoint ---"
if [ -f "$PROJETO_DIR/loop_runner.py" ]; then
    cd "$PROJETO_DIR" && python -c "
from engine import SwarmDB
db = SwarmDB()
cp = db.get_last_checkpoint()
if cp:
    print(f'  Fase: {cp[\"phase\"]}')
    print(f'  Ciclo: {cp[\"cycle_id\"]}')
    print(f'  Data: {cp[\"created_at\"]}')
    print(f'  Retomado: {\"Sim\" if cp[\"resumed\"] else \"Nao\"}')
else:
    print('  Nenhum checkpoint pendente')
" 2>/dev/null || echo "  (nao foi possivel ler checkpoints)"
fi

echo ""
echo "======================================"
