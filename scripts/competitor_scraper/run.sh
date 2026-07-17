#!/usr/bin/env bash
# Runner local do scraper de concorrentes.
# Raspa o preço da página pública do ML (via dev-browser, IP residencial) e faz
# POST no endpoint de ingestão do MSM_Pro. Rode diariamente (Task Scheduler).
#
# Por que local: a API pública do ML dá 403 p/ item de terceiro, e o preço só sai
# do JSON-LD da página pública, que bloqueia IP de datacenter (Railway cai no muro
# account-verification). Ver o vault "12 - Ideias / Coleta de preço de concorrentes".
#
# Uso:  MSM_SENHA='***' bash run.sh
set -uo pipefail

API="${MSM_API:-https://msmpro-production.up.railway.app}"
EMAIL="${MSM_EMAIL:-maikeo@msmrp.com}"
SENHA="${MSM_SENHA:-Msm@2026}"

# id_ml | URL pública | is_buy_box(true=catálogo/false=item de terceiro).
# Itens de terceiro: produto.mercadolivre.com.br/MLB-<dig>-_JM (preço do próprio item).
# Catálogo/MLBU: www.mercadolivre.com.br/p/<id> (preço = vencedor da buy box).
TARGETS=(
  "MLB4185585590|https://produto.mercadolivre.com.br/MLB-4185585590-_JM|false"
  "MLB4664920981|https://produto.mercadolivre.com.br/MLB-4664920981-_JM|false"
  "MLB5496628754|https://produto.mercadolivre.com.br/MLB-5496628754-_JM|false"
  "MLB6429093518|https://produto.mercadolivre.com.br/MLB-6429093518-_JM|false"
  "MLB6460154858|https://produto.mercadolivre.com.br/MLB-6460154858-_JM|false"
  "MLB3377496529|https://produto.mercadolivre.com.br/MLB-3377496529-_JM|false"
  "MLB4130481127|https://produto.mercadolivre.com.br/MLB-4130481127-_JM|false"
  "MLBU3453370601|https://www.mercadolivre.com.br/p/MLBU3453370601|true"
  "MLB66736353|https://www.mercadolivre.com.br/p/MLB66736353|true"
  "MLB66987007|https://www.mercadolivre.com.br/p/MLB66987007|true"
  "MLB68602042|https://www.mercadolivre.com.br/p/MLB68602042|true"
)

echo "[1/3] Raspando ${#TARGETS[@]} páginas (uma por vez, browser persistente)..."
ROWS=()
for t in "${TARGETS[@]}"; do
  ID="${t%%|*}"; REST="${t#*|}"; URL="${REST%|*}"; BB="${REST##*|}"
  PRICE=$(dev-browser 2>/dev/null <<EOF | grep '::P::' | sed 's/.*::P:://'
const page = await browser.getPage("ml-scraper");
try {
  await page.goto("$URL", { waitUntil: "domcontentloaded", timeout: 25000 });
  await new Promise(r => setTimeout(r, 1200));
  const p = await page.evaluate(() => {
    for (const el of document.querySelectorAll('script[type="application/ld+json"]')) {
      try { const j = JSON.parse(el.textContent); if (j?.offers?.price != null) return j.offers.price; } catch(e){}
    }
    const f = document.querySelector(".andes-money-amount__fraction");
    const c = document.querySelector(".andes-money-amount__cents");
    if (f) { const i = f.textContent.replace(/[^0-9]/g,""); const cc = c ? c.textContent.replace(/[^0-9]/g,"") : "0"; if (i) return parseFloat(i + "." + (cc||"0")); }
    return null;
  });
  console.log("::P::" + (p == null ? "" : p));
} catch (e) { console.log("::P::"); }
EOF
)
  # Ignora vazio e preço <= 0 (produto sem oferta ativa) — não grava lixo.
  VALID=$(python -c "import sys; p='$PRICE'.strip(); print('1' if p and float(p)>0 else '0')" 2>/dev/null || echo 0)
  if [ "$VALID" = "1" ]; then
    echo "  $ID: R\$ $PRICE  (buy_box=$BB)"
    ROWS+=("{\"id_ml\":\"$ID\",\"price\":$PRICE,\"is_buy_box\":$BB}")
  else
    echo "  $ID: (sem preço válido)"
  fi
done

if [ ${#ROWS[@]} -eq 0 ]; then echo "Nada raspado — abortando."; exit 1; fi
BODY="[$(IFS=,; echo "${ROWS[*]}")]"

echo "[2/3] Autenticando..."
TOKEN="$(curl -s -X POST "$API/api/v1/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$SENHA\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")"
[ -n "$TOKEN" ] || { echo "ERRO: login falhou"; exit 1; }

echo "[3/3] POST /competitors/prices/ingest (${#ROWS[@]} preços)..."
curl -s -X POST "$API/api/v1/competitors/prices/ingest" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "$BODY" | python -m json.tool
echo "OK."
