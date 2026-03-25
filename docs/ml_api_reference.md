# API do Mercado Livre — Referencia Validada

> Este arquivo e a FONTE DA VERDADE para integracao ML no MSM_Pro.
> Todo endpoint usado no projeto DEVE estar documentado aqui.
> O agente `ml-api` e responsavel por manter este arquivo atualizado.

**Base URL:** `https://api.mercadolibre.com`
**Auth:** Bearer token no header `Authorization: Bearer {access_token}`
**Rate Limit:** ~1 req/seg por app. Respeitar header `Retry-After` em 429.
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br

---

## 1. Dados do Anuncio

### GET /items/{ITEM_ID}

Retorna todos os dados de um anuncio.

**Parametros:** nenhum obrigatorio (pode adicionar `?attributes=all` para mais campos)

**Resposta real (MLB6205732214 — validado 2026-03-25):**
```json
{
  "id": "MLB6205732214",
  "title": "Cesto De Roupa Suja Separador Organizador Dobravel Multiuso",
  "price": 50.7,
  "base_price": 50.7,
  "original_price": 84.5,
  "sale_price": null,
  "sale_conditions": null,
  "promotions": null,
  "deal_ids": [],
  "available_quantity": 15,
  "sold_quantity": 263,
  "status": "active",
  "listing_type_id": "gold_special",
  "tags": ["standard_price_by_quantity", "catalog_boost", "immediate_payment", "cart_eligible"],
  "catalog_listing": true,
  "catalog_product_id": "MLB62743947",
  "seller_id": 2050442871,
  "category_id": "MLB269766",
  "condition": "new",
  "shipping": {
    "mode": "me2",
    "logistic_type": "fulfillment",
    "free_shipping": false,
    "local_pick_up": false
  },
  "item_relations": [{"id": "MLB4071282513", "variation_id": 188076460991}]
}
```

---

### HIERARQUIA DE PRECOS — EXPLICACAO COMPLETA (validado 2026-03-25)

#### Campos de preco no /items/{id}

| Campo | Tipo | Nullable | Descricao | Quando presente |
|-------|------|----------|-----------|-----------------|
| `price` | float | Nunca | Preco ATUAL que o comprador paga na tela | SEMPRE |
| `base_price` | float | Nunca | Preco base do anuncio ANTES de qualquer desconto | SEMPRE |
| `original_price` | float | Sim | Preco cheio (riscado) quando vendedor aplica desconto proprio | Quando vendedor cria desconto |
| `sale_price` | object/null | Sim | Objeto com `amount`, `currency_id`. Promoco do MARKETPLACE (ML cria, nao o vendedor) | RARAMENTE — so campanhas do ML |
| `sale_conditions` | null | Sim | Campo legado — nunca visto populado em 2026 | Quase nunca |
| `promotions` | null | Sim | Campo legado — nunca visto populado em 2026 | Quase nunca |
| `deal_ids` | list | Sim | IDs de deals do marketplace. Lista vazia `[]` quando nao tem deal ativo | SEMPRE (lista vazia ou preenchida) |
| `tags` | list | Sim | Tags do anuncio (catalog_boost, immediate_payment, etc.) | SEMPRE |

#### Regra de interpretacao de precos

```
CASO 1 — Sem promocao (o mais comum):
  price = 50.70   (preco de venda)
  base_price = 50.70
  original_price = null
  => O comprador paga: price

CASO 2 — Desconto proprio do vendedor (ex: SELLER_CAMPAIGN):
  price = 50.70   (preco com desconto)
  base_price = 84.50 (pode variar)
  original_price = 84.50   (preco cheio, aparece RISCADO na tela)
  sale_price = null   (NAO eh usado para desconto do vendedor!)
  => O comprador paga: price
  => Preco cheio (riscado) = original_price

CASO 3 — Campanha do MARKETPLACE (ML cria a promocao):
  price = 50.70   (preco base do vendedor)
  original_price = null (ou preco anterior)
  sale_price = {"amount": 45.00, "currency_id": "BRL", ...}
  => O comprador paga: sale_price.amount
  => Para calcular preco efetivo: usar sale_price.amount quando sale_price != null E sale_price.amount < price

CASO 4 — Anuncio do MLB6205732214 (situacao REAL em 2026-03-25):
  price = 50.70          (preco de venda ATUAL — com desconto do vendedor ATIVO)
  base_price = 50.70     (igual ao price quando promocao ja esta aplicada)
  original_price = 84.50 (preco cheio riscado)
  sale_price = null
  => O comprador paga: 50.70
  => Preco cheio = 84.50
  => Desconto = 40.1%
```

#### O que e o preco R$57,18 / R$57,38?

Esses valores aparecem no endpoint `/seller-promotions/items/{id}` (nao em /items):
- `P-MLB17129028` (SMART, status=started): preco sugerido para campanha "Aumente suas vendas" = R$57,38
- `P-MLB17313012` (SMART, status=candidate): campanha futura = R$57,38
- `C-MLB3450113` (SELLER_CAMPAIGN, status=started): campanha "ate 09 abril" = R$63,38

O preco R$57,38 e o preco que ficaria ativo SE o vendedor aderisse a campanha SMART do ML.
O preco atual (que o comprador paga de fato) e R$50,70 — conforme `price` no /items/{id}.

IMPORTANTE: O nosso sistema salva `price = 50.70` corretamente.
O `original_price = 84.50` esta correto (preco cheio riscado).
NAO ha discrepancia no banco — o preco correto esta salvo.

#### O que usar para "preco que o comprador paga"?

```python
# LOGICA CORRETA (ja implementada em service_sync.py):
price = item["price"]  # preco base de venda

# Se ML criou uma campanah marketplace (raro):
sale_price_data = item.get("sale_price")
if sale_price_data and isinstance(sale_price_data, dict):
    sp_amount = sale_price_data.get("amount")
    if sp_amount and float(sp_amount) < float(price):
        price = sp_amount  # comprador paga sale_price.amount

# Preco cheio (riscado):
original_price = item.get("original_price")  # None se sem desconto
```

---

### Campos importantes

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `price` | float | Nao | Preco ATUAL de venda — o que o comprador paga |
| `base_price` | float | Nao | Preco base antes de qualquer desconto (igual a price quando promocao ja aplicada) |
| `original_price` | float | **Sim** | Preco antes do desconto do VENDEDOR. Null se sem desconto. Aparece riscado na tela. |
| `sale_price` | object/null | **Sim** | Objeto com `amount`. So para promocoes do MARKETPLACE (ML cria). sale_price.amount e o preco final quando presente. |
| `sale_conditions` | null | **Sim** | Campo legado, raramente preenchido |
| `promotions` | null | **Sim** | Campo legado, raramente preenchido |
| `deal_ids` | list | Nao | IDs de deals ativos. Lista vazia quando nao tem deal. |
| `available_quantity` | int | Nao | Estoque disponivel |
| `sold_quantity` | int | Nao | Total vendido historico (cresce monotonicamente, NAO e vendas do dia) |
| `listing_type_id` | string | Nao | `"gold_special"` (classico), `"gold_pro"` (premium) |
| `status` | string | Nao | `"active"`, `"paused"`, `"closed"`, `"under_review"` |
| `catalog_listing` | bool | Nao | Se o anuncio e de catalogo ML |
| `item_relations` | list | Sim | Anuncios relacionados (variantes de catalogo) |

**ATENCAO — Bug de listing_type confirmado (2026-03-25):**
- MLB6205732214 retorna `listing_type_id: "gold_special"` E `shipping.logistic_type: "fulfillment"`
- O banco salva como `listing_type: "full"` (correto pela logica do service_sync.py)
- A logica atual e: `"gold_pro" + fulfillment = full`. Mas este anuncio e `"gold_special" + fulfillment`
- CONCLUSAO: Um anuncio `"gold_special"` pode ter fulfillment (frete Full) mas a taxa seria de Classico (~11.5%), nao Premium
- A classificacao como "full" esta incorreta para este caso especifico

**Gotchas:**
- `sale_price` e um OBJETO, nao float. Acessar via `sale_price["amount"]` se presente.
- `sale_price` e null para descontos do VENDEDOR — usar `original_price` como preco cheio
- Para saber se e Full: checar `shipping.logistic_type == "fulfillment"` (independente de listing_type_id)
- `sold_quantity` e total historico, NAO vendas do dia.
- `base_price` e diferente de `price` quando ha desconto ativo no ML (antes da aplicacao do desconto)
- `catalog_listing: true` significa que o preco pode ser controlado pelo catalogo ML

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-25 (MLB6205732214)

---

## 2. Visitas por Item

### GET /items/{ITEM_ID}/visits/time_window

Retorna visitas diarias de UM item especifico.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `last` | int | Sim | Quantidade de periodos |
| `unit` | string | Sim | `"day"` ou `"hour"` |

**Resposta real:**
```json
{
  "item_id": "MLB1234567890",
  "results": [
    {"date": "2026-03-11T00:00:00Z", "total": 45},
    {"date": "2026-03-12T00:00:00Z", "total": 62}
  ]
}
```

**Campos:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `results[].date` | string ISO | Data do periodo |
| `results[].total` | int | Total de visitas naquele dia |

**Gotchas:**
- Funciona para itens de QUALQUER vendedor (publico).
- `last=1&unit=day` retorna apenas o dia atual (pode estar parcial ate meia-noite).
- Para ontem/anteontem: usar `last=3&unit=day` e pegar por indice de data.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

## 3. Visitas em Bulk (multiplos itens)

### GET /visits/items

Retorna visitas de MULTIPLOS itens em uma unica chamada.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `ids` | string | Sim | IDs separados por virgula (max 50) |
| `date_from` | string | Sim | `YYYY-MM-DD` |
| `date_to` | string | Sim | `YYYY-MM-DD` |

**Resposta real:**
```json
{
  "MLB1234567890": 62,
  "MLB9876543210": 38
}
```

**ATENCAO:** A resposta e um dict simples `{ item_id: total_visits }`.
NAO retorna breakdown por dia — retorna o TOTAL do periodo.

**Gotchas:**
- Maximo 50 IDs por chamada. Paginar se necessario.
- IDs devem ser normalizados (sem hifen): `MLB1234567890`, nao `MLB-1234567890`.
- Se um ID nao existe, simplesmente nao aparece no resultado (sem erro).
- Para ter visitas POR DIA, usar endpoint individual (#2) ou o endpoint por usuario (#4).

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

## 4. Visitas Agregadas do Vendedor

### GET /users/{USER_ID}/items_visits/time_window

Retorna visitas TOTAIS de TODOS os itens do vendedor, agregadas por dia.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `last` | int | Sim | Quantidade de periodos |
| `unit` | string | Sim | `"day"` |

**Resposta real:**
```json
{
  "user_id": 2050442871,
  "date_from": "2026-03-10T00:00:00Z",
  "date_to": "2026-03-12T23:59:59Z",
  "total_visits": 2923,
  "results": [
    {"date": "2026-03-10T00:00:00Z", "total": 800},
    {"date": "2026-03-11T00:00:00Z", "total": 1100},
    {"date": "2026-03-12T00:00:00Z", "total": 1023}
  ]
}
```

**ATENCAO:** Este endpoint retorna o TOTAL de TODOS os anuncios somados.
NAO retorna breakdown por item. Use para KPI geral, nao para snapshots individuais.

**Gotchas:**
- Requer token do proprio vendedor.
- Util para KPI "Total de visitas hoje" no dashboard.
- NAO serve para snapshot por MLB — use endpoint #2 ou #3.

**Validado com curl:** Pendente validacao real
**Ultima validacao:** —

---

## 5. Pedidos/Vendas

### GET /orders/search

Busca pedidos do vendedor com filtros.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `seller` | string | Sim | ID do vendedor ML |
| `order.date_created.from` | string ISO | Sim | Inicio do periodo. Formato: `2026-03-12T00:00:00.000-03:00` |
| `order.date_created.to` | string ISO | Recomendado | Fim do periodo. Formato: `2026-03-12T23:59:59.000-03:00` |
| `order.status` | string | Recomendado | `paid` para so pedidos pagos |
| `q` | string | Opcional | Busca textual (pode usar MLB ID) |
| `sort` | string | Opcional | `date_desc`, `date_asc` |
| `limit` | int | Opcional | Max 50 |
| `offset` | int | Opcional | Para paginacao |

**Resposta real:**
```json
{
  "query": "",
  "results": [
    {
      "id": 123456789,
      "status": "paid",
      "date_created": "2026-03-12T14:30:00.000-03:00",
      "date_closed": "2026-03-12T14:30:05.000-03:00",
      "order_items": [
        {
          "item": {
            "id": "MLB1234567890",
            "title": "Produto Exemplo",
            "variation_id": null
          },
          "quantity": 1,
          "unit_price": 129.90
        }
      ],
      "total_amount": 129.90,
      "buyer": {
        "id": 987654321,
        "nickname": "COMPRADOR123"
      }
    }
  ],
  "paging": {
    "total": 5,
    "offset": 0,
    "limit": 50
  }
}
```

**Campos importantes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `results[].order_items[].item.id` | string | MLB ID do item vendido |
| `results[].order_items[].quantity` | int | Quantidade vendida nesse pedido |
| `results[].order_items[].unit_price` | float | Preco unitario de venda |
| `results[].status` | string | `"paid"`, `"cancelled"`, etc. |
| `paging.total` | int | Total de resultados (para paginacao) |

**Status possiveis de order (confirmado via HAR do ML Metricas):**
| Status | Descricao | Uso no MSM_Pro |
|--------|-----------|----------------|
| `paid` | Pedido pago | Contamos como venda valida |
| `cancelled` | Pedido cancelado | Contamos como cancelamento |
| `returned` / `refunded` | Devolvido/reembolsado | Contamos como devolucao |
| `pending` | Aguardando pagamento | Ignoramos |

**Metricas que o ML calcula internamente (extraido do HAR):**
- `gross_sales` = soma de unit_price * quantity de todos os pedidos
- `sell_quantity` = numero de pedidos (NAO unidades)
- `sold_units` = numero de unidades
- `average_price_by_unit` = gross_sales / sold_units
- `average_price_by_sell` = gross_sales / sell_quantity
- `conversion` = sell_quantity / visits * 100
- `cancelled_gross_sales` = valor R$ dos cancelamentos
- `returns_gross_sales` = valor R$ das devolucoes

**Gotchas:**
- Para vendas validas: usar `order.status=paid`
- Para cancelamentos: usar `order.status=cancelled`
- Para devolucoes: buscar sem filtro de status e filtrar por `returned`/`refunded`
- **SEMPRE usar `order.date_created.to`** — delimitar o periodo exato.
- **Fuso horario `-03:00`** (Brasilia) nas datas, NAO `-00:00`.
- O parametro `q` e busca TEXTUAL, nao filtro exato por item. Para filtrar por item, iterar `order_items[].item.id` no resultado.
- Maximo 50 resultados por pagina. Se `paging.total > 50`, paginar.
- `item.id` pode vir com ou sem hifen — normalizar antes de comparar.
- `sell_quantity` != `sold_units`: 1 pedido com 2 unidades = 1 venda, 2 unidades.

**Validado com curl:** Sim
**Validado com HAR do ML Metricas:** Sim (12 metricas diarias confirmadas)
**Ultima validacao:** 2026-03-12

---

## 6. Listar Anuncios do Vendedor

### GET /users/{SELLER_ID}/items/search

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `status` | string | Opcional | `"active"`, `"paused"`, etc. |
| `offset` | int | Opcional | Para paginacao |
| `limit` | int | Opcional | Max 50 |

**Resposta real:**
```json
{
  "seller_id": "2050442871",
  "results": ["MLB1234567890", "MLB9876543210"],
  "paging": {
    "total": 16,
    "offset": 0,
    "limit": 50
  }
}
```

**Gotchas:**
- Retorna apenas os IDs, nao os dados completos. Para dados, chamar `/items/{id}` para cada um.
- Paginar se `paging.total > limit`.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

## 7. Promocoes do Vendedor

### GET /seller-promotions/items/{ITEM_ID}

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `app_version` | string | Recomendado | `"v2"` |

**Resposta real (MLB6205732214 — validado 2026-03-25):**
```json
[
  {
    "id": "P-MLB17129028",
    "type": "SMART",
    "ref_id": "OFFER-MLB6205732214-12674803799",
    "status": "started",
    "price": 57.38,
    "meli_percentage": 3.2,
    "seller_percentage": 28.9,
    "original_price": 84.5,
    "name": "Aumente suas vendas"
  },
  {
    "id": "C-MLB3450113",
    "type": "SELLER_CAMPAIGN",
    "sub_type": "FLEXIBLE_PERCENTAGE",
    "status": "started",
    "price": 63.38,
    "original_price": 84.5,
    "start_date": "2026-03-10T00:00:00",
    "finish_date": "2026-04-09T23:59:59",
    "name": "ate 09 abril"
  },
  {
    "id": "P-MLB17313012",
    "type": "SMART",
    "ref_id": "CANDIDATE-MLB6205732214-75529536833",
    "status": "candidate",
    "price": 57.38,
    "meli_percentage": 3.2,
    "seller_percentage": 28.9,
    "original_price": 84.5,
    "name": "Abril Casa Super Ofertas"
  },
  {
    "type": "PRICE_DISCOUNT",
    "status": "candidate",
    "price": 0,
    "original_price": 84.5,
    "min_discounted_price": 24,
    "max_discounted_price": 80.27,
    "suggested_discounted_price": 57.38
  }
]
```

**Tipos de promocao (type):**
| type | Descricao | Quem cria |
|------|-----------|-----------|
| `SMART` | Campanhas inteligentes do ML (Aumente suas vendas, Black Friday, etc.) | ML propoe, vendedor adere |
| `SELLER_CAMPAIGN` | Campanha criada pelo proprio vendedor no Gerenciador de Promocoes | Vendedor |
| `PRICE_DISCOUNT` | Desconto de preco simples (riscado) | Vendedor |
| `DEAL` | Campanhas de eventos sazonais (Liquida, Outlet) | ML propoe, vendedor adere |

**Campos de cada promocao:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `id` | string | ID da promocao (prefixo P- para campanhas ML, C- para do vendedor) |
| `type` | string | SMART / SELLER_CAMPAIGN / PRICE_DISCOUNT / DEAL |
| `status` | string | `started` = ativa agora, `candidate` = ML propoe, nao ativa, `finished` = encerrada |
| `price` | float | Preco QUE FICARIA ativo se a promocao estiver `started` (nao e o preco atual do item!) |
| `original_price` | float | Preco cheio (riscado). Sempre o `base_price` do anuncio. |
| `meli_percentage` | float | Percentual que o ML subsidia do desconto (campanhas SMART) |
| `seller_percentage` | float | Percentual de desconto que o vendedor da |
| `suggested_discounted_price` | float | Preco sugerido pelo ML para desconto (candidates) |

**ATENCAO — Relacao entre seller-promotions e /items/{id}:**

O endpoint /items/{id} retorna `price: 50.70` para o MLB6205732214.
O seller-promotions mostra campanhas com `price: 57.38` e `price: 63.38`.

ISSO NAO E CONTRADICAO. Sao precos diferentes:
- `price` em /items = preco ATUAL que o comprador paga (50.70 = preco do vendedor com desconto proprio ativo)
- `price` em seller-promotions = preco que FICARIA ativo SE a campanha entrar em vigor
- Uma campanha SMART com `status=started` pode ter price=57.38 mas o vendedor pode ter seu proprio desconto ainda mais agressivo (50.70)
- O comprador sempre paga o menor preco disponivel: `min(price_item, sale_price_amount_if_present)`

**Gotchas:**
- Resposta e uma lista direta (nao dict com results).
- `status=candidate`: ML propoe a campanha mas o vendedor ainda NAO aderiu. NAO afeta o preco atual.
- `status=started`: a campanha esta ativa. Se o price da campanha for MENOR que o price atual do item, o comprador paga o price da campanha.
- Pode retornar 404 se item nao tem promocoes — tratar como lista vazia.
- Requer token do vendedor dono do anuncio (nao e endpoint publico).
- `price=0` em candidates sem sub_type = slot vazio para o vendedor configurar.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-25 (MLB6205732214)

---

## 8. Perguntas do Anuncio

### GET /questions/search

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `item` | string | Sim | MLB ID |
| `status` | string | Opcional | `"unanswered"` para so nao respondidas |

**Resposta real:**
```json
{
  "total": 3,
  "questions": [
    {
      "id": 123,
      "text": "Tem na cor azul?",
      "status": "UNANSWERED",
      "date_created": "2026-03-12T10:00:00Z"
    }
  ]
}
```

**Gotchas:**
- Campo de contagem e `total`, nao `count`.
- Lista de perguntas em `questions`, nao `results`.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

## 9. OAuth — Refresh Token

### POST /oauth/token

**Body (form-urlencoded):**
| Param | Tipo | Obrigatorio |
|-------|------|-------------|
| `grant_type` | string | Sim — `"refresh_token"` |
| `client_id` | string | Sim |
| `client_secret` | string | Sim |
| `refresh_token` | string | Sim |

**Resposta real:**
```json
{
  "access_token": "APP_USR-...",
  "token_type": "Bearer",
  "expires_in": 21600,
  "scope": "offline_access read write",
  "user_id": 2050442871,
  "refresh_token": "TG-..."
}
```

**Gotchas:**
- `expires_in` e em SEGUNDOS (21600 = 6 horas).
- Refresh token tambem pode mudar — sempre salvar o novo.
- Se refresh falhar com 400, o usuario precisa re-autorizar via OAuth.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

## 10. Alterar Preco

### PUT /items/{ITEM_ID}

**Body (JSON):**
```json
{
  "price": 139.90
}
```

**Resposta:** Retorna o item completo atualizado (mesmo formato do GET /items/{id}).

**Gotchas:**
- Se o item tem promocao ativa, alterar o preco pode desativar a promocao.
- Precisa de token do vendedor dono.

**Validado com curl:** Pendente
**Ultima validacao:** —

---

## Mapeamento: listing_type_id → Tipo comercial

| listing_type_id | Tipo | Taxa ML (estimada) |
|-----------------|------|---------|
| `gold_special` | Classico | ~11.5% |
| `gold_pro` | Premium | ~17% (inclui parcelamento) |
| `gold_pro` + `shipping.logistic_type = "fulfillment"` | Full | ~17% + frete gratis |

> **NOTA:** Taxas REAIS variam por categoria. Usar endpoint #11 para taxa exata.
> O print real da conta MSM IMPORTS confirmou: Premium = 17% (R$84,66 sobre R$498).

---

## 11. Taxas por Categoria (Comissao Real)

### GET /sites/MLB/listing_prices

Retorna a taxa REAL que o ML cobra, por categoria e tipo de anuncio.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `price` | float | Sim | Preco de venda |
| `category_id` | string | Sim | Categoria ML (ex: MLB189462) |
| `listing_type_id` | string | Sim | `gold_pro`, `gold_special`, `free` |

**Resposta real (pode ser lista):**
```json
[
  {
    "listing_type_id": "gold_pro",
    "listing_type_name": "Premium",
    "sale_fee_amount": 2000,
    "sale_fee_details": {
      "percentage_fee": 36,
      "fixed_fee": 200,
      "gross_amount": 2000,
      "financing_add_on_fee": 23
    },
    "listing_fee_amount": 0
  }
]
```

**Campos importantes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `sale_fee_amount` | int | Valor total da comissao em CENTAVOS |
| `sale_fee_details.percentage_fee` | int | Percentual da comissao (varia por categoria) |
| `sale_fee_details.fixed_fee` | int | Taxa fixa adicional em centavos |
| `sale_fee_details.financing_add_on_fee` | int | Taxa de parcelamento |

**Gotchas:**
- Resposta pode ser LISTA (um item por listing_type). Filtrar pelo `listing_type_id` desejado.
- Valores em CENTAVOS, nao reais. Dividir por 100.
- `percentage_fee` eh o percentual TOTAL (ja inclui parcelamento em alguns casos).
- Se `category_id` nao informado, retorna taxa generica.

**Validado com curl:** Pendente validacao real
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/comissao-por-vender
**Ultima validacao:** —

---

## 12. Custo de Frete do Vendedor

### GET /users/{USER_ID}/shipping_options/free

Retorna o custo de frete que o ML desconta do vendedor.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `dimensions` | string | Sim* | Formato: `HxWxL,PESO` (cm e gramas). Ex: `60x364x63,661` |
| `item_id` | string | Sim* | MLB ID (alternativa a dimensions) |
| `item_price` | float | Sim | Preco do item |
| `mode` | string | Nao | `me2` (padrao), `me1`, `custom` |
| `free_shipping` | bool | Nao | True/False |
| `listing_type_id` | string | Nao | `gold_pro`, `gold_special` |

*Usar `dimensions` OU `item_id`.

**Resposta real:**
```json
{
  "coverage": {
    "all_country": {
      "list_cost": 8106.49,
      "currency_id": "BRL",
      "billable_weight": 5828
    }
  }
}
```

**Gotchas:**
- `list_cost` eh em REAIS (nao centavos).
- Sem `dimensions` e sem `item_id`, retorna erro.
- Para Full: o custo de frete eh diferente (ML subsidia parte).
- Para itens com "envio por conta do comprador", o seller nao paga frete.

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/custos-de-envio
**Ultima validacao:** —

---

## 13. SKU do Vendedor no Item

No response de `GET /items/{ITEM_ID}`, o SKU aparece em dois lugares:

### Campo direto:
```json
{
  "seller_custom_field": "SKU-001-AZUL"
}
```

### Atributo no array:
```json
{
  "attributes": [
    {"id": "SELLER_SKU", "value_name": "SKU-001"}
  ]
}
```

### Em variacoes:
```json
{
  "variations": [
    {
      "seller_custom_field": "SKU-001-AZUL",
      "attributes": [
        {"id": "SELLER_SKU", "value_name": "SKU-001-AZUL"}
      ]
    }
  ]
}
```

**Prioridade de leitura:**
1. `seller_custom_field` do item (mais comum)
2. Atributo `SELLER_SKU` em `attributes[]`
3. Se tem variacoes, pegar da variacao principal

**Gotchas:**
- Pode ser null/vazio se vendedor nao cadastrou SKU
- Pode ser diferente por variacao (cor, tamanho)
- Campo de texto livre, sem validacao

---

## 14. Imagens do Item

No response de `GET /items/{ITEM_ID}`:

```json
{
  "thumbnail": "http://http2.mlstatic.com/D_...-I.jpg",
  "secure_thumbnail": "https://http2.mlstatic.com/D_...-I.jpg",
  "pictures": [
    {
      "id": "959699-MLB...",
      "secure_url": "https://http2.mlstatic.com/D_...-O.jpg",
      "size": "500x500",
      "max_size": "994x1020"
    }
  ]
}
```

**Usar:** `secure_thumbnail` para miniatura HTTPS no frontend.
**Sufixos de tamanho:** `-I.jpg` = thumbnail, `-O.jpg` = medio, `-F.jpg` = full.

---

## 15. Reputacao do Vendedor

### GET /users/{SELLER_ID}

Retorna dados completos do usuario ML, incluindo reputacao.

**Campo relevante: `seller_reputation`**

```json
{
  "id": 2050442871,
  "nickname": "MSM_PRIME",
  "seller_reputation": {
    "level_id": "5_green",
    "power_seller_status": "gold",
    "transactions": {
      "total": 2545,
      "completed": 2530,
      "canceled": 15,
      "period": "historic",
      "ratings": {
        "positive": 0.98,
        "negative": 0.01,
        "neutral": 0.01
      }
    },
    "metrics": {
      "claims": {
        "rate": 0.0,
        "value": 0,
        "period": "60 days"
      },
      "delayed_handling_time": {
        "rate": 0.0246,
        "value": 3,
        "period": "60 days"
      },
      "cancellations": {
        "rate": 0.0007,
        "value": 1,
        "period": "60 days"
      },
      "sales": {
        "period": "60 days",
        "completed": 122
      }
    }
  }
}
```

**Campos importantes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `seller_reputation.level_id` | string | Nivel: `"5_green"`, `"4_light_green"`, `"3_yellow"`, `"2_orange"`, `"1_red"` |
| `seller_reputation.power_seller_status` | string/null | `"gold"`, `"platinum"`, `"silver"`, ou null |
| `seller_reputation.transactions.total` | int | Total de transacoes historicas |
| `seller_reputation.transactions.completed` | int | Transacoes concluidas |
| `seller_reputation.metrics.claims.rate` | float | Taxa de reclamacoes (0.0 a 1.0). Multiplicar por 100 para %. |
| `seller_reputation.metrics.delayed_handling_time.rate` | float | Taxa de atrasos no envio |
| `seller_reputation.metrics.cancellations.rate` | float | Taxa de cancelamentos |
| `seller_reputation.metrics.*.value` | int | Quantidade absoluta de casos no periodo |

**Gotchas:**
- `rate` vem como decimal (0.0007 = 0.07%). Multiplicar por 100 para exibir como percentual.
- `mediations` pode nao estar presente como campo separado em todas as contas.
- `transactions.total` e historico completo, nao apenas 60 dias. Para 60 dias, usar `metrics.sales.completed`.
- Requer token do proprio vendedor para dados completos.

**Validado com curl:** Pendente validacao com dados reais
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/dados-do-usuario
**Ultima validacao:** 2026-03-12

---

---

## 16. OAuth — Trocar Codigo por Token

### POST /oauth/token (grant_type=authorization_code)

Usado no callback do OAuth apos o usuario autorizar o app.

**Body (form-urlencoded):**
| Param | Tipo | Obrigatorio |
|-------|------|-------------|
| `grant_type` | string | Sim — `"authorization_code"` |
| `client_id` | string | Sim |
| `client_secret` | string | Sim |
| `code` | string | Sim — codigo recebido no callback |
| `redirect_uri` | string | Sim — deve ser identico ao cadastrado no app |

**Resposta real:**
```json
{
  "access_token": "APP_USR-...",
  "token_type": "Bearer",
  "expires_in": 21600,
  "scope": "offline_access read write",
  "user_id": 2050442871,
  "refresh_token": "TG-..."
}
```

**Gotchas:**
- `user_id` vem no proprio token response — nao precisa de chamada extra a /users/me
- Em producao, ML retorna sempre o novo `refresh_token` — salvar imediatamente
- Se `code` ja foi usado: 400 bad_request

**Validado com curl:** Sim (producao)
**Ultima validacao:** 2026-03-12

---

## 17. Informacoes do Usuario ML Autenticado

### GET /users/me

Retorna informacoes do usuario dono do token. Usado apos OAuth para pegar nickname e email.

**Parametros:** Nenhum. Token no header obrigatorio.

**Resposta real (campos relevantes):**
```json
{
  "id": 2050442871,
  "nickname": "MSM_PRIME",
  "email": "maikeo@example.com",
  "country_id": "BR",
  "site_id": "MLB",
  "seller_reputation": { ... }
}
```

**Gotchas:**
- Em `save_ml_account()`, o `user_id` ja vem no token response. `/users/me` e chamado para pegar `nickname` e `email`.
- `email` pode ser `null` se usuario nao autorizou scope de email.

**Validado com curl:** Sim (via auth flow)
**Ultima validacao:** 2026-03-12

---

## 18. Estoque Full (Fulfillment)

### GET /user-products/{ITEM_ID}/stock/fulfillment

Retorna o estoque Full de um item no centro de distribuicao do ML.

**Parametros:** Nenhum (item_id no path).

**Resposta real:**
```json
{
  "available": 42,
  "in_transit": 5,
  "not_available": 0
}
```

**Gotchas:**
- Retorna 404 se o item nao e Full — tratar com fallback `{"available": 0, "in_transit": 0}`.
- `available` = estoque pronto para venda no CD do ML.
- `in_transit` = estoque a caminho do CD, ainda nao disponivel.
- Requer token do vendedor dono do anuncio.
- Nao confundir com `available_quantity` do `/items/{id}` (que e o estoque total).

**Validado com curl:** Pendente validacao real
**Ultima validacao:** —

---

## 19. Taxas por Listing (listing_prices)

### GET /sites/MLB/listing_prices

Referencia: ver secao 11 acima. Este endpoint retorna a comissao ESTIMADA.

**AVISO CRITICO:** Os valores em `sale_fee_amount` e `sale_fee_details.percentage_fee` podem estar em CENTAVOS (dividir por 100) ou ja em unidades dependendo da versao da API. Validar com curl antes de usar em producao.

**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 20. Product Ads — Advertiser ID

### GET /advertising/advertisers

Verifica se a conta tem acesso a Product Ads e retorna o `advertiser_id`.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `product_id` | string | Sim | `PADS` (Product Ads), `DISPLAY`, `BADS` (Brand Ads) |

**Headers obrigatorios:**
- `Authorization: Bearer {access_token}`
- `Api-Version: 1` (recomendado)

**Resposta real (validada via doc oficial):**
```json
{
  "advertisers": [
    {
      "advertiser_id": 123456,
      "site_id": "MLB",
      "advertiser_name": "NOME_DO_ANUNCIANTE",
      "account_name": "NOME_DA_CONTA - ID"
    }
  ]
}
```

**ATENCAO — BUG CRITICO NO client.py:**
O codigo atual em `get_advertiser_id()` trata a resposta como `list` direta:
```python
if isinstance(data, list) and len(data) > 0:
    return str(data[0].get("advertiser_id"))
```
Mas a resposta REAL e um dict com chave `"advertisers"` (lista dentro do dict).
O codigo NAO acessa `data["advertisers"][0]` — portanto SEMPRE retorna `None`.

**Correcao necessaria:**
```python
# A resposta e: {"advertisers": [...]}
advertisers = data.get("advertisers", [])
if isinstance(advertisers, list) and advertisers:
    return str(advertisers[0].get("advertiser_id"))
return None
```

**Erros possiveis:**
- `404 No permissions found for user_id` = conta sem Product Ads habilitado (usuario precisa ir em ML > Mi perfil > Publicidad)
- `403 Forbidden` = token sem scope de publicidade

**Validado com curl:** Nao (API de ads nao e publica — requer conta com PADS ativo)
**Doc oficial:** https://developers.mercadolivre.com.br/en_us/product-ads-us-read
**Ultima validacao:** 2026-03-16 (via doc oficial)

---

## 21. Product Ads — Campanhas

### GET /advertising/advertisers/{ADVERTISER_ID}/product_ads/campaigns

Retorna campanhas de Product Ads com metricas de um anunciante.

**AVISO:** Existe versao mais nova do endpoint com sufixo `/search`. A versao sem `/search` foi deprecada em junho 2025. Verificar se o endpoint atual ainda funciona ou migrar para `/search`.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `date_from` | string | Sim | Formato `YYYY-MM-DD` |
| `date_to` | string | Sim | Formato `YYYY-MM-DD`. Range maximo: 90 dias retroativos. |
| `metrics` | string | Sim | Lista separada por virgula. Ver metricas abaixo. |
| `metrics_summary` | string | Opcional | `"true"` (STRING, nao boolean) — inclui totais agregados |
| `limit` | int | Opcional | Max por pagina |

**Metricas validas confirmadas pela doc oficial:**
`clicks, prints, ctr, cost, cpc, acos, organic_units_quantity, organic_units_amount, organic_items_quantity, direct_items_quantity, indirect_items_quantity, advertising_items_quantity, cvr, roas, sov, direct_units_quantity, indirect_units_quantity, units_quantity, direct_amount, indirect_amount, total_amount, impression_share, top_impression_share, lost_impression_share_by_budget, lost_impression_share_by_ad_rank, acos_benchmark`

**AVISO — Metricas no client.py:**
O client.py usa `"units_quantity,total_amount,cpc,ctr,cvr"` — esses nomes estao corretos.
POREM `"roas"` e `"acos"` sao metricas validas. `"cost"` e o correto (nao `"spend"`).

**Resposta esperada:**
```json
{
  "results": [
    {
      "id": "campaign_123",
      "name": "Campanha Principal",
      "status": "active",
      "daily_budget": 50.00,
      "metrics": {
        "clicks": 120,
        "prints": 5000,
        "cost": 35.50,
        "roas": 4.2,
        "acos": 23.8
      }
    }
  ],
  "paging": { "total": 1, "offset": 0, "limit": 50 }
}
```

**ATENCAO — BUG no client.py:**
O campo de gasto e `"cost"` na API ML, nao `"spend"`.
O `ads/service.py` usa `metric.get("spend", 0)` — **sempre retorna 0**.
Corrigir para `metric.get("cost", 0)`.

**Gotchas:**
- `metrics_summary: "true"` e STRING, nao boolean Python `True`.
- Metricas sao atualizadas diariamente as 10:00 GMT-3.
- `prints` = impressoes (nao confundir com `impressions`).
- Se conta nao tem PADS: 404.

**Validado com curl:** Nao (requer conta com PADS ativo)
**Doc oficial:** https://developers.mercadolivre.com.br/en_us/product-ads-us-read
**Ultima validacao:** 2026-03-16 (via doc oficial)

---

## 22. Product Ads — Metricas por Item

### GET /advertising/advertisers/{ADVERTISER_ID}/product_ads/items

Retorna metricas de ads agrupadas por item (anuncio MLB).

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `date_from` | string | Sim | `YYYY-MM-DD` |
| `date_to` | string | Sim | `YYYY-MM-DD` |
| `metrics` | string | Sim | Lista separada por virgula |
| `item_id` | string | Opcional | Filtrar por MLB ID especifico |
| `limit` | int | Opcional | Paginacao |

**Formato do `item_id` na resposta:**
O campo retornado para identificar o anuncio e `"item_id"` (com hifen) ou `"id"` (sem hifen).
**DEVE-SE NORMALIZAR** antes de comparar: `.upper().replace("-", "")`.

**Resposta esperada:**
```json
{
  "results": [
    {
      "item_id": "MLB1234567890",
      "title": "Produto X",
      "metrics": {
        "clicks": 45,
        "prints": 2000,
        "cost": 12.30,
        "roas": 3.8
      }
    }
  ]
}
```

**Gotchas:**
- O campo de gasto e `"cost"` (nao `"spend"`). O client.py nao usa esse endpoint diretamente para salvar snapshots — mas o `ads/service.py` vai encontrar `"spend"` como 0 sempre.
- `item_id` pode ou nao ter hifen — normalizar sempre.

**Validado com curl:** Nao (requer conta com PADS ativo)
**Doc oficial:** https://developers.mercadolivre.com.br/en_us/product-ads-us-read
**Ultima validacao:** 2026-03-16 (via doc oficial)

---

## 23. Campanhas de Publicidade (endpoint legado)

### GET /advertising/campaigns

**STATUS: POSSIVELMENTE DEPRECATED / NAO DOCUMENTADO OFICIALMENTE**

O client.py usa este endpoint em `get_campaigns()`:
```
GET /advertising/campaigns?user_id={seller_id}
```

**PROBLEMA:** Este endpoint NAO aparece na documentacao oficial atual do ML.
A doc oficial de Product Ads usa `/advertising/advertisers/{id}/product_ads/campaigns`.
O endpoint `/advertising/campaigns` provavelmente pertencia a uma versao antiga pre-PADS.

**Recomendacao:** Substituir por:
1. `get_advertiser_id()` — obter advertiser_id
2. `get_product_ads_campaigns(advertiser_id, ...)` — obter campanhas reais

O `ads/service.py` ja tenta `get_campaigns()` como primeiro passo — e correto ter fallback quando retorna 403/404.

**Validado com curl:** Nao
**Ultima validacao:** —

---

## 24. Metricas de Campanha (endpoint legado)

### GET /advertising/campaigns/{CAMPAIGN_ID}/metrics

**STATUS: POSSIVELMENTE DEPRECATED / NAO DOCUMENTADO OFICIALMENTE**

Usado em `get_campaign_metrics()` no client.py.
Nao encontrado na doc oficial atual. A doc atual usa o endpoint de campanhas com metricas embutidas (`/advertising/advertisers/{id}/product_ads/campaigns` com param `metrics=...`).

**Campos que o ads/service.py espera na resposta:**
```python
metric.get("impressions")  # ATENCAO: campo correto pode ser "prints"
metric.get("clicks")       # OK
metric.get("spend")        # ERRADO: campo correto e "cost"
metric.get("attributed_sales")   # campo pode nao existir
metric.get("attributed_revenue") # campo pode nao existir
metric.get("organic_sales")      # campo pode nao existir
```

**Recomendacao:** Migrar para endpoint novo de campanhas com metricas.

**Validado com curl:** Nao
**Ultima validacao:** —

---

## 25. Product Ads Individual (deprecated)

### GET /advertising/product_ads

Usado no metodo `get_item_ads()` no client.py (marcado como DEPRECATED no proprio docstring).
Substituido por `get_product_ads_items()` com `advertiser_id`.

**Status no client.py:** DEPRECATED — nao usar.

---

## Resumo de Bugs Criticos Identificados

| # | Endpoint | Bug | Impacto | Arquivo |
|---|---------|-----|---------|---------|
| 1 | `GET /advertising/advertisers` | Resposta e `{"advertisers": [...]}` mas codigo trata como lista direta | `get_advertiser_id()` SEMPRE retorna None | client.py:379-383 |
| 2 | `GET /advertising/.../campaigns` | Campo de gasto e `"cost"` nao `"spend"` | `spend` sempre 0 no banco | ads/service.py:233 |
| 3 | `GET /advertising/.../campaigns` | Campo de impressoes e `"prints"` nao `"impressions"` | `impressions` sempre 0 no banco | ads/service.py:231 |
| 4 | `GET /visits/items` | Resposta e dict `{item_id: visits}` mas codigo trata os dois formatos (ok) | Nenhum — codigo ja trata | client.py:601-610 |
| 5 | `GET /advertising/campaigns?user_id=` | Endpoint legado nao documentado oficialmente | Retorna 404 em contas sem PADS legado | client.py:625 |

---

## Checklist para novo endpoint

Antes de usar qualquer endpoint novo no projeto:

- [ ] Existe na doc oficial do ML?
- [ ] Testado com curl real e token valido?
- [ ] Resposta documentada aqui com campos reais?
- [ ] Campos nullable identificados?
- [ ] Tratamento de erro (404, 401, 429) implementado?
- [ ] Rate limit respeitado?
- [ ] Adicionado ao client.py com docstring?
