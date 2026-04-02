# Auditoria client.py vs docs/ml_api_reference.md

> Gerado em 2026-04-02. Cruzamento dos 35 metodos do `client.py` contra a doc validada.

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
| 2 | `update_item_price` | PUT /items/{id} | **NAO** | NAO | FALTA | Endpoint real mas sem doc no projeto. Usar com cuidado — ML pode rejeitar se item em catalogo |
| 3 | `get_item_sale_price` | GET /items/{id}/sale_price | Sim (sec 11) | Sim (2026-03-25) | OK | Fonte primaria de preco desde migração |
| 4 | `get_item_prices` | GET /items/{id}/prices | **NAO** | NAO | FALTA | Lista todas camadas de preco. Nao documentado na referencia |
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
| 15 | `create_promotion` | POST /seller-promotions/users/{id} | **NAO** | NAO | FALTA+RISCO | Endpoint de ESCRITA sem doc validada |
| 16 | `update_promotion` | PUT /seller-promotions/{id} | **NAO** | NAO | FALTA+RISCO | Endpoint de ESCRITA sem doc validada |

### PUBLICIDADE (ADS)

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 17 | `get_advertiser_id` | GET /advertising/advertisers | **NAO** | NAO | FALTA | API Ads nao e publica — pode dar 403 |
| 18 | `get_product_ads_campaigns` | GET /advertising/.../product_ads/campaigns | **NAO** | NAO | FALTA | Header Api-Version:2. Nao documentado |
| 19 | `get_product_ads_items` | GET /advertising/.../product_ads/items | **NAO** | NAO | FALTA | Metricas por item ads. Nao documentado |
| 20 | `get_item_ads` | GET /advertising/product_ads | **NAO** | NAO | FALTA+DEPRECATED | Marcado como deprecated no proprio codigo |
| 21 | `get_campaigns` | GET /advertising/campaigns | **NAO** | NAO | FALTA | Busca campanhas. Nao documentado |
| 22 | `get_campaign_metrics` | GET /advertising/campaigns/{id}/metrics | **NAO** | NAO | FALTA | Metricas diarias. Nao documentado |

### ENVIOS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 23 | `get_shipment` | GET /shipments/{id} | **NAO** | NAO | FALTA | Custo de frete real. Critico para margem |
| 24 | `get_full_stock` | GET /user-products/{id}/stock/fulfillment | **NAO** | NAO | FALTA+RISCO | Endpoint de Full. Nao documentado — pode nao existir |

### PERGUNTAS E RESPOSTAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 25 | `get_item_questions` | GET /questions/search | Sim (sec 8) | Parcial | OK | Filtra por item |
| 26 | `get_received_questions` | GET /my/received_questions/search | **NAO** | NAO | FALTA | Perguntas recebidas pelo vendedor |
| 27 | `answer_question` | POST /answers | **NAO** | NAO | FALTA | Endpoint de ESCRITA |

### TAXAS

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 28 | `get_listing_fees` | GET /sites/MLB/listing_prices | **NAO** | NAO | FALTA | Taxa real por categoria. Critico para margem |

### BUSCA

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 29 | `search_items` | GET /sites/MLB/search | **NAO** | NAO | FALTA | Busca publica. Funciona mas nao documentado |

### RECLAMACOES (CLAIMS)

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 30 | `get_claims` | GET /v1/claims/search | **NAO** | NAO | FALTA+RISCO | Endpoint v1 — pode ser diferente da v2 |
| 31 | `get_claim_detail` | GET /v1/claims/{id} | **NAO** | NAO | FALTA | |
| 32 | `send_claim_message` | POST /v1/claims/{id}/messages | **NAO** | NAO | FALTA+RISCO | ESCRITA sem doc |

### MENSAGENS POS-VENDA

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 33 | `get_messages` | GET /messages/packs/{id}/sellers/{id} | **NAO** | NAO | FALTA+RISCO | Formato pode variar |
| 34 | `send_message` | POST /messages/packs/{id}/sellers/{id} | **NAO** | NAO | FALTA+RISCO | ESCRITA sem doc |
| 35 | `get_message_packs` | GET /messages/search | **NAO** | NAO | FALTA | |

### DEVOLUCOES

| # | Metodo | Endpoint | Doc? | Validado? | Status | Notas |
|---|--------|----------|------|-----------|--------|-------|
| 36 | `get_returns` | GET /v1/claims/search?claim_type=return | **NAO** | NAO | FALTA | |

---

## Resumo

| Categoria | Total | OK | FALTA doc | RISCO |
|-----------|-------|-----|-----------|-------|
| Core (anuncios/precos) | 5 | 3 | 2 | 0 |
| Visitas | 3 | 3 | 0 | 0 |
| Pedidos/vendas | 3 | 3 | 0 | 0 |
| Vendedor/listagens | 2 | 2 | 0 | 0 |
| Promocoes | 3 | 1 | 2 | 2 |
| Publicidade (Ads) | 6 | 0 | 6 | 1 |
| Envios | 2 | 0 | 2 | 1 |
| Perguntas/Respostas | 3 | 1 | 2 | 0 |
| Taxas | 1 | 0 | 1 | 0 |
| Busca | 1 | 0 | 1 | 0 |
| Claims | 3 | 0 | 3 | 2 |
| Mensagens | 3 | 0 | 3 | 2 |
| Devolucoes | 1 | 0 | 1 | 0 |
| **TOTAL** | **36** | **13** | **23** | **8** |

### Conclusao

- **13/36 metodos (36%)** estao documentados e validados — SEGUROS
- **23/36 metodos (64%)** NAO estao documentados — RISCO DE ERRO
- **8 metodos** tem risco elevado (endpoints de escrita ou formato incerto)
- **6 metodos de Ads** nao tem nenhuma doc — API Ads do ML nao e publica

### Top 5 prioridades para documentar

1. **`get_shipment`** — critico para calculo de margem real
2. **`get_listing_fees`** — critico para calculo de taxa ML
3. **`get_received_questions` + `answer_question`** — modulo Q&A depende disso
4. **`get_claims` + `get_claim_detail`** — modulo atendimento depende disso
5. **`get_messages` + `send_message`** — modulo mensagens depende disso

### Acao recomendada

Para cada metodo FALTA: o agente `ml-api` deve:
1. Consultar doc oficial ML via MCP `mercadolibre-official`
2. Testar com curl real usando token de producao
3. Documentar em `docs/ml_api_reference.md`
4. Marcar como validado com data
