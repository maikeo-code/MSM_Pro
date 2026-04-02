# ML API Reference — MSM_Pro
# Fonte da verdade para todos os endpoints da API do Mercado Livre usados no projeto.
# SEMPRE leia este arquivo antes de implementar ou modificar qualquer chamada à API ML.

Base URL: `https://api.mercadolibre.com`
Documentação oficial: https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br

---

## REGRAS GERAIS

- Rate limit: 1 req/seg por aplicação — implementar backoff exponencial
- Token OAuth expira em ~6h — tratar 401 com refresh automático (uma tentativa)
- Scopes mínimos necessários: `read write offline_access`
- Header obrigatório em todas as chamadas autenticadas: `Authorization: Bearer {access_token}`
- Formato de data aceito: ISO 8601 com timezone, ex: `2026-04-02T00:00:00.000-03:00`

---

## 1. ANÚNCIOS (ITEMS)

### GET /items/{id}
Busca dados completos de um anúncio.

**URL:** `GET https://api.mercadolibre.com/items/{item_id}`
**Auth:** Obrigatória (Bearer token)
**Params:**
- `include_attributes=all` — inclui atributos extras como SKU (SELLER_SKU)

**Response (campos relevantes):**
```json
{
  "id": "MLB6205732214",
  "title": "Nome do produto",
  "price": 57.38,
  "original_price": 69.90,
  "sale_price": null,
  "currency_id": "BRL",
  "available_quantity": 42,
  "sold_quantity": 188,
  "listing_type_id": "gold_special",
  "status": "active",
  "seller_id": 2050442871,
  "category_id": "MLB12345",
  "thumbnail": "https://http2.mlstatic.com/...",
  "attributes": [
    {"id": "SELLER_SKU", "value_name": "SKU-001"}
  ]
}
```

**Notas:**
- `price` = preço atual de venda (JÁ com desconto de promoção do vendedor)
- `original_price` = preço cheio antes de promoção do vendedor (pode ser null sem promo)
- `sale_price` = campo para promoções do marketplace (raramente presente para vendedores)
- Desde março 2026, usar `/items/{id}/sale_price` como fonte primária de preço

**Validado com curl:** Sim (2026-03-25)

---

### GET /items/{id}/sale_price
Fonte primária de preço atual (substitui o campo `price` depreciado).

**URL:** `GET https://api.mercadolibre.com/items/{item_id}/sale_price`
**Auth:** Obrigatória

**Response:**
```json
{
  "price": 57.38,
  "currency_id": "BRL",
  "payment_method_prices": [],
  "regular_amount": 69.90
}
```

**Validado com curl:** Sim (2026-03-25)

---

### PUT /items/{id}
Atualiza dados de um anúncio (preço, estoque, etc).

**URL:** `PUT https://api.mercadolibre.com/items/{item_id}`
**Auth:** Obrigatória (Bearer token com scope `write`)
**Body:**
```json
{"price": 59.90}
```

**ATENCAO — BLOQUEIO POR PROMOÇÃO ATIVA:**
Se o item tiver uma promoção ativa (PRICE_DISCOUNT, DOD, LIGHTNING, DEAL), o PUT de preço
retorna erro 400. A solução correta é:
1. Deletar a promoção existente via DELETE /seller-promotions/items/{id}
2. Aplicar novo preço via PUT /items/{id}
   OU criar nova promoção com o preço desejado via POST /seller-promotions/items/{id}

---

## 2. PROMOÇÕES DO VENDEDOR (SELLER PROMOTIONS)

### Visão Geral dos Tipos de Promoção

| Tipo | Descrição | Modificável via PUT |
|------|-----------|-------------------|
| `PRICE_DISCOUNT` | Desconto individual criado pelo vendedor | NÃO — deletar e recriar |
| `DEAL` | Evento de vendas (campanhas tradicionais) | NÃO — deletar e recriar |
| `DOD` | Oferta do Dia | NÃO — deletar e recriar |
| `LIGHTNING` | Oferta Relâmpago | NÃO — deletar e recriar |
| `MARKETPLACE_CAMPAIGN` | Campanha co-financiada pelo marketplace | NÃO |
| `SELLER_CAMPAIGN` | Campanha criada pelo vendedor | PUT disponível |
| `PRE_NEGOTIATED` | Desconto pré-negociado por item | NÃO |
| `SELLER_COUPON_CAMPAIGN` | Cupom do vendedor | NÃO |

---

### GET /seller-promotions/items/{item_id}
Lista TODAS as promoções ativas e pendentes de um item.

**URL:** `GET https://api.mercadolibre.com/seller-promotions/items/{item_id}`
**Auth:** Obrigatória
**Params:**
- `app_version=v2` — obrigatório para receber formato novo da resposta

**Exemplo de request:**
```bash
curl -X GET 'https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?app_version=v2' \
  -H 'Authorization: Bearer $ACCESS_TOKEN'
```

**Response (lista de promoções):**
```json
[
  {
    "id": "MLB6205732214",
    "type": "PRICE_DISCOUNT",
    "status": "started",
    "price": 54.90,
    "original_price": 69.90,
    "currency_id": "BRL",
    "start_date": "2026-04-01T00:00:00Z",
    "finish_date": "2026-04-30T23:59:59Z",
    "offer_id": "PDISC-MLB12345",
    "deal_price": 54.90,
    "meli_percentage": null
  }
]
```

**Notas:**
- `status` pode ser: `started`, `pending`, `finished`, `candidate`
- Resposta pode ser lista direta ou dict com campo `results` dependendo da versão
- Se não houver promoção, retorna lista vazia `[]`
- Endpoint é público para GETs (não precisa de token para ler promoções de outros vendedores)

**Validado com curl:** Pendente — executar antes de implementar

---

### POST /seller-promotions/items/{item_id}
Cria uma nova promoção de desconto individual (PRICE_DISCOUNT) para um item.

**URL:** `POST https://api.mercadolibre.com/seller-promotions/items/{item_id}?user_id={seller_id}`
**Auth:** Obrigatória (scope `write`)

**Params obrigatórios na query string:**
- `user_id` = ID do vendedor ML (ex: `2050442871`)

**Body obrigatório (PRICE_DISCOUNT):**
```json
{
  "promotion_type": "PRICE_DISCOUNT",
  "deal_price": 54.90,
  "start_date": "2026-04-02T00:00:00Z",
  "finish_date": "2026-05-02T23:59:59Z"
}
```

**Body com desconto para melhores compradores (opcional):**
```json
{
  "promotion_type": "PRICE_DISCOUNT",
  "deal_price": 54.90,
  "top_deal_price": 51.90,
  "start_date": "2026-04-02T00:00:00Z",
  "finish_date": "2026-05-02T23:59:59Z"
}
```

**Exemplo de request:**
```bash
curl -X POST 'https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?user_id=2050442871' \
  -H 'Authorization: Bearer $ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "promotion_type": "PRICE_DISCOUNT",
    "deal_price": 54.90,
    "start_date": "2026-04-02T00:00:00Z",
    "finish_date": "2026-05-02T23:59:59Z"
  }'
```

**Response (sucesso 201):**
```json
{
  "id": "PDISC-MLB12345",
  "item_id": "MLB6205732214",
  "promotion_type": "PRICE_DISCOUNT",
  "status": "pending",
  "deal_price": 54.90,
  "original_price": 69.90,
  "start_date": "2026-04-02T00:00:00Z",
  "finish_date": "2026-05-02T23:59:59Z"
}
```

**Campos:**
- `deal_price` (obrigatório): preço promocional em R$ para todos os compradores
- `top_deal_price` (opcional): preço especial para compradores Mercado Pontos nível 3-6
  - Regra: `top_deal_price` deve ser pelo menos 5% menor que `deal_price` (desconto <= 35%)
  - Regra: `top_deal_price` deve ser pelo menos 10% menor que `deal_price` (desconto > 35%)
- `start_date` (obrigatório): início da promoção em formato ISO 8601 UTC
- `finish_date` (obrigatório): fim da promoção em formato ISO 8601 UTC
- `promotion_type` (obrigatório): sempre `"PRICE_DISCOUNT"` para desconto do vendedor

**Restrições importantes:**
- O item deve ter `status = active`
- O `deal_price` deve ser menor que o preço atual do item (o ML valida isso)
- NÃO é possível ter duas promoções PRICE_DISCOUNT ativas ao mesmo tempo no mesmo item
- Se já existir uma promoção ativa, o POST retorna erro — deletar primeiro com DELETE
- Para editar uma promoção PRICE_DISCOUNT existente: deletar e criar nova

**Validado com curl:** Pendente — executar com token real antes de ir para produção

---

### DELETE /seller-promotions/items/{item_id}
Remove/finaliza uma promoção de um item. Necessário antes de criar nova promoção ou antes de alterar preço via PUT /items.

**URL:** `DELETE https://api.mercadolibre.com/seller-promotions/items/{item_id}?user_id={seller_id}&promotion_type={type}`
**Auth:** Obrigatória (scope `write`)

**Params obrigatórios na query string:**
- `user_id` = ID do vendedor ML
- `promotion_type` = tipo da promoção a remover (ex: `PRICE_DISCOUNT`)

**Exemplo de request:**
```bash
curl -X DELETE 'https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?user_id=2050442871&promotion_type=PRICE_DISCOUNT' \
  -H 'Authorization: Bearer $ACCESS_TOKEN'
```

**Response (sucesso 200 ou 204):**
- Body pode ser vazio ou `{"status": "ok"}`

**Alternativa — DELETE massivo (remove TODAS as promoções não-DOD/LIGHTNING do item):**
```bash
curl -X DELETE 'https://api.mercadolibre.com/seller-promotions/items/massive/MLB6205732214?user_id=2050442871' \
  -H 'Authorization: Bearer $ACCESS_TOKEN'
```

**Notas:**
- Para DOD e LIGHTNING: usar DELETE individual com `promotion_id` específico (não o massivo)
- Para PRICE_DISCOUNT: o DELETE massivo funciona
- Após DELETE, aguardar alguns segundos antes de criar nova promoção (propagação da API)

**Validado com curl:** Pendente — executar com token real antes de ir para produção

---

### POST /seller-promotions/items/{item_id} (SELLER_CAMPAIGN)
Cria promoção baseada em campanha do vendedor (tipo diferente de PRICE_DISCOUNT).

**URL:** `POST https://api.mercadolibre.com/marketplace/seller-promotions/items/{item_id}?user_id={seller_id}`
**NOTA:** Este endpoint usa o path `/marketplace/seller-promotions/` (diferente do PRICE_DISCOUNT)
**Header adicional:** `version: v2`

**Body:**
```json
{
  "promotion_id": "C-MLB703970",
  "promotion_type": "SELLER_CAMPAIGN",
  "deal_price": 54.90,
  "top_deal_price": 51.90
}
```

**Notas:**
- Requer que a campanha (`promotion_id`) já exista
- Diferente de PRICE_DISCOUNT: necessita de uma campanha criada previamente

---

### GET /seller-promotions/promotions/{promotion_id}/items
Lista os itens dentro de uma campanha/promoção específica.

**URL:** `GET https://api.mercadolibre.com/seller-promotions/promotions/{promotion_id}/items`
**Auth:** Obrigatória

**Response:**
```json
{
  "results": [
    {
      "id": "MLB6205732214",
      "status": "started",
      "price": 54.90,
      "original_price": 69.90,
      "currency_id": "BRL",
      "offer_id": "PDISC-MLB12345",
      "meli_percentage": null,
      "start_date": "2026-04-01T00:00:00Z",
      "end_date": "2026-04-30T23:59:59Z",
      "net_proceeds": {
        "amount": 47.23,
        "currency_id": "BRL"
      }
    }
  ],
  "paging": {
    "offset": 0,
    "limit": 50,
    "total": 1
  }
}
```

---

## 3. FLUXO CORRETO — Alterar Preço com Promoção Ativa

```
1. GET /seller-promotions/items/{id}?app_version=v2
   → Verificar se há promoção ativa (status = "started" ou "pending")

2a. Se SEM promoção ativa:
    → PUT /items/{id} com {"price": novo_preco}

2b. Se COM promoção ativa (PRICE_DISCOUNT):
    → DELETE /seller-promotions/items/{id}?user_id={seller_id}&promotion_type=PRICE_DISCOUNT
    → PUT /items/{id} com {"price": novo_preco}
    (OU criar nova promoção com o deal_price desejado em vez de alterar o preço base)

2c. Se COM promoção ativa (DOD/LIGHTNING):
    → NÃO alterar — estas promoções são gerenciadas pelo marketplace
    → Retornar erro ao usuário informando que o item está em oferta do marketplace
```

---

## 4. PEDIDOS (ORDERS)

### GET /orders/search
Busca pedidos do vendedor com filtros.

**URL:** `GET https://api.mercadolibre.com/orders/search`
**Auth:** Obrigatória
**Params:**
- `seller` (obrigatório): ID do vendedor ML
- `order.date_created.from`: data de início ISO 8601
- `order.date_created.to`: data de fim ISO 8601 (opcional)
- `order.status`: status do pedido (`paid`, `cancelled`, etc)
- `sort`: `date_desc` ou `date_asc`
- `offset`: paginação (padrão 0)
- `limit`: máximo 50 por página

**Notas:**
- Parâmetro `q` é busca textual — NÃO é filtro exato por item_id
- Validar item_id no resultado comparando `order_items[].item.id` (uppercase, sem hífens)
- Paginar se `paging.total > limit`

**Validado com curl:** Sim (2026-03-12)

---

## 5. VISITAS

### GET /items/{id}/visits/time_window
Visitas de um item por janela de tempo.

**URL:** `GET https://api.mercadolibre.com/items/{item_id}/visits/time_window`
**Auth:** Não obrigatória
**Params:**
- `last`: número de unidades (ex: `7`)
- `unit`: `day`, `hour`, `month`

**Response:**
```json
{
  "item_id": "MLB6205732214",
  "total_visits": 142,
  "results": [
    {"date": "2026-04-01T00:00:00Z", "total": 22},
    {"date": "2026-04-02T00:00:00Z", "total": 18}
  ]
}
```

**Validado com curl:** Sim (2026-03-12)

---

### GET /visits/items
Visitas em bulk para múltiplos itens.

**URL:** `GET https://api.mercadolibre.com/visits/items`
**Auth:** Não obrigatória
**Params:**
- `ids`: lista separada por vírgulas (máx 50 por chamada)
- `date_from`: YYYY-MM-DD
- `date_to`: YYYY-MM-DD

**Response (lista):**
```json
[
  {"item_id": "MLB6205732214", "total_visits": 142},
  {"item_id": "MLB9876543210", "total_visits": 89}
]
```

**Validado com curl:** Sim (2026-03-25)

---

## 6. USUÁRIOS E AUTENTICAÇÃO

### GET /users/{seller_id}
Dados do vendedor incluindo reputação.

**URL:** `GET https://api.mercadolibre.com/users/{seller_id}`
**Auth:** Obrigatória

**Campos relevantes:**
```json
{
  "id": 2050442871,
  "nickname": "MSM_PRIME",
  "seller_reputation": {
    "level_id": "5_green",
    "power_seller_status": "gold",
    "transactions": {"total": 500, "completed": 492, "canceled": 8},
    "metrics": {
      "claims": {"rate": 0.0007, "value": 3},
      "delayed_handling_time": {"rate": 0.0, "value": 0},
      "cancellations": {"rate": 0.016, "value": 8}
    }
  }
}
```

**Validado com curl:** Sim (2026-03-12)

---

### POST /oauth/token (Refresh)
Renova o token de acesso usando o refresh_token.

**URL:** `POST https://api.mercadolibre.com/oauth/token`
**Auth:** Não obrigatória no header (credenciais no body)
**Content-Type:** `application/x-www-form-urlencoded`

**Body:**
```
grant_type=refresh_token
&refresh_token={refresh_token}
&client_id={ML_CLIENT_ID}
&client_secret={ML_CLIENT_SECRET}
```

**Response:**
```json
{
  "access_token": "APP_USR-...",
  "token_type": "bearer",
  "expires_in": 21600,
  "scope": "offline_access read write",
  "refresh_token": "TG-..."
}
```

**Validado com curl:** Sim (2026-03-12)

---

## 7. ANÚNCIOS DO VENDEDOR

### GET /users/{seller_id}/items/search
Lista anúncios de um vendedor com filtros.

**URL:** `GET https://api.mercadolibre.com/users/{seller_id}/items/search`
**Auth:** Obrigatória
**Params:**
- `status`: `active`, `paused`, `closed`
- `offset`: paginação
- `limit`: máximo 50

**Validado com curl:** Sim (2026-03-12)

---

## 8. STATUS DE VALIDAÇÃO DOS ENDPOINTS DE PROMOÇÃO

| Endpoint | Método | Validado | Data |
|----------|--------|----------|------|
| `/seller-promotions/items/{id}` (GET) | GET | PENDENTE | — |
| `/seller-promotions/items/{id}` (POST PRICE_DISCOUNT) | POST | PENDENTE | — |
| `/seller-promotions/items/{id}` (DELETE) | DELETE | PENDENTE | — |
| `/seller-promotions/items/massive/{id}` (DELETE) | DELETE | PENDENTE | — |

**ACAO NECESSÁRIA:** Executar curl real com token de produção antes de implementar repricing via promoções.

```bash
# Obter token MSM
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# Obter token ML da conta
ML_TOKEN=$(curl -s https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data[0]['access_token'])")

# Testar GET promoções de um item
curl -s "https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?app_version=v2" \
  -H "Authorization: Bearer $ML_TOKEN" | python3 -m json.tool

# Testar POST criar promoção PRICE_DISCOUNT (usar item de teste!)
curl -X POST "https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?user_id=2050442871" \
  -H "Authorization: Bearer $ML_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"promotion_type":"PRICE_DISCOUNT","deal_price":54.90,"start_date":"2026-04-02T00:00:00Z","finish_date":"2026-05-02T23:59:59Z"}' \
  | python3 -m json.tool

# Testar DELETE promoção
curl -X DELETE "https://api.mercadolibre.com/seller-promotions/items/MLB6205732214?user_id=2050442871&promotion_type=PRICE_DISCOUNT" \
  -H "Authorization: Bearer $ML_TOKEN" \
  -v
```

---

## 9. PROBLEMAS CONHECIDOS DO CLIENT.PY ATUAL

### create_promotion (linhas 376-403) — DIVERGÊNCIA CRÍTICA
O método atual usa:
- URL: `POST /seller-promotions/users/{seller_id}` — **INCORRETO**
- Body: `{"items": [...], "discount": {"type": "percentage", "value": pct}}` — **INCORRETO**

O endpoint correto documentado acima é:
- URL: `POST /seller-promotions/items/{item_id}?user_id={seller_id}`
- Body: `{"promotion_type": "PRICE_DISCOUNT", "deal_price": float, "start_date": "...", "finish_date": "..."}`

### update_promotion (linhas 405-430) — DIVERGÊNCIA
O método atual usa `PUT /seller-promotions/{promotion_id}`.
A documentação oficial indica que PRICE_DISCOUNT NÃO suporta PUT — é necessário DELETE + POST.
PUT só funciona para SELLER_CAMPAIGN com endpoint `/marketplace/seller-promotions/seller-campaign/{campaign_id}`.

**ACAO:** Corrigir `create_promotion` e `update_promotion` no client.py antes de usar em produção.
