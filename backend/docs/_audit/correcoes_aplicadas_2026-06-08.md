# Correções de endpoints aplicadas no client.py — 2026-06-08

> Decisão autônoma com 3 papéis (crítico/fundamentalista/criativo) + chefe.
> Base: `reverificacao_mcp_2026-06-08.md` (contratos confirmados no MCP oficial).
> Regra do usuário respeitada: nenhum endpoint fora do que o MCP oficial confirma.

## ✅ APLICADO E TESTADO (bloco seguro — pós-venda/perguntas/promoções)

Não afetam cálculo financeiro central; corrigem chamadas hoje quebradas (retornavam vazio/400).

| Método | Correção aplicada | Arquivo |
|---|---|---|
| `send_message` | `to.user_id` = Agente do site (MLB `3037675074`) + `?tag=post_sale` + limite 350 chars. Constante `ML_MESSAGING_AGENT_IDS`. | client.py |
| `send_claim_message` | Path → `/post-purchase/v1/claims/{id}/actions/send-message`; body `{receiver_role, message, attachments?}`; default `receiver_role=complainant`. | client.py + atendimento/service.py |
| `get_returns` | `type=return` (era `claim_type` inexistente) + `players.user_id`+`players.role=respondent`. | client.py |
| `get_claims` | `players.user_id`+`players.role=respondent`; status normalizado p/ `opened`/`closed`; limit≤100, offset≤9999. | client.py |
| `get_my_open_claims` / `get_my_open_mediations` | Agora recebem `seller_id` e enviam `players.*`. | client.py + vendas/service_dashboard_cards.py |
| `get_item_questions` | `item_id` (era `item`) + `status=UNANSWERED` + `api_version=4`. | client.py |
| `get_messages` | `?tag=post_sale` nas consultas pós-venda. | client.py |
| `create_price_discount_promotion` | Removido `user_id` da query (inexistente na doc); mantém `app_version=v2`. | client.py |
| `delete_price_discount_promotion` | Removido `user_id`; mantido `promotion_type`+`app_version=v2` (ambos válidos). | client.py |

Callers ajustados: `atendimento/service.py` (statuses opened-only; filtro de devolução `type` em vez de `claim_type`), `atendimento/service_claims.py` (statuses `opened`/`closed`), `vendas/service_dashboard_cards.py` (passa `ml_user_id`).
Teste atualizado: `test_ml_client_methods.py::TestSendClaimMessage` (novo path/body). Suíte afetada: 90 passed. Suíte total: 1843 passed (7 falhas pré-existentes em `test_vendas_sync_mock.py` — financeiro/health, fora deste escopo).

## ⏸️ NÃO APLICADO — bloco FINANCEIRO (exige validação com token real antes de produção)

Tocam margem/comissão/frete. Regra Absoluta #2 do projeto exige `curl`+token real antes de produção; alterar às cegas pode inflar/deflacionar margem silenciosamente. Contratos já confirmados no MCP — falta apenas a validação prática.

| Método | Correção a aplicar | Risco |
|---|---|---|
| `get_shipment` | Header `x-format-new: true`; migrar leitura do frete para `GET /shipments/{id}/costs → senders[].cost`. Hoje `extract_seller_shipping_cost` lê `cost_components.sender_cost` (formato antigo) — migração quebra ~3 suítes de teste de frete e muda valores. | ALTO (frete/margem) |
| `get_free_shipping_cost` | `verbose=true`; subtrair `coverage.discount` do `list_cost`. Muda o valor do frete grátis. | MÉDIO |
| `get_listing_fees` | Enviar `logistic_type`+`shipping_mode` (desde 02/03/2026 MLB). Muda a comissão calculada. | MÉDIO |
| `update_item_price` | PUT só-`price` rejeitado (400) desde 18/03/2026; substituto `POST /items/{id}/prices/standard` ainda NÃO liberado pelo ML. Sem ação possível hoje. | BLOQUEADO no ML |

**Próximo passo do bloco financeiro:** validar cada um com `curl` + token real de uma conta ativa, ajustar `extract_seller_shipping_cost` para o formato novo, atualizar testes de frete, e só então aplicar + deploy.
