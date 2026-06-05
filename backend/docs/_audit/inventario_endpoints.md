# Inventário Mestre — Endpoints API Mercado Livre (MSM_Pro)

> Artefato de trabalho da auditoria 2026-06-03 (ARCH-014). Insumo da fonte canônica
> `backend/docs/ml_endpoints_canonical.md`. **Não é a fonte da verdade** — é o levantamento bruto.
> Base: `backend/app/mercadolivre/client.py` (1253 linhas) + call sites por módulo.

Base URL: `https://api.mercadolibre.com` (`ML_API_BASE` client.py:9 / `settings.ml_api_base` config.py).
Tudo passa por `MLClient._request()` (rate limit Redis 1 req/s + retry backoff + refresh 401).
Únicas chamadas httpx diretas (fora do MLClient): `auth/service.py` → `/oauth/token` (x2) e `/users/me` (pré-token, intencional).

## Tabela definitiva (método client.py | linha | verbo | path | observação)

| Método | Linha | Verbo | Path | Observação |
|--------|-------|-------|------|-----------|
| get_item | 196 | GET | /items/{id}?include_attributes=all | dados do anúncio; `price` depreciado |
| update_item_price | 212 | PUT | /items/{id} body {price} | bloqueado se houver promoção ativa |
| get_item_visits | 227 | GET | /items/{id}/visits/time_window?last&unit=day | visitas N dias |
| get_item_orders_by_status | 243 | GET | /orders/search (seller,q,date,status) | `q` é textual, validar no caller |
| get_item_orders | 302 | GET | /orders/search (status=paid) | idem, status fixo paid |
| get_full_stock | 340 | GET | /user-products/{id}/stock/fulfillment | fallback {available:0} |
| get_item_promotions | 358 | GET | /seller-promotions/items/{id}?app_version=v2 | lista promoções |
| create_price_discount_promotion | 389 | POST | /seller-promotions/items/{id}?user_id | PRICE_DISCOUNT; **Validado: PENDENTE** |
| delete_price_discount_promotion | 443 | DELETE | /seller-promotions/items/{id}?user_id&promotion_type | **PENDENTE**; nunca chamado |
| **create_promotion** | 479 | — | — | **DEPRECADO** (raise NotImplementedError) |
| **update_promotion** | 510 | — | — | **DEPRECADO** (PRICE_DISCOUNT não aceita PUT) |
| get_advertiser_id | 537 | GET | /advertising/advertisers?product_id=PADS | header Api-Version:2 |
| get_product_ads_campaigns | 563 | GET | /advertising/advertisers/{id}/product_ads/campaigns | Api-Version:2; nunca chamado |
| get_product_ads_items | 592 | GET | /advertising/advertisers/{id}/product_ads/items | Api-Version:2 |
| **get_item_ads** | 623 | GET | /advertising/product_ads?item_id&status=active | **DEPRECADO** |
| get_listing_fees | 645 | GET | /sites/MLB/listing_prices?price&category_id&listing_type_id | taxa comissão |
| get_free_shipping_cost | 690 | GET | /users/{seller_id}/shipping_options/free?item_id&free_shipping=true | frete grátis vendedor (bug orders) |
| get_seller_reputation | 736 | GET | /users/{seller_id} | seller_reputation |
| get_my_unanswered_questions | 752 | GET | /my/received_questions/search?status=UNANSWERED | |
| get_my_open_claims | 756 | GET | /post-purchase/v1/claims/search?status=opened | |
| get_my_open_mediations | 760 | GET | /post-purchase/v1/claims/search?status=opened&stage=dispute | |
| get_unread_messages_count | 771 | GET | /messages/unread?role=seller&tag=post_sale | |
| get_mp_balance | 786 | GET | /users/{seller_id}/mercadopago_account/balance | nunca chamado |
| get_full_inventory_summary | 790 | GET | /users/{seller_id}/fbm_stock/summary | beta; nunca chamado |
| get_listing | 806 | GET | /items/{id} (alias get_item) | legado |
| get_listing_visits | 810 | GET | /visits/items?ids&date_from&date_to | legado |
| get_user_listings | 831 | GET | /users/{ml_user_id}/items/search?status&offset&limit | paginação |
| get_item_questions | 849 | GET | /questions/search?item&status=unanswered | |
| get_items_visits_bulk | 861 | GET | /visits/items?ids(50)&date_from&date_to | bulk, chunks 50 |
| get_campaigns | 901 | GET | /advertising/campaigns?user_id | nunca chamado |
| get_campaign_metrics | 924 | GET | /advertising/campaigns/{id}/metrics | nunca chamado |
| get_orders | 950 | GET | /orders/search?seller&date_created.from&sort | genérico paginado |
| get_shipment | 983 | GET | /shipments/{id} | cost_components/base_cost |
| get_received_questions | 991 | GET | /my/received_questions/search?status&offset&limit&sort | |
| answer_question | 1011 | POST | /answers body {question_id,text} | |
| search_items | 1024 | GET | /sites/MLB/search?q&offset&limit | público |
| get_claims | 1043 | GET | /post-purchase/v1/claims/search?status&sort | |
| get_claim_detail | 1069 | GET | /post-purchase/v1/claims/{id} | |
| send_claim_message | 1076 | POST | /post-purchase/v1/claims/{id}/messages body {message} | |
| get_messages | 1091 | GET | /messages/packs/{pack}/sellers/{seller} ou /messages/orders/{id} | |
| send_message | 1114 | POST | /messages/packs/{pack}/sellers/{seller} body {from,text} | |
| get_message_packs | 1125 | GET | /messages/search?seller_id&offset&limit | |
| get_returns | 1152 | GET | /post-purchase/v1/claims/search?claim_type=return | |
| get_item_sale_price | 1176 | GET | /items/{id}/sale_price?context=channel_marketplace | **fonte primária de preço** |
| get_item_prices | 1210 | GET | /items/{id}/prices | camadas de preço; nunca chamado |

## Call sites (módulo → endpoint → propósito)

- **auth/service.py** (httpx direto): `/oauth/token` (authorization_code + refresh_token), `/users/me` (info pós-OAuth).
- **vendas/service_sync.py**: get_item, get_item_sale_price, get_item_promotions, get_listing_fees, get_item_visits, get_free_shipping_cost, orders → sync de anúncios + preço + taxa + frete.
- **jobs/tasks_listings.py**: get_item, get_item_sale_price, get_item_promotions, get_listing_fees, get_items_visits_bulk, get_item_visits (fallback), get_item_orders_by_status (paid/cancelled/returned), get_item_questions, get_shipment → snapshot diário.
- **jobs/tasks_orders.py**: get_orders, get_shipment → sync pedidos 2h + backfill pós-reconexão.
- **jobs/tasks_competitors.py**: get_items_visits_bulk, get_item, get_item_sale_price → snapshots concorrentes.
- **vendas/service_price.py**: get_item_promotions, create_price_discount_promotion → repricing.
- **vendas/service_analytics.py**: get_item_ads (DEPRECADO), get_item_promotions, search_items → analytics/posição.
- **analise/service.py**: get_advertiser_id, get_product_ads_items → métricas ads por item.
- **perguntas/service.py + context_collector.py**: get_received_questions, answer_question, get_item, /items/{id}/description.
- **atendimento/service.py + service_claims.py**: received_questions, claims/search, messages/search, answers, claims messages, messages packs/orders, get_item.
- **reputacao/service.py**: get_seller_reputation.

## Suspeitos prioritários (entram na validação com atenção)

1. `create_promotion` / `update_promotion` — **DEPRECADOS**, confirmar forma correta oficial.
2. `get_item_ads` — **DEPRECADO**, confirmar substituto product_ads/items.
3. `/orders/search` + `/shipments/{id}` + frete grátis/comissão — bug [[bug-orders-frete-comissao]].
4. `get_free_shipping_cost` (`/users/{id}/shipping_options/free`) — verificar `list_cost` oficial.
5. Métodos nunca chamados (get_item_prices, get_mp_balance, get_full_inventory_summary, get_campaigns, get_campaign_metrics, get_product_ads_campaigns, delete_price_discount_promotion) — manter/aposentar.
