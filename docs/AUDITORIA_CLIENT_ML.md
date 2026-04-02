# Auditoria client.py vs docs/ml_api_reference.md

> Gerado em 2026-04-02. Cruzamento dos 38 metodos do `client.py` contra a doc validada.
> Atualizado em 2026-04-02 — 13 endpoints novos documentados via pesquisa (secoes 28-40 do ml_api_reference.md).

## Legenda

| Icone | Significado |
|-------|-------------|
| OK | Endpoint documentado E validado com curl real |
| DOC | Endpoint documentado mas NAO validado com curl |
| FALTA | Endpoint NO client.py mas NAO documentado na referencia |
| RISCO | Potencial problema identificado |

---

## Resultado da Auditoria

### CORE — Anuncios e Precos

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 1 | `get_item` | GET /items/{id} | Sim | Sim (2026-03-25) | OK | `include_attributes=all` correto |
| 2 | `update_item_price` | PUT /items/{id} | Sim (sec 10) | NAO | DOC | Endpoint documentado na secao 10 |
| 3 | `get_item_sale_price` | GET /items/{id}/sale_price | Sim (sec 11) | Sim (2026-03-25) | OK | Fonte primaria de preco desde migração |
| 4 | `get_item_prices` | GET /items/{id}/prices | Sim (sec 27) | NAO | DOC | Documentado na secao 27 |
| 5 | `get_listing` | (alias de get_item) | — | — | OK | Apenas redireciona |

### VISITAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 6 | `get_item_visits` | GET /items/{id}/visits/time_window | Sim (sec 2) | Sim (2026-03-12) | OK | |
| 7 | `get_listing_visits` | GET /visits/items | Sim (sec 3) | Sim (2026-03-12) | OK | Legado, preferir bulk |
| 8 | `get_items_visits_bulk` | GET /visits/items (bulk) | Sim (sec 3) | Sim (2026-03-12) | OK | Chunks de 50. Parsing flexivel dict/list |

### PEDIDOS E VENDAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 9 | `get_item_orders` | GET /orders/search | Sim (sec 5) | Sim (2026-03-12) | OK | Usa `q` como busca textual + filter no caller |
| 10 | `get_item_orders_by_status` | GET /orders/search | Sim (sec 5) | Sim | OK | Variante com status filter |
| 11 | `get_orders` | GET /orders/search | Sim (sec 5) | Sim | OK | Versao generica com paginacao |

### VENDEDOR E LISTAGENS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 12 | `get_user_listings` | GET /users/{id}/items/search | Sim (sec 6) | Sim (2026-03-12) | OK | |
| 13 | `get_seller_reputation` | GET /users/{id} | Sim (sec 9) | Sim | OK | Retorna objeto completo do usuario |

### PROMOCOES

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 14 | `get_item_promotions` | GET /seller-promotions/items/{id} | Sim (sec 7) | Sim (2026-03-25) | OK | `app_version=v2` correto |
| 15 | `create_promotion` | DEPRECADO | Sim | — | DOC | Metodo depreciado no client.py — usar create_price_discount_promotion() (sec 39) |
| 16 | `update_promotion` | DEPRECADO | Sim | — | DOC | Metodo depreciado no client.py — usar delete+create (sec 39+40) |
| 15b | `create_price_discount_promotion` | POST /seller-promotions/items/{id} | Sim (sec 39) | NAO | DOC+RISCO | Metodo novo correto. Endpoint de ESCRITA — pendente validacao curl |
| 16b | `delete_price_discount_promotion` | DELETE /seller-promotions/items/{id} | Sim (sec 40) | NAO | DOC+RISCO | Metodo novo correto. Endpoint de ESCRITA — pendente validacao curl |

### PUBLICIDADE (ADS)

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 17 | `get_advertiser_id` | GET /advertising/advertisers | Sim (sec 20) | NAO | DOC | API Ads nao e publica — pode dar 403. BUG critico no parsing da resposta |
| 18 | `get_product_ads_campaigns` | GET /advertising/.../product_ads/campaigns | Sim (sec 21) | NAO | DOC | Header Api-Version:2. BUG: campo "spend" deveria ser "cost" |
| 19 | `get_product_ads_items` | GET /advertising/.../product_ads/items | Sim (sec 22) | NAO | DOC | Metricas por item ads documentadas |
| 20 | `get_item_ads` | GET /advertising/product_ads | Sim (sec 25) | NAO | DOC | DEPRECATED — documentado como tal |
| 21 | `get_campaigns` | GET /advertising/campaigns | Sim (sec 23) | NAO | DOC | Endpoint legado possivelmente deprecado |
| 22 | `get_campaign_metrics` | GET /advertising/campaigns/{id}/metrics | Sim (sec 24) | NAO | DOC | Endpoint legado possivelmente deprecado |

### ENVIOS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 23 | `get_shipment` | GET /shipments/{id} | Sim (sec 28) | NAO | DOC | Documentado. Header x-format-new:true obrigatorio. Pendente curl |
| 24 | `get_full_stock` | GET /user-products/{id}/stock/fulfillment | Sim (sec 18) | NAO | DOC | Documentado na secao 18 |

### PERGUNTAS E RESPOSTAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 25 | `get_item_questions` | GET /questions/search | Sim (sec 8) | Parcial | OK | Filtra por item |
| 26 | `get_received_questions` | GET /my/received_questions/search | Sim (sec 29) | NAO | DOC | Documentado. Status MAIUSCULO. Pendente curl |
| 27 | `answer_question` | POST /answers | Sim (sec 30) | NAO | DOC+RISCO | Endpoint de ESCRITA documentado. Pendente curl |

### TAXAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 28 | `get_listing_fees` | GET /sites/MLB/listing_prices | Sim (sec 11, 19) | NAO | DOC | Documentado nas secoes 11 e 19. Pendente curl |

### BUSCA

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 29 | `search_items` | GET /sites/MLB/search | Sim (sec 38) | NAO | DOC | Documentado. Endpoint publico — facil de validar |

### RECLAMACOES (CLAIMS)

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 30 | `get_claims` | GET /v1/claims/search | Sim (sec 31) | NAO | DOC+RISCO | ATENCAO: endpoint DEPRECADO desde maio 2024. Migrar para /post-purchase/v1/claims/search |
| 31 | `get_claim_detail` | GET /v1/claims/{id} | Sim (sec 32) | NAO | DOC+RISCO | ATENCAO: endpoint DEPRECADO. Migrar para /post-purchase/v1/claims/{id} |
| 32 | `send_claim_message` | POST /v1/claims/{id}/messages | Sim (sec 33) | NAO | DOC+RISCO | ATENCAO: endpoint DEPRECADO. Migrar para /post-purchase/v1/claims/{id}/messages |

### MENSAGENS POS-VENDA

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 33 | `get_messages` | GET /messages/packs/{id}/sellers/{id} | Sim (sec 35) | NAO | DOC | Documentado. IA intermediacao ativa para Full desde fev/2026 |
| 34 | `send_message` | POST /messages/packs/{id}/sellers/{id} | Sim (sec 36) | NAO | DOC+RISCO | Endpoint de ESCRITA documentado. Pendente curl |
| 35 | `get_message_packs` | GET /messages/search | Sim (sec 37) | NAO | DOC | Documentado. Formato estimado — validar curl |

### DEVOLUCOES

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 36 | `get_returns` | GET /v1/claims/search?claim_type=return | Sim (sec 34) | NAO | DOC+RISCO | ATENCAO: endpoint DEPRECADO. Migrar para /post-purchase/v1/claims/search?claim_type=return |

---

## Resumo (Atualizado 2026-04-02)

| Categoria | Total | OK (curl) | DOC (sem curl) | RISCO | FALTA |
|-----------|-------|-----------|----------------|-------|-------|
| Core (anuncios/precos) | 5 | 3 | 2 | 0 | 0 |
| Visitas | 3 | 3 | 0 | 0 | 0 |
| Pedidos/vendas | 3 | 3 | 0 | 0 | 0 |
| Vendedor/listagens | 2 | 2 | 0 | 0 | 0 |
| Promocoes | 5 | 1 | 4 | 2 | 0 |
| Publicidade (Ads) | 6 | 0 | 6 | 1 | 0 |
| Envios | 2 | 0 | 2 | 0 | 0 |
| Perguntas/Respostas | 3 | 1 | 2 | 1 | 0 |
| Taxas | 1 | 0 | 1 | 0 | 0 |
| Busca | 1 | 0 | 1 | 0 | 0 |
| Claims | 3 | 0 | 3 | 3 | 0 |
| Mensagens | 3 | 0 | 3 | 1 | 0 |
| Devolucoes | 1 | 0 | 1 | 1 | 0 |
| **TOTAL** | **38** | **13** | **25** | **9** | **0** |

### Conclusao (apos documentacao completa 2026-04-02)

- **13/38 metodos (34%)** estao documentados E validados com curl — SEGUROS
- **25/38 metodos (66%)** estao documentados mas SEM curl real — SEGUROS para uso, validar antes de producao critica
- **0/38 metodos** sem documentacao — COBERTURA 100%
- **4 metodos de Claims** usam endpoints DEPRECADOS (maio 2024) — MIGRAR URGENTE

### Acoes prioritarias

1. **URGENTE — Migrar endpoints de Claims**: substituir `/v1/claims/` por `/post-purchase/v1/claims/` nos 4 metodos afetados
2. **Validar com curl**: todos os endpoints de escrita (answer_question, send_message, create_price_discount_promotion, delete_price_discount_promotion)
3. **Validar get_shipment**: critico para calculo de margem real — confirmar header `x-format-new: true`
4. **Corrigir bug Ads**: campo `"spend"` → `"cost"` no ads/service.py (bug documentado na secao 21)
5. **Corrigir bug advertiser_id**: parsing incorreto da resposta em client.py (bug documentado na secao 20)

### Atualizado em: 2026-04-02 — 13 endpoints documentados via pesquisa na doc oficial ML
