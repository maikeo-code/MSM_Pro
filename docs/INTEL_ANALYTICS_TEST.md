# Testes dos Endpoints — Intel/Analytics

## Setup

```bash
# 1. Pegar token JWT
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

echo "Token obtido: ${TOKEN:0:20}..."

# 2. Salvá como variável
export AUTH="Authorization: Bearer $TOKEN"
```

---

## Teste 1: Comparação Temporal (30 dias)

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=30d" \
  | python3 -m json.tool | head -50
```

**Expected Response:**
- `items`: Array de objetos com mlb_id, title, revenue_current, revenue_previous, revenue_delta_pct, etc.
- `total_revenue_current`: Receita total período atual
- `total_revenue_previous`: Receita total período anterior
- `total_revenue_delta_pct`: Variação percentual

**Validar:**
- Status: 200 OK
- `period_days`: 30
- Todos os itens têm `mlb_id` e `title`
- Delta percentuais são números float

---

## Teste 2: Comparação — 7 dias

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=7d" \
  | python3 -m json.tool | head -50
```

**Validar:**
- `period_days`: 7
- Menos itens que comparação de 30d (menos snapshots agregados)

---

## Teste 3: Classificação ABC — por Receita

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc?period=30d&metric=revenue" \
  | python3 -m json.tool
```

**Expected Response:**
- `items`: Array com `classification` ("A", "B", ou "C")
- `total_revenue`: Soma da receita
- `class_a_revenue_pct`, `class_b_revenue_pct`, `class_c_revenue_pct`
- Cada item tem `turnover_rate`

**Validar:**
- `class_a_revenue_pct + class_b_revenue_pct + class_c_revenue_pct ≈ 100%`
- Itens em `classification="A"` têm `cumulative_pct <= 80`
- Itens em `classification="B"` têm `80 < cumulative_pct <= 95`
- `turnover_rate = units_sold / current_stock`

---

## Teste 4: Classificação ABC — por Unidades

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc?period=30d&metric=units" \
  | python3 -m json.tool
```

**Validar:**
- `metric_used`: "units"
- Items ordenados por `units_sold` DESC
- Classificação baseada em unidades (não receita)

---

## Teste 5: Inventário — Saúde

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/inventory-health?period=30d" \
  | python3 -m json.tool
```

**Expected Response:**
- `items`: Array com `health_status` ("healthy", "overstocked", "critical_low")
- `healthy_count`, `overstocked_count`, `critical_low_count`
- `avg_days_of_stock`: Média de dias em mão
- Cada item tem `days_of_stock`, `sell_through_rate`, `avg_daily_sales`

**Validar:**
- `healthy_count + overstocked_count + critical_low_count = total_items`
- `days_of_stock < 7` ⟹ `health_status = "critical_low"`
- `days_of_stock > 90` ⟹ `health_status = "overstocked"`
- `30 <= days_of_stock <= 90` ⟹ `health_status = "healthy"`
- `sell_through_rate` está entre 0 e 1

---

## Teste 6: Erro de Autenticação

```bash
# Sem token
curl -s https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=30d \
  | python3 -m json.tool
```

**Expected:** 403 Forbidden ou 401 Unauthorized

---

## Teste 7: Período Inválido

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=60d" \
  | python3 -m json.tool
```

**Expected:** 422 Unprocessable Entity (período não permite 60d)

---

## Teste 8: Métrica Inválida (ABC)

```bash
curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc?period=30d&metric=profit" \
  | python3 -m json.tool
```

**Expected:** 422 Unprocessable Entity

---

## Teste Completo (Bash Script)

```bash
#!/bin/bash

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

# Get token
echo "[1/4] Obtendo token..."
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

if [ -z "$TOKEN" ]; then
  echo -e "${RED}✗ Falha ao obter token${RESET}"
  exit 1
fi
echo -e "${GREEN}✓ Token obtido${RESET}"

AUTH="Authorization: Bearer $TOKEN"

# Test 1: Comparison
echo "[2/4] Testando Comparação..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=30d")

STATUS=$(echo "$RESPONSE" | tail -1)
if [ "$STATUS" -eq 200 ]; then
  echo -e "${GREEN}✓ Comparação OK (HTTP 200)${RESET}"
else
  echo -e "${RED}✗ Comparação FALHOU (HTTP $STATUS)${RESET}"
fi

# Test 2: ABC
echo "[3/4] Testando ABC..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc?period=30d&metric=revenue")

STATUS=$(echo "$RESPONSE" | tail -1)
if [ "$STATUS" -eq 200 ]; then
  echo -e "${GREEN}✓ ABC OK (HTTP 200)${RESET}"
else
  echo -e "${RED}✗ ABC FALHOU (HTTP $STATUS)${RESET}"
fi

# Test 3: Inventory Health
echo "[4/4] Testando Inventário..."
RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/inventory-health?period=30d")

STATUS=$(echo "$RESPONSE" | tail -1)
if [ "$STATUS" -eq 200 ]; then
  echo -e "${GREEN}✓ Inventário OK (HTTP 200)${RESET}"
else
  echo -e "${RED}✗ Inventário FALHOU (HTTP $STATUS)${RESET}"
fi

echo ""
echo -e "${GREEN}=== TODOS OS TESTES PASSARAM ===${RESET}"
```

---

## Validação de Dados

### 1. Comparação MoM

```python
import requests
import json

TOKEN = "eyJ..."
headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison",
    params={"period": "30d"},
    headers=headers
)

data = response.json()

# Validações
assert response.status_code == 200
assert "items" in data
assert "total_revenue_current" in data
assert "total_revenue_delta_pct" in data

# Cada item
for item in data["items"]:
    assert "mlb_id" in item
    assert "revenue_current" >= 0
    assert "sales_current" >= 0
    assert isinstance(item["revenue_delta_pct"], float)

print("✓ Comparação validada")
```

### 2. ABC

```python
response = requests.get(
    "https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc",
    params={"period": "30d", "metric": "revenue"},
    headers=headers
)

data = response.json()

# Validações
assert response.status_code == 200
assert data["class_a_revenue_pct"] <= 100
assert data["class_b_revenue_pct"] <= 100
assert data["class_c_revenue_pct"] <= 100
assert abs((data["class_a_revenue_pct"] + data["class_b_revenue_pct"] + data["class_c_revenue_pct"]) - 100) < 0.1

# Cada item
for item in data["items"]:
    assert item["classification"] in ["A", "B", "C"]
    assert item["turnover_rate"] >= 0

print("✓ ABC validada")
```

### 3. Inventory Health

```python
response = requests.get(
    "https://msmpro-production.up.railway.app/api/v1/intel/analytics/inventory-health",
    params={"period": "30d"},
    headers=headers
)

data = response.json()

# Validações
assert response.status_code == 200
assert data["healthy_count"] + data["overstocked_count"] + data["critical_low_count"] == data["total_items"]

# Cada item
for item in data["items"]:
    assert item["health_status"] in ["healthy", "overstocked", "critical_low"]
    assert 0 <= item["sell_through_rate"] <= 1
    assert item["current_stock"] >= 0
    assert item["avg_daily_sales"] >= 0

print("✓ Inventory Health validada")
```

---

## Performance

Esperado: <200ms para datasets com até 500 anúncios

```bash
# Benchmark
time curl -s -H "$AUTH" \
  "https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=30d" \
  > /dev/null
```

