# Catálogo de Dados — MSM_Pro

> **Propósito:** mapa único de rastreabilidade de TODO número que o app mostra. Para cada campo de
> cada tela, cada endpoint interno e cada método do cliente ML, este documento diz: de onde o dado
> vem, quem é o dono, qual endpoint do ML o alimenta, e se existe um teste/checagem que garante que
> está certo. É o pré-requisito para "testar cada dado" — transforma o app inteiro numa lista finita.
>
> Criado na Etapa E6 (Fase 0) do Plano Definitivo. Preenchido nas Fases 1B, 2 e 2B.
> Status por item: ✓ tem dono e check | ✗ tem dono, falta check | 🔴 órfão/duvidoso (vira bug).

---

## 1. TELAS (preenchido na Fase 2 — E20 a E36)

> Formato por tela: campo exibido → endpoint backend → serviço:função → tabela.coluna →
> endpoint ML → check/teste → status.

### E20 — Dashboard (`pages/Dashboard/index.tsx`) — preenchido 2026-07-10

5 fontes de dados: `getKpiSummary`, `getFunnel`, `getHeatmap`, `list` (tabela), `getDashboardExtraCards`.

**KPI cards (topo) — todos de `kpi.hoje` via `GET /listings/kpi/summary`:**

| Campo exibido | Fonte no payload | Serviço:função | Tabela.coluna | Endpoint ML | Check paridade | Status |
|---------------|------------------|----------------|---------------|-------------|----------------|--------|
| Pedidos Válidos | `kpi.hoje.pedidos` | service_kpi.get_kpi_by_period → metrics.aggregate_metrics | Order (count, status ∉ NON_SALE) | `/orders/search` | `pedidos_dia` | ✓ (⚠️ sobreconta +1 → Fase 4/E52) |
| Unidades Vendidas | `kpi.hoje.vendas` | idem → `_kpi_single_day` | Order.quantity (Σ) | `/orders/search` | `unidades_dia` | ✓ (⚠️ +1 → Fase 4) |
| Receita Total | `kpi.hoje.receita_total` | idem | Order.total_amount (Σ) | `/orders/search` | `receita_dia` | ✓ (⚠️ +R$ → Fase 4) |
| Preço Médio | `kpi.hoje.preco_medio` | idem (derivado receita/unidades) | derivado | — | (sem check direto) | ✗ tem dono, sem check |
| Conversão | `kpi.hoje.conversao` | idem (vendas/visitas) | Order + ListingSnapshot.visits | `/orders/search` + `/items/{id}/visits/time_window` | via visitas | ✗ derivado; visitas têm timing (Fase 3/E43) |

**Tabela KPI multiperíodo (Hoje/Ontem/Anteontem/7d/30d)** — mesmo `/kpi/summary`; campos `vendas`/`visitas`/`receita` (ou `*_media_dia` no modo média) + `conversao`. Mesma origem/dono acima. ⚠️ Σ diária vs 7d/30d ainda pode divergir até E52 (max() não-aditivo — bug-kpi-inconsistencia-multitela).

**Funil de Conversão** — `GET /listings/analytics/funnel` → `service_analytics.py:34`. 🔴 usa **dia UTC, sem filtro de status** → diverge do summary. Migração planejada **Fase 6/E69**.

**Heatmap** — `GET /listings/analytics/heatmap` → `service_analytics.py:376`. ⚠️ filtra `payment_status=="approved"` (exclui refunded que deveria contar) → **Fase 6/E71**.

**Tabela de anúncios** — `GET /listings` → `service_kpi.list_listings`. Colunas detalhadas em E21/E94.

**Cards ML extras** — `GET /listings/dashboard/extra-cards` → `service_dashboard_cards.py`:

| Card | Método cliente ML | Endpoint ML | Check | Status |
|------|-------------------|-------------|-------|--------|
| Reputação (nível, vendas 60d) | get_seller_reputation | `/users/{id}` | `reputacao_vendas_60d`, `reputacao_claims` | ✓ (E14 corrigiu — 4/4 PASS) |
| Perguntas sem resposta | get_my_unanswered_questions | `/my/received_questions/search` | — | ✗ |
| Reclamações abertas | get_my_open_claims | `/post-purchase/v1/claims/search` | — | ✗ |
| Mediações abertas | get_my_open_mediations | `/post-purchase/v1/claims/search` | — | ✗ |
| Mensagens não lidas | get_unread_messages_count | `/messages/unread` | — | ✗ |
| Saldo Mercado Pago | get_mp_balance | `/users/{id}/mercadopago_account/balance` | — | ✗ (leitura de saldo — EC7) |
| Estoque FULL | get_full_inventory_summary | `/users/{id}/fbm_stock/summary` | — | ✗ |
| Sparkline vendas 7d/conta | `extraCards.accounts[].vendas_7d` | service_dashboard_cards:224 | ✓ constante (net_amount) | ✗ |

---

### E21 — Anúncios lista (`pages/Anuncios/index.tsx`) — preenchido 2026-07-10

Fonte única: `GET /listings` → `service_kpi.list_listings`. Colunas da tabela:

| Coluna exibida | Campo payload | Como é calculado (service_kpi) | Tabela.coluna | Endpoint ML | Check | Status |
|----------------|---------------|-------------------------------|---------------|-------------|-------|--------|
| Preço | `price` | Listing (sync) | Listing.price | `/items/{id}/sale_price` | `preco[mlb]` | ✓ 10/10 PASS |
| Preço original | `original_price` | Listing | Listing.original_price | `/items/{id}` | — | ✗ |
| **Você recebe** | `voce_recebe` | real: `Order.net_amount` médio/unid; fallback: preço − sale_fee_pct·preço − avg_shipping | Order.net_amount / Listing.sale_fee_pct+avg_shipping_cost | `/orders/search` + `/sites/MLB/listing_prices` | via comissão | ✗ crítico histórico (validar E94/EA16) |
| Comissão | `sale_fee_amount`/`sale_fee_pct` | Listing (sync fees) | Listing.sale_fee_amount/pct | `/sites/MLB/listing_prices` (+logistic_type+me2) | `comissao[mlb]` | ✓ 10/10 PASS |
| Frete | `avg_shipping_cost` | Listing (sync) | Listing.avg_shipping_cost | `/users/{id}/shipping_options/free` · `/shipments/{id}/costs`→senders.cost | — | ✗ sem check direto |
| Estoque | `last_snapshot.stock` | último snapshot | ListingSnapshot.stock | `/items/{id}` (Σ variations, E9) | `estoque[mlb]` | ✓ 9/10 (E9) |
| Dias p/ zerar | `dias_para_zerar` | stock / vendas_média_7snap | derivado | — | — | ✗ derivado |
| Preço médio/venda | `avg_price_per_sale` | snap_revenue / orders_count | derivado | — | — | ✗ derivado |
| Participação % | `participacao_pct` | rev_listing / Σrev_todos | derivado | — | — | ✗ derivado |
| Quality score | `quality_score` | Listing | Listing.quality_score | `/items/{id}` | — | ✗ |
| Var. vendas/receita | `vendas_variacao`/`receita_variacao` | metrics | Order | `/orders/search` | — | ✗ |

⚠️ **`voce_recebe`** é o ponto de maior risco histórico (preço de tabela vs "você recebe" líquido). Trava definitiva em **E94** (characterization) e **EA16** (export == tela).

---

### Demais telas (E22-E36) — a preencher

| Tela | Campo | Endpoint backend | Serviço:função | Tabela.coluna | Endpoint ML | Check | Status |
|------|-------|------------------|----------------|---------------|-------------|-------|--------|
| _(E22 Anúncio detalhe em diante)_ | | | | | | | |

---

## 2. ENDPOINTS INTERNOS (preenchido na Fase 2B — EA1 a EA18)

> Inventário completo: 124 endpoints em 17 routers (extraído por grep em 2026-07-09).
> Formato: método+path → serviço:função → tabelas lidas/escritas → endpoint(s) ML → tela que usa →
> teste → status (✓ / 🔴 órfão / 🟡 debug-interno).

| Router | Método + Path | Serviço:função | Tabelas | Endpoint ML | Tela que usa | Teste | Status |
|--------|---------------|----------------|---------|-------------|--------------|-------|--------|
| _(a preencher — EA1 auth em diante)_ | | | | | | | |

---

## 3. CLIENTE ML — 47 MÉTODOS PÚBLICOS (Fase 1B — EC1, gerado 2026-07-10)

> `backend/app/mercadolivre/client.py` — o único arquivo que fala com a API do ML.
> Inventário: **47 métodos públicos, 39 ATIVOS, 8 MORTOS** (sem call-site em `app/`).
> (Correção à estimativa "51" do plano — são 47 públicos.)

### 🔴 8 métodos MORTOS (candidatos a limpeza — remoção só com OK do Maikeo, EC5/EC6/EC12)
| Método | Linha | Endpoint ML | Nota |
|--------|-------|-------------|------|
| `update_item_price` | 227 | PUT `/items/{id}` | ML rejeita PUT só-price com 400 desde 18/03/2026. Repricing usa promoções. |
| `get_item_orders` | 349 | `/orders/search` | Variante substituída por `get_orders` (ativo). |
| `get_full_stock` | 387 | `/user-products/{id}/stock/fulfillment` | Estoque FULL detalhado; E9 usa soma de variações. Manter p/ refino futuro se FULL divergir. |
| `get_listing_visits` | 904 | `/visits/items` ❌ LIFETIME | ⚠️ EC2: marcado NÃO CONECTAR (causou visitas infladas). |
| `get_campaigns` | 1005 | `/advertising/campaigns` | API de Ads antiga; substituída por `get_product_ads_campaigns` (ativo). EC6. |
| `get_campaign_metrics` | 1028 | `/advertising/campaigns/{id}/metrics` | Idem — API de Ads antiga. EC6. |
| `get_messages` | 1236 | `/messages/packs/{pack}/sellers/{id}` | `send_message` é ativo; este get específico não tem call-site. |
| `get_item_prices` | 1388 | `/items/{id}/prices` | Histórico de preço; sem call-site atual (oportunidade, não bug). |

### ✅ 39 métodos ATIVOS (endpoint → call-sites principais)
| Método | L | Endpoint ML | Chamado por |
|--------|---|-------------|-------------|
| get_item | 211 | `/items/{id}` | context_collector, service, parity_audit, service_sync |
| get_item_visits | 242 | `/items/{id}/visits/time_window` | tasks_listings (fallback) |
| get_item_visits_on_day | 258 | `/items/{id}/visits/time_window` | parity_audit, tasks_listings |
| get_item_orders_by_status | 290 | `/orders/search` | tasks_listings |
| get_item_promotions | 405 | `/seller-promotions/items/{id}` | service_analytics, service_price |
| create_price_discount_promotion | 436 | `/seller-promotions/items/{id}` | service_price |
| delete_price_discount_promotion | 492 | `/seller-promotions/items/{id}` | service_price |
| get_advertiser_id | 588 | `/advertising/advertisers` | ads/service |
| get_product_ads_campaigns | 614 | `/advertising/advertisers/{id}/product_ads/campaigns` | ads/service |
| get_product_ads_items | 643 | `/advertising/advertisers/{id}/product_ads/items` | ads/service |
| get_item_ads | 674 | `/advertising/product_ads` | service_analytics |
| get_listing_fees | 696 | `/sites/MLB/listing_prices` | parity_audit, service_sync, tasks_listings |
| get_free_shipping_cost | 758 | `/users/{id}/shipping_options/free` | tasks_listings |
| get_seller_reputation | 808 | `/users/{id}` | reputacao/service, dashboard_cards |
| get_my_unanswered_questions | 824 | `/my/received_questions/search` | dashboard_cards |
| get_my_open_claims | 828 | `/post-purchase/v1/claims/search` | dashboard_cards |
| get_my_open_mediations | 848 | `/post-purchase/v1/claims/search` | dashboard_cards |
| get_unread_messages_count | 865 | `/messages/unread` | dashboard_cards |
| get_mp_balance | 880 | `/users/{id}/mercadopago_account/balance` | dashboard_cards (leitura de saldo — EC7) |
| get_full_inventory_summary | 884 | `/users/{id}/fbm_stock/summary` | dashboard_cards |
| get_listing | 900 | alias de get_item | router, service, service_analytics, service_price |
| get_user_listings | 932 | `/users/{id}/items/search` | service_sync |
| get_item_questions | 950 | `/questions/search` | tasks_listings |
| get_items_visits_bulk | 965 | `/visits/items` ⚠️ | router (backfill — E65 corrige), tasks_competitors |
| get_orders | 1054 | `/orders/search` | service, parity_audit, tasks_orders |
| get_shipment | 1087 | `/shipments/{id}` | tasks_listings |
| get_shipment_costs | 1103 | `/shipments/{id}/costs` | tasks_helpers (frete real senders.cost) |
| get_received_questions | 1113 | `/my/received_questions/search` | perguntas/service |
| answer_question | 1133 | `/answers` | router, perguntas/service |
| search_items | 1146 | `/sites/MLB/search` | service_analytics |
| get_claims | 1165 | `/post-purchase/v1/claims/search` | atendimento/service, service_claims |
| get_claim_detail | 1199 | `/post-purchase/v1/claims/{id}` | atendimento/service |
| send_claim_message | 1206 | `/post-purchase/v1/claims/{id}/actions/send-message` | atendimento/service |
| send_message | 1266 | `/messages/packs/{pack}/sellers/{id}` | atendimento/service |
| get_message_packs | 1296 | `/messages/search` | atendimento/service |
| get_returns | 1323 | `/post-purchase/v1/claims/search` | atendimento/service |
| get_item_sale_price | 1354 | `/items/{id}/sale_price` | parity_audit, service_sync, tasks_competitors, tasks_listings |

> ⚠️ `get_items_visits_bulk` (965) usa `/visits/items` (lifetime) — só é seguro no backfill se
> combinado com o dia certo; **E65 (Fase 5) troca por `get_item_visits_on_day`**.

---

## 4. CRUZAMENTO (preenchido em EA17)

> Mapa navegável nos dois sentidos: dado uma tela, quais endpoints e métodos ML a alimentam; dado um
> método ML, quais endpoints e telas dependem dele. Preenchido ao final da Fase 2B.

_(a preencher — EA17)_
