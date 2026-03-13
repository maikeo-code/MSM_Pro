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

## Checklist para novo endpoint

Antes de usar qualquer endpoint novo no projeto:

- [ ] Existe na doc oficial do ML?
- [ ] Testado com curl real e token valido?
- [ ] Resposta documentada aqui com campos reais?
- [ ] Campos nullable identificados?
- [ ] Tratamento de erro (404, 401, 429) implementado?
- [ ] Rate limit respeitado?
- [ ] Adicionado ao client.py com docstring?
