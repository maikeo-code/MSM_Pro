# ML Endpoints — FONTE DA VERDADE CANÔNICA (MSM_Pro)

> **Este é o arquivo canônico.** Substitui `ml_api_reference.md` (mantido como `.legacy.md` para histórico).
> Validado contra a documentação oficial do Mercado Livre via **MCP oficial** (`mcp.mercadolibre.com`)
> em **2026-06-03** (auditoria ARCH-014) e **reverificado em 2026-06-08** (ver `_audit/reverificacao_mcp_2026-06-08.md`).
> Antes de implementar/alterar qualquer chamada ML, consulte aqui.
>
> **Atualizações da reverificação 2026-06-08:** (1) `send_claim_message` é ❌ DIVERGENTE — o POST oficial é
> `/post-purchase/v1/claims/{id}/actions/send-message` com `{receiver_role, message}` (o `/messages` é só GET);
> (2) `create_price_discount_promotion` e `delete_price_discount_promotion` enviam `user_id` **inexistente** na
> doc — remover (no delete, `promotion_type` **é válido**); (3) `get_item_questions` → usar `item_id` (a doc oficial é ambígua: tabela diz `item`, exemplo usa `item_id`).
> Espelho no cérebro: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/02 - API Mercado Livre/Endpoints Usados.md`.

Base URL: `https://api.mercadolibre.com` · Cliente: `backend/app/mercadolivre/client.py` (`MLClient._request`).
Docs oficiais (paths do MCP, idioma pt_br): citados em cada bloco como **[doc: <path>]**.

## Legenda de status

| Status | Significado |
|--------|-------------|
| ✅ OK | Endpoint, verbo, params e estrutura conferem com a doc oficial. |
| ⚠️ PARCIAL | Funciona, mas falta param/header recomendado (resultado pode divergir do real). |
| ❌ DIVERGENTE | Path/param/body errado vs. oficial — **corrigir** (ver backlog). |
| ⛔ DEPRECADO | Não usar; aposentar. |
| 🔒 RESTRITO | Endpoint existe mas exige acesso especial / não público (fallback gracioso). |

---

## BLOCO A — Itens & Preço  [doc: api-de-precos, itens-e-buscas, custos-de-envio]

| Método (client.py) | Endpoint | Status | Nota |
|---|---|---|---|
| get_item / get_listing | GET /items/{id}?include_attributes=all | ✅ OK | `price`, `base_price`, `original_price` **em depreciação** — não usar como preço de venda. `shipping.free_shipping`/`logistic_type` válidos aqui. |
| get_item_sale_price | GET /items/{id}/sale_price?context=channel_marketplace | ✅ OK | **Fonte primária de preço.** Resposta: `price_id, amount, regular_amount, currency_id, reference_date, metadata{promotion_id,promotion_type}`. `context` aceita canal + `buyer_loyalty_3..6`. |
| get_item_prices | GET /items/{id}/prices | ✅ OK | Camadas `standard`/`promotion` com `conditions.context_restrictions` e `start_time/end_time`. Implementado, **nunca chamado** — candidato a usar para histórico/checagem. |
| update_item_price | PUT /items/{id} body {price} | ⚠️ PARCIAL/RISCO | **Desde 18/03/2026 o PUT só com `price` é rejeitado (400).** Se enviado com outros atributos, o `price` é ignorado (200 + warning). A edição de preço migrará para `POST /items/{id}/prices/standard` (**ainda não disponível**). Verificar automação de preços ativa antes. |
| (futuro) editar preço | POST /items/{id}/prices/standard | 🔒 N/D | Endpoint oficial que substituirá o PUT de preço — **"em breve"**, ainda não liberado. Registrar para migração. |
| get_item (description) | GET /items/{id}/description | ✅ OK | Usado em perguntas/context_collector (`plain_text`). |
| get_user_listings | GET /users/{id}/items/search?status&offset&limit | ✅ OK | Paginação por offset/limit (máx 50). Para catálogos grandes, considerar `search_type=scan`. |

## BLOCO B — Visitas  [doc: itens-e-buscas / visits]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_item_visits | GET /items/{id}/visits/time_window?last&unit=day | ✅ OK | Visitas por janela. |
| get_listing_visits / get_items_visits_bulk | GET /visits/items?ids&date_from&date_to | ✅ OK | Bulk, chunks de 50 ids. Datas YYYY-MM-DD. |

## BLOCO C — Promoções do vendedor  [doc: gerenciar-ofertas, desconto-individua]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_item_promotions | GET /seller-promotions/items/{id}?app_version=v2 | ✅ OK | Retorna todas as ofertas do item (PRICE_DISCOUNT, DEAL, DOD, LIGHTNING, SELLER_CAMPAIGN, MARKETPLACE_CAMPAIGN, VOLUME, SMART, BANK, SELLER_COUPON_CAMPAIGN...). Campos: `type, status(candidate/started/pending), price, original_price, min/max/suggested_discounted_price`. |
| create_price_discount_promotion | POST /seller-promotions/items/{id}?user_id={seller} body {promotion_type:PRICE_DISCOUNT, deal_price, start_date, finish_date} | 🔧 CORRIGIR (reverif. 2026-06-08) | Body **confirmado** (`{deal_price, top_deal_price?, start_date, finish_date, promotion_type:"PRICE_DISCOUNT"}`). **Remover `?user_id`** — não existe na doc oficial; usar só `?app_version=v2`. Regras: 5–80%, reputação verde, item ativo/novo, máx 14 dias. [doc: desconto-individua] |
| delete_price_discount_promotion | DELETE /seller-promotions/items/{id}?user_id&promotion_type | 🔧 CORRIGIR (reverif. 2026-06-08) | **`promotion_type` É válido** (delete individual oficial: `?promotion_type=PRICE_DISCOUNT&app_version=v2`). **Remover apenas `user_id`** (não existe na doc). Delete massivo = sem `promotion_type` → remove todas exceto DOD/LIGHTNING, resposta `{successful_ids, errors}`. [doc: desconto-individua, gerenciar-ofertas] |
| create_promotion | POST /seller-promotions/users/{seller} (antigo) | ⛔ DEPRECADO | Path/body errados (`/users/{id}` é GET de convites, não criação). Já lança NotImplementedError. **Remover.** |
| update_promotion | PUT /seller-promotions/{id} (antigo) | ⛔ DEPRECADO | Oficial confirma: PRICE_DISCOUNT/DOD/LIGHTNING **não editam via PUT — deletar e recriar.** Já lança NotImplementedError. **Remover.** |
| (não implementado) | GET /seller-promotions/users/{id}?app_version=v2 | ➕ FALTANTE | Lista convites/campanhas do vendedor (DEAL, MARKETPLACE_CAMPAIGN, VOLUME...). Útil p/ módulo de promoções. |
| (não implementado) | GET /seller-promotions/promotions/{id}/items?promotion_type&app_version=v2&search_after | ➕ FALTANTE | Itens de uma campanha; paginação por `search_after` (TTL 5min). |

## BLOCO D — Pedidos & Envios  [doc: gerenciamento-de-vendas, custos-de-envio]  ← bug de frete/comissão

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_orders / get_item_orders(_by_status) | GET /orders/search?seller&order.status&order.date_created.from/to&q&sort&offset&limit | ✅ OK | `q` é genérico (order id, item id, título, nickname) — validar item no caller. Salva orders por **até 12 meses**; busca de vendedor filtra canceladas. Status: confirmed/paid/cancelled/etc. |
| **comissão real** | `order_items[].sale_fee` (dentro de GET /orders/{id} ou /search) | ✅ OK | **`sale_fee` = comissão de venda real do ML** (ex.: 14.29). Já confirmado no [[bug-orders-frete-comissao]]. |
| **descontos** | GET /orders/{id}/discounts | ➕ FALTANTE | Detalha cupons/cashback/desconto por item (`amounts.total`, `amounts.seller`). Útil p/ margem precisa. |
| get_shipment | GET /shipments/{id} | ⚠️ PARCIAL | Para o **frete real pago pelo vendedor**, usar header **`x-format-new: true`**. `lead_time.cost` = custo estimado; o **custo real faturado** é `GET /shipments/{id}/costs` → `senders[].cost` (mais preciso, inclui desconto). [fundamentalista]. Código lê `cost_components.sender_cost` **sem** header — frete vinha 0/None. Corrigir. |
| get_free_shipping_cost | GET /users/{id}/shipping_options/free?item_id&free_shipping=true&verbose | ⚠️ PARCIAL | Endpoint **correto** (`coverage.all_country.list_cost`). Porém o código usa `verbose=false` → não retorna `coverage.discount`; o vendedor paga `list_cost` **menos** o desconto. Enviar `verbose=true` e subtrair `discount`. Considerar `logistic_type`/`mode` p/ precisão. |
| (compra) | GET /items/{id}/shipping_options?zip_code | ➕ FALTANTE | Custo de envio no checkout por CEP (`options[].list_cost/base_cost/cost`). |

## BLOCO E — Taxas & Busca  [doc: comissao-por-vender, itens-e-buscas]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_listing_fees | GET /sites/MLB/listing_prices?price&category_id&listing_type_id | ⚠️ PARCIAL | Estrutura lida (`sale_fee_details.percentage_fee/fixed_fee`, `sale_fee_amount`) **correta**. Mas desde **02/03/2026 (Brasil)** o `fixed_fee` depende de `logistic_type`+`shipping_mode`(+`billable_weight`); **sem esses params o fixed_fee não bate com o cobrado.** Adicionar params. |
| search_items | GET /sites/MLB/search?q&offset&limit | ✅ OK | Busca pública. |

## BLOCO F — Perguntas  [doc: perguntas-e-respostas, gerenciamento-perguntas-respostas]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_received_questions / get_my_unanswered_questions | GET /my/received_questions/search?status&offset&limit&sort_fields&sort_types | ✅ OK | Status válidos: ANSWERED, BANNED, CLOSED_UNANSWERED, DELETED, DISABLED, UNANSWERED, UNDER_REVIEW. Recomenda `api_version=4`. |
| get_item_questions | GET /questions/search?item_id&status | ⚠️ PARCIAL | Doc usa **`item_id`** (o código usa `item`). Recomenda `api_version=4`. Status minúsculo `unanswered` vs maiúsculo — padronizar com received_questions (UNANSWERED). |
| answer_question | POST /answers body {question_id, text} | ✅ OK | Confere exatamente. |

## BLOCO G — Pós-venda: Reclamações, Devoluções, Mensagens  [doc: gerenciar-reclamacoes, gerenciar-devolucoes, mensagens-post-venda, gerenciar-mensagem-de-uma-eclamacao]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_claims | GET /post-purchase/v1/claims/search?status&offset&limit&sort | ❌ DIVERGENTE | **Só `status` é má prática (custoso, risco de rate-limit/400).** Oficial exige ≥1 filtro real; recomenda **`players.user_id={seller}` + `players.role=respondent`** como base. `offset`+`limit` sozinhos → 400. `limit` máx 100 (default 30), `offset` máx 9999. |
| get_my_open_claims | GET /post-purchase/v1/claims/search?status=opened | ❌ DIVERGENTE | Mesmo problema; adicionar `players.user_id`+`players.role=respondent`. `status` válidos: **opened, closed** (não "open"). |
| get_my_open_mediations | GET /post-purchase/v1/claims/search?status=opened&stage=dispute | ⚠️ PARCIAL | `stage=dispute` válido; ainda assim adicionar `players.user_id`+`role`. |
| get_returns | GET /post-purchase/v1/claims/search?claim_type=return | ❌ DIVERGENTE (grave) | **`claim_type` NÃO existe na API** → provável 400 silencioso em prod. Correto: `type=return` (+ `players.user_id`+`players.role=respondent`). Para os dados da devolução em si (envio de retorno, `refund_at`), usar **`GET /post-purchase/v2/claims/{id}/returns`**. [fundamentalista] |
| get_claim_detail | GET /post-purchase/v1/claims/{id} | ✅ OK | Há também `/{id}/detail`, `/{id}/actions-history`, `/{id}/status-history`, `/{id}/affects-reputation` (úteis p/ reputação). |
| send_claim_message | POST /post-purchase/v1/claims/{id}/messages body {message} | ❌ DIVERGENTE (reverif. 2026-06-08) | **Path errado: `/messages` é só GET.** POST oficial = `POST /post-purchase/v1/claims/{id}/actions/send-message` body `{receiver_role, message, attachments?}`. `receiver_role` ∈ {complainant, respondent, mediator} **obrigatório**, derivado de `available_actions`. Resposta 201. |
| get_messages | GET /messages/packs/{pack}/sellers/{seller}?tag=post_sale | ⚠️ PARCIAL | Falta `?tag=post_sale`. GET marca como lido — usar `mark_as_read=false` quando não quiser. `order_id` usa o mesmo path `/packs`. |
| get_messages (order) | GET /messages/orders/{id} | ⚠️ VERIFICAR | Doc prioriza `/packs/{pack}/sellers/{seller}`; usar order_id dentro do path de packs. |
| send_message | POST /messages/packs/{pack}/sellers/{seller}?tag=post_sale body {from{user_id}, to{user_id}, text} | ❌ DIVERGENTE/BUG | **Falta o campo `to.user_id` (obrigatório).** Desde **02/02/2026 (MLB)** `to.user_id` deve ser o **ID do Agente do Brasil = `3037675074`** (não o comprador). Sem `to` → 400. Limite 350 chars. Adicionar `?tag=post_sale`. |
| get_unread_messages_count | GET /messages/unread?role=seller&tag=post_sale | ⚠️ VERIFICAR | Plausível; confirmar contra doc de mensagens pendentes. |
| get_message_packs | GET /messages/search?seller_id&offset&limit | ⚠️ VERIFICAR | Endpoint de listagem de packs não aparece em `mensagens-post-venda`; confirmar (pode ser `/messages/packs` ou tópico de notificações). |

## BLOCO H — Usuários & Autenticação  [doc: autenticacao-e-autorizacao, consulta-de-usuarios]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| (auth/service) exchange/refresh | POST /oauth/token (authorization_code, refresh_token) | ✅ OK | `grant_type`, `client_id/secret`, `redirect_uri`, `code`/`refresh_token`. Scope `offline_access read write` (ARCH-010). x-www-form-urlencoded. |
| (auth/service) get_ml_user_info | GET /users/me | ✅ OK | Info da conta autenticada. |
| get_seller_reputation | GET /users/{seller_id} | ✅ OK | `seller_reputation.{level_id, power_seller_status, transactions, metrics{claims, delayed_handling_time, cancellations}}` (rates 0..1). |

## BLOCO I — Ads, Estoque Full, Mercado Pago  [doc: product-ads / publicidade — acesso restrito]

| Método | Endpoint | Status | Nota |
|---|---|---|---|
| get_advertiser_id | GET /advertising/advertisers?product_id=PADS (Api-Version:2) | 🔒 RESTRITO | Product Ads não público para todas as contas (ARCH-007). Fallback None. |
| get_product_ads_items / _campaigns | GET /advertising/advertisers/{id}/product_ads/items \| /campaigns (Api-Version:2) | 🔒 RESTRITO | Métricas ROAS/ACOS. Mantém fallback []. |
| get_item_ads | GET /advertising/product_ads?item_id&status=active | ⛔ DEPRECADO | Substituir por `get_product_ads_items`. **Remover.** |
| get_campaigns / get_campaign_metrics | GET /advertising/campaigns \| /campaigns/{id}/metrics | 🔒 RESTRITO | Implementados, **nunca chamados**. Avaliar remover ou ligar ao módulo ads. |
| get_full_stock | GET /user-products/{id}/stock/fulfillment | ⚠️ VERIFICAR | Confirmar path atual de estoque Full na doc de fulfillment. Fallback {available:0}. |
| get_full_inventory_summary | GET /users/{id}/fbm_stock/summary | 🔒 RESTRITO | Beta/não público; **nunca chamado**. |
| get_mp_balance | GET /users/{id}/mercadopago_account/balance | 🔒 RESTRITO | Saldo MP exige escopo OAuth diferente (ADIADO). **Nunca chamado.** |

---

## LISTA DE LIMPEZA (antigo/errado → novo/correto)

### ⛔ Aposentar (remover do client.py)
- `create_promotion` — usar `create_price_discount_promotion`.
- `update_promotion` — usar delete + create.
- `get_item_ads` — usar `get_product_ads_items`.

### ❌ Corrigir (divergência confirmada na doc oficial)
1. `delete_price_discount_promotion` → delete massivo `?app_version=v2` (sem user_id/promotion_type).
2. `get_claims` / `get_my_open_claims` / `get_my_open_mediations` → adicionar `players.user_id`+`players.role=respondent`; `status` ∈ {opened, closed}.
3. `get_returns` → `type=return` (não `claim_type`).
4. `send_message` → incluir `to.user_id` = Agente MLB `3037675074` + `?tag=post_sale` (bug ativo).
5. `get_messages` / `send_message` → `?tag=post_sale`.
6. `get_item_questions` → `item_id` (não `item`) + `api_version=4`.
7. `get_shipment` → header `x-format-new: true` + usar `lead_time.cost`.
8. `get_free_shipping_cost` → `verbose=true` e subtrair `coverage.discount`.
9. `get_listing_fees` → enviar `logistic_type`+`shipping_mode`(+`billable_weight`).

### ⚠️ Validar com curl/token real antes de produção
- `create_price_discount_promotion` (body via `desconto-individua`).
- `send_claim_message` (receiver/role).
- `get_message_packs`, `get_unread_messages_count`, `get_full_stock` (paths).

### ➕ Faltantes úteis (avaliar implementar)
- GET /orders/{id}/discounts (margem precisa).
- GET /items/{id}/prices (já implementado, ligar ao sync).
- GET /seller-promotions/users/{id} e /promotions/{id}/items.
- GET /post-purchase/v1/claims/{id}/affects-reputation (reputação).

> **Escopo desta auditoria:** apenas documentar (não alterar `client.py`). As correções acima estão
> detalhadas em `backend/docs/_audit/backlog_correcao_endpoints.md` para execução futura separada.

---

## REVISÃO MULTI-AGENTE (2026-06-03) — veredito do decisor

Revisão por 4 papéis (crítico=`qa`, criativo=`insights`, fundamentalista=`ml-api`, decisor=Opus). Ajustes incorporados:

1. **Cobertura:** 45 métodos públicos em `client.py` — todos com veredito (números de linha do backlog conferidos 1:1 pelo crítico). Notas de cobertura:
   - `get_my_unanswered_questions` (752): ✅ OK — hardcode `status=UNANSWERED` é válido.
   - `get_listing_visits` (810): ⚠️ LEGADO — redundante com `get_items_visits_bulk`; candidato a aposentar.
   - `get_item_orders` (302): ⚠️ nota de risco — `order.status="paid"` **hardcoded** → nunca pega cancelados/devolvidos (relevante p/ margem).
2. **`get_claims` status:** o default `"open"` (errado, deve ser `"opened"`) afeta **somente `get_claims`**; `get_my_open_claims`/`get_my_open_mediations` já usam `"opened"`. O problema de falta de `players.*` afeta os três. (correção do crítico ao backlog item 6).
3. **`update_item_price`:** contradição de severidade resolvida — **se** o PUT só-`price` retorna 400 desde 18/03/2026, o repricing direto via PUT está **quebrado (seria P0)**. Como o projeto usa promoções para repricing e não foi testado com curl, fica como ⚠️ **VERIFICAR com prioridade** (não P2 silencioso).
4. **`get_returns`/`send_message`/`get_shipment`:** reforçados inline acima com as nuances do fundamentalista (todas as 6 divergências P0/P1 **CONFIRMADAS** contra a doc oficial, nenhuma refutada).
5. **Docstrings:** métodos de promoção (linhas 421/466/494/524) ainda citam `docs/ml_api_reference.md` (aposentado) → adicionar atualização ao backlog P3.

**Oportunidades de produto** levantadas pelo criativo (quick wins, baixo esforço/alto impacto): margem líquida com `/orders/{id}/discounts`; linha do tempo de preço com `/items/{id}/prices` (já implementado); simulador de risco com `/claims/{id}/affects-reputation`; vigia de preço via webhook `items_prices`. Detalhe e priorização no relatório da auditoria (não implementadas nesta entrega).
