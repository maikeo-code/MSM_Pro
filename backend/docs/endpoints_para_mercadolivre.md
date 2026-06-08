# MSM_Pro — Endpoints da API do Mercado Livre utilizados

> Documento preparado para avaliação técnica do time do Mercado Livre.
> Aplicação: **MSM_Pro** — painel de gestão de vendas para sellers (análise de preço,
> margem, concorrência, pós-venda e perguntas).
> Base URL utilizada: `https://api.mercadolibre.com`
> Data de referência: 2026-06-08

O sistema consome a API oficial em nome do próprio seller (OAuth 2.0, scopes
`offline_access read write`). Abaixo a lista completa de endpoints usados, agrupados por
área funcional, com a finalidade de cada um dentro do produto.

---

## 1. Autenticação e usuário

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| POST | `/oauth/token` | Troca de `authorization_code` por token e renovação via `refresh_token`. |
| GET | `/users/me` | Identificar a conta autenticada após o OAuth. |
| GET | `/users/{seller_id}` | Reputação do vendedor (nível, power seller status, métricas de reclamações, cancelamentos, tempo de manuseio). |

## 2. Itens e preço

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/items/{id}?include_attributes=all` | Dados do anúncio: título, SKU, status, frete grátis, tipo logístico, atributos. |
| GET | `/items/{id}/sale_price?context=channel_marketplace` | **Fonte primária do preço de venda exibido na vitrine.** |
| GET | `/items/{id}/prices` | Camadas de preço (standard/promotion) com janelas de vigência — usado para histórico/checagem de preço. |
| GET | `/items/{id}/description` | Texto da descrição, usado como contexto na resposta automática de perguntas. |
| PUT | `/items/{id}` | Atualização de preço do anúncio (repricing). **Ver dúvida nº 1.** |
| GET | `/users/{id}/items/search?status&offset&limit` | Listar os anúncios do seller (paginação por offset/limit). |

## 3. Visitas

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/items/{id}/visits/time_window?last&unit=day` | Visitas de um anúncio por janela de tempo. |
| GET | `/visits/items?ids&date_from&date_to` | Visitas em lote (chunks de 50 ids) para cálculo de conversão. |

## 4. Promoções do vendedor

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/seller-promotions/items/{id}?app_version=v2` | Listar todas as ofertas/promoções aplicáveis a um item. |
| POST | `/seller-promotions/items/{id}` | Criar desconto individual (PRICE_DISCOUNT). **Ver dúvida nº 2.** |
| DELETE | `/seller-promotions/items/{id}` | Remover promoção do item. **Ver dúvida nº 2.** |

## 5. Pedidos e envios

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/orders/search?seller&order.status&order.date_created.from/to&q&sort&offset&limit` | Listar e sincronizar pedidos do seller. |
| GET | `/orders/{id}` | Detalhe do pedido — usamos `order_items[].sale_fee` como **comissão de venda real**. |
| GET | `/shipments/{id}` | Dados do envio e custo de frete pago pelo vendedor. **Ver dúvida nº 3.** |
| GET | `/shipments/{id}/costs` | Custo real faturado do frete (`senders[].cost`). |
| GET | `/users/{id}/shipping_options/free?item_id&free_shipping=true&verbose` | Custo do frete grátis bancado pelo vendedor. **Ver dúvida nº 4.** |

## 6. Taxas e busca

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/sites/MLB/listing_prices?price&category_id&listing_type_id` | Cálculo da comissão/tarifa de venda por categoria e tipo de anúncio. **Ver dúvida nº 5.** |
| GET | `/sites/MLB/search?q&offset&limit` | Busca pública de itens (análise de concorrência). |

## 7. Perguntas e respostas

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/my/received_questions/search?status&offset&limit&sort_fields&sort_types` | Perguntas recebidas pelo seller. |
| GET | `/questions/search?item_id&status` | Perguntas de um item específico. **Ver dúvida nº 6.** |
| POST | `/answers` | Responder uma pergunta (body `{question_id, text}`). |

## 8. Pós-venda: reclamações, devoluções e mensagens

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/post-purchase/v1/claims/search` | Buscar reclamações/mediações do seller. **Ver dúvida nº 7.** |
| GET | `/post-purchase/v1/claims/{id}` | Detalhe de uma reclamação. |
| POST | `/post-purchase/v1/claims/{id}/messages` | Enviar mensagem dentro de uma reclamação. |
| GET | `/post-purchase/v2/claims/{id}/returns` | Dados da devolução (envio de retorno, reembolso). |
| GET | `/messages/packs/{pack}/sellers/{seller}?tag=post_sale` | Ler mensagens da conversa pós-venda. |
| POST | `/messages/packs/{pack}/sellers/{seller}?tag=post_sale` | Enviar mensagem ao comprador. **Ver dúvida nº 8.** |
| GET | `/messages/unread?role=seller&tag=post_sale` | Contagem de mensagens não lidas. |

## 9. Publicidade, estoque Full e Mercado Pago (acesso restrito)

| Verbo | Endpoint | Para que serve no MSM_Pro |
|---|---|---|
| GET | `/advertising/advertisers?product_id=PADS` | Identificar advertiser de Product Ads. **Ver dúvida nº 9.** |
| GET | `/advertising/advertisers/{id}/product_ads/items` | Métricas de anúncios patrocinados (ROAS/ACOS). |
| GET | `/advertising/advertisers/{id}/product_ads/campaigns` | Campanhas de Product Ads. |
| GET | `/user-products/{id}/stock/fulfillment` | Estoque no Fulfillment (Full). **Ver dúvida nº 10.** |
| GET | `/users/{id}/mercadopago_account/balance` | Saldo disponível no Mercado Pago. **Ver dúvida nº 10.** |

---

## Pontos onde observamos comportamento divergente (pedido de avaliação)

Estes são os casos em que o resultado retornado pela API não bate com o esperado, ou em que
temos dúvida sobre o contrato correto. São os pontos onde gostaríamos de orientação.

1. **Atualização de preço via `PUT /items/{id}`** — desde ~18/03/2026 observamos que o PUT
   contendo apenas `price` é rejeitado, e quando enviado junto com outros atributos o `price`
   parece ser ignorado. Qual é o endpoint oficial atual para alteração de preço
   (`POST /items/{id}/prices/standard`?) e ele já está liberado em produção?

2. **Promoções (`/seller-promotions/items/{id}`)** — gostaríamos de confirmar o body exato
   para criação de desconto individual (PRICE_DISCOUNT) e a assinatura correta do DELETE
   (com ou sem `user_id`/`promotion_type`; comportamento do delete massivo `?app_version=v2`).

3. **`GET /shipments/{id}`** — para obter o **frete real pago pelo vendedor** é necessário o
   header `x-format-new: true`? Sem ele, o custo retorna 0/None em alguns envios.

4. **`/users/{id}/shipping_options/free`** — com `verbose=false` não retorna
   `coverage.discount`. Confirmar que o valor efetivamente pago pelo vendedor é
   `list_cost - discount` e que `verbose=true` é o caminho recomendado.

5. **`/sites/MLB/listing_prices`** — desde ~02/03/2026 o `fixed_fee` parece depender de
   `logistic_type` + `shipping_mode` (+ `billable_weight`). Sem esses parâmetros a tarifa
   calculada diverge da efetivamente cobrada. Quais parâmetros são obrigatórios hoje?

6. **`/questions/search`** — o parâmetro de filtro por item é `item_id` ou `item`? E qual o
   `api_version` recomendado?

7. **`/post-purchase/v1/claims/search`** — filtrar apenas por `status` retorna erro/ineficiência.
   Confirmar os filtros obrigatórios (`players.user_id` + `players.role=respondent`?) e os
   valores válidos de `status` (`opened`/`closed`). Também: o filtro de devoluções é
   `type=return` (e não `claim_type=return`)?

8. **`POST /messages/packs/{pack}/sellers/{seller}`** — confirmar o preenchimento do campo
   `to.user_id`. Entendemos que desde ~02/02/2026 (MLB) ele deve ser o ID do Agente do Brasil
   (`3037675074`) em vez do ID do comprador. Está correto? É obrigatório `?tag=post_sale`?

9. **Product Ads (`/advertising/...`)** — quais são os requisitos para a conta ter acesso a
   estes endpoints? Hoje recebemos resposta vazia/sem acesso para a nossa conta.

10. **Estoque Full e saldo Mercado Pago** — confirmar os paths atuais de
    `/user-products/{id}/stock/fulfillment` e `/users/{id}/mercadopago_account/balance`, e
    quais scopes/permissões são necessários.

---

*Fonte interna: auditoria ARCH-014 (`backend/docs/ml_endpoints_canonical.md`), validada contra a
documentação oficial via MCP do Mercado Livre.*
