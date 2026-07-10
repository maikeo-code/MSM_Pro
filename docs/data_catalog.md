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

### E20 — Dashboard (`pages/Dashboard/index.tsx`) — preenchido 2026-07-10

5 fontes de dados: `getKpiSummary`, `getFunnel`, `getHeatmap`, `list` (tabela), `getDashboardExtraCards`.

**KPI cards (topo) — todos de `kpi.hoje` via `GET /listings/kpi/summary`:**

| Campo exibido | Fonte no payload | Serviço:função | Tabela.coluna | Endpoint ML | Check paridade | Status |
|---------------|------------------|----------------|---------------|-------------|----------------|--------|
| Pedidos Válidos | `kpi.hoje.pedidos` | service_kpi.get_kpi_by_period → metrics.aggregate_metrics | Order (count, status ∉ NON_SALE) | `/orders/search` | `pedidos_dia` | ✓ (⚠️ sobreconta +1 → Fase 4/E52) |
| Unidades Vendidas | `kpi.hoje.vendas` | idem → `_kpi_single_day` | Order.quantity (Σ) | `/orders/search` | `unidades_dia` | ✓ (⚠️ +1 → Fase 4) |
| Receita Total | `kpi.hoje.receita_total` | idem | Order.total_amount (Σ) | `/orders/search` | `receita_dia` | ✓ (⚠️ +R$ → Fase 4) |
| Preço Médio | `kpi.hoje.preco_medio` | idem (derivado receita/unidades) | derivado | — | (sem check direto) | ✗ tem dono, sem check |
| Conversão | `kpi.hoje.conversao` | idem (vendas/visitas) | Order + ListingSnapshot.visits | `/orders/search` + `/items/{id}/visits/time_window` | via visitas | ✗ derivado; visitas têm timing (Fase 3/E43) |

**Tabela KPI multiperíodo (Hoje/Ontem/Anteontem/7d/30d)** — mesmo `/kpi/summary`; campos `vendas`/`visitas`/`receita` (ou `*_media_dia` no modo média) + `conversao`. Mesma origem/dono acima. ⚠️ Σ diária vs 7d/30d ainda pode divergir até E52 (max() não-aditivo — bug-kpi-inconsistencia-multitela).

**Funil de Conversão** — `GET /listings/analytics/funnel` → `service_analytics.py:34`. 🔴 usa **dia UTC, sem filtro de status** → diverge do summary. Migração planejada **Fase 6/E69**.

**Heatmap** — `GET /listings/analytics/heatmap` → `service_analytics.py:376`. ⚠️ filtra `payment_status=="approved"` (exclui refunded que deveria contar) → **Fase 6/E71**.

**Tabela de anúncios** — `GET /listings` → `service_kpi.list_listings`. Colunas detalhadas em E21/E94.

**Cards ML extras** — `GET /listings/dashboard/extra-cards` → `service_dashboard_cards.py`:

| Card | Método cliente ML | Endpoint ML | Check | Status |
|------|-------------------|-------------|-------|--------|
| Reputação (nível, vendas 60d) | get_seller_reputation | `/users/{id}` | `reputacao_vendas_60d`, `reputacao_claims` | ✓ (E14 corrigiu — 4/4 PASS) |
| Perguntas sem resposta | get_my_unanswered_questions | `/my/received_questions/search` | — | ✗ |
| Reclamações abertas | get_my_open_claims | `/post-purchase/v1/claims/search` | — | ✗ |
| Mediações abertas | get_my_open_mediations | `/post-purchase/v1/claims/search` | — | ✗ |
| Mensagens não lidas | get_unread_messages_count | `/messages/unread` | — | ✗ |
| Saldo Mercado Pago | get_mp_balance | `/users/{id}/mercadopago_account/balance` | — | ✗ (leitura de saldo — EC7) |
| Estoque FULL | get_full_inventory_summary | `/users/{id}/fbm_stock/summary` | — | ✗ |
| Sparkline vendas 7d/conta | `extraCards.accounts[].vendas_7d` | service_dashboard_cards:224 | ✓ constante (net_amount) | ✗ |

---

### E21 — Anúncios lista (`pages/Anuncios/index.tsx`) — preenchido 2026-07-10

Fonte única: `GET /listings` → `service_kpi.list_listings`. Colunas da tabela:

| Coluna exibida | Campo payload | Como é calculado (service_kpi) | Tabela.coluna | Endpoint ML | Check | Status |
|----------------|---------------|-------------------------------|---------------|-------------|-------|--------|
| Preço | `price` | Listing (sync) | Listing.price | `/items/{id}/sale_price` | `preco[mlb]` | ✓ 10/10 PASS |
| Preço original | `original_price` | Listing | Listing.original_price | `/items/{id}` | — | ✗ |
| **Você recebe** | `voce_recebe` | real: `Order.net_amount` médio/unid; fallback: preço − sale_fee_pct·preço − avg_shipping | Order.net_amount / Listing.sale_fee_pct+avg_shipping_cost | `/orders/search` + `/sites/MLB/listing_prices` | via comissão | ✗ crítico histórico (validar E94/EA16) |
| Comissão | `sale_fee_amount`/`sale_fee_pct` | Listing (sync fees) | Listing.sale_fee_amount/pct | `/sites/MLB/listing_prices` (+logistic_type+me2) | `comissao[mlb]` | ✓ 10/10 PASS |
| Frete | `avg_shipping_cost` | Listing (sync) | Listing.avg_shipping_cost | `/users/{id}/shipping_options/free` · `/shipments/{id}/costs`→senders.cost | — | ✗ sem check direto |
| Estoque | `last_snapshot.stock` | último snapshot | ListingSnapshot.stock | `/items/{id}` (Σ variations, E9) | `estoque[mlb]` | ✓ 9/10 (E9) |
| Dias p/ zerar | `dias_para_zerar` | stock / vendas_média_7snap | derivado | — | — | ✗ derivado |
| Preço médio/venda | `avg_price_per_sale` | snap_revenue / orders_count | derivado | — | — | ✗ derivado |
| Participação % | `participacao_pct` | rev_listing / Σrev_todos | derivado | — | — | ✗ derivado |
| Quality score | `quality_score` | Listing | Listing.quality_score | `/items/{id}` | — | ✗ |
| Var. vendas/receita | `vendas_variacao`/`receita_variacao` | metrics | Order | `/orders/search` | — | ✗ |

⚠️ **`voce_recebe`** é o ponto de maior risco histórico (preço de tabela vs "você recebe" líquido). Trava definitiva em **E94** (characterization) e **EA16** (export == tela).

---

### E22 — Anúncio detalhe (`pages/Anuncios/AnuncioDetalhe.tsx` + 5 componentes) — preenchido 2026-07-10

Tela mais densa: 6 fontes de dados + subcomponentes. mlbId da rota `/anuncios/:mlbId`.

| Bloco / componente | Service call | Endpoint backend | Serviço:função | Tabela / ML | Check | Status |
|--------------------|--------------|------------------|----------------|-------------|-------|--------|
| KPIs + gráfico (vendas/visitas/preço) | `getAnalysis(mlb, days)` | `GET /listings/{mlb}/analysis` (router:875) | service `get_listing_analysis` | ListingSnapshot (série) + Order | via visitas/vendas | ✗ visitas timing (E43) |
| `MetricasAvancadas` | (usa getAnalysis) | idem | idem | derivado | — | ✗ derivado |
| `SearchPosition` | (dado interno da rota) | `GET /listings/{mlb}/search-position` (router:832) | service | `/sites/MLB/search` | — | ✗ EA13 valida ML |
| `PriceBandsTable` | (via analysis/margem) | — | service_price | Listing/Order | — | ✗ |
| `PriceHistory` | `getPriceHistory` | `GET /listings/{mlb}/price-history` (router:1002) | service | ListingSnapshot.price série | — | ✗ |
| `CalculadoraMargem` | `getMargem(mlb, preco)` | `GET /listings/{mlb}/margem` (router:896) | service_price `calcular_margem` | Listing.sale_fee + custo (Produto) + frete | — | ✗ crítico: fórmula margem (trava E101) |
| Saúde do anúncio | `getListingHealth(mlb)` | `GET /listings/{mlb}/health` (router:907) | service | Listing/Snapshot | — | 🟡 sem tela clara no plano — TEM (é este bloco) |
| Vínculo SKU/custo | `productsService.list` + `linkSku` | `GET/POST /produtos` | produtos/service | Produto.custo | — | ✗ (alimenta margem) |
| Concorrente + histórico | `competitorsService.listByListing`/`getHistory` | `GET /concorrencia/listing/{id}`, `/{id}/history` | concorrencia/service | Competitor snapshots | — | ✗ (E31/E102) |

⚠️ **Achado E22:** `GET /{mlb}/health` estava marcado "🟡 sem tela clara" no inventário da Fase 2B —
**confirmado que TEM tela** (bloco Saúde do anúncio no detalhe). Atualizar EA3.
⚠️ **CalculadoraMargem** = fórmula preço−custo−taxa−frete; ponto de risco, trava em **E101**.

---

### E23 — Análise de Anúncios (`pages/AnaliseAnuncios/index.tsx`) — preenchido 2026-07-10

Fonte única: `analysisService.getListingsAnalysis` → `GET /analise/listings` → `analise/service.py:get_analysis_listings`.

| Campo | Cálculo | Tabela.coluna | Endpoint ML | Status |
|-------|---------|---------------|-------------|--------|
| Vendas (7/15/30d) | agregação por listing na janela | Order (via CTEs) | `/orders/search` | 🔴 usa `=="approved"` (exclui refunded) → **Fase 6/E72** |
| Visitas (7/15/30d) | soma de snapshots | ListingSnapshot.visits | `/items/{id}/visits/time_window` | 🔴 **sem dedup por snapshot_day** (infla com legado) → **Fase 6/E79** |
| Conversão | vendas/visitas | derivado | — | ✗ herda os 2 problemas acima |
| ROAS/ACOS (se exibido) | ads | AdsSnapshot | Product Ads v2 | ✗ (E32) |

⚠️ **Achado E23:** esta tela é um dos alvos centrais da Fase 6 (E72 filtro de status + E79 breakdown por
listing com dedup). Números NÃO batem com a tela Vendas hoje por causa da falta de dedup de visitas.

### E24 — Vendas MT (`pages/VendasMT/index.tsx` + `types.ts`) — preenchido 2026-07-10

Fonte: `listVendasMT` → `GET /vendas-mt/` → `vendas_mt/service.py` (cadeia Mercado Turbo sobre a API ML).
Decomposição financeira por venda (type `Venda`):

| Campo | Significado | Origem ML | Status |
|-------|-------------|-----------|--------|
| `total`/`produtos` | valor dos produtos (base imposto/margem) | order_items | ✓ paridade fina 20/20 (06/2026) — trava E95 |
| `pago` | paid_amount (o que o comprador pagou) | `/orders/{id}` paid_amount | ✓ |
| `tarifaML` | comissão ML | order_items[].sale_fee | ✓ |
| `frete` | custo vendedor + frete comprador | `/shipments/{id}/costs` senders.cost | ✓ (cheat-sheet) |
| `lucroBruto`/`receitaLiquida` | pago − frete − tarifa | derivado | ✓ |
| `custoProduto` | custo cadastrado (SKU) | Produto.custo | ✗ depende de cadastro |
| `imposto`/`impostoPct` | Simples (8,5%) | tax-config | ✓ |
| `margem`/`lucro` | lucroBruto − custo − imposto | derivado | ✗ (E101) |
| `entrega` (Entrega) | dados logísticos | `/shipments/{id}` | ✗ |

⚠️ VendasMT já atingiu **paridade fina 20/20 em 06/2026** — a Fase 8 (E95) TRAVA isso com characterization.

### E25 — Pedidos (`pages/Pedidos/index.tsx`) — preenchido 2026-07-10

Fonte: `listOrders` → `GET /listings/orders/` → `service` (query direto na tabela Order). 1 linha por pedido:

| Coluna | Campo | Tabela.coluna | Endpoint ML | Status |
|--------|-------|---------------|-------------|--------|
| Data | `order_date` | Order.order_date | `/orders/search` | ✓ |
| Anúncio/título | `mlb_id`/`item_title` | Order.mlb_id/item_title | `/orders/search` | ✓ |
| Comprador | `buyer_nickname` | Order.buyer_nickname | `/orders/search` | ✓ |
| Qtd | `quantity` | Order.quantity | `/orders/search` | ✓ |
| Preço unit. | `unit_price` | Order.unit_price | `/orders/search` | ✓ |
| Total | `total_amount` | Order.total_amount | `/orders/search` | ✓ |
| Tarifa | `sale_fee` | Order.sale_fee | order_items[].sale_fee | ✓ |
| Frete | `shipping_cost` | Order.shipping_cost | `/shipments/{id}/costs` senders.cost | ✓ |
| Líquido | `net_amount` | Order.net_amount | derivado (total−fee−frete) | ✓ trava E96 |
| Status pgto/envio | `payment_status`/`shipping_status` | Order.* | `/orders/search` + `/shipments/{id}` | ✓ |

✅ **Pedidos é a tela mais "sã"**: lê Order direto, é a própria fonte da verdade que a Fase 4 vai
tornar canônica. Trava em **E96**. É o espelho contra o qual as telas agregadas devem bater.

---

### E26 — Financeiro (`pages/Financeiro/index.tsx`) — preenchido 2026-07-10

4 fontes no frontend: `getResumo`, `getTimeline`, `getDetalhado`, `getCashflow` (+ `/dre`, `/rentabilidade-sku`, `/tax-config` no backend). **Tela crítica — alvo central da Fase 6 (E74-E78).**

**Resumo (`GET /financeiro/resumo` → `financeiro/service.py:110`):**

| Campo | Fórmula (comentário do schema) | Fonte hoje | Status |
|-------|-------------------------------|-----------|--------|
| `vendas_brutas` | `SUM(revenue)` | 🔴 **ListingSnapshot.revenue** (não Order) | migra p/ aggregate_metrics **E76** |
| `taxas_ml_total` | `SUM(taxa_ml_pct·revenue/100)` | Snapshot + Listing.sale_fee_pct | E76 |
| `frete_total` | `SUM(avg_shipping_cost·orders_count)` | 🔴 Snapshot.orders_count | E76 |
| `receita_liquida` | vendas − taxas − frete | derivado | E76 |
| `custo_total` | `SUM(custo·unidades)` (só SKU vinculado) | Produto.custo | ✗ depende cadastro |
| `margem_bruta`/`margem_pct` | receita_liq − custo | derivado | ✗ |
| `total_pedidos`/`cancelamentos`/`devolucoes` | contagens | 🔴 Snapshot (não Order) | E76 |

**Detalhado por SKU (`/financeiro/detalhado`:265) + Rentabilidade SKU (`/rentabilidade-sku`:826):** breakdown por listing — migra p/ `aggregate_metrics_by_listing` (**E77/E78**). **Timeline (`/timeline`:404):** série temporal, mesma fonte. **DRE (`/dre`:527):** linhas Receita/(-)Taxas/(-)Frete/(-)CMV/(-)Imposto — tem bloco `_aggregate` **DUPLICADO** com o resumo (consolidar em **E74**). **Cashflow (`/cashflow`:1029):** projeção de recebíveis D+8, usa `=="approved"` — **legítimo** para projeção (E73 decide manter + comentar).

🔴 **Achado E26 (o mais importante da Fase 2):** TODO o Financeiro lê `revenue`/`orders_count` do
**snapshot**, as MESMAS colunas duplicadas que causam a divergência (Falha estrutural 1). Por isso a
receita do Financeiro pode não bater com o `/kpi/summary`. A migração inteira está mapeada na Fase 6
(E74 dedup DUPLICADO, E75 fuso BRT, E76 resumo/DRE, E77 breakdown, E78 SKU). Fonte de custo/imposto
(CMV + Simples 8,5%) fica por cima — só a base de receita/pedidos muda de fonte.

---

### E27-E29 — Intel/Analytics (7 painéis, `pages/Intel/`) — preenchido 2026-07-10

7 painéis = 7 endpoints `GET /intel/analytics/*` = 7 services (mapa 1:1). **TODOS leem
`ListingSnapshot.revenue`/`sales_today`** (colunas duplicadas) — migração na Fase 6 (E80-E86).

| Painel (E) | Service call | Endpoint | Serviço | Fonte / problema | Migração |
|------------|--------------|----------|---------|------------------|----------|
| ABC (E27) | getABC | `/abc` | service_abc.py | Snapshot.revenue, window function por listing | E80 |
| Pareto (E27) | getPareto | `/pareto` | service_pareto.py | Snapshot.revenue Σ por listing (core/long_tail) | E81 |
| Distribuição (E28) | getDistribution | `/distribution` | service_distribution.py | 🔴 Σ Snapshot.revenue/sales_today **sem dedup** | E83 |
| Forecast (E28) | getForecast | `/forecast/{mlb}` | service_forecast.py | 🔴 Σ sales_today por dia (captured_at) **sem dedup** | E85 |
| Comparação (E29) | getComparison | `/comparison` | service_comparison.py | 🔴 Σ Snapshot.revenue/sales_today atual vs anterior | E82 |
| Estoque/InventoryHealth (E29) | getInventoryHealth | `/inventory-health` | service_inventory.py | Snapshot.stock (último por listing) — ok p/ estoque | E84 (mín. dedup) |
| Insights (E29) | getInsights | `/insights` | service_insights.py | deriva do Pareto/Snapshot | E86 |

🔴 **Achado E27-E29:** Distribuição, Forecast e Comparação somam `sales_today`/`revenue` de MÚLTIPLOS
snapshots sem `DISTINCT snapshot_day` → com dados legados (>1 snapshot/dia antes da constraint da
Fase 2 antiga) **inflam**. InventoryHealth usa só o ÚLTIMO snapshot (estoque) — esse é seguro. Todos
mapeados E80-E86.

### E30 — Reputação (`pages/Reputacao/index.tsx`) — preenchido 2026-07-10

Fonte: `GET /reputacao/current` (+`/history`, `/risk-simulator`) → `reputacao/service.py`.

| Campo | Origem | Endpoint ML | Check | Status |
|-------|--------|-------------|-------|--------|
| Nível (cor/termômetro) | seller_reputation.level_id | `/users/{id}` | — | ✓ |
| Vendas 60d (EXIBIDO) | `metrics.sales.completed` (espelho painel) | `/users/{id}` | `reputacao_vendas_60d` | ✓ 2/2 PASS (E13/E14) |
| Reclamações/mediações | reputation.metrics.claims | `/users/{id}` | `reputacao_claims` | ✓ 2/2 PASS |
| Atrasos/cancelamentos | reputation.metrics | `/users/{id}` | — | ✗ |
| Contagem local (diagnóstico) | `calculate_orders_60d` (Order) | — | — | ✗ campo separado (não é o exibido) |

✅ **Reputação = caso de sucesso da sessão:** E13 confirmou que o valor exibido já era `metrics.sales.completed`
(espelho do painel); E14 (sync 3h) matou a defasagem. Baseline tinha reputação subcontando −46/−14;
medição 2 (07-10): **4/4 PASS**. Trava em E99.

---

### E31 — Concorrência (`pages/Concorrencia/index.tsx`) — preenchido 2026-07-10
Fonte: `competitorsService.list/getHistory` → `GET /concorrencia/` (+`/listing/{id}`, `/sku/{id}`, `/{id}/history`) → `concorrencia/service.py`.

| Campo | Origem | Endpoint ML | Status |
|-------|--------|-------------|--------|
| Preço do concorrente | Competitor snapshot | `/items/{id}/sale_price` | ✗ (E102) |
| Posição/ranking | busca | `/sites/MLB/search` | ✗ EA13 valida |
| Histórico de preço | CompetitorSnapshot série | — | ✗ |

### E32 — Publicidade (`pages/Publicidade/index.tsx`) — preenchido 2026-07-10
Fonte: `adsService.list/getCampanha/sync` → `GET /ads/` (+`/{campaign_id}`, `POST /sync`) → `ads/service.py`.

| Campo | Origem | Endpoint ML | Status |
|-------|--------|-------------|--------|
| ROAS/ACOS geral e por campanha | AdsSnapshot (attributed_revenue/cost) | Product Ads v2 `prints/clicks/cost/roas/acos` | ✗ (E105) |
| Impressões/cliques/gasto | AdsSnapshot | Product Ads v2 | ✗ |
| `roas_target` | **vazio hoje** (idea: skill Amazon) | — | ✗ backlog |

⚠️ **Decisão arquitetural:** API de Ads do ML é limitada → **fallback honesto** (nunca inventar ACOS). Trava E105.

### E33 — Alertas + Notificações (`pages/Alertas`, `pages/Notificacoes`) — preenchido 2026-07-10
`alertasService.*` → `GET/POST/PUT/DELETE /alertas` (+`/events`) → `alertas/service.py`. `notificationsService.*` → `GET /notifications` (+count/read). Valores monitorados = condições sobre Order/Snapshot; disparo avaliado por task. Status ✗ (trava E100/E107 — sem falso positivo com dado parcial).

### E34 — Atendimento + Perguntas (`pages/Atendimento`, `pages/Perguntas`) — preenchido 2026-07-10
`atendimentoService.*`+`claimsService.*` → `GET /atendimento/*` (15 endpoints). `perguntas` via mutations → `/perguntas/*` (7 endpoints).

| Campo | Origem | Endpoint ML | Status |
|-------|--------|-------------|--------|
| SLA/tempos/contagens atendimento | claims/messages | `/post-purchase/v1/claims/search`, `/messages/*` | ✗ (E103) |
| Perguntas (contagem, sync 15min) | Question DB | `/questions/search`, `/my/received_questions/search` | ✗ (E104) |
| Auto-answer (só high-confidence) | IA | `/answers` | ✗ (E104) |

### E35 — Produtos + Sugestões de Preço (`pages/Produtos`, `pages/PriceSuggestions`) — preenchido 2026-07-10
`productsService.*` → `GET/POST/PUT/DELETE /produtos` (custo/SKU — alimenta margem). `pricingService` → `GET /intel/pricing/recommendations` (+generate/dismiss/daily-report/email).

| Campo | Origem | Status |
|-------|--------|--------|
| Custo/SKU do produto | Produto.custo (cadastro manual) | ✗ base de toda margem (E101) |
| Recomendação de preço | intel/pricing service | ✗ (E106 consultor não recalcula) |
| Preço sugerido/simulado | pricing recommendation | ✗ |

### E36 — Consolidação da Fase 2 (resumo por status) — preenchido 2026-07-10

**17 telas mapeadas** (E20-E35). Contagem de campos por status:
- ✓ **tem dono E check de paridade:** comissão, preço, estoque (E9), reputação (E14), pedidos (Order direto), Vendas MT (20/20).
- ✗ **tem dono, FALTA check:** maioria dos derivados (preço médio, conversão, dias p/ zerar, participação), operacionais (atendimento, perguntas, ads, concorrência), custo/margem (dependem de cadastro).
- 🔴 **órfão/duvidoso (= bugs a corrigir nas Fases 4-6):**
  1. **Sobrecontagem de vendas** (KPI cards, tabela multiperíodo) → Fase 4/E52.
  2. **Financeiro inteiro** lê `revenue`/`orders_count` do snapshot duplicado → Fase 6/E74-E78.
  3. **Funil** dia-UTC-sem-status → E69. **Heatmap** approved-only → E71.
  4. **Análise de Anúncios** visitas sem dedup → E79. **Intel** Distribuição/Forecast/Comparação sem dedup → E80-E86.
  5. **Visitas** timing D-1 (transversal) → Fase 3/E43.

**Conclusão da Fase 2:** a causa-raiz dos 🔴 é UMA só — **as 7 colunas de vendas duplicadas no
ListingSnapshot** (Falha estrutural 1). Todas as telas que divergem leem dessas colunas ou de
agregação não-aditiva sobre elas. Confirma a tese do plano: a Fase 4 (Order como dono único) +
Fase 6 (migrar telas) resolvem a maioria dos 🔴 de uma vez. `voce_recebe` (E21) e as fórmulas de
margem (E22/E24/E35) são risco separado, travado por characterization (E94/E101).

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
