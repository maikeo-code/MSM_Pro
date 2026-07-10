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

| Tela | Campo | Endpoint backend | Serviço:função | Tabela.coluna | Endpoint ML | Check | Status |
|------|-------|------------------|----------------|---------------|-------------|-------|--------|
| _(a preencher — E20 Dashboard em diante)_ | | | | | | | |

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
