# Backlog — Correção dos endpoints ML no client.py (execução FUTURA)

> Gerado pela auditoria ARCH-014 (2026-06-03). **Esta lista NÃO foi executada** (escopo: só documentar).
> Fonte da verdade: `ml_endpoints_canonical.md`. Cada item cita o método, a linha em
> `backend/app/mercadolivre/client.py`, a divergência e a correção fundamentada na doc oficial.
> Ao executar: validar cada um com curl + token real (Regra Absoluta #2) antes de produção.

## P0 — Bug ativo (impacto direto em funcionalidade)

1. **`send_message` (linha 1114) — mensagem pós-venda não envia `to.user_id`.**
   - Divergência: body `{from{user_id}, text}` sem `to`. Oficial exige `to.user_id`; desde 02/02/2026 (MLB) deve ser o **Agente do Brasil `3037675074`**, não o comprador. Sem `to` → 400. Falta `?tag=post_sale`.
   - Correção: `POST /messages/packs/{pack}/sellers/{seller}?tag=post_sale` body `{from:{user_id:seller}, to:{user_id:"3037675074"}, text}`. Limite 350 chars. [doc: mensagens-post-venda]

## P1 — Divergências que envenenam dados (margem, atendimento)

2. **`get_shipment` (linha 983) — frete real não capturado.**
   - Correção: header `x-format-new: true`. `lead_time.cost` = estimado; **custo real faturado ao vendedor = `GET /shipments/{id}/costs` → `senders[].cost`** (inclui desconto — preferir este p/ margem). Resolve [[bug-orders-frete-comissao]]. [doc: gerenciamento-de-vendas + gerenciamento-de-envios] [revalidado: fundamentalista]
3. **`get_free_shipping_cost` (linha 690) — custo de frete grátis superestimado.**
   - Correção: `verbose=true` e subtrair `coverage.discount` de `coverage.all_country.list_cost`. Considerar `logistic_type`/`mode`. [doc: custos-de-envio]
4. **`get_listing_fees` (linha 645) — fixed_fee não bate com cobrado.**
   - Correção: enviar `logistic_type` + `shipping_mode` (+ `billable_weight`). Estrutura de leitura já correta. [doc: comissao-por-vender]
5. **`get_returns` (linha 1152) — param INEXISTENTE (bug pior que o descrito).**
   - `claim_type` **não existe** na API → provável 400 silencioso em produção. Correção: `type=return` + `players.user_id`+`players.role=respondent`. Para os dados da devolução (envio de retorno, `refund_at`, status), chamar adicionalmente **`GET /post-purchase/v2/claims/{id}/returns`** por claim. [doc: gerenciar-reclamacoes + gerenciar-devolucoes] [revalidado: fundamentalista]
6. **`get_claims`/`get_my_open_claims`/`get_my_open_mediations` (1043/756/760) — busca não acotada.**
   - Correção (TODOS): adicionar `players.user_id={seller}` + `players.role=respondent`; `limit`≤100; `offset`≤9999. `offset/limit` sozinhos → 400. [doc: gerenciar-reclamacoes]
   - Correção (SÓ `get_claims`, linha 1046): default `status="open"` → **`"opened"`** (os outros dois já usam "opened"). [crítico]
7. **`delete_price_discount_promotion` (linha 443) — assinatura do delete.**
   - Correção: delete massivo `DELETE /seller-promotions/items/{id}?app_version=v2` (sem user_id/promotion_type); tratar `{successful_ids, errors}`; DOD/LIGHTNING não entram no massivo. [doc: gerenciar-ofertas]

## P2 — Ajustes menores / robustez

8. **`get_item_questions` (linha 849)** → `item_id` (não `item`) + `api_version=4`. [doc: perguntas-e-respostas]
9. **`get_messages` (linha 1091)** → `?tag=post_sale`; usar `mark_as_read=false` quando não quiser marcar lido. [doc: mensagens-post-venda]
10. **`update_item_price` (linha 212)** → desde 18/03/2026 PUT só-`price` é 400. Planejar migração para `POST /items/{id}/prices/standard` quando ML liberar. [doc: api-de-precos]

## P3 — Aposentar (remover métodos mortos/deprecados)

11. **`create_promotion` (479)** e **`update_promotion` (510)** — já lançam NotImplementedError; remover.
12. **`get_item_ads` (623)** — usar `get_product_ads_items`; remover.
13. Métodos nunca chamados: `get_item_prices`, `get_campaigns`, `get_campaign_metrics`, `get_product_ads_campaigns`, `get_full_inventory_summary`, `get_mp_balance` — decidir ativar ou remover.
14. **Docstrings desatualizados:** métodos de promoção (linhas 421/466/494/524) citam `docs/ml_api_reference.md` (aposentado) → apontar para `ml_endpoints_canonical.md`. [crítico]
15. **`get_item_orders` (302)** — `order.status="paid"` hardcoded nunca pega cancelados/devolvidos; avaliar parametrizar. [crítico]

## Severidade a reclassificar (verificar com curl)

- **`update_item_price` (212)** — se PUT só-`price` retorna 400 desde 18/03/2026, o repricing direto está **quebrado (P0)**, não P2. Testar com curl + token real antes de classificar. Migração futura: `POST /items/{id}/prices/standard` (ainda não liberado). [crítico/decisor]

## ➕ Faltantes úteis (avaliar implementar)

- `GET /orders/{id}/discounts` (cupons/cashback → margem precisa).
- `GET /seller-promotions/users/{id}` + `/promotions/{id}/items` (módulo promoções).
- `GET /post-purchase/v1/claims/{id}/affects-reputation` (reputação).
- `GET /items/{id}/shipping_options?zip_code` (frete no checkout).

## Validar com curl antes de produção (não confirmados 100% por doc)

- `create_price_discount_promotion` (body via página `desconto-individua`).
- `send_claim_message` (receiver/role via `gerenciar-mensagem-de-uma-eclamacao`).
- `get_message_packs`, `get_unread_messages_count`, `get_full_stock` (paths exatos).
