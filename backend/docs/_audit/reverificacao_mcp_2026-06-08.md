# Reverificação de endpoints ML via MCP oficial — 2026-06-08

> **Fonte única:** servidor MCP oficial do Mercado Livre (`mcp.mercadolibre.com`), docs `pt_br` / `siteId=MLB`.
> Nenhum endpoint foi aceito de fonte não-oficial. Cada veredito cita a página oficial consultada.
> Escopo: reverificar os itens que estavam **🔴 em dúvida** e **🟡 provavelmente certos** na auditoria ARCH-014.
> Método: 3 papéis de análise sobre a evidência oficial — **crítico** (`qa`), **fundamentalista** (`ml-api`), **criativo** (`insights`); decisor: Opus.
> Continuação de [[ml_endpoints_canonical]] e ARCH-014.

## Páginas oficiais consultadas nesta rodada

| Página (path MCP) | Cobre |
|---|---|
| `api-de-precos` | sale_price, /prices, PUT /items (preço), POST /items/{id}/prices/standard |
| `comissao-por-vender` | listing_prices (fixed_fee, logistic_type/shipping_mode) |
| `custos-de-envio` | shipping_options/free (verbose), items/{id}/shipping_options |
| `gerenciamento-de-envios` | shipments/{id} (x-format-new), /costs, /lead_time |
| `mensagens-post-venda` | messages packs/sellers (to.user_id, agente, tag) |
| `gerenciar-reclamacoes` | claims/search (players.*, status), claims/{id} e derivados |
| `gerenciar-devolucoes` | v2/claims/{id}/returns, return-review |
| `gerenciar-mensagem-de-uma-eclamacao` | mensagens DENTRO de uma reclamação (actions/send-message) |
| `desconto-individua` | criar/excluir PRICE_DISCOUNT |
| `gerenciar-ofertas` | seller-promotions (consulta, delete massivo, users) |
| `perguntas-e-respostas` | questions/search (item vs item_id) |

---

## VEREDITO POR ENDPOINT

Legenda: ✅ CERTO (usar como está) · 🔧 CORRIGIR (endpoint oficial, mas falta param/header/body) · ❌ DIVERGENTE (path/param não existe na API oficial).

### Grupo A — confirmados CERTOS após reverificação (estavam 🟡)

| Método (client.py) | Endpoint oficial confirmado | Ajuste necessário | Página |
|---|---|---|---|
| `get_shipment` | `GET /shipments/{id}` | 🔧 **Enviar header `x-format-new: true`** (a doc afirma explicitamente que é necessário para o JSON de shipments). Frete real do vendedor vem de `GET /shipments/{id}/costs → senders[].cost`. | gerenciamento-de-envios |
| `get_free_shipping_cost` | `GET /users/{id}/shipping_options/free` | 🔧 Enviar `verbose=true` **e** `free_shipping=true`; valor pago pelo vendedor = `coverage.all_country.list_cost` menos `coverage.discount` (o array `discount` só vem se houver desconto). | custos-de-envio |
| `get_listing_fees` | `GET /sites/MLB/listing_prices` | 🔧 Desde **02/03/2026 (MLB)** enviar `logistic_type` + `shipping_mode`. Sem eles o `fixed_fee` não bate com o cobrado. `billable_weight` obrigatório só p/ Argentina. | comissao-por-vender |
| `get_messages` | `GET /messages/packs/{pack}/sellers/{seller}` | 🔧 Adicionar `?tag=post_sale`. GET marca como lido; usar `mark_as_read=false` para não marcar. order_id usa o mesmo path `/packs`. | mensagens-post-venda |

**Veredito dos papéis (Grupo A):** crítico, fundamentalista e criativo concordam — os 4 são endpoints **oficiais e corretos**, divergência apenas de parâmetro/header. Sem ressalvas.

### Grupo B — confirmados DIVERGENTES / a corrigir (estavam 🔴)

#### B1. `send_message` (mensagem pós-venda ao comprador) — ❌ BUG confirmado
- Oficial: `POST /messages/packs/{pack}/sellers/{seller}?tag=post_sale`, body `{from:{user_id}, to:{user_id}, text}`.
- **`to.user_id` é obrigatório** — a doc lista o erro literal `400 "The field 'to.user_id' is required"`.
- Para **MLB**, desde **02/02/2026**, `to.user_id` deve ser o **ID do Agente do Brasil = `3037675074`** (não o comprador). Tabela oficial de agentes confirmada.
- Limite 350 caracteres; 1 mensagem por vez; o vendedor não pode iniciar conversa.
- **Crítico:** nosso `send_message(pack_id, text, seller_id)` não monta `to` → 400 garantido. **Fundamentalista:** confirmado contra a tabela de agentes e a lista de erros oficiais. **Criativo:** o ID do agente deve ser configurável por site (não hardcode), pensando em multi-país futuro.
- **Veredito: CORRIGIR (P0).** Página: mensagens-post-venda.

#### B2. `send_claim_message` (mensagem DENTRO de uma reclamação) — ❌ DIVERGENTE (achado novo do fundamentalista)
- Nosso código: `POST /post-purchase/v1/claims/{id}/messages` body `{message}`.
- **Oficial:** `/post-purchase/v1/claims/{id}/messages` é **somente GET** (listar). A criação de mensagem é:
  `POST /post-purchase/v1/claims/{CLAIM_ID}/actions/send-message`, body `{receiver_role, message, attachments?}`.
- `receiver_role` ∈ {`complainant`, `respondent`, `mediator`} é **obrigatório** e depende da etapa/`available_actions` (`send_message_to_complainant` / `_mediator`).
- **Crítico:** este estava como ✅/⚠️ antes — era falso positivo. **Fundamentalista:** path e body ambos errados; sem `receiver_role` não há como rotear. **Criativo:** dá para derivar `receiver_role` automaticamente lendo `available_actions` do `claims/{id}`.
- **Veredito: CORRIGIR (P1) — path `/actions/send-message` + `receiver_role`.** Página: gerenciar-mensagem-de-uma-eclamacao.

#### B3. `get_returns` — ❌ DIVERGENTE confirmado
- Nosso código: `claims/search?claim_type=return`. **`claim_type` não existe.**
- Oficial: o filtro é `type=return` em `claims/search` (+ `players.user_id`+`players.role=respondent`). Os **dados da devolução** vêm de `GET /post-purchase/v2/claims/{CLAIM_ID}/returns` (campos `refund_at`, `status_money`, `shipments[]`, `subtype`). Identificar via `related_entities:["return"]` no `claims/{id}`.
- **Veredito: CORRIGIR (P0).** Páginas: gerenciar-reclamacoes + gerenciar-devolucoes.

#### B4. `get_claims` / `get_my_open_claims` / `get_my_open_mediations` — ❌ DIVERGENTE confirmado
- Oficial: `claims/search` exige **≥1 filtro real**. Só `offset/limit` → `400 invalid_query`. Só `status=opened` é válido porém "altamente ineficiente / risco de rate-limit".
- Recomendação oficial: `players.user_id={seller}` + `players.role=respondent`.
- `status` válidos = **`opened` / `closed`** (o default `"open"` do nosso `get_claims` é inválido). `limit` máx 100, `offset` máx 9999.
- **Veredito: CORRIGIR (P1).** Página: gerenciar-reclamacoes.

#### B5. `update_item_price` — ❌ QUEBRADO confirmado
- Oficial (`api-de-precos`): desde **18/03/2026** o `PUT /items/{id}` só com `price` é **rejeitado (400)**; com outros atributos, o `price` é **ignorado** (200 + warning).
- O substituto `POST /items/{id}/prices/standard` está documentado mas **"ainda não disponível"**.
- **Crítico:** repricing direto via PUT está quebrado hoje. **Fundamentalista:** confirmado. **Criativo:** enquanto `prices/standard` não abre, repricing real só via promoções (PRICE_DISCOUNT).
- **Veredito: CORRIGIR/MONITORAR (P0 funcional).** Página: api-de-precos.

### Grupo C — promoções: refinado pelo fundamentalista (param `user_id` indevido)

#### C1. `create_price_discount_promotion` — 🔧 CORRIGIR (remover `user_id`)
- Oficial (`desconto-individua`): `POST /seller-promotions/items/{ITEM_ID}?app_version=v2`, body `{deal_price, top_deal_price?, start_date, finish_date, promotion_type:"PRICE_DISCOUNT"}`.
- **O POST oficial NÃO leva `user_id` na query.** Nosso código envia `?user_id={seller}` → param inexistente na doc. Remover.
- Regras: desconto entre 5% e 80%; reputação verde; item ativo/novo; prazo máx 14 dias (desde 24/03/2025).
- **Veredito: CORRIGIR (P2) — body está certo, tirar `user_id`.**

#### C2. `delete_price_discount_promotion` — 🔧 CORRIGIR (remover `user_id`, manter `promotion_type`)
- Oficial (`desconto-individua`): delete individual = `DELETE /seller-promotions/items/{ITEM_ID}?promotion_type=PRICE_DISCOUNT&app_version=v2`. **`promotion_type` É válido** (correção ao backlog anterior, que sugeria removê-lo).
- Delete massivo (`gerenciar-ofertas`) = `DELETE /seller-promotions/items/{ITEM_ID}?app_version=v2` (sem `promotion_type`) → remove todas exceto DOD/LIGHTNING; resposta `{successful_ids, errors}`.
- **O problema do nosso código é o `user_id` extra (não existe na doc), não o `promotion_type`.** Remover `user_id`.
- **Veredito: CORRIGIR (P2) — tirar `user_id`; `promotion_type` permanece.**

### Grupo D — ambíguo na própria doc oficial

#### D1. `get_item_questions` — 🔧 usar `item_id` + `api_version=4`
- Oficial (`perguntas-e-respostas`): a **tabela** mostra `/questions/search?item=$ITEM_ID`, mas o **exemplo curl oficial** usa `/questions/search?item_id=MLA608007087`. A própria doc é ambígua.
- Decisão: seguir o **exemplo executável oficial** → `item_id`. Recomenda `api_version=4`. Padronizar status maiúsculo (`UNANSWERED`).
- **Veredito: CORRIGIR (P2) — `item_id` + `api_version=4`.** (Validar com curl/token real qual filtro o backend aceita, já que a doc lista os dois.)

---

## Resumo executivo da reverificação

| Item | Antes (ARCH-014) | Reverificação MCP 2026-06-08 |
|---|---|---|
| `get_shipment` (x-format-new) | 🟡 | ✅ oficial — só falta header |
| `get_free_shipping_cost` (verbose) | 🟡 | ✅ oficial — só falta param |
| `get_listing_fees` (logistic/shipping) | 🟡 | ✅ oficial — só falta param |
| `get_messages` (tag) | 🟡 | ✅ oficial — só falta tag |
| `get_item_questions` (item_id) | 🟡 | 🔧 doc ambígua → usar `item_id` |
| `create_price_discount_promotion` | 🟡 | 🔧 remover `user_id` (achado novo) |
| `send_message` (to.user_id agente) | 🔴 | ❌ confirmado P0 |
| `get_returns` (type=return) | 🔴 | ❌ confirmado P0 |
| `get_claims` family (players.*) | 🔴 | ❌ confirmado P1 |
| `update_item_price` (PUT 400) | 🔴 | ❌ confirmado P0 funcional |
| `delete_price_discount_promotion` | 🔴 | 🔧 refinado: tirar `user_id`, manter `promotion_type` |
| **`send_claim_message`** | ✅/⚠️ (falso positivo) | ❌ **NOVA divergência** — path `/actions/send-message` + `receiver_role` |

**Principais achados desta rodada (não detectados antes):**
1. `send_claim_message` usa path inexistente para POST (`/messages` é só GET) e falta `receiver_role`.
2. `create_price_discount_promotion` e `delete_price_discount_promotion` enviam `user_id` que **não existe** na doc oficial; o `promotion_type` do delete, ao contrário, **é válido**.

**Regra reforçada (pedido do usuário):** nenhum endpoint deve ser usado sem confirmação no MCP oficial do Mercado Livre. As correções acima vão para `backlog_correcao_endpoints.md`; `client.py` não foi alterado nesta rodada (escopo: reverificar e registrar).
