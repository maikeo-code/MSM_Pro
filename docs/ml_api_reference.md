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

**Resposta real (campos que usamos):**
```json
{
  "id": "MLB1234567890",
  "title": "Produto Exemplo",
  "price": 129.90,
  "original_price": 159.90,
  "sale_price": null,
  "available_quantity": 42,
  "sold_quantity": 318,
  "status": "active",
  "listing_type_id": "gold_pro",
  "permalink": "https://www.mercadolivre.com.br/...",
  "thumbnail": "http://http2.mlstatic.com/D_...",
  "seller_id": 2050442871,
  "category_id": "MLB12345",
  "condition": "new",
  "date_created": "2024-01-15T10:30:00.000Z",
  "last_updated": "2026-03-12T14:00:00.000Z",
  "shipping": {
    "free_shipping": true,
    "mode": "me2",
    "logistic_type": "fulfillment"
  }
}
```

**Campos importantes:**
| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| `price` | float | Nao | Preco ATUAL de venda (ja com desconto se houver) |
| `original_price` | float | **Sim** | Preco antes do desconto do VENDEDOR. Null se sem desconto. |
| `sale_price` | object/null | **Sim** | Objeto com `amount`, `currency_id` etc. So para promocoes do MARKETPLACE. Raramente presente para promocoes do vendedor. |
| `available_quantity` | int | Nao | Estoque disponivel |
| `sold_quantity` | int | Nao | Total vendido (historico, cresce monotonicamente) |
| `listing_type_id` | string | Nao | `"gold_special"` (classico), `"gold_pro"` (premium), `"gold_pro"` + fulfillment (full) |
| `status` | string | Nao | `"active"`, `"paused"`, `"closed"`, `"under_review"` |

**Gotchas:**
- `sale_price` e um OBJETO, nao float. Acessar via `sale_price.amount` se presente.
- Para saber se e Full: checar `shipping.logistic_type == "fulfillment"`
- `listing_type_id`: "gold_special" = classico, "gold_pro" = premium. Full e "gold_pro" + fulfillment.
- `sold_quantity` e total historico, NAO vendas do dia.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

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

**Resposta real:**
```json
[
  {
    "id": "PROMO-123",
    "type": "PRICE_DISCOUNT",
    "status": "started",
    "start_date": "2026-03-01T00:00:00Z",
    "finish_date": "2026-03-31T23:59:59Z",
    "original_price": 159.90,
    "price": 129.90,
    "name": "Oferta do dia"
  }
]
```

**Gotchas:**
- Resposta pode ser lista direta OU dict com `results` dependendo da versao.
- `status`: `"started"` = ativa, `"pending"` = agendada, `"finished"` = encerrada.
- Para desconto do vendedor: `original_price` aqui e o preco cheio, `price` e o com desconto.
- Pode retornar 404 se item nao tem promocoes — tratar como lista vazia.
- Requer token do vendedor dono do anuncio.

**Validado com curl:** Sim
**Ultima validacao:** 2026-03-12

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

## 16. OAuth — Autorizacao (Authorization Code)

### GET https://auth.mercadolivre.com.br/authorization

URL de autorizacao para iniciar o fluxo OAuth. O usuario e redirecionado para esta URL.

**Parametros (query string):**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `response_type` | string | Sim | Sempre `"code"` |
| `client_id` | string | Sim | APP ID da aplicacao |
| `redirect_uri` | string | Sim | URL de callback (deve bater com o cadastrado na app) |
| `state` | string | Recomendado | String aleatoria para prevenir CSRF |
| `code_challenge` | string | Se PKCE | Challenge para PKCE |
| `code_challenge_method` | string | Se PKCE | `"S256"` ou `"plain"` |

### POST /oauth/token (Authorization Code → Token)

**Body (form-urlencoded):**
| Param | Tipo | Obrigatorio |
|-------|------|-------------|
| `grant_type` | string | Sim — `"authorization_code"` |
| `client_id` | string | Sim |
| `client_secret` | string | Sim |
| `code` | string | Sim — codigo recebido no callback |
| `redirect_uri` | string | Sim |
| `code_verifier` | string | Se PKCE |

**Resposta:** Mesmo formato do endpoint #9 (access_token, refresh_token, expires_in=21600, etc.)

**Gotchas:**
- URL de auth e `auth.mercadolivre.com.br` (com acento, .com.br) — diferente da API!
- Token endpoint e `api.mercadolibre.com` (sem acento, .com) — padrao da API
- `redirect_uri` DEVE ser identico ao cadastrado na aplicacao ML
- Token expira em 21600 segundos (6 horas)

**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao

---

## 17. Multiget de Itens (Bulk)

### GET /items?ids={ID1},{ID2},...

Busca dados de ATE 20 itens em UMA unica chamada. Essencial para performance.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `ids` | string | Sim | IDs separados por virgula (max 20) |
| `attributes` | string | Opcional | Campos especificos: `id,title,price,available_quantity` |

**Resposta real:**
```json
[
  {
    "code": 200,
    "body": {
      "id": "MLB1234567890",
      "title": "Produto Exemplo",
      "price": 129.90,
      "available_quantity": 42,
      "status": "active"
    }
  },
  {
    "code": 200,
    "body": {
      "id": "MLB9876543210",
      "title": "Outro Produto",
      "price": 89.90,
      "available_quantity": 15,
      "status": "active"
    }
  }
]
```

**Gotchas:**
- Maximo **20 itens** por chamada. Para mais, dividir em batches.
- Resposta e um ARRAY de objetos `{code, body}`, nao os itens diretamente.
- Cada item tem seu proprio `code` (200, 404, etc). Verificar individualmente.
- Use `attributes` para reduzir payload e melhorar performance.
- Usar em vez de N chamadas individuais a `/items/{id}` para economizar rate limit.

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/itens-e-buscas
**Ultima validacao:** —

---

## 18. Visitas Totais do Vendedor (por periodo)

### GET /users/{USER_ID}/items_visits

Retorna total de visitas de TODOS os itens do vendedor em um periodo.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `date_from` | string | Sim | Data ISO (YYYY-MM-DD) |
| `date_to` | string | Sim | Data ISO (YYYY-MM-DD) |

**Resposta real:**
```json
{
  "user_id": 2050442871,
  "date_from": "2026-03-01",
  "date_to": "2026-03-15",
  "total_visits": 32369,
  "visits_detail": [
    {
      "company": "mercadolibre",
      "quantity": 32369
    }
  ]
}
```

**Gotchas:**
- Retorna total AGREGADO, nao breakdown por item nem por dia.
- Para breakdown por dia, usar endpoint #4 (time_window).
- Para breakdown por item, usar endpoint #3 (visits/items).
- `visits_detail` quebra por plataforma (sempre "mercadolibre" no Brasil).

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/recurso-visits
**Ultima validacao:** —

---

## 19. Visitas por Anuncio (entre datas)

### GET /items/visits

Retorna visitas de um item em um periodo especifico.

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `ids` | string | Sim | MLB ID do anuncio |
| `date_from` | string | Sim | Data ISO |
| `date_to` | string | Sim | Data ISO |

**Resposta real:**
```json
{
  "item_id": "MLB1234567890",
  "total_visits": 536,
  "visits_detail": [
    {
      "company": "mercadolibre",
      "quantity": 536
    }
  ]
}
```

**Gotchas:**
- Diferente do endpoint #3 (`/visits/items`): este retorna detalhes por empresa.
- Endpoint #3 retorna dict simples `{id: count}`, este retorna objeto com `visits_detail`.

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/recurso-visits
**Ultima validacao:** —

---

## 20. API de Precos (Sale Price)

### GET /items/{ITEM_ID}/sale_price

Retorna o preco de venda real considerando promocoes e contexto (canal, nivel de fidelidade).

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `context` | string | Opcional | Filtros: `channel_marketplace`, `buyer_loyalty_3` a `_6` |

**Resposta real:**
```json
{
  "price_id": "PRICE-123",
  "amount": 129.90,
  "regular_amount": 159.90,
  "currency_id": "BRL",
  "reference_date": "2026-03-15T00:00:00Z",
  "metadata": {
    "promotion_id": "PROMO-456",
    "promotion_type": "PRICE_DISCOUNT"
  }
}
```

**Campos importantes:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `amount` | float | Preco de venda REAL (com desconto) |
| `regular_amount` | float/null | Preco original (sem desconto) |
| `metadata.promotion_type` | string | Tipo da promocao aplicada |

### GET /items/{ITEM_ID}/prices

Retorna TODOS os precos configurados (standard + promocoes).

**Resposta real:**
```json
{
  "id": "MLB1234567890",
  "prices": [
    {
      "id": "PRICE-STD",
      "type": "standard",
      "amount": 159.90,
      "currency_id": "BRL",
      "last_updated": "2026-03-10T10:00:00Z",
      "conditions": {
        "context_restrictions": ["channel_marketplace"],
        "start_time": null,
        "end_time": null
      }
    },
    {
      "id": "PRICE-PROMO",
      "type": "promotion",
      "amount": 129.90,
      "regular_amount": 159.90,
      "currency_id": "BRL",
      "conditions": {
        "start_time": "2026-03-01T00:00:00Z",
        "end_time": "2026-03-31T23:59:59Z"
      }
    }
  ]
}
```

**Gotchas:**
- `type: "standard"` = preco base, `type: "promotion"` = preco com desconto.
- `conditions.context_restrictions` indica em qual canal o preco se aplica.
- Mais preciso que `item.price` / `item.original_price` para entender a estrutura de precos.

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/api-de-precos
**Ultima validacao:** —

---

## 21. Pedidos Arquivados

### GET /orders/search/archived

Busca pedidos com mais de 12 meses.

**Parametros:** Mesmos do endpoint #5 (`/orders/search`).

**Resposta:** Mesmo formato do endpoint #5.

**Gotchas:**
- Pedidos normais ficam disponiveis por 12 meses.
- Apos 12 meses, so acessiveis por este endpoint.
- Filtros identicos ao `/orders/search`.

**Validado com curl:** Pendente
**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-vendas
**Ultima validacao:** —

---

## 22. Categorias e Atributos

### GET /sites/MLB/categories

Retorna todas as categorias raiz do site MLB (Brasil).

**Resposta real:**
```json
[
  {
    "id": "MLB5672",
    "name": "Acessorios para Veiculos"
  },
  {
    "id": "MLB1051",
    "name": "Celulares e Telefones"
  }
]
```

### GET /categories/{CATEGORY_ID}/attributes

Retorna atributos obrigatorios/opcionais de uma categoria.

**Resposta real:**
```json
[
  {
    "id": "BRAND",
    "name": "Marca",
    "value_type": "string",
    "tags": {"required": true}
  },
  {
    "id": "MODEL",
    "name": "Modelo",
    "value_type": "string"
  }
]
```

**Gotchas:**
- Categorias mudam com frequencia. Cachear com TTL de 24h.
- Atributos com `tags.required = true` sao obrigatorios para publicar.

**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 23. Informacoes do Vendedor (Dados Basicos)

### GET /users/me

Retorna dados do usuario autenticado (dono do token).

**Resposta:** Mesmo formato do endpoint #15, mas sem precisar saber o user_id.

**Gotchas:**
- Util no fluxo de OAuth callback para descobrir o user_id apos autorizacao.
- Requer token valido.

---

## 24. Metodos de Pagamento do Vendedor

### GET /users/{USER_ID}/accepted_payment_methods

**Resposta real:**
```json
[
  {
    "id": "visa",
    "name": "Visa",
    "payment_type_id": "credit_card"
  },
  {
    "id": "account_money",
    "name": "Dinheiro na conta do Mercado Pago",
    "payment_type_id": "account_money"
  }
]
```

---

## 25. Automacao de Precos

### GET /pricing-automation/items/{ITEM_ID}/rules

Retorna regras de automacao de preco disponivel para um item.

### GET /pricing-automation/users/{USER_ID}/items

Retorna lista de IDs de itens com automacao ativa.

### POST /pricing-automation/items/{ITEM_ID}/automation

Ativa automacao de preco para um item.

**Gotchas:**
- A partir de marco 2026: itens com automacao ativa tem edicao de preco BLOQUEADA via API.
- Verificar se o item tem automacao antes de tentar alterar preco (endpoint #10).

**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br/automatizacoes-de-precos
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 26. Tipos de Listagem e Exposicao

### GET /sites/MLB/listing_types

Retorna todos os tipos de anuncio disponiveis.

### GET /sites/MLB/listing_exposures

Retorna niveis de exposicao associados a cada tipo.

### GET /users/{USER_ID}/available_listing_types

Retorna tipos de listagem disponiveis para o usuario (pode filtrar por categoria).

**Parametros:**
| Param | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `category_id` | string | Opcional | Filtrar por categoria |

**Gotchas:**
- Nem todos os tipos estao disponiveis para todos os vendedores.
- Util para validar se vendedor pode usar Premium/Full.

**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 27. Moedas e Conversao

### GET /currencies

Retorna todas as moedas disponiveis no ML.

### GET /currencies/{CURRENCY_ID}

Retorna detalhes de uma moeda.

### GET /currency_conversions/search?from={CUR1}&to={CUR2}

Retorna taxa de conversao entre moedas.

**Gotchas:**
- Brasil usa `BRL`. Sempre verificar `currency_id` nas respostas.
- Util para cross-border selling (Global Selling).

**Validado com curl:** Pendente
**Ultima validacao:** —

---

## 28. Notificacoes (Webhooks)

### Topicos suportados:
| Topico | Descricao |
|--------|-----------|
| `items` | Mudancas em anuncios publicados |
| `questions` | Novas perguntas |
| `payments` | Mudancas em pagamentos |
| `messages` | Mensagens pos-venda |
| `orders_v2` | Vendas confirmadas |
| `shipments` | Mudancas em envios |

### GET /missed_feeds?app_id={APP_ID}

Retorna notificacoes perdidas (quando webhook falhou).

**Gotchas:**
- Configurar webhook no painel de apps do ML.
- Retry automatico: ML tenta 3x. Apos falha, fica em `missed_feeds`.
- Topico `orders_v2` e o recomendado (substitui `orders`).

**Doc oficial:** https://developers.mercadolivre.com.br/pt_br/product-notifications
**Validado com curl:** Pendente
**Ultima validacao:** —

---

## Indice Rapido — Todos os Endpoints

| # | Metodo | Endpoint | Descricao | Validado |
|---|--------|----------|-----------|----------|
| 1 | GET | `/items/{ITEM_ID}` | Dados completos do anuncio | Sim |
| 2 | GET | `/items/{ITEM_ID}/visits/time_window` | Visitas diarias de 1 item | Sim |
| 3 | GET | `/visits/items?ids=...` | Visitas bulk (ate 50 itens) | Sim |
| 4 | GET | `/users/{USER_ID}/items_visits/time_window` | Visitas totais do vendedor/dia | Pendente |
| 5 | GET | `/orders/search` | Pedidos/vendas com filtros | Sim |
| 6 | GET | `/users/{SELLER_ID}/items/search` | Listar IDs dos anuncios | Sim |
| 7 | GET | `/seller-promotions/items/{ITEM_ID}` | Promocoes do item | Sim |
| 8 | GET | `/questions/search` | Perguntas do anuncio | Sim |
| 9 | POST | `/oauth/token` | Refresh/troca de token | Sim |
| 10 | PUT | `/items/{ITEM_ID}` | Alterar preco/dados | Pendente |
| 11 | GET | `/sites/MLB/listing_prices` | Taxa real por categoria | Pendente |
| 12 | GET | `/users/{USER_ID}/shipping_options/free` | Custo de frete | Pendente |
| 13 | — | (campo em /items) | SKU do vendedor | Sim |
| 14 | — | (campo em /items) | Imagens do item | Sim |
| 15 | GET | `/users/{SELLER_ID}` | Reputacao do vendedor | Pendente |
| 16 | GET | `auth.mercadolivre.com.br/authorization` | OAuth autorizacao | Sim |
| 17 | GET | `/items?ids=...` | Multiget itens (ate 20) | Pendente |
| 18 | GET | `/users/{USER_ID}/items_visits` | Visitas totais por periodo | Pendente |
| 19 | GET | `/items/visits?ids=...` | Visitas item entre datas | Pendente |
| 20 | GET | `/items/{ITEM_ID}/sale_price` | Preco real com promocoes | Pendente |
| 20b | GET | `/items/{ITEM_ID}/prices` | Todos os precos configurados | Pendente |
| 21 | GET | `/orders/search/archived` | Pedidos antigos (>12 meses) | Pendente |
| 22 | GET | `/sites/MLB/categories` | Categorias raiz | Pendente |
| 22b | GET | `/categories/{CAT_ID}/attributes` | Atributos da categoria | Pendente |
| 23 | GET | `/users/me` | Dados do usuario autenticado | Pendente |
| 24 | GET | `/users/{USER_ID}/accepted_payment_methods` | Metodos de pagamento | Pendente |
| 25 | GET | `/pricing-automation/items/{ITEM_ID}/rules` | Regras de automacao preco | Pendente |
| 26 | GET | `/sites/MLB/listing_types` | Tipos de anuncio | Pendente |
| 27 | GET | `/currencies` | Moedas disponiveis | Pendente |
| 28 | GET | `/missed_feeds` | Notificacoes perdidas | Pendente |

---

## Links da Documentacao Oficial

| Recurso | URL |
|---------|-----|
| Portal principal | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br |
| Autenticacao | https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao |
| Itens e Buscas | https://developers.mercadolivre.com.br/pt_br/itens-e-buscas |
| Visitas | https://developers.mercadolivre.com.br/pt_br/recurso-visits |
| Pedidos/Vendas | https://developers.mercadolivre.com.br/pt_br/gerenciamento-de-vendas |
| Precos | https://developers.mercadolivre.com.br/pt_br/api-de-precos |
| Promocoes | https://developers.mercadolivre.com.br/pt_br/gerenciar-ofertas |
| Taxas/Comissao | https://developers.mercadolivre.com.br/pt_br/comissao-por-vender |
| Frete | https://developers.mercadolivre.com.br/pt_br/custos-de-envio |
| Automacao de Precos | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br/automatizacoes-de-precos |
| Notificacoes | https://developers.mercadolivre.com.br/pt_br/product-notifications |
| Usuarios | https://developers.mercadolivre.com.br/pt_br/usuarios-e-aplicativos |
| Estoque Distribuido | https://developers.mercadolivre.com.br/pt_br/estoque-distribuido |

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
