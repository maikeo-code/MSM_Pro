#!/usr/bin/env bash
#
# check_parity.sh — PORTÃO DE PRONTO para tarefas de dados do MSM_Pro.
#
# Chama GET /api/v1/listings/audit/parity (harness que compara os números do
# MSM_Pro contra a API REAL do Mercado Livre) e SAI COM ERRO se qualquer métrica
# divergir (summary.failed > 0). É a materialização do princípio mestre:
# "MSM_Pro = espelho do painel do ML; divergência = bug do MSM_Pro".
#
# Uso:
#   TOKEN="<jwt>" scripts/check_parity.sh                 # ontem, prod
#   TOKEN="<jwt>" scripts/check_parity.sh 2026-07-06      # dia específico
#   TOKEN="<jwt>" BASE_URL=http://localhost:8000 scripts/check_parity.sh
#
# Variáveis:
#   TOKEN        (obrigatório) JWT de um usuário com contas ML ativas
#   BASE_URL     (opcional) padrão: https://msmpro-production.up.railway.app
#   SAMPLE_ITEMS (opcional) padrão: 5  — qtd de anúncios na amostra
#
# Códigos de saída: 0 = paridade total; 1 = houve FAIL; 2 = erro de uso/conexão.
set -euo pipefail

BASE_URL="${BASE_URL:-https://msmpro-production.up.railway.app}"
SAMPLE_ITEMS="${SAMPLE_ITEMS:-5}"
DATE_ISO="${1:-}"

# Interpretador Python: prefere python3, cai para python. Testa a EXECUCAO real
# (nao so a presenca no PATH) porque no Git Bash do Windows 'python3' e um stub da
# Microsoft Store que existe mas nao roda — quebraria o parsing do JSON.
PYTHON=""
for cand in python3 python py; do
  if "$cand" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PYTHON="$cand"
    break
  fi
done
if [ -z "$PYTHON" ]; then
  echo "ERRO: nenhum Python funcional encontrado (tentei python3, python, py)." >&2
  exit 2
fi

if [ -z "${TOKEN:-}" ]; then
  echo "ERRO: defina a variável TOKEN com um JWT válido." >&2
  echo "  Ex.: TOKEN=\"eyJ...\" scripts/check_parity.sh" >&2
  exit 2
fi

URL="${BASE_URL}/api/v1/listings/audit/parity?sample_items=${SAMPLE_ITEMS}"
if [ -n "$DATE_ISO" ]; then
  URL="${URL}&date_iso=${DATE_ISO}"
fi

echo "[check_parity] Auditando ${URL}"
# A auditoria bate na API real do ML por anuncio (~20-45s) e o Railway as vezes
# devolve corpo vazio sob carga. Ate 3 tentativas com corpo nao-vazio.
RESP=""
for attempt in 1 2 3; do
  RESP="$(curl -sS --max-time 120 -H "Authorization: Bearer ${TOKEN}" "$URL" || true)"
  if [ -n "$RESP" ] && printf '%s' "$RESP" | grep -q '"summary"'; then
    break
  fi
  echo "[check_parity] tentativa ${attempt}/3 sem resposta valida; repetindo..." >&2
  sleep 5
done
if [ -z "$RESP" ] || ! printf '%s' "$RESP" | grep -q '"summary"'; then
  echo "ERRO: endpoint de paridade nao retornou JSON valido apos 3 tentativas." >&2
  printf '%s\n' "$RESP" | head -c 400 >&2
  exit 2
fi

# Parsing e veredito via python (sem depender de jq).
echo "$RESP" | "$PYTHON" - <<'PY'
import json, sys

data = json.load(sys.stdin)
s = data.get("summary", {})
failed = s.get("failed", 0)
errors = s.get("errors", 0)

print(f"\n=== Paridade MSM_Pro vs painel do ML — dia {data.get('day')} ===")
print(f"  checks={s.get('checks')} passed={s.get('passed')} "
      f"failed={failed} no_data={s.get('no_data')} errors={errors} "
      f"parity={s.get('parity_pct')}%\n")

# Detalha cada divergência para o número aparecer na cara.
for acc in data.get("accounts", []):
    for c in acc.get("checks", []):
        if c.get("verdict") == "FAIL":
            print(f"  FAIL [{acc.get('nickname')}] {c['metric']}: "
                  f"ML={c.get('ml')} vs APP={c.get('app')}")

if failed and failed > 0:
    print(f"\nX PORTÃO BLOQUEADO: {failed} métrica(s) divergem do painel do ML. "
          f"NÃO declare a tarefa pronta — corrija a divergência primeiro.")
    sys.exit(1)

print("\nOK Paridade total com o painel do ML. Portão liberado.")
if errors and errors > 0:
    print(f"(aviso: {errors} check(s) com ERROR/sem resposta do ML — reveja se relevante)")
PY
