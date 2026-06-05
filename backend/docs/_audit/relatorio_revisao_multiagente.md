# Relatório — Revisão Multi-Agente da Auditoria de Endpoints ML (2026-06-03)

> Auditoria ARCH-014. 4 papéis: **crítico** (`qa`), **criativo** (`insights`), **fundamentalista** (`ml-api`),
> **decisor** (Opus). Escopo: revisar/testar os entregáveis (não alterar `client.py`).

## 1. Fundamentalista — revalidação independente via MCP oficial

Os 6 itens P0/P1 foram **CONFIRMADOS** (nenhum refutado), com nuances:

| Item | Veredito | Nuance |
|---|---|---|
| send_message `to.user_id`=Agente MLB `3037675074` + `?tag=post_sale` | CONFIRMADO | Rollout progressivo (começa por Full); curl da doc mostra exatamente esse `to`. |
| Frete: `x-format-new: true` + `lead_time.cost` | CONFIRMADO | **`GET /shipments/{id}/costs` → `senders[].cost`** é o custo real faturado (melhor que `lead_time.cost`). |
| Devoluções `type=return` (não `claim_type`) | CONFIRMADO (pior) | `claim_type` não existe → 400. Dados da devolução via `GET /post-purchase/v2/claims/{id}/returns`. |
| claims/search `players.user_id`+`role=respondent`; `status`∈{opened,closed} | CONFIRMADO | `offset/limit` sozinhos → 400; `limit`≤100, `offset`≤9999. |
| DELETE promoção massivo `?app_version=v2` | CONFIRMADO | DOD/LIGHTNING não entram no massivo; resposta sempre 200 com `errors[]`. |
| listing_prices `logistic_type`+`shipping_mode`(+`billable_weight`) | CONFIRMADO | Brasil desde 02/03/2026; `billable_weight` obrigatório só na Argentina. |

## 2. Crítico — lacunas e correções (incorporadas)

- Números de linha do backlog: **100% corretos** (verificados método a método).
- Cobertura: 45 métodos públicos; deram veredito próprio a `get_my_unanswered_questions`, `get_listing_visits` (legado), `get_item_orders` (status=paid hardcoded).
- `get_claims` default "open"→"opened" afeta **só** `get_claims` (separado do problema `players.*`).
- `update_item_price`: contradição de severidade — se PUT só-`price` é 400, é **P0** (não P2). → marcado VERIFICAR.
- Docstrings de promoção citam `ml_api_reference.md` (aposentado) → backlog P3 item 14.

## 3. Criativo — oportunidades de produto (NÃO implementadas)

Quick wins (alto impacto / baixo esforço):

| # | Feature | Endpoint | Faixa |
|---|---------|----------|-------|
| 1 | Margem líquida verdadeira (cupom/cashback) | `GET /orders/{id}/discounts` (`amounts.seller`) | Quick win |
| 2 | Linha do tempo de preço/promoção | `GET /items/{id}/prices` (já implementado, não chamado) | Quick win |
| 3 | Custo real de frete grátis + comissão fiel | fix `get_free_shipping_cost`/`get_listing_fees` | Quick win |
| 4 | Simulador de risco com claims reais | `GET /post-purchase/v1/claims/{id}/affects-reputation` | Aposta forte |
| 5 | Vigia de preço em tempo real | webhook `items_prices` | Aposta forte |
| 6 | Inbox pós-venda proativo | webhook `claims`/`candidate` + `user_notifications` | Aposta forte |
| 7 | Central de campanhas e convites | `GET /seller-promotions/users/{id}` + `/promotions/{id}/items` | Módulo novo |
| 8 | Calculadora de frete por região | `GET /items/{id}/shipping_options?zip_code` | Diferencial |
| 9 | Timeline de disputa + SLA | `/claims/{id}/actions-history` + `/status-history` | Pós-venda |

**Dependência:** features de pós-venda (#4/#6/#9) exigem antes corrigir `get_claims` (P1.6).

## 4. Decisor — sequência recomendada (quando for executar o backlog)

1. **P0** `send_message` (validar Agente `3037675074` com curl primeiro).
2. **Cluster margem precisa** (frete `/costs`, free_shipping `verbose`, listing_fees `logistic_type`, `/orders/{id}/discounts`) — resolve [[bug-orders-frete-comissao]] e destrava features #1/#3.
3. **Cluster pós-venda** (claims `players.*`, returns `type`/v2, send_message `tag`) — destrava #4/#6/#9.
4. **Limpeza** (remover deprecados, atualizar docstrings).
5. Reavaliar `update_item_price` (curl) — pode ser P0.
