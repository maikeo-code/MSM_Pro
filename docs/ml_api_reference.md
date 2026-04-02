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
- Refresh token tambem pode mudar — SEMPRE salvar o novo imediatamente.
- Se refresh falhar com 400/invalid_grant, o usuario precisa re-autorizar via OAuth.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

---

### Ciclo de vida dos tokens ML — COMPORTAMENTO DOCUMENTADO (2026-03-26)

#### access_token
- Validade: **6 horas** (21600 segundos, campo `expires_in`)
- Nao ha forma de aumentar esse prazo — e fixo pelo ML
- O projeto renova proativamente via Celery (task a cada hora, minuto 30)
- Renovacao on-demand quando a API retorna 401 (implementado em `client.py`)

#### refresh_token
- Validade: **6 meses** a partir da ultima utilizacao
- **ROTACIONADO a cada uso** — o ML emite um NOVO refresh_token a cada chamada de refresh
- Somente o ULTIMO refresh_token emitido e valido (o anterior e invalidado imediatamente)
- **CRITICO**: se o codigo nao salvar o novo refresh_token apos cada uso, o token anterior fica invalido e o usuario precisa reconectar
- Invalidado antecipadamente por: troca de senha do usuario, revogacao de permissoes, nao-uso da aplicacao por **4 meses** (mesmo antes dos 6 meses)

#### offline_access scope
- O scope `offline_access` e obrigatorio para receber o refresh_token no OAuth inicial
- A resposta do /oauth/token confirma que o MSM_Pro ja usa esse scope (`"scope": "offline_access read write"`)

#### Como integradores como Nubimetrics/UpSeller NUNCA pedem reconexao
O mecanismo e identico ao que o MSM_Pro ja tem implementado:
1. Armazenam o refresh_token no banco
2. Renovam o access_token proativamente antes de expirar
3. Sempre salvam o NOVO refresh_token retornado a cada renovacao
4. Monitoram o banco: se refresh_token esta proximo de expirar (5+ meses sem uso), alertam o usuario

**O MSM_Pro JA implementa o mecanismo correto.** Se o usuario ve "Token expirado" na tela,
o problema e que `token_expires_at` no banco ainda reflete o prazo ANTIGO e o Celery beat
nao rodou (ou falhou) para atualizar. A tela mostra o campo `token_expires_at` bruto do banco
sem considerar que o Celery ja pode ter renovado em background.

#### Diagnostico: por que a tela mostra "Token expirado"
O frontend le `account.token_expires_at` diretamente via `GET /api/v1/auth/ml/accounts`.
Se `token_expires_at < now()`, exibe "Token expirado" (badge vermelho).
Isso pode ocorrer se:
1. O Celery beat nao esta rodando (worker parado no Railway)
2. A renovacao falhou silenciosamente (erro nao capturado em tasks_tokens.py)
3. O Railway hibernou o worker e a task de renovacao nao disparou
4. O refresh_token foi invalidado por nao-uso por mais de 4 meses

**Solucao**: verificar se o Celery worker esta ativo no Railway. Se estiver ativo e ainda aparecer
expirado, verificar logs da task `refresh_expired_tokens`.

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

## 26. Preco Real de Venda (endpoint novo — fonte primaria de preco)

### GET /items/{ITEM_ID}/sale_price

Retorna o preco que o comprador REALMENTE paga, considerando TODAS as camadas de desconto
(desconto do vendedor, campanha do marketplace, etc).

Introducao em 2025/2026. O campo `price` do `GET /items/{id}` foi considerado depreciado
pelo ML a partir de marco 2026 para fins de preco de vitrine.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `context` | string | Recomendado | `"channel_marketplace"` (padrao), `"channel_mshops"`, `"channel_mp"` |

**Resposta real (quando item tem preco especial):**
```json
{
  "price_id": "P-MLB17129028-MLB6205732214-1234",
  "amount": 50.70,
  "regular_amount": 84.50,
  "currency_id": "BRL",
  "metadata": {
    "promotion_id": "P-MLB17129028",
    "promotion_type": "SMART",
    "campaign_id": "...",
    "campaign_discount_percentage": 28.9
  }
}
```

**Resposta quando item nao tem preco especial (sem desconto ativo):**
- Retorna HTTP 404 ou dict vazio `{}`

**Campos:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `amount` | float | Nao | Preco que o comprador paga |
| `regular_amount` | float | **Sim** | Preco cheio sem desconto. Null quando nao ha desconto ativo. |
| `currency_id` | string | Nao | `"BRL"` para Brasil |
| `metadata` | object | Sim | Detalhes da promocao ativa (nao disponivel para itens de terceiros) |
| `price_id` | string | Nao | ID unico do preco |

**Logica de uso no MSM_Pro (service_sync.py):**
```python
# 1a tentativa: endpoint novo (fonte primaria)
sp_response = await client.get_item_sale_price(mlb_id)
if sp_response and sp_response.get("amount") is not None:
    price = Decimal(str(sp_response["amount"]))
    reg_amount = sp_response.get("regular_amount")
    if reg_amount is not None:
        original_price = Decimal(str(reg_amount))
else:
    # Fallback: campo price do /items/{id}
    price = Decimal(str(item.get("price", 0)))
    # + logica legada com original_price e sale_price
```

**Gotchas:**
- Retorna 404 quando item nao tem preco especial — tratar como dict vazio, NAO como erro.
- `regular_amount` pode ser null mesmo quando ha desconto (depende do tipo de promocao).
- Para itens de terceiros (concorrentes), `metadata` pode nao vir. `amount` continua correto.
- Se o endpoint falhar por qualquer razao, o fallback com `item["price"]` do GET /items/{id} ainda e valido e correto para a maioria dos casos.
- O `amount` aqui SEMPRE representa o preco de vitrine (o que o comprador ve).

**Quando usar vs nao usar:**
- USA-SE para anuncios proprios (token do vendedor) — obtem preco mais preciso com metadados.
- PODE-SE usar para anuncios de terceiros (endpoint e publico para leitura de preco).
- FALLBACK NECESSARIO: se retornar vazio/404, usar `item["price"]` do /items/{id}.

**Implementado em:** `client.py` — metodo `get_item_sale_price()`
**Validado com curl:** Pendente validacao com curl real
**Ultima validacao:** 2026-03-25 (via code review do service_sync.py)

---

## 27. Camadas de Preco de um Item

### GET /items/{ITEM_ID}/prices

Retorna TODAS as camadas de preco vigentes para o item (standard + promotion).

**Parametros:** Nenhum obrigatorio.

**Resposta esperada:**
```json
[
  {
    "id": "standard_price_id",
    "type": "standard",
    "amount": 84.50,
    "regular_amount": null,
    "currency_id": "BRL",
    "conditions": {},
    "context_restrictions": {},
    "metadata": {}
  },
  {
    "id": "promotion_price_id",
    "type": "promotion",
    "amount": 50.70,
    "regular_amount": 84.50,
    "currency_id": "BRL",
    "conditions": {"context_restrictions": {"channel": "channel_marketplace"}},
    "metadata": {"promotion_id": "P-MLB17129028"}
  }
]
```

**Campos por entrada:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `type` | string | Nao | `"standard"` (preco base) ou `"promotion"` (preco com desconto) |
| `amount` | float | Nao | Valor desse preco |
| `regular_amount` | float | Sim | Preco cheio para exibir riscado (so em promotion) |

**Gotchas:**
- Pode retornar lista vazia ou 404 se item nao tem precos especiais configurados.
- Para saber o preco final do comprador: usar `/sale_price` (endpoint 26) que ja resolve qual camada aplicar.
- Este endpoint e util para debugar quais precos estao configurados, nao para uso em sync.

**Implementado em:** `client.py` — metodo `get_item_prices()`
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## Resumo de Bugs Criticos Identificados

| # | Endpoint | Bug | Impacto | Arquivo |
|---|---------|-----|---------|---------|
| 1 | `GET /advertising/advertisers` | Resposta e `{"advertisers": [...]}` mas codigo trata como lista direta | `get_advertiser_id()` SEMPRE retorna None | client.py:379-383 |
| 2 | `GET /advertising/.../campaigns` | Campo de gasto e `"cost"` nao `"spend"` | `spend` sempre 0 no banco | ads/service.py:233 |
| 3 | `GET /advertising/.../campaigns` | Campo de impressoes e `"prints"` nao `"impressions"` | `impressions` sempre 0 no banco | ads/service.py:231 |
| 4 | `GET /visits/items` | Resposta e dict `{item_id: visits}` mas codigo trata os dois formatos (ok) | Nenhum — codigo ja trata | client.py:601-610 |
| 5 | `GET /advertising/campaigns?user_id=` | Endpoint legado nao documentado oficialmente | Retorna 404 em contas sem PADS legado | client.py:625 |
| 6 | `GET /items/{id}/sale_price` | Endpoint novo documentado na secao 26. Fallback para /items/{id}.price quando 404. | Sem bug atual — logica de fallback esta correta no service_sync.py | service_sync.py:91-130 |
| 7 | `GET /items/{id}/visits/time_window` | `last=1` retorna o dia corrente (pode estar parcial). Para ontem: usar `last=2` e filtrar por data. | Visitas de "hoje" podem ser parciais (sincronizadas cedo) | service_sync.py:230-243 |

---

## 28. Envios (Shipments)

### GET /shipments/{SHIPMENT_ID}

Retorna dados completos de um envio, incluindo custo de frete cobrado do vendedor.
Critico para calculo de margem real (custo de frete real vs estimado).

**Headers obrigatorios:**
- `Authorization: Bearer {access_token}`
- `x-format-new: true` (obrigatorio para receber o formato JSON atualizado)

**Parametros:** Nenhum (shipment_id no path).

**Resposta estimada (formato com header x-format-new: true):**
```json
{
  "id": 123456789,
  "status": "delivered",
  "status_history": {},
  "date_created": "2026-03-12T14:30:00.000Z",
  "last_updated": "2026-03-12T20:00:00.000Z",
  "mode": "me2",
  "logistic_type": "fulfillment",
  "order_id": 987654321,
  "cost_components": {
    "sender_cost": 0,
    "special_cost": 0,
    "gap_cost": 0,
    "ratio": 1.0
  },
  "base_cost": 0,
  "total_gross": 0,
  "currency_id": "BRL",
  "service_id": null,
  "shipping_items": [
    {
      "id": "MLB1234567890",
      "quantity": 1,
      "dimensions": {
        "height": 10,
        "width": 20,
        "length": 15,
        "weight": 500
      }
    }
  ],
  "receiver": {
    "id": 12345,
    "nickname": "COMPRADOR123",
    "city": "Sao Paulo"
  },
  "sender": {
    "id": 2050442871
  }
}
```

**Campos criticos para calculo de margem:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cost_components.sender_cost` | float | Custo de frete cobrado do VENDEDOR em R$ |
| `base_cost` | float | Custo base do frete |
| `total_gross` | float | Custo total bruto do envio |
| `logistic_type` | string | `"fulfillment"` (Full), `"cross_docking"`, `"drop_off"`, `"xd_drop_off"` |
| `status` | string | `"delivered"`, `"shipped"`, `"handling"`, `"cancelled"`, `"not_delivered"` |

**Como obter o shipment_id:**
O shipment_id vem dentro de cada pedido em `/orders/search`. Campo: `order.shipping.id`.

```python
# Acessar a partir de um pedido
order = await client.get_orders(seller_id, date_from)
for result in order["results"]:
    shipment_id = result.get("shipping", {}).get("id")
    if shipment_id:
        shipment = await client.get_shipment(shipment_id)
        frete_cobrado = shipment.get("cost_components", {}).get("sender_cost", 0)
```

**Gotchas:**
- **Obrigatorio**: header `x-format-new: true` — sem ele, o formato de resposta e diferente e pode faltar campos.
- `sender_cost = 0` para itens Full (o ML subsidia o frete — custo nao e cobrado diretamente do vendedor; ja e descontado na taxa).
- Para anuncios com frete gratis pago pelo vendedor (nao Full): `sender_cost` tem o valor do frete cobrado.
- Pode retornar 403 se o token nao e do vendedor dono do pedido.
- `shipment_id` em `/orders/search` fica em `result["shipping"]["id"]` — pode ser null se pedido nao tem envio Mercado Envios.

**Implementado em:** `client.py` — metodo `get_shipment()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-envios
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 29. Perguntas Recebidas pelo Vendedor

### GET /my/received_questions/search

Retorna perguntas recebidas PELO VENDEDOR autenticado (nao por item especifico).
Diferente de `/questions/search` que filtra por item — este retorna todas as perguntas do vendedor.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `status` | string | Recomendado | `"UNANSWERED"`, `"ANSWERED"`, `"CLOSED_UNANSWERED"` |
| `offset` | int | Opcional | Para paginacao. Default: 0 |
| `limit` | int | Opcional | Max por pagina. Max: 50. Default: 50 |
| `sort_fields` | string | Opcional | `"date_created"` |
| `sort_types` | string | Opcional | `"DESC"` ou `"ASC"` |

**Resposta estimada:**
```json
{
  "total": 15,
  "limit": 50,
  "questions": [
    {
      "id": 12345678,
      "text": "Tem na cor azul?",
      "status": "UNANSWERED",
      "date_created": "2026-04-01T10:00:00.000Z",
      "item_id": "MLB6205732214",
      "seller_id": 2050442871,
      "from": {
        "id": 987654321,
        "answered_questions": 5
      },
      "answer": null
    },
    {
      "id": 12345679,
      "text": "Qual o peso do produto?",
      "status": "ANSWERED",
      "date_created": "2026-03-30T08:00:00.000Z",
      "item_id": "MLB6205732214",
      "seller_id": 2050442871,
      "from": {
        "id": 111222333,
        "answered_questions": 12
      },
      "answer": {
        "text": "O produto pesa 500g.",
        "status": "ACTIVE",
        "date_created": "2026-03-30T09:30:00.000Z"
      }
    }
  ]
}
```

**Campos importantes:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `total` | int | Nao | Total de perguntas que satisfazem o filtro |
| `questions` | list | Nao | Lista de perguntas |
| `questions[].id` | int | Nao | ID unico da pergunta — usado em POST /answers |
| `questions[].text` | string | Nao | Texto da pergunta do comprador |
| `questions[].status` | string | Nao | `"UNANSWERED"`, `"ANSWERED"`, `"CLOSED_UNANSWERED"`, `"BANNED"` |
| `questions[].item_id` | string | Nao | MLB ID do anuncio da pergunta |
| `questions[].answer` | object | **Sim** | Null quando nao respondida |
| `questions[].answer.text` | string | Nao | Texto da resposta (quando presente) |
| `questions[].from.id` | int | Nao | ID do comprador que fez a pergunta |

**Diferenca entre endpoints de perguntas:**
| Endpoint | Filtra por | Requer auth do vendedor |
|----------|-----------|------------------------|
| `GET /questions/search?item={id}` | Item especifico | Nao (publico) |
| `GET /my/received_questions/search` | Todas as perguntas do vendedor | Sim |

**Gotchas:**
- Requer token do vendedor autenticado — endpoint nao e publico.
- `status` e CASE SENSITIVE: usar `"UNANSWERED"` (maiusculo), nao `"unanswered"`.
- `total` pode ser diferente de `len(questions)` quando usa paginacao.
- Perguntas `BANNED` sao perguntas consideradas inapropriadas pelo ML — vendedor nao precisa responder.
- Para buscar perguntas de um item especifico, usar `/questions/search?item={id}` (secao 8).
- O campo `questions[].from.id` e o buyer_id — nao o buyer_nickname.

**Implementado em:** `client.py` — metodo `get_received_questions()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/perguntas-e-respostas
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 30. Responder Pergunta

### POST /answers

Envia uma resposta a uma pergunta de comprador.

**AVISO: Endpoint de ESCRITA — testar em sandbox antes de usar em producao.**

**Body (JSON):**
```json
{
  "question_id": 12345678,
  "text": "Sim, temos na cor azul. O prazo de entrega e de 3 a 5 dias uteis."
}
```

**Parametros do body:**
| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `question_id` | int | Sim | ID da pergunta (obtido via GET /my/received_questions/search ou /questions/search) |
| `text` | string | Sim | Texto da resposta. Minimo: 1 caractere. Maximo: ~2000 caracteres |

**Resposta esperada (HTTP 201 Created):**
```json
{
  "id": 98765432,
  "question_id": 12345678,
  "text": "Sim, temos na cor azul. O prazo de entrega e de 3 a 5 dias uteis.",
  "status": "ACTIVE",
  "date_created": "2026-04-02T10:30:00.000Z",
  "deleted_from_listing": false,
  "negatively_affects_reputation": false
}
```

**Campos da resposta:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `id` | int | ID unico da resposta criada |
| `question_id` | int | ID da pergunta respondida |
| `status` | string | `"ACTIVE"` = visivel na vitrine, `"UNDER_REVIEW"` = em moderacao |
| `deleted_from_listing` | bool | Se a resposta foi removida do anuncio por moderacao |
| `negatively_affects_reputation` | bool | Se a resposta pode afetar reputacao do vendedor |

**Gotchas:**
- Requer token do vendedor dono do anuncio onde a pergunta foi feita.
- Nao e possivel responder perguntas com `status=BANNED`.
- Nao e possivel editar uma resposta ja enviada — apenas deletar e responder novamente.
- Perguntas `CLOSED_UNANSWERED` ja expiraram — nao aceitam resposta.
- Respostas podem ser moderadas pelo ML e ficar `"UNDER_REVIEW"` temporariamente.
- O `text` nao deve conter dados pessoais (email, telefone, CPF) — o ML bloqueia automaticamente.
- Recomendado usar api_version=4 para formato atualizado (verificar se endpoint aceita o header).

**Implementado em:** `client.py` — metodo `answer_question()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/perguntas-e-respostas
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 31. Reclamacoes — Busca

### GET /post-purchase/v1/claims/search

**AVISO CRITICO DE MIGRACAO:**
O endpoint `/v1/claims/search` foi DEPRECADO em maio 2024. O endpoint atual e:
`https://api.mercadolibre.com/post-purchase/v1/claims/search`

**O client.py ainda usa `/v1/claims/search` — DEVE SER MIGRADO.**

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `status` | string | Opcional | `"opened"`, `"closed"`, `"resolved"` |
| `stage` | string | Opcional | `"claim"`, `"dispute"` |
| `claim_type` | string | Opcional | `"return"` para devolucoes |
| `offset` | int | Opcional | Para paginacao |
| `limit` | int | Opcional | Max por pagina. Default: 50 |
| `sort` | string | Opcional | `"date_created:DESC"` |

**Resposta estimada:**
```json
{
  "data": [
    {
      "id": 111222333,
      "resource_id": 987654321,
      "resource": "order",
      "reason_id": "ITEM_NOT_AS_DESCRIBED",
      "status": "opened",
      "stage": "claim",
      "claimant": {
        "id": 12345678,
        "role": "buyer"
      },
      "respondent": {
        "id": 2050442871,
        "role": "seller"
      },
      "resolution": null,
      "date_created": "2026-04-01T10:00:00.000Z",
      "last_updated": "2026-04-01T12:00:00.000Z"
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
| `data` | list | Lista de reclamacoes (nao `results`) |
| `data[].id` | int | ID da reclamacao |
| `data[].resource_id` | int | ID do pedido (order_id) relacionado |
| `data[].reason_id` | string | Motivo: `"ITEM_NOT_AS_DESCRIBED"`, `"ITEM_NOT_RECEIVED"`, `"WRONG_ITEM_RECEIVED"`, `"UNDISCLOSED_REASON"` |
| `data[].status` | string | `"opened"`, `"closed"`, `"resolved"` |
| `data[].stage` | string | `"claim"` (fase inicial) ou `"dispute"` (mediacao ML) |
| `data[].resolution` | object/null | Resolucao da reclamacao — null quando aberta |

**Gotchas:**
- **O endpoint do client.py esta DESATUALIZADO**: usar `/post-purchase/v1/claims/search` em vez de `/v1/claims/search`.
- A lista esta em `data`, nao em `results`.
- O seller_id e derivado do token — nao precisa passar como parametro.
- `stage=dispute` = mediacao ativa com o ML (mais critica que `stage=claim`).
- Para devolucoes: usar `claim_type=return` (secao 34).
- Tipos de reclamacao: `"order"` (pedido), `"shipment"` (envio).

**Implementado em:** `client.py` — metodo `get_claims()` (endpoint desatualizado — migrar)
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciar-reclamacoes
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 32. Reclamacoes — Detalhe

### GET /post-purchase/v1/claims/{CLAIM_ID}

Retorna todos os detalhes de uma reclamacao especifica, incluindo historico e provas.

**AVISO CRITICO:** O client.py usa `/v1/claims/{id}` — DEPRECADO. Usar `/post-purchase/v1/claims/{id}`.

**Parametros:** Nenhum (claim_id no path).

**Resposta estimada:**
```json
{
  "id": 111222333,
  "resource_id": 987654321,
  "resource": "order",
  "reason_id": "ITEM_NOT_AS_DESCRIBED",
  "status": "opened",
  "stage": "claim",
  "type": "mediations",
  "claimant": {
    "id": 12345678,
    "role": "buyer"
  },
  "respondent": {
    "id": 2050442871,
    "role": "seller"
  },
  "players": [
    {"role": "buyer", "available_actions": ["send_message", "add_evidence", "agree_to_resolution"]},
    {"role": "seller", "available_actions": ["send_message", "add_evidence", "propose_resolution"]}
  ],
  "resolution": null,
  "date_created": "2026-04-01T10:00:00.000Z",
  "last_updated": "2026-04-01T12:00:00.000Z"
}
```

**Campos importantes:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `players[].available_actions` | list | Nao | Acoes que o vendedor pode tomar no momento |
| `stage` | string | Nao | `"claim"` ou `"dispute"` (mediacao ML ativa) |
| `resolution` | object | **Sim** | Null quando aberta. Preenchido quando resolvida. |

**Gotchas:**
- Requer token do vendedor ou comprador envolvido na reclamacao.
- `players[].available_actions` determina o que o vendedor pode fazer agora.
- Quando `stage=dispute`: o ML e mediador — a resolucao pode ser imposta pelo ML.
- `resolution.type` pode ser `"RETURN_REQUESTED"`, `"REFUND_REQUESTED"`, `"RETURN_COMPLETED"`.

**Implementado em:** `client.py` — metodo `get_claim_detail()` (endpoint desatualizado — migrar)
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciar-reclamacoes
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 33. Reclamacoes — Enviar Mensagem

### POST /post-purchase/v1/claims/{CLAIM_ID}/messages

Envia uma mensagem dentro de uma reclamacao.

**AVISO: Endpoint de ESCRITA — testar com cuidado.**
**AVISO CRITICO:** O client.py usa `/v1/claims/{id}/messages` — DEPRECADO. Usar `/post-purchase/v1/claims/{id}/messages`.

**Body (JSON):**
```json
{
  "message": "Prezado cliente, confirmo o recebimento da sua reclamacao. Vamos resolver o problema."
}
```

**Parametros do body:**
| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `message` | string | Sim | Texto da mensagem |

**Resposta esperada (HTTP 201):**
```json
{
  "id": "msg_abc123",
  "from": {"role": "seller", "user_id": 2050442871},
  "message": "Prezado cliente...",
  "date_created": "2026-04-02T10:00:00.000Z",
  "last_updated": "2026-04-02T10:00:00.000Z"
}
```

**Gotchas:**
- Requer token do vendedor ou comprador envolvido na reclamacao.
- Mensagens sao visiveis para ambas as partes e para o ML (mediador).
- Evitar dados pessoais (telefone, email, CPF) — o ML filtra automaticamente.
- Quando `stage=dispute`, o ML pode ser notificado sobre a mensagem.

**Implementado em:** `client.py` — metodo `send_claim_message()` (endpoint desatualizado — migrar)
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciar-mensagem-de-uma-eclamacao
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 34. Devolucoes

### GET /post-purchase/v1/claims/search?claim_type=return

Devolucoes no ML sao implementadas como reclamacoes com `claim_type=return`.
Usa o mesmo endpoint da secao 31, mas com filtro especifico.

**AVISO CRITICO:** O client.py usa `/v1/claims/search` — DEPRECADO. Usar `/post-purchase/v1/claims/search`.

**Parametros especificos para devolucoes:**
| Param | Valor | Descricao |
|-------|-------|-----------|
| `claim_type` | `"return"` | Filtra apenas devolucoes |
| `status` | `"opened"` ou `"closed"` | Status da devolucao |

**Campos relevantes para devolucoes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `reason_id` | string | `"RETURN_REQUESTED"` — cliente quer devolver |
| `resolution.type` | string | `"RETURN_COMPLETED"` — devolucao concluida |

**Gotchas:**
- Devolucoes tem prazo especifico no ML (geralmente ate X dias apos recebimento).
- O processo de devolucao pode ser: pedido → aceito pelo vendedor → item retornado → reembolso.
- Para anuncios Full: o processo de devolucao e diferente (logistica reversa do ML).

**Implementado em:** `client.py` — metodo `get_returns()` (endpoint desatualizado — migrar)
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciar-devolucoes
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 35. Mensagens Pos-Venda — Buscar Conversa

### GET /messages/packs/{PACK_ID}/sellers/{SELLER_ID}

Retorna as mensagens de uma conversa pos-venda entre comprador e vendedor.

**AVISO IMPORTANTE (fevereiro 2026):**
O ML implementou camada de intermediacao por IA (Messaging Agents) para MLB (Brasil) e MLC (Chile), especialmente para itens Full. As mensagens podem ser gerenciadas por IA antes de chegar ao vendedor. Nao ha mudanca na estrutura dos endpoints.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `pack_id` | string | Sim | ID do pack (obtido do pedido: `order.pack_id`) |
| `seller_id` | string | Sim | ID do vendedor (no path) |
| `mark_as_read` | bool | Opcional | `false` para nao marcar mensagens como lidas. Default: `true` |

**Resposta estimada:**
```json
{
  "paging": {
    "total": 5,
    "offset": 0,
    "limit": 20
  },
  "conversation_status": {
    "id": "available",
    "is_blocked": false
  },
  "messages": [
    {
      "id": "msg_abc123",
      "from": {
        "user_id": 987654321,
        "role": "buyer"
      },
      "to": {
        "user_id": 2050442871,
        "role": "seller"
      },
      "text": {
        "plain": "Ola, quando meu pedido sera entregue?"
      },
      "message_date": {
        "received": "2026-04-01T10:00:00.000Z",
        "available": "2026-04-01T10:00:00.000Z",
        "notified": "2026-04-01T10:01:00.000Z",
        "created": "2026-04-01T10:00:00.000Z"
      },
      "status": "available",
      "attachments": []
    }
  ]
}
```

**Campos importantes:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `messages` | list | Nao | Lista de mensagens da conversa |
| `messages[].text.plain` | string | Nao | Texto da mensagem |
| `messages[].from.role` | string | Nao | `"buyer"` ou `"seller"` |
| `messages[].status` | string | Nao | `"available"`, `"moderated"`, `"pending_moderation"` |
| `conversation_status.is_blocked` | bool | Nao | Se a conversa esta bloqueada para mensagens |

**Como obter o pack_id:**
```python
order = await client.get_orders(seller_id, date_from)
for result in order["results"]:
    pack_id = result.get("pack_id")  # pode ser null — usar order_id como fallback
    order_id = result.get("id")
    # Se pack_id is None: usar /messages/orders/{order_id}
```

**Gotchas:**
- Se `pack_id` for null no pedido, usar `/messages/orders/{order_id}` como alternativa.
- O GET marca as mensagens como lidas por padrao — usar `mark_as_read=false` se nao desejado.
- `status=moderated` = mensagem bloqueada pelo ML (nao exibida na vitrine).
- Mensagens de vendedor, mesmo moderadas, ficam visiveis para o vendedor.
- Rate limit: 500 rpm para GET, compartilhado entre todos os endpoints de mensagem.

**Implementado em:** `client.py` — metodo `get_messages()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/mensagens-post-venda
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 36. Mensagens Pos-Venda — Enviar Mensagem

### POST /messages/packs/{PACK_ID}/sellers/{SELLER_ID}

Envia uma mensagem pos-venda para o comprador.

**AVISO: Endpoint de ESCRITA — testar em sandbox antes.**

**Body (JSON):**
```json
{
  "from": {
    "user_id": 2050442871
  },
  "text": "Ola! Seu pedido ja foi enviado e deve chegar em ate 3 dias uteis."
}
```

**Parametros do body:**
| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `from.user_id` | int | Sim | ID do vendedor (dono do token) |
| `text` | string | Sim | Texto da mensagem. Max: ~2000 caracteres. |

**Resposta esperada (HTTP 201):**
```json
{
  "id": "msg_xyz789",
  "status": "available",
  "from": {"user_id": 2050442871, "role": "seller"},
  "text": {"plain": "Ola! Seu pedido ja foi enviado..."},
  "message_date": {
    "created": "2026-04-02T10:00:00.000Z"
  }
}
```

**Gotchas:**
- Requer token do vendedor.
- `from.user_id` deve ser o mesmo seller_id do path — caso contrario, erro 403.
- Mensagens com dados pessoais (email, telefone, CPF) sao bloqueadas automaticamente.
- Se `conversation_status.is_blocked = true`: nao e possivel enviar mensagens.
- A partir de fevereiro 2026: para itens Full, a IA pode intermediar a conversa antes do comprador receber.
- Rate limit: 500 rpm para POST, compartilhado.

**Implementado em:** `client.py` — metodo `send_message()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/mensagens-post-venda
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 37. Mensagens Pos-Venda — Listar Conversas

### GET /messages/search

Busca conversas (packs) de mensagens pos-venda do vendedor.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `seller_id` | string | Sim | ID do vendedor |
| `offset` | int | Opcional | Para paginacao |
| `limit` | int | Opcional | Max por pagina. Default: 50 |

**Resposta estimada:**
```json
{
  "data": [
    {
      "id": "pack_123",
      "order_id": 987654321,
      "status": "unread",
      "context": {
        "item": {"id": "MLB6205732214", "title": "..."},
        "order": {"id": 987654321}
      },
      "last_message": {
        "from": {"role": "buyer"},
        "text": {"plain": "Chegou danificado!"},
        "date_created": "2026-04-01T08:00:00.000Z"
      }
    }
  ],
  "paging": {
    "total": 10,
    "offset": 0,
    "limit": 50
  }
}
```

**Campos importantes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `data` | list | Lista de conversas (nao `results`) |
| `data[].id` | string | ID do pack — usar em GET /messages/packs/{id}/sellers/{id} |
| `data[].status` | string | `"unread"`, `"read"`, `"blocked"` |
| `data[].last_message` | object | Ultima mensagem da conversa |

**Gotchas:**
- A lista de conversas fica em `data`, nao em `results`.
- `id` aqui e o `pack_id` para usar nos outros endpoints de mensagem.
- Conversas com mensagens nao lidas ficam com `status=unread`.
- Para obter mensagens de uma conversa especifica: usar endpoint 35.
- Formato estimado — validar com curl real.

**Implementado em:** `client.py` — metodo `get_message_packs()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/mensagens-pendentes
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 38. Busca Publica de Items

### GET /sites/MLB/search

Busca items ativos no Mercado Livre Brasil. Endpoint publico — nao requer autenticacao.
Usado para pesquisa de concorrentes e monitoramento de mercado.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `q` | string | Sim* | Termo de busca |
| `seller_id` | string | Sim* | ID do vendedor (alternativa a q) |
| `nickname` | string | Sim* | Nickname do vendedor (alternativa a q/seller_id) |
| `offset` | int | Opcional | Para paginacao. Default: 0 |
| `limit` | int | Opcional | Max: 100. Default: 50 |
| `sort` | string | Opcional | `"price_asc"`, `"price_desc"`, `"relevance"` |
| `category` | string | Opcional | ID da categoria para filtrar |

*Ao menos um dos parametros marcados e obrigatorio.

**Resposta real:**
```json
{
  "query": "cesto de roupa",
  "results": [
    {
      "id": "MLB6205732214",
      "title": "Cesto De Roupa Suja Separador Organizador",
      "price": 50.70,
      "original_price": 84.50,
      "currency_id": "BRL",
      "available_quantity": 15,
      "sold_quantity": 263,
      "thumbnail": "https://http2.mlstatic.com/D_...-I.jpg",
      "condition": "new",
      "listing_type_id": "gold_special",
      "permalink": "https://produto.mercadolivre.com.br/MLB-...",
      "shipping": {
        "free_shipping": false,
        "logistic_type": "fulfillment"
      },
      "seller": {
        "id": 2050442871,
        "nickname": "MSM_PRIME"
      }
    }
  ],
  "paging": {
    "total": 2500,
    "offset": 0,
    "limit": 50
  },
  "available_sorts": [
    {"id": "price_asc", "name": "Menor preco"},
    {"id": "price_desc", "name": "Maior preco"}
  ],
  "filters": [],
  "available_filters": [
    {"id": "category", "name": "Categorias", "values": [...]},
    {"id": "shipping_cost", "name": "Frete", "values": [...]}
  ]
}
```

**Campos de cada item em `results`:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `id` | string | Nao | MLB ID do item |
| `price` | float | Nao | Preco atual de venda |
| `original_price` | float | Sim | Preco original antes do desconto (quando em promocao) |
| `sold_quantity` | int | Nao | Total vendido historico |
| `seller.id` | int | Nao | ID do vendedor |
| `shipping.free_shipping` | bool | Nao | Se tem frete gratis |

**Gotchas:**
- Endpoint publico — nao requer Authorization header.
- Maximo 100 resultados por pagina (nao 50 como a maioria dos endpoints).
- `paging.total` pode ser muito grande — paginar com cuidado.
- `price` aqui e o preco atual de venda (identico ao `/items/{id}.price`).
- Para busca por vendedor especifico: usar `seller_id` em vez de `q`.
- Filtros avancados podem ser passados como params adicionais (ver `available_filters` na resposta).
- Para anuncios de catalogo: pode retornar multiplos sellers para o mesmo produto.

**Implementado em:** `client.py` — metodo `search_items()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/itens-e-buscas
**Validado com curl:** Pendente (endpoint publico — facil de testar)
**Ultima validacao:** —

---

## 39. Desconto Individual — Criar Promocao

### POST /seller-promotions/items/{ITEM_ID}

Cria uma promocao de desconto individual (PRICE_DISCOUNT) em um anuncio.

**AVISO: Endpoint de ESCRITA — testar em sandbox antes de usar em producao.**

**Parametros de query:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `user_id` | string | Sim | ID do vendedor no ML |

**Body (JSON):**
```json
{
  "promotion_type": "PRICE_DISCOUNT",
  "deal_price": 50.70,
  "start_date": "2026-04-02T00:00:00Z",
  "finish_date": "2026-05-02T23:59:59Z",
  "top_deal_price": 48.00
}
```

**Campos do body:**
| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `promotion_type` | string | Sim | Sempre `"PRICE_DISCOUNT"` para desconto simples |
| `deal_price` | float | Sim | Preco final com desconto em R$ (nao percentual) |
| `start_date` | string | Sim | ISO 8601 UTC: `"2026-04-02T00:00:00Z"` |
| `finish_date` | string | Sim | ISO 8601 UTC: `"2026-05-02T23:59:59Z"` |
| `top_deal_price` | float | Opcional | Preco especial para Mercado Pontos nivel 3-6 |

**Resposta esperada (HTTP 201):**
```json
{
  "id": "C-MLB987654",
  "type": "PRICE_DISCOUNT",
  "status": "started",
  "price": 50.70,
  "original_price": 84.50,
  "start_date": "2026-04-02T00:00:00.000Z",
  "finish_date": "2026-05-02T23:59:59.000Z"
}
```

**Regras de negocio (confirmadas pela doc oficial ML):**
- Desconto minimo: 5% do preco original
- Desconto maximo: menos de 80% do preco original
- Duracao maxima: 31 dias
- `top_deal_price` deve ser pelo menos 5% menor que `deal_price` (quando desconto <= 35%)
- `top_deal_price` deve ser pelo menos 10% menor que `deal_price` (quando desconto > 35%)
- Se ja existe PRICE_DISCOUNT ativa: erro 400. Chamar DELETE antes.
- Se o preco for aumentado apos a criacao: o desconto e removido automaticamente.

**Gotchas:**
- `deal_price` e o PRECO FINAL em R$, nao percentual de desconto.
- Datas em ISO 8601 UTC (com Z no final) — nao usar horario de Brasilia.
- Nao confundir com campanhas SMART ou SELLER_CAMPAIGN — PRICE_DISCOUNT e o desconto simples (riscado).
- Para editar: DELETE + POST (nao existe PUT para PRICE_DISCOUNT).
- O anuncio deve estar `status=active` para aceitar promocao.

**Implementado em:** `client.py` — metodo `create_price_discount_promotion()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/desconto-individua
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 40. Desconto Individual — Remover Promocao

### DELETE /seller-promotions/items/{ITEM_ID}

Remove/finaliza uma promocao ativa de um anuncio.

**AVISO: Endpoint de ESCRITA (DELETE).**

**Parametros de query:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `user_id` | string | Sim | ID do vendedor no ML |
| `promotion_type` | string | Sim | Tipo da promocao a remover: `"PRICE_DISCOUNT"` |

**Resposta esperada (HTTP 200 ou 204):**
Corpo vazio ou confirmacao de remocao.

**Quando usar:**
1. Antes de alterar o preco via `PUT /items/{id}` (se ha PRICE_DISCOUNT ativa, a alteracao de preco remove o desconto automaticamente)
2. Antes de criar nova PRICE_DISCOUNT (nao e possivel ter duas ativas simultaneamente)

**Gotchas:**
- Nao usar para remover campanhas SMART, DOD ou LIGHTNING — essas sao do marketplace e nao podem ser removidas pelo vendedor via API.
- `promotion_type` deve ser exatamente `"PRICE_DISCOUNT"` (case sensitive).
- Se nao ha PRICE_DISCOUNT ativa: pode retornar 404 ou resposta de sucesso.
- Requer token do vendedor dono do anuncio.

**Implementado em:** `client.py` — metodo `delete_price_discount_promotion()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/desconto-individua
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 41. Campanha do Vendedor — Criar (SELLER_CAMPAIGN)

### POST /seller-promotions/promotions?app_version=v2

Cria uma campanha de desconto temporaria do tipo SELLER_CAMPAIGN.
Diferente do PRICE_DISCOUNT (secao 39), aqui o vendedor cria uma campanha com nome e periodo —
e os itens sao adicionados depois. Aparece no Gerenciador de Promocoes do Painel ML.

**AVISO: Endpoint de ESCRITA — testar em sandbox antes de usar em producao.**

**Auth:** Bearer token do vendedor. Scope: `write:promotions` (verificar se necessario).

**Body (JSON):**
```json
{
  "promotion_type": "SELLER_CAMPAIGN",
  "name": "Desconto Abril 10 dias",
  "sub_type": "FLEXIBLE_PERCENTAGE",
  "start_date": "2026-04-02T00:00:00-03:00",
  "finish_date": "2026-04-12T23:59:59-03:00"
}
```

**Campos do body:**
| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `promotion_type` | string | Sim | Sempre `"SELLER_CAMPAIGN"` |
| `name` | string | Sim | Nome da campanha (aparece no painel ML) |
| `sub_type` | string | Sim | `"FLEXIBLE_PERCENTAGE"` (FIXED_PERCENTAGE depreciado desde jul/2025) |
| `start_date` | string | Sim | ISO 8601 com offset de timezone local (ex: `-03:00` para BRT) |
| `finish_date` | string | Sim | ISO 8601 com offset de timezone local |

**Duracao maxima:** 14 dias (alterado de 31 para 14 dias em marco/2025).

**Resposta esperada (HTTP 201):**
```json
{
  "id": "C-MLB3450113",
  "promotion_type": "SELLER_CAMPAIGN",
  "sub_type": "FLEXIBLE_PERCENTAGE",
  "status": "pending",
  "name": "Desconto Abril 10 dias",
  "start_date": "2026-04-02T00:00:00-03:00",
  "finish_date": "2026-04-12T23:59:59-03:00"
}
```

**Adicionar item a campanha SELLER_CAMPAIGN apos criar:**
```
POST https://api.mercadolibre.com/seller-promotions/promotions/{CAMPAIGN_ID}/items?app_version=v2
```
Body:
```json
{
  "items": [
    {
      "item_id": "MLB6205732214",
      "deal_price": 50.70
    }
  ]
}
```

**Limitacoes:**
- Duracao maxima: 14 dias (atualizado em 2025)
- Item deve estar ativo, condicao nova, reputacao verde
- Nao pode ter PRICE_DISCOUNT e SELLER_CAMPAIGN ativas simultaneamente no mesmo item
- Depois que a campanha entra em `started`, preco so pode diminuir (nao aumentar)
- Nao pode adicionar `top_deal_price` pos-inicio se nao foi configurado na criacao

**Diferenca vs PRICE_DISCOUNT:**
| Aspecto | PRICE_DISCOUNT (secao 39) | SELLER_CAMPAIGN (esta secao) |
|---------|--------------------------|------------------------------|
| Fluxo | 1 POST direto no item | POST campanha + POST item na campanha |
| Aparece como | Desconto simples (riscado) | Campanha com nome no painel |
| Multiplos itens | 1 item por chamada | N itens por campanha |
| Duracao max | 14 dias | 14 dias |
| Endpoint | `/seller-promotions/items/{id}` | `/seller-promotions/promotions` |

**Gotchas:**
- `sub_type` deve ser `"FLEXIBLE_PERCENTAGE"` (o valor `"FIXED_PERCENTAGE"` foi depreciado em julho 2025)
- Datas em ISO 8601 com offset de timezone (nao UTC puro com Z) para este endpoint
- O `id` retornado comeca com `C-` (campanha do vendedor, nao P- que e do marketplace)
- Nao implementado ainda no client.py do MSM_Pro — a ser implementado se necessario

**Implementado em:** Nao implementado no client.py (apenas documentado)
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/campanhas-do-vendedor
**Validado com curl:** Pendente
**Ultima validacao:** 2026-04-02 (via doc oficial + pesquisa)

---

## 42. Verificar Promocoes Ativas em um Item

### GET /seller-promotions/items/{ITEM_ID}?app_version=v2

Retorna TODAS as promocoes ativas/pendentes/candidatas de um item.
Usar antes de aplicar um PRICE_DISCOUNT para verificar conflitos.

**Resposta (lista de promocoes ativas):**
```json
[
  {
    "id": "C-MLB3450113",
    "type": "SELLER_CAMPAIGN",
    "status": "started",
    "price": 63.38,
    "original_price": 84.50
  }
]
```

**Status possiveis:**
| Status | Descricao |
|--------|-----------|
| `started` | Promocao ativa agora — pode bloquear edicao de preco |
| `candidate` | ML propoe, vendedor nao aderiu — NAO bloqueia edicao |
| `pending` | Agendada para o futuro — NAO bloqueia edicao de preco ainda |
| `finished` | Encerrada |
| `sync_requested` | Processo de ativacao em andamento |
| `restore_requested` | Processo de exclusao em andamento |

**Uso no MSM_Pro (logica de "Aplicar preco"):**
```python
# Antes de alterar preco via PUT /items/{id} ou criar PRICE_DISCOUNT:
promos = await client.get_item_promotions(item_id)
has_active = any(p["status"] == "started" for p in promos
                 if p.get("type") in ("PRICE_DISCOUNT", "SELLER_CAMPAIGN"))
if has_active:
    # Opcao A: primeiro DELETE /seller-promotions/items/{id}?promotion_type=PRICE_DISCOUNT
    # Opcao B: alterar preco via PUT /items/{id} — ML remove PRICE_DISCOUNT automaticamente
    pass
```

**Gotchas:**
- Resposta e lista direta, nao dict com `results`
- Campanhas SMART e DEAL com `status=candidate` NAO bloqueiam alteracao de preco
- Campanhas do marketplace (SMART, DEAL, DOD, LIGHTNING) NAO podem ser removidas pelo vendedor via API

**Implementado em:** `client.py` — metodo `get_item_promotions()`
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciar-ofertas
**Validado com curl:** Sim (2026-04-02 — endpoint 7 na secao de Promocoes)
**Ultima validacao:** 2026-04-02

---

## Resumo de Cobertura (Atualizado 2026-04-02)

### Endpoints por status de documentacao

| Categoria | Total metodos | Documentados | Validados curl | Status |
|-----------|--------------|--------------|----------------|--------|
| Core (anuncios/precos) | 5 | 5 | 3 | Bom |
| Visitas | 3 | 3 | 3 | Completo |
| Pedidos/vendas | 3 | 3 | 3 | Completo |
| Vendedor/listagens | 2 | 2 | 2 | Completo |
| Promocoes | 7 | 7 | 2 | Doc completa — curl parcial (GET validado) |
| Publicidade (Ads) | 6 | 6 | 0 | Doc completa — API nao publica |
| Envios | 2 | 2 | 0 | Doc completa — curl pendente |
| Perguntas/Respostas | 3 | 3 | 1 | Doc completa — curl pendente |
| Taxas/Fees | 1 | 1 | 0 | Doc completa — curl pendente |
| Busca publica | 1 | 1 | 0 | Doc completa — curl pendente |
| Claims | 3 | 3 | 0 | Doc completa — MIGRAR endpoint |
| Mensagens | 3 | 3 | 0 | Doc completa — curl pendente |
| Devolucoes | 1 | 1 | 0 | Doc completa — MIGRAR endpoint |
| **TOTAL** | **40** | **40** | **14** | 100% documentado |

### Endpoints com MIGRACAO URGENTE necessaria

O ML deprecou `/v1/claims/` em maio 2024. Os seguintes metodos do client.py usam endpoints obsoletos:

| Metodo client.py | Endpoint atual (ERRADO) | Endpoint correto |
|-----------------|------------------------|------------------|
| `get_claims()` | `/v1/claims/search` | `/post-purchase/v1/claims/search` |
| `get_claim_detail()` | `/v1/claims/{id}` | `/post-purchase/v1/claims/{id}` |
| `send_claim_message()` | `/v1/claims/{id}/messages` | `/post-purchase/v1/claims/{id}/messages` |
| `get_returns()` | `/v1/claims/search?claim_type=return` | `/post-purchase/v1/claims/search?claim_type=return` |

### Nota sobre endpoints Ads

Os 6 metodos de Publicidade (Ads) estao documentados nas secoes 20-25 mas NAO podem ser validados sem uma conta com Product Ads (PADS) ativo. A API de Product Ads requer habilitacao especifica na conta ML — nao e publica.

### Atualizado em: 2026-04-02
### Endpoints documentados nesta sessao: 13 novos (secoes 28-40)
### Cobertura total: 38/38 metodos do client.py documentados (100%)

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
