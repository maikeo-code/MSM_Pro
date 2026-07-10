# PLANO DEFINITIVO MSM_Pro — 161 etapas, 10 fases + 5 blocos (Fable 5, 2026-07-09)

> Escrito por Fable 5 após ler o código-fonte diretamente (metrics.py, models.py, service_kpi.py,
> tasks, routers, o cliente HTTP do ML) e inventariar as 17 telas + 15 módulos de API + 124 endpoints
> internos + 51 métodos do cliente ML — todos extraídos por grep real no código, não estimados.
> Público-alvo: uma IA executora sem o contexto desta conversa, operada por um usuário não-dev
> (Maikeo, ~5 meses de experiência com Claude Code).
>
> **Este plano NÃO é a soma das sugestões de modelos anteriores** (`HANDOFF_PROBLEMAS_RECORRENTES.md`,
> `BRIEFING_FABLE5.md`, ambos movidos para `docs/handoff/` do projeto na Etapa E3) — é uma reanálise.
> Onde os handoffs anteriores estavam errados ou rasos, a seção "Fatos verificados" corrige.
>
> **Nota de processo:** este plano já passou por uma divisão em 3 arquivos isolados e foi
> reunificado aqui — a divisão só compensa no momento em que uma parte for de fato entregue a uma
> sessão de execução separada da que está lendo as outras partes. Enquanto o plano ainda está sendo
> ajustado, um arquivo único é mais fácil de manter coerente. A estrutura em fases abaixo já isola
> os blocos de risco/dependência (ver "Ordem e ritmo" no fim) — dividir fisicamente em 3 arquivos
> depois é um corte mecânico simples pelos títulos `## FASE`.

---

## CONTEXTO — por que 4 meses de correções nunca estabilizaram

Li o código com meus próprios olhos. O problema NÃO é falta de mais correções. São **3 falhas
estruturais** que nenhuma correção pontual resolve — e é por isso que consertar um quebrava outro:

### Falha estrutural 1 — O mesmo fato é guardado DUAS vezes e as cópias divergem
A tabela `ListingSnapshot` guarda 7 colunas de VENDAS (`sales_today`, `orders_count`, `revenue`,
`cancelled_orders`, `cancelled_revenue`, `returns_count`, `returns_revenue`) que são **cópias
derivadas** do que a tabela `Order` já guarda como fato original. Duas cópias da mesma verdade
sempre divergem (sync parcial, timing, bug de escrita). Para remendar a divergência, o
`metrics.py:121-126` usa `max(snapshot, order)` — que é **matematicamente não-aditivo**
(Σmax ≥ maxΣ), logo `/kpi/daily` somado NUNCA pode bater com `/kpi/summary` por construção.
Todas as telas que divergem entre si divergem por causa disso. **Resolvido na Fase 4.**

### Falha estrutural 2 — A ingestão nunca é VERIFICADA; a leitura tenta compensar
Nenhum processo confirma que o dia foi capturado por completo (todas as orders? visitas de 100%
dos anúncios?). Por isso nasceram os remendos de leitura: `max()`, fallbacks, guardas anti-corrupção.
**Resolvido na Fase 5 — Fechamento do Dia.**

### Falha estrutural 3 — Não existe o MAPA do que cada tela mostra
17 telas, 15 módulos, 124 endpoints internos, 51 métodos no cliente ML, e nenhum documento diz "este
número desta tela vem desta coluna, que vem deste endpoint do ML, e é verificado por este teste".
Sem o mapa, cada sessão de IA mexe às cegas. **Resolvido nas Fases 2, 2B e 1B — pré-requisito de tudo.**

### Por que NÃO reescrever do zero (decisão mantida)
O código embute ~151 correções de pegadinhas REAIS da API do ML (sale_price, time_window,
senders.cost, listing_prices, BRT, refunded conta...). Reescrever joga esse conhecimento fora e
recomeça o ciclo de 4 meses. O que falta não é código novo — é dono único por dado, ingestão
provada e o mapa completo. Este plano entrega os três, sem remover nenhuma feature existente.

---

## REGRAS DE EXECUÇÃO (para a IA executora; o Maikeo não é dev — isto protege ele)

1. **1 etapa = 1 commit pequeno.** Nunca agrupar etapas. Mensagem: `fix|feat|test|refactor: [E##] descrição`.
2. **Vermelho = reverter.** Teste quebrou sem intenção → `git checkout` / reverter, NUNCA "ajustar o teste
   para passar". Mudou número de propósito → atualizar golden master NO MESMO commit com justificativa.
3. **Nada é pronto sem prova.** Cada etapa tem seção *Prova* — executá-la literalmente e mostrar a saída
   ao Maikeo. Em dados: o número tem que bater com o painel do ML.
4. **Antes de todo commit:** `cd backend && python -m pytest tests/test_metrics_characterization.py tests/test_metrics_parity.py -q` (~5s).
5. **Deploy = `git push origin main`** (Railway auto). NUNCA `railway up`. Após deploy: `/health` 200.
6. **Endpoint ML novo/duvidoso → perguntar ao MCP oficial** (`mercadolibre-official`) ANTES de codar.
   ⚠️ MCP só autentica na sessão principal — nunca delegar validação ML a subagente.
7. **Ao terminar cada FASE:** atualizar vault Obsidian (`_Dashboard/🗺️ Plano Mestre.md`, `08 - Bugs e
   Fixes/`, `14 - ADR/`) e reportar ao Maikeo: o que mudou, prova, e % de paridade atual.
8. **Escopo travado:** sem poda, sem features novas (exceto o que o plano lista), sem reescrita de módulo.
9. **Se uma etapa travar por >2 tentativas:** parar, registrar o bloqueio, perguntar ao Maikeo. Não inventar.

### Cheat-sheet ML (fatos que custaram retrabalho — violar = bug)
- URL `api.mercadolibre.com` (libre). Preço real: `/items/{id}/sale_price` (`price` cru é DEPRECIADO).
- Visitas do dia: `/items/{id}/visits/time_window?last=1&unit=day&ending={D+1}` (`ending` exclusivo).
  `/visits/items?ids=` retorna LIFETIME — proibido para visitas de dia.
- Frete do vendedor: `/shipments/{id}/costs → senders[].cost` (header `x-format-new`). `list_cost` já é líquido.
- Comissão: `/sites/MLB/listing_prices` (+`logistic_type`+`shipping_mode=me2`) → `sale_fee_amount`;
  na order: `order_items[].sale_fee`.
- Reputação 60d: `seller_reputation.metrics.sales.completed`. Dia do painel = BRT (-03:00).
- `refunded` CONTA como venda; `cancelled`/`rejected` não (`backend/app/vendas/constants.py`).

### Comandos de verificação
```bash
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
cd backend && python -m pytest tests/test_metrics_characterization.py tests/test_metrics_parity.py -q  # núcleo ~5s
cd backend && python -m pytest tests/ -q      # suíte completa (baseline 2026-07-09: 1865 passed)
TOKEN="$TOKEN" scripts/check_parity.sh        # gate de paridade (após E1)
```

### Estratégia de execução (agentes) — resumo; guia completo no fim do documento
Regra base do projeto (Regra Absoluta #6): **um agente por arquivo, nunca dois escrevendo ao mesmo
tempo.** Fases 2, 2B e 1B são leitura/documentação — paralelizável. Fases 0, 1, 3, 4, 5, 6 (quando
arquivos se cruzam) e 7 tocam núcleo compartilhado — sequencial. Mapeamento por subagente do
projeto (`dev`/`qa`/`insights`/`ml-api`) no fim do documento.

---

## FATOS VERIFICADOS NO CÓDIGO (correções aos handoffs anteriores — esta seção é a verdade)

1. **`scripts/check_parity.sh` QUEBRADO:** aponta `/api/v1/vendas/audit/parity`; rota real é
   `GET /api/v1/listings/audit/parity`. O portão de pronto retorna 404 hoje.
2. **`period=30d`:** `/kpi/summary` (`vendas/router.py:298`) NÃO declara `period` — ignora o parâmetro e
   sempre devolve `{hoje, ontem, anteontem, 7dias, 30dias}` (a chave `30dias` é correta). O perigo real:
   fallbacks `.get(period, 7)` em `service_kpi.py:617,670,682` degradam período desconhecido p/ 7d em silêncio.
3. **Orders NÃO é INSERT puro:** `tasks_orders.py` tem upsert read-modify-write DUPLICADO
   (~213-259 sync e ~516-559 backfill) com race condition → IntegrityError engolido → order perdida no ciclo.
4. **Reputação já usa `metrics.sales.completed`** (`reputacao/service.py:122-130`), MAS `total_sales`
   prefere contagem local (`calculate_orders_60d`) — se Order local não cobre 60d, subconta (ML=2150 vs
   App=2034). Sync roda 1×/dia (06:30 BRT).
5. **Não há resíduo de `item["price"]`** como fonte primária (auditoria completa — tudo é fallback marcado).
6. **Safeguard visitas>3000 já removido**; hook `before_insert` só deriva `snapshot_day`, não soma nada.
7. **Snapshot flow-columns:** confirmado por leitura direta de `models.py:117-127` — as 7 colunas de
   vendas duplicam a Order (Falha estrutural 1).
8. **Cliente ML tem métodos mortos com endpoints proibidos/redundantes** (achado na Fase 1B — ver
   tabela na Fase 1B): `get_listing_visits` chama o endpoint LIFETIME proibido mas nunca é chamado;
   `get_full_stock` (endpoint de estoque FULL) nunca é usado — pode faltar no fix de estoque (E9).

### Inventário de funcionalidades (base do Catálogo — Fases 1B, 2, 2B)
Telas (17): Dashboard, Anúncios (lista+detalhe), Análise de Anúncios, Vendas MT, Pedidos, Financeiro,
Intel (ABC, Pareto, Distribuição, Forecast, Comparação, Estoque, Insights), Reputação, Concorrência,
Publicidade, Alertas, Atendimento, Perguntas, Produtos, Sugestões de Preço, Notificações, Configurações.
Módulos de API (15): vendas, vendas_mt, financeiro, analise, intel, reputacao, concorrencia, produtos,
alertas, atendimento, perguntas, ads, consultor, notifications, auth.

### Mapa: quem agrega vendas/receita FORA do metrics.py (alvos da Fase 6)
| Módulo | Local | Janela | Filtro status | Migração |
|---|---|---|---|---|
| Funnel | `vendas/service_analytics.py:34` | dia UTC ❌ | nenhum ❌ | trivial |
| Heatmap | `vendas/service_analytics.py:376` | BRT ✓ | `=="approved"` ❌ | só filtro |
| P&L resumo/DRE | `financeiro/service.py:110,527` | UTC, fim=ontem ❌ | nenhum ❌ | média (bloco `_aggregate` duplicado) |
| P&L detalhado/SKU/timeline | `financeiro/service.py:265,404,826` | UTC/misto ❌ | nenhum ❌ | precisa breakdown por listing |
| Cashflow | `financeiro/service.py:1029` | D+8 | `=="approved"` | não migrar (projeção) |
| Análise anúncios | `analise/service.py:29` | visitas SEM dedup ❌ | `=="approved"` ❌ | breakdown por listing |
| Sparkline 7d | `service_dashboard_cards.py:224` | BRT ✓ | constante ✓ | manter (net_amount) |
| intel/analytics (7 services) | `intel/analytics/service_*.py` | UTC rolling, SEM dedup ❌ | nenhum ❌ | média |
| Parity audit | `service_parity_audit.py` | BRT ✓ | constante ✓ | NÃO migrar (verificador) |

---

# AS ETAPAS

## FASE 0 — Fundação: o verificador tem que funcionar antes de qualquer código (E1-E7)

- **E1.** Corrigir `scripts/check_parity.sh:33`: `/api/v1/vendas/` → `/api/v1/listings/`.
  *Prova:* rodar com token real; imprime placar; exit 0/1 (nunca 404).
- **E2.** Versionar o pre-commit: criar `scripts/hooks/pre-commit` (roda o núcleo, bloqueia regressão) +
  `scripts/install_hooks.sh`. *Prova:* sabotar 1 número no metrics.py → commit bloqueado; reverter.
- **E3.** Commitar a blindagem: `backend/tests/test_metrics_characterization.py`, `scripts/`, e mover
  `HANDOFF_PROBLEMAS_RECORRENTES.md`+`BRIEFING_FABLE5.md` → `docs/handoff/`. *Prova:* git status limpo; `/health` 200 pós-deploy.
- **E4.** CI: job "metrics-core" (só o núcleo, ~5s, falha rápida) antes da suíte em `.github/workflows/ci.yml`.
  *Prova:* Actions verde com o novo job.
- **E5.** Baseline inicial: suíte completa + `check_parity.sh` em prod → registrar números e data em
  `docs/handoff/BASELINE_2026-07.md`. *Prova:* arquivo commitado (~81,3%, 4 FAIL estoque, 19 visitas, 2 reputação).
- **E6.** Criar esqueleto `docs/data_catalog.md` com o formato: tela → campo → endpoint backend →
  serviço:função → tabela.coluna → endpoint ML → check → status(✓/✗/órfão). *Prova:* arquivo commitado.
- **E7.** Adicionar ao `msm_pro/CLAUDE.md` a seção curta "Regras de execução do Plano Definitivo"
  (as 9 regras acima, resumidas, com link a este plano). *Prova:* seção presente e commitada.

## FASE 1 — Bugs P0 confirmados: dados errados AGORA (E8-E19) → paridade 81,3% → ≥95%

- **E8.** MCP oficial ML: confirmar semântica de estoque de itens com `variations` (soma de
  `variations[].available_quantity` = valor do painel?). Registrar em `backend/docs/ml_endpoints_canonical.md`.
  *Prova:* nota datada no doc.
- **E9.** `tasks_listings.py:107`: se o item tem `variations` → `stock = Σ variations[].available_quantity`;
  senão top-level. *Prova:* teste unitário (3 variações 20+30+19=69; sem variações → top-level).
  ⚠️ **Verificar EC3/EC4 (Fase 1B) antes de fechar esta etapa** — itens FULL podem precisar de
  `get_full_stock` em vez de somar variações.
- **E10.** Deploy + re-sync de MLB5276909636 (ML=69), MLB7118364802 (69), MLB6620170054 (33).
  *Prova:* `check_parity.sh` → estoque 31/31 PASS.
- **E11.** `tasks_orders.py`: extrair `_upsert_order()` única com `INSERT ... ON CONFLICT (ml_order_id)
  DO UPDATE` (via `sqlalchemy.dialects.postgresql.insert`), substituindo os 2 blocos duplicados.
  *Prova:* teste inserindo a mesma order 2× e em concorrência simulada — sem IntegrityError; suíte verde.
- **E12.** Rodar backfill de orders em prod. *Prova:* `SyncLog` sem IntegrityError; `pedidos_dia` PASS na paridade.
- **E13.** `reputacao/service.py`: o valor EXIBIDO de vendas 60d = `metrics.sales.completed` da API
  (espelho do painel); contagem local vira campo separado de diagnóstico. *Prova:* teste unitário da preferência.
- **E14.** Beat: `sync_reputation` de 1×/dia → a cada 3h (`celery_app.py:116-123`).
  *Prova:* SyncLog com execuções 3/3h; paridade reputação 2/2 PASS.
- **E15.** Investigar visitas MLB5982716652 (ML=1, App=7) via MCP `msm-database` (`query_snapshots`):
  conferir `snapshot_day`/`captured_at`/`visits` vs `time_window` real do mesmo dia. Corrigir dado + causa.
  *Prova:* causa documentada no vault `08 - Bugs e Fixes/`; check do anúncio PASS ou timing justificado.
- **E16.** `service_kpi.py`: remover função morta `_period_to_dates` (:617); trocar `.get(period, 7)`
  (:670,:682) por validação que rejeita período desconhecido (ValueError→422). *Prova:* teste `period="30D"` → erro explícito.
- **E17.** Decidir e documentar o contrato do `/kpi/summary` (dict multiperíodo; `period` não aceito) OU
  declarar `period` de verdade — escolher UM e alinhar frontend. *Prova:* docstring/openapi + frontend consistente.
- **E18.** `GET /ml/accounts` (`auth/router.py:229`): preencher `last_sync_at` real via `max(SyncLog)` de
  sucesso por conta. *Prova:* curl mostra timestamp real, não null.
- **E19.** Alerta "dados congelados": banner no frontend quando `last_sync_at > 2h` ou `needs_reauth`;
  notificação in-app já na 1ª falha de refresh de token (`tasks_tokens.py` — hoje espera 5).
  *Prova:* simular token inválido → banner + notificação aparecem.

## FASE 1B — AUDITORIA DO CLIENTE ML: os 51 métodos que realmente falam com o Mercado Livre (EC1-EC12)

> As Fases 2/2B auditam as rotas INTERNAS do nosso backend (124 endpoints do nosso FastAPI). Esta
> fase audita o outro lado: `backend/app/mercadolivre/client.py`, o único arquivo que fala com a API
> do ML — **51 métodos**, cada um chamando um endpoint real do ML. É aqui que moram TODAS as
> pegadinhas do cheat-sheet (sale_price, time_window, senders.cost, listing_prices...). Auditoria
> feita em 2026-07-09 via grep de definições + call-sites; achados já confirmados abaixo.

### Achados reais desta auditoria (não estimados — confirmados por grep de call-sites)
| Método (linha) | Endpoint ML | Chamado por | Achado |
|---|---|---|---|
| `get_listing_visits` (904) | `/visits/items` ❌ LIFETIME proibido | **Ninguém — morto** | ⚠️ Mina: se reconectado no futuro, reintroduz bug de visitas infladas |
| `get_full_stock` (387) | `/user-products/{id}/stock/fulfillment` | **Ninguém — morto** | Endpoint próprio p/ estoque FULL nunca usado — pode faltar no fix de estoque (E9) |
| `create_promotion` (530) / `update_promotion` (561) | `/seller-promotions/items/{id}` (forma antiga) | **Ninguém — morto** | Substituído por `create_price_discount_promotion` (436), que É usado via `service_price.py:205` |
| `get_item_visits` (242, fallback) | `/items/{id}/visits/time_window` (dias, não dia exato) | `tasks_listings.py:219` (fallback quando `get_item_visits_on_day` falha) | ✓ Seguro — usa time_window, não lifetime |
| `get_mp_balance` (880) | `/users/{id}/mercadopago_account/balance` | `service_dashboard_cards.py:73` | Ativo — checar contra decisão "MP integração direta ADIADA" (é só leitura de saldo, não integração?) |
| `get_free_shipping_cost` (758) | `/users/{id}/shipping_options/free` | `tasks_listings.py:454` | Ativo — endpoint DIFERENTE do `/shipments/{id}/costs` do cheat-sheet; confirmar quando cada um se aplica |
| `get_campaigns`/`get_campaign_metrics` (998/1021) vs `get_product_ads_campaigns` (614) | 2 formatos de API de Ads distintos (`/advertising/campaigns` vs `/advertising/advertisers/{id}/product_ads/campaigns`) | só a 2ª tem call-site confirmado (`ads/service.py:233`) | Checar se a 1ª é resquício de tentativa anterior (dead code) |

- **EC1.** Inventariar os 51 métodos do `client.py` numa tabela única: método, linha, endpoint ML,
  verbo HTTP, call-sites (grep em `app/`), status (ativo/morto). Registrar em
  `backend/docs/ml_endpoints_canonical.md` (nova seção "Cliente ML — inventário completo").
  **Agente: `ml-api`** (é literalmente a função dele — validar endpoints ML contra a doc canônica).
- **EC2.** `get_listing_visits` (morto, endpoint lifetime proibido): decidir e aplicar — remover OU
  marcar com comentário `# NUNCA CONECTAR — usa endpoint lifetime proibido, ver cheat-sheet` bem
  visível, para virar barreira contra reconexão futura acidental. **Agente: `dev`** (mudança pequena,
  1 arquivo). *Prova:* `test_forbidden_patterns.py` (E93) passa a cobrir este método também.
- **EC3.** Validar no MCP oficial (`mercadolibre-official`): para itens com `logistic_type=fulfillment`
  (FULL), o estoque exibido no painel do vendedor vem de `/user-products/{id}/stock/fulfillment` ou
  da soma de `variations[]`? Cruzar a resposta com os 3 anúncios do bug de estoque conhecido
  (MLB5276909636, MLB7118364802, MLB6620170054 — via MCP `msm-database`, checar `logistic_type`
  desses 3 no banco). **Agente: sessão principal** (MCP só autentica ali). *Prova:* resposta do MCP +
  `logistic_type` dos 3 anúncios registrados no catálogo.
- **EC4.** Se EC3 confirmar que FULL precisa do endpoint próprio: ajustar o escopo de E9 (Fase 1,
  fix de estoque) ANTES de implementá-lo — variations→soma para itens normais; FULL→`get_full_stock`.
  Se E9 já foi implementado sem essa distinção, reabrir como bug. **Agente: `dev`**.
  *Prova:* teste cobrindo os 2 casos (item comum com variações vs item FULL).
- **EC5.** `create_promotion`/`update_promotion` (mortos, substituídos por `create_price_discount_promotion`):
  reportar ao Maikeo com recomendação de remover (reduz superfície de erro) — **só remover com
  confirmação explícita dele** (escopo travado contra poda não autorizada, mesma regra da EA12).
  **Agente: relatório direto, sem subagente.**
- **EC6.** Investigar `get_campaigns`/`get_campaign_metrics` (`/advertising/campaigns`) vs
  `get_product_ads_campaigns` (`/advertising/advertisers/{id}/product_ads/campaigns`, ativo) — grep
  completo de call-sites; se a primeira forma for resquício de tentativa anterior de integração de Ads,
  mesma decisão de EC5. **Agente: `ml-api`** (pesquisa) → relatório ao Maikeo.
- **EC7.** `get_mp_balance` (ativo): documentar no catálogo se é "leitura de saldo" (ok, dentro do
  escopo atual) ou se extrapola a decisão arquitetural "Mercado Pago integração direta ADIADA" — não
  mudar comportamento, só classificar corretamente. **Agente: `insights`** (tem contexto de decisões
  arquiteturais) → registrar no vault `14 - ADR/`.
- **EC8.** Formalizar no catálogo: `get_item_visits` (fallback, days-based) é seguro (usa time_window),
  usado só quando `get_item_visits_on_day` falha (`tasks_listings.py:219`). Adicionar nota explicando
  a diferença de precisão (dias corridos vs dia calendário exato). **Agente: `dev`** (só documentação).
- **EC9.** Para os métodos que tocam preço/frete/comissão/visitas/estoque (o núcleo do cheat-sheet:
  `get_item_sale_price`, `get_item_visits_on_day`, `get_shipment_costs`, `get_listing_fees`,
  `get_free_shipping_cost`), validar cada um no MCP oficial se o endpoint ainda é o recomendado hoje
  (a API do ML muda; correto em 06/2026 pode não ser mais em 07/2026). **Agente: `ml-api`** + sessão
  principal p/ MCP. *Prova:* nota datada por método no `ml_endpoints_canonical.md`.
- **EC10.** Métodos de atendimento (`get_claims`, `get_claim_detail`, `send_claim_message`,
  `get_messages`, `send_message`, `get_message_packs`, `get_returns`, `get_received_questions`,
  `answer_question` — 9 métodos) validados contra o MCP — sustentam os 15 endpoints internos de
  `atendimento/router.py` (EA6). **Agente: `ml-api`**.
- **EC11.** Consolidar: nova seção "Cliente ML — 51 métodos" em `docs/data_catalog.md`, cruzando com
  as seções "Telas" e "Endpoints" já existentes (um método do client pode alimentar vários endpoints
  internos, que alimentam várias telas — o mapa fica completo nos 3 níveis). **Agente: `dev`**.
- **EC12.** Reportar ao Maikeo: quantos métodos mortos encontrados (3 confirmados: EC2, EC5, EC6-se-
  confirmado), quantos endpoints desatualizados (EC9-EC10), decisão pendente sobre remoção.
  **Agente: relatório direto.** *Prova:* nota no vault `08 - Bugs e Fixes/` com os números.

## FASE 2 — O CATÁLOGO DE DADOS: mapear cada número de cada tela (E20-E36)

> Uma etapa por tela. Em cada uma: abrir a tela + o código do componente, listar TODO campo numérico
> exibido, rastrear campo → endpoint backend → serviço → tabela.coluna → endpoint ML, registrar no
> `docs/data_catalog.md`, e marcar: ✓ tem dono e check | ✗ tem dono, falta check | 🔴 órfão/duvidoso.
> *Prova (todas):* seção da tela completa no catálogo, commitada. Campos 🔴 viram bugs listados no vault.

- **E20.** Dashboard (`pages/Dashboard`) — KPI cards, sparkline, cards ML (reputação/saldo/full).
- **E21.** Anúncios lista (`pages/Anuncios/index`) — colunas da tabela, "você recebe", comissão, frete.
- **E22.** Anúncio detalhe (`AnuncioDetalhe` + 8 componentes) — KPIs, métricas avançadas, price bands,
  histórico de preço, posição de busca, concorrente, calculadora de margem.
- **E23.** Análise de Anúncios (`pages/AnaliseAnuncios`) — janelas 7/15/30d, conversão, ROAS.
- **E24.** Vendas MT (`pages/VendasMT` + 5 componentes) — KPIs, custo/imposto, entrega, tarifa, lucro bruto.
- **E25.** Pedidos (`pages/Pedidos`) — valores por pedido, frete, tarifa, líquido.
- **E26.** Financeiro (`pages/Financeiro`) — P&L, DRE, timeline, cashflow, rentabilidade por SKU.
- **E27.** Intel: ABC + Pareto (`pages/Intel/Analytics/ABC,ParetoChart`).
- **E28.** Intel: Distribuição + Forecast (`SalesDistribution`, `SalesForecast`).
- **E29.** Intel: Comparação + Estoque + Insights (`Comparison`, `InventoryHealth`, `InsightsPanel`).
- **E30.** Reputação (`pages/Reputacao`) — nível, vendas 60d, claims, atrasos.
- **E31.** Concorrência (`pages/Concorrencia`) — preços de concorrentes, posição.
- **E32.** Publicidade (`pages/Publicidade`) — ACOS/ROAS/fallback honesto (API não pública).
- **E33.** Alertas + Notificações (`pages/Alertas`, `pages/Notificacoes`) — condições e valores monitorados.
- **E34.** Atendimento + Perguntas (`pages/Atendimento`, `pages/Perguntas`) — SLA, contagens, tempos.
- **E35.** Produtos + Sugestões de Preço (`pages/Produtos`, `pages/PriceSuggestions`) — custos, margens.
- **E36.** Consolidação: revisar o catálogo inteiro, contar campos por status (✓/✗/🔴), publicar resumo
  no vault e priorizar os 🔴 como lista de bugs. *Prova:* tabela-resumo no catálogo + nota no vault.

## FASE 2B — AUDITORIA ENDPOINT-A-ENDPOINT (não só por tela) — EA1-EA18

> A Fase 2 mapeia campos POR TELA. Isso deixa de fora endpoints que nenhuma tela chama diretamente
> (debug, admin, health, export). Esta fase complementa com o inventário COMPLETO e real dos 124
> endpoints do backend (extraído via grep em 2026-07-09, não estimado), agrupado por router.
> Para cada etapa: para cada endpoint do grupo, registrar em `docs/data_catalog.md` (seção
> "Endpoints"): método+path, service:função que implementa, tabela(s) que lê/escreve, endpoint(s)
> ML que chama (se houver, validado no MCP oficial), qual tela usa (ou "🔴 ÓRFÃO — nenhuma tela
> chama" / "🟡 DEBUG — uso interno/operacional, ok ser órfão"), e se tem teste. *Prova (cada etapa):*
> seção do router completa no catálogo + qualquer endpoint sem uso claro reportado como pendência.

### Inventário real (124 endpoints, 17 routers) — base desta fase
```
ads (3): GET /, GET /{campaign_id}, POST /sync
alertas (7): GET /, POST /, GET /events/, GET /events/{id}, GET /{id}, PUT /{id}, DELETE /{id}
analise (1): GET /listings
atendimento (15): GET /, GET /stats, POST /{tipo}/{id}/respond, GET /{tipo}/{id}/ai-suggestion,
  GET /templates-test [🟡 nome sugere debug], GET /templates, GET/POST/PUT/DELETE /templates/{id},
  POST /claims/sync, GET /claims, GET /claims/stats, GET /claims/similar/{mlb_id}, POST /claims/{id}/resolve
auth (18): POST /login, GET /me, POST /refresh, GET /ml/connect, GET /ml/callback,
  GET /ml/accounts, POST /ml/accounts/{id}/refresh, GET /ml/tokens-health, DELETE /ml/accounts/{id},
  GET /diagnostics, GET/PUT /preferences, POST /ml/accounts/{id}/backfill-orders,
  POST /debug/trigger-health-check [🟡], POST /debug/trigger-task/{name} [🟡],
  GET /debug/smtp-status [🟡], POST /debug/send-test-email [🟡]
concorrencia (6): GET /, POST /, GET /listing/{id}, GET /sku/{id}, DELETE /{id}, GET /{id}/history
consultor (2): POST /analisar, POST /chat
financeiro (8): GET /resumo, /detalhado, /timeline, /cashflow, /dre, GET/PUT /tax-config,
  GET /rentabilidade-sku
intel/analytics (7): GET /pareto, /forecast/{mlb_id}, /distribution, /insights, /comparison, /abc,
  /inventory-health
intel/pricing (6): GET /recommendations, POST /recommendations/{id}/dismiss,
  POST /recommendations/generate, GET /email/status, POST /email/test, GET /daily-report
notifications (5): GET /, GET /count, POST /read-all, POST /{id}/read, DELETE /{id}
perguntas (7): GET /, GET /stats, POST /sync, POST /{id}/answer, POST /{id}/suggest,
  POST /{id}/rate-suggestion, GET /by-listing/{mlb_id}
produtos (5): GET /, POST /, GET/PUT/DELETE /{id}
reputacao (4): GET /current, GET /history, POST /sync, GET /risk-simulator
vendas (31): POST /sync, POST /backfill-snapshots [⚠️ E65 corrige], GET /, POST /, GET /export,
  GET /kpi/summary [⚠️ E16-17], GET /kpi/compare, GET /kpi/daily, GET /dashboard/extra-cards,
  GET /audit/parity [⚠️ E37 estende], GET /analytics/funnel [⚠️ E69], GET /analytics/heatmap [⚠️ E71],
  GET /coverage [🟡 sem tela clara — checar], GET /sales-trend [⚠️ E70], GET /orders/,
  GET/PUT/DELETE /repricing-rules[/{id}], GET /{mlb}/search-position, GET /{mlb}, GET /{mlb}/snapshots,
  GET /{mlb}/analysis, GET /{mlb}/margem, GET /{mlb}/health [🟡 sem tela clara — checar],
  PATCH /{mlb}/price, POST /{mlb}/promotions, POST /{mlb}/suggestion_apply,
  GET /{mlb}/price-history, POST /{mlb}/simulate-price [🟡 sem tela clara — checar], PATCH /{mlb}/sku
vendas_mt (1): GET /
```

- **EA1.** `auth/router.py` (18 endpoints) — auditar todos, com atenção especial aos 4 `/debug/*`
  (confirmar se ficam acessíveis só a admin/dev, nunca expostos sem guarda — risco de segurança).
- **EA2.** `vendas/router.py` bloco KPI/analytics (`kpi/*`, `analytics/*`, `sales-trend`, `audit/*`,
  `coverage`, `dashboard/extra-cards`) — 10 endpoints, cruzar com as fases já planejadas.
- **EA3.** `vendas/router.py` bloco listing individual (`/{mlb_id}/*`, 11 endpoints) — inclui
  `health`, `simulate-price`: confirmar se têm tela ou são só uso interno/futuro.
- **EA4.** `vendas/router.py` bloco CRUD + export + repricing (10 endpoints restantes).
- **EA5.** `financeiro/router.py` (8 endpoints) — cruzar com a Fase 6 (migração de agregação).
- **EA6.** `atendimento/router.py` (15 endpoints) — atenção ao `/templates-test` (nome de debug em rota de produção — decidir: remover, proteger, ou renomear).
- **EA7.** `intel/analytics/router.py` (7) + `intel/pricing/router.py` (6) — 13 endpoints.
- **EA8.** `alertas/router.py` (7) + `notifications/router.py` (5) — 12 endpoints.
- **EA9.** `perguntas/router.py` (7) + `reputacao/router.py` (4) — 11 endpoints.
- **EA10.** `concorrencia/router.py` (6) + `produtos/router.py` (5) — 11 endpoints.
- **EA11.** `consultor/router.py` (2) + `ads/router.py` (3) + `analise/router.py` (1) +
  `vendas_mt/router.py` (1) — 7 endpoints restantes.
- **EA12.** Cruzar o inventário completo com o Catálogo de Telas (Fase 2): listar TODO endpoint
  marcado 🔴/🟡 acima + qualquer outro achado — decidir para cada um: mantém (documentar por quê é
  interno), protege (auth/rate-limit se for debug em prod), ou remove (se for lixo comprovado —
  **só remover com confirmação explícita do Maikeo**, escopo travado contra poda não-autorizada).
- **EA13.** Para cada endpoint que chama a API do ML (buscar `client\.` ou `ml_client` no corpo da
  função — estimativa: ~35-45 dos 124), validar no MCP `mercadolibre-official` se o endpoint/campo
  usado ainda é o recomendado (API do ML muda; o que era certo em 06/2026 pode ter mudado).
  *Prova:* lista de endpoints ML por rota + resposta do MCP, registrada em `ml_endpoints_canonical.md`.
- **EA14.** Testar manualmente (curl com token real) os 4 endpoints `/debug/*` de auth — confirmar
  que não vazam dado sensível em resposta e que exigem autenticação. *Prova:* saída dos 4 curls.
- **EA15.** Conferir CORS/autenticação em TODOS os 124 endpoints (nenhum sem `Depends(get_current_user)`
  exceto os que são propositalmente públicos: `/login`, `/ml/callback`, `/health*`). *Prova:* tabela
  de endpoints públicos vs autenticados, com justificativa para cada público.
- **EA16.** Conferir se `/vendas/export` (CSV) usa os MESMOS números das telas (reaproveita o bug
  histórico do `item["price"]` cru citado no handoff, e a coluna "preço de tabela" vs "você recebe").
  *Prova:* export comparado linha a linha com a tela Anúncios para 5 SKUs.
- **EA17.** Consolidar `docs/data_catalog.md`: seção "Endpoints" completa (124 linhas), seção "Telas"
  da Fase 2, e uma seção "Cruzamento" mostrando quais campos de tela vêm de quais endpoints — o mapa
  fica navegável nos dois sentidos (por tela e por endpoint). *Prova:* arquivo final revisado.
- **EA18.** Publicar resumo desta fase no vault (`08 - Bugs e Fixes/`): quantos endpoints órfãos
  encontrados, quantos exigiram correção de segurança/autenticação, quantos usavam endpoint ML
  desatualizado. *Prova:* nota criada com números reais.

## FASE 3 — AUDITORIA TOTAL: estender o harness para cobrir todo o catálogo (E37-E48)

> O harness atual (`service_parity_audit.py`) cobre vendas do dia, visitas/estoque/preço/comissão e
> reputação. Estender para TODOS os blocos do catálogo — vira o "espelho auditável" completo. Esta
> fase entrega a ferramenta que a Fase 4 vai usar para provar que a reestruturação de dados não
> quebrou nada (E60 roda esta auditoria completa).

- **E37.** Refatorar o harness para blocos plugáveis: `?blocks=sales,stock,price,fees,shipping,visits,
  reputation,questions,claims` (default: todos). *Prova:* endpoint aceita subset; payload por bloco.
- **E38.** Bloco FRETE por order: amostra de N orders do dia vs `/shipments/{id}/costs → senders.cost`.
  *Prova:* check `frete[order]` PASS/FAIL por order auditada.
- **E39.** Bloco COMISSÃO por order: `Order.sale_fee` vs `order_items[].sale_fee` real. *Prova:* idem.
- **E40.** Bloco LÍQUIDO ("você recebe"): `Order.net_amount` = total − sale_fee − frete vendedor.
  *Prova:* check `liquido[order]` para amostra do dia.
- **E41.** Bloco PERGUNTAS + CLAIMS: contagens vs API. *Prova:* checks novos no payload.
- **E42.** Bloco ESTOQUE v2: item com `variations` → comparar contra a SOMA (valida E9 para sempre).
  *Prova:* check diferencia itens com/sem variações.
- **E43.** VISITAS honestas: comparar D-1 (dia fechado, tol=0); dia corrente vira INFO (não FAIL) —
  elimina os ~14 FAILs de timing sem esconder erro real. *Prova:* placar sem FAILs de timing.
- **E44.** Bloco MULTI-CONTA: cada check por conta (MSM_PRIME 2050442871, MSMPRIME 90599588) +
  consolidado; detecta o bug histórico de inconsistência multi-conta. *Prova:* payload agrupado por conta.
- **E45.** `check_parity.sh` v2: aceita `?blocks=`, imprime placar por bloco, exit≠0 se qualquer FAIL.
  *Prova:* rodada completa em prod com placar por bloco.
- **E46.** Persistir resultado de cada rodada de paridade (tabela `ParityRun` ou `SyncLog` estendido) —
  histórico de paridade ao longo do tempo. *Prova:* rodadas aparecem no banco.
- **E47.** Endpoint `GET /audit/parity/history` para ver evolução. *Prova:* curl retorna série histórica.
- **E48.** Atualizar BASELINE com a auditoria total (será <81,3% porque agora audita MAIS coisas — isso é
  BOM: revela o que estava sem vigilância). *Prova:* baseline v2 commitado com placar por bloco.

---

## BLOCO A — Rede de segurança ANTES de mexer nos dados (E117-E120)

> Executar estas 4 etapas ANTES da Fase 4. Sem elas, a troca de fonte de dados (E52) é arriscada
> demais para um sistema em produção que o Maikeo usa para decisão de negócio todo dia.

- **E117.** Ritual de backup: antes de cada fase que toca dados/migrations (Fase 4, 5), fazer dump do
  Postgres Railway (`pg_dump` via `DATABASE_URL`) para arquivo datado + documentar o restore em
  `docs/handoff/RESTORE.md`. *Prova:* dump gerado e restore testado 1× num banco local/descartável.
- **E118.** Ambiente staging no Railway: serviço backend apontando para branch `staging` com banco
  próprio (clone do prod via dump de E117). Mudanças sensíveis (E52, migrations novas) validam em
  staging ANTES de ir à main. *Prova:* staging no ar; `/health` 200; paridade roda contra staging.
- **E119.** Feature flag `METRICS_SOURCE` (env var: `legacy_max` | `order_additive`) controlando a
  troca de E52 — reverter o cálculo SEM deploy, só trocando a variável no Railway. *Prova:* alternar
  a flag muda o payload; documentado no catálogo.
- **E120.** Modo sombra: durante 3-7 dias antes de virar a chave de E52, calcular AMBOS os modos e
  gravar as diferenças por dia/conta (log estruturado ou tabela `MetricsShadowDiff`). Virar a chave
  só quando toda diferença estiver explicada. *Prova:* relatório de diffs zerado/justificado no vault.

## FASE 4 — UM FATO, UM DONO: Order vira o dono único de vendas (E49-E60)

> A mudança mais importante do plano inteiro. Mata o `max()` não-aditivo pela raiz. NÃO iniciar sem
> Fases 0-1-1B-2-2B-3 completas (rede de segurança + orders confiáveis + catálogo pronto).

- **E49.** Auditoria histórica (somente leitura): por dia BRT e por conta, Σvendas/Σreceita de `Order`
  vs snapshots deduplicados, últimos 90 dias. Identificar dias com Order < snapshot (buracos de sync).
  *Prova:* `docs/handoff/audit_order_vs_snapshot.md` com a tabela de divergências.
- **E50.** Backfill de orders nos buracos encontrados (upsert seguro de E11). *Prova:* re-rodar E49 →
  zero dias com Order < snapshot (resíduos justificados por escrito).
- **E51.** Estender a query de Order no `metrics.py` para derivar TAMBÉM cancelados
  (`payment_status ∈ CANCEL_STATUSES`) e devoluções (`refunded`) — hoje só vêm de snapshot.
  *Prova:* teste unitário com orders de cada status.
- **E52.** **A troca:** `metrics.py` passa a ler vendas/pedidos/receita/cancelados/devoluções SÓ de
  `Order` (aditivo). Snapshot permanece APENAS para visitas/estoque/preço. Fallback para snapshot
  somente se a janela não tem NENHUMA order E tem snapshots (dado legado), com flag `"fonte":
  "snapshot_fallback"` no payload. *Prova:* golden master atualizado NO MESMO commit; núcleo verde.
- **E53.** ADR no vault (`14 - ADR/`): "Order como fonte aditiva única; snapshot = visitas+estado".
  *Prova:* ADR criado e linkado no Plano Mestre.
- **E54.** Teste de ADITIVIDADE no núcleo: Σ`_kpi_single_day`(cada dia) == `_kpi_date_range`(janela),
  para 7d e 30d — a propriedade que o `max()` tornava impossível. *Prova:* teste verde no pre-commit.
- **E55.** Prova em prod: Σ`/kpi/daily` == `/kpi/summary` exatamente (7d e 30d). *Prova:* curl + diff zero.
- **E56.** Prova contra o painel: vendas/receita de ontem e 7d vs painel real das 2 contas.
  *Prova:* `check_parity.sh` PASS em sales; anotação no vault com os números do painel.
- **E57.** Marcar as 7 colunas de vendas do snapshot como DEPRECATED (comentário no model + catálogo);
  a escrita continua (compat), mas NENHUMA leitura nova pode usá-las. *Prova:* comentário + regra no forbidden-patterns (E93).
- **E58.** Guarda anti-corrupção revisada: com Order como dono, a guarda `visitas < vendas` do
  `metrics.py:131` continua válida para visitas — revisar se ainda precisa zerar ou se marca "indisponível".
  *Prova:* teste do comportamento escolhido.
- **E59.** Conferir `valor_estoque`/`preco_medio` pós-troca (dependem de snapshot/receita — validar fórmulas).
  *Prova:* golden master cobre ambos.
- **E60.** Rodar auditoria total (Fase 3) completa pós-troca. *Prova:* nenhum bloco piorou vs E48.

## FASE 5 — FECHAMENTO DO DIA: ingestão provada, não presumida (E61-E68)

- **E61.** Criar tabela `DailyClose` (dia BRT, conta, orders_ml, orders_db, visitas_esperadas,
  visitas_capturadas, status: OPEN/VERIFIED/INCOMPLETE, verified_at). Migration + `alembic current`.
  *Prova:* migration aplicada em prod (via start.sh).
- **E62.** Task `close_day` (beat ~07:30 BRT): para D-1, compara `paging.total` do `/orders/search` da
  janela BRT vs COUNT no banco; se diferente → re-sync da janela e re-verifica. *Prova:* SyncLog + DailyClose VERIFIED.
- **E63.** `close_day` verifica visitas: 100% dos listings ativos com snapshot de D-1 com visitas
  capturadas; faltantes → re-dispara `sync_listing_snapshot` individual. *Prova:* dia INCOMPLETE → redisparo → VERIFIED.
- **E64.** Notificação quando D-1 não fecha VERIFIED até 09:00 BRT (in-app + email). *Prova:* simular falha → notificação.
- **E65.** Corrigir `POST /listings/backfill-snapshots` (`vendas/router.py:59`): usa
  `get_items_visits_bulk` (endpoint LIFETIME proibido!) → trocar por `get_item_visits_on_day` por item.
  *Prova:* backfill de 1 dia → visitas == `time_window` (spot-check 5 anúncios).
- **E66.** Badge de confiança no frontend: dias VERIFIED exibem dado normal; INCOMPLETE exibem indicador
  "dados parciais" (UX honesta, padrão já usado nos cards). *Prova:* screenshot dos 2 estados.
- **E67.** Endpoint `GET /health/data-quality`: últimos 7 DailyClose por conta + % cobertura.
  *Prova:* curl retorna o quadro.
- **E68.** Backfill histórico do DailyClose (últimos 30 dias) para ancorar o histórico de confiança.
  *Prova:* 30 dias com status no banco.

## FASE 6 — MIGRAÇÃO DAS TELAS: todo mundo lê da fonte única (E69-E86)

- **E69.** Funnel → `aggregate_metrics` (era: dia UTC, sem Order, sem filtro — `service_analytics.py:34`).
  *Prova:* funnel(7d) == summary(7dias) em prod.
- **E70.** Sales-trend → `aggregate_metrics` por dia (mesma via do `/kpi/daily`).
  *Prova:* Σ sales-trend(7d) == summary(7dias) em prod.
- **E71.** Heatmap: trocar `payment_status == "approved"` pela constante `notin_(NON_SALE_PAYMENT_STATUSES)`
  (`service_analytics.py:416`). *Prova:* teste com order refunded → conta no heatmap.
- **E72.** `analise/service.py`: trocar `== "approved"` pela constante nas CTEs (:120,:133,:146,:157...).
  *Prova:* teste idem.
- **E73.** Cashflow (:1065): decidir caso a caso — projeção de recebíveis pode exigir `approved`
  legitimamente; se mantiver, comentar o porquê. *Prova:* decisão documentada no código + catálogo.
- **E74.** Financeiro: consolidar o bloco `_aggregate` DUPLICADO (:129 e :559) numa função única.
  *Prova:* diff de payload zero antes/depois (refactor puro).
- **E75.** Financeiro: `_parse_period` (:89) de data UTC/fim=ontem → dia BRT consistente com metrics.
  *Prova:* teste de janela; diferença documentada (só fuso).
- **E76.** Financeiro resumo + DRE → consumir `aggregate_metrics` (receita/pedidos/cancelados),
  mantendo por cima só a camada de custos/taxas/impostos (CMV, taxa ML, Simples 8,5%).
  *Prova:* receita financeiro(7d) == summary(7dias) em prod.
- **E77.** **Estender metrics.py**: `aggregate_metrics_by_listing(db, listing_ids, date_from, date_to)
  -> dict[listing_id, métricas]` — mesmas regras (Order aditivo, dias BRT, constante de status).
  Pré-requisito para migrar análise/intel/financeiro-detalhado sem perder granularidade.
  *Prova:* teste: Σ breakdown == agregado (consistência por construção).
- **E78.** Financeiro detalhado + rentabilidade por SKU + timeline → breakdown por listing (E77).
  *Prova:* Σ por SKU == resumo do mesmo período.
- **E79.** `analise/service.py::get_analysis_listings` → breakdown por listing nas janelas 7/15/30d
  (mata: visitas sem dedup que inflam com dados legados). *Prova:* 3 anúncios: números da Análise == tela Vendas.
- **E80-E86.** intel/analytics, um service por etapa: **E80** `service_abc.py:57`, **E81**
  `service_pareto.py:36`, **E82** `service_comparison.py:45,74`, **E83** `service_distribution.py:52`,
  **E84** `service_inventory.py:56`, **E85** `service_forecast.py:93`, **E86** `service_insights.py:92` —
  migrar para breakdown (E77) ou, no mínimo, dedup por `snapshot_day` + janela BRT.
  *Prova (cada):* receita do ranking == receita summary do mesmo período.

## FASE 7 — TRAVA DEFINITIVA: paridade entre telas no pre-commit (E87-E89)

- **E87.** Teste `test_cross_screen_parity.py`: com a MESMA fixture, chama summary, daily, funnel,
  sales-trend e financeiro-resumo → exige igualdade EXATA de vendas/receita. Entra no núcleo do pre-commit.
  *Prova:* sabotar 1 módulo → teste falha; reverter.
- **E88.** Golden master v2: ampliar `test_metrics_characterization.py` cobrindo o payload pós-E52
  (fonte Order) + breakdown por listing (E77). *Prova:* núcleo roda <10s.
- **E89.** Prova visual final da fase: mesma métrica em 5 telas do frontend (screenshot) + curl dos 5
  endpoints — números idênticos. *Prova:* registro no vault com prints.

## FASE 8 — VERIFICAÇÃO CONTÍNUA + CAMPANHA DE TESTES DE TUDO QUE EXISTE (E90-E109)

- **E90.** Task Celery semanal `parity_check` (segunda ~10:00 UTC): roda a auditoria total internamente,
  grava `ParityRun`, notifica (in-app+email) se qualquer FAIL. *Prova:* disparo manual → notificação com placar.
- **E91.** Protocolo Maxwell/dev-browser (spot-check contra o painel real): criar `scripts/chrome_debug.bat`
  (`chrome.exe --remote-debugging-port=9222` — a falta disso quebrou a tentativa anterior); documentar no
  vault o roteiro: dev-browser conecta → Maxwell (`mercadolivre.com.br/maxwell/new-chat`) → perguntar para
  5 anúncios aleatórios "comissão em R$? visitas ontem? vendas hoje/7d? receita? estoque?" → comparar com o
  app → divergência vira bug no vault. Limites conhecidos: Maxwell recusa perguntas técnicas de API; não
  escala para massa (massa = harness E90). *Prova:* 1 rodada executada e registrada.
- **E92.** Relatório mensal de validação manual: gerar automaticamente o markdown com todos os anúncios
  (app) + colunas vazias "ML Real" para o Maikeo preencher 10 min/mês (amostragem humana).
  *Prova:* script gera o arquivo a partir do harness.
- **E93.** `test_forbidden_patterns.py` (CI): falha se aparecer (a) `/visits/items?ids` sem marcador
  `# lifetime-ok`; (b) leitura de `item["price"]` como fonte primária sem `# sale_price-fallback-ok`;
  (c) "mercadolivre" na URL do client; (d) leitura das colunas DEPRECATED do snapshot (E57) fora de
  metrics/audit. Marcar usos legítimos existentes. *Prova:* violação de propósito → CI falha.
- **E94-E109.** Characterization tests módulo a módulo (travar o comportamento ATUAL depois de
  verificado contra o painel/catálogo — 1 módulo por etapa, prova = testes verdes + nota no catálogo):
  - **E94** `vendas/service_kpi.py::list_listings` (colunas da tela Anúncios: você recebe, comissão, frete).
  - **E95** Vendas MT (`vendas_mt/`) — paridade fina já atingida 20/20 em 06/2026: travar com teste.
  - **E96** Pedidos (`vendas/` orders endpoints) — valores, frete, tarifa, líquido por pedido.
  - **E97** Financeiro P&L com custos conhecidos (fixture com CMV + taxa + Simples 8,5% → resultado exato).
  - **E98** Análise de anúncios (janelas 7/15/30d coerentes entre si).
  - **E99** Reputação (nível, claims, 60d = espelho da API).
  - **E100** Alertas (`alertas/` evaluate: condições disparam certo; sem falso positivo com dado parcial).
  - **E101** Produtos/margem (`produtos/`, calculadora: preço − custo − taxa − frete = margem).
  - **E102** Concorrência (`concorrencia/` snapshots de concorrente, posição).
  - **E103** Atendimento (SLA, tempos, contagens).
  - **E104** Perguntas (sync 15min, auto-answer só high-confidence).
  - **E105** Publicidade (fallback honesto quando API não responde — nunca inventar ACOS).
  - **E106** Consultor/chat (números citados pelo chat == metrics.py; nunca cálculo próprio).
  - **E107** Notificações (dedupe, canais).
  - **E108** Auth/multi-conta (filtro por conta consistente em TODAS as rotas — bug histórico).
  - **E109** Export CSV (colunas = tela; preço de tabela vs você recebe distintos).

## BLOCO B — Fechar o último elo: o número RENDERIZADO na tela (E121-E123)

- **E121.** Gerar tipos TypeScript do OpenAPI do backend (`openapi-typescript`) e adotar nos hooks de
  API do frontend — campo renomeado no backend quebra o BUILD, nunca a tela em silêncio.
  *Prova:* renomear 1 campo de propósito → `npx vite build` falha; reverter.
- **E122.** Teste E2E (Playwright): login → Dashboard e Vendas → extrair os números renderizados nos
  cards → comparar com a resposta da API na mesma sessão. Entra no CI como smoke.
  *Prova:* sabotar a formatação de 1 card → E2E falha; reverter.
- **E123.** Teste E2E de formatação pt-BR: moeda (R$ 1.234,56), percentual e milhar nos cards
  principais — bug clássico de tela que nenhum teste de backend pega. *Prova:* teste verde no CI.

## BLOCO C — Operação para o dono não-dev (E124-E126)

- **E124.** Tela "Saúde dos Dados" no app (rota admin): status do DailyClose (7 dias), última rodada
  de paridade + placar, cobertura de snapshots, saúde dos tokens, `last_sync` por conta. Consome
  `/health/sync`, `/health/data-quality` (E67) e `/audit/parity/history` (E47).
  *Prova:* screenshot da tela com dados reais.
- **E125.** Comando `/checkup` no Claude Code (`.claude/commands/checkup.md`): roda núcleo de testes +
  `check_parity.sh` + `/health/sync` e imprime resumo único (verde/vermelho por bloco). O Maikeo audita
  o sistema inteiro com 1 comando. *Prova:* rodar `/checkup` e ver o resumo.
- **E126.** Template de relatório de fim de sessão (`docs/handoff/TEMPLATE_SESSAO.md`): o que mudou
  (etapas E##), provas executadas com saída, paridade antes/depois, pendências. TODA IA executora
  preenche ao encerrar. *Prova:* template commitado + referenciado nas regras do CLAUDE.md.

## BLOCO D — Infraestrutura de teste mais forte (E127-E130)

- **E127.** Fixture "golden day": exportar 1 dia real completo (orders + snapshots das 2 contas,
  anonimizando comprador) como JSON versionado em `backend/tests/fixtures/`; characterization tests
  passam a usar dado realista em vez de sintético. *Prova:* núcleo roda sobre a fixture real.
- **E128.** CI: job com Postgres efêmero (service container) que roda `alembic upgrade head` do zero +
  a suíte — migration quebrada falha no CI, não derruba prod via start.sh. *Prova:* migration sabotada
  → CI vermelho; reverter.
- **E129.** Harness de auditoria: concorrência limitada + retry com backoff em 429/5xx nas chamadas ML
  (a auditoria total multiplica chamadas; sem isso, rate limit gera FAIL falso).
  *Prova:* rodada completa sem erros de rate limit.
- **E130.** Sentry (ou equivalente) ativo no backend em prod: exceções de Celery/API visíveis com
  alerta — o "Celery parou em silêncio" passa a gritar. *Prova:* exceção de teste aparece no Sentry.

## BLOCO E — Proteção do fluxo git (E131)

- **E131.** Branch protection na `main` (GitHub): push só com CI verde (required status checks).
  Mudanças sensíveis (a partir da Fase 4) entram via PR `staging` → `main`.
  *Prova:* push com CI vermelho é rejeitado.

## FASE 9 — ENCERRAMENTO (E110-E116)

- **E110.** Rodar suíte completa + cobertura: meta ≥55% mantida (ideal 60%+ com os novos testes).
  *Prova:* relatório de cobertura no CI.
- **E111.** Auditoria total final em prod (todos os blocos) + comparação com BASELINE inicial.
  *Prova:* baseline final commitado lado a lado.
- **E112.** Rodada Maxwell final (E91) com 5 anúncios + conferência manual do Maikeo no painel (10 min).
  *Prova:* zero divergência não explicada.
- **E113.** Atualizar TODO o vault: Plano Mestre (concluídos/pendências), Bug Tracker, ADRs, catálogo linkado.
  *Prova:* notas atualizadas com data.
- **E114.** Atualizar `docs/handoff/`: o que mudou, decisões, estado final — para a próxima IA não
  recomeçar do zero. *Prova:* handoff v2 commitado.
- **E115.** Limpeza: remover código morto identificado no caminho (ex.: `_period_to_dates`), SEM poda de
  features. *Prova:* suíte verde.
- **E116.** Relatório final ao Maikeo: link + credenciais + placar de paridade + os 5 números principais
  conferidos contra o painel (print). *Prova:* entregue.

---

## CRITÉRIOS DE ACEITE GLOBAIS (Definition of Done do plano inteiro)
1. **Paridade ≥98%** nos checks estáveis (dias fechados/VERIFIED) — partida: 81,3%.
2. **Aditividade provada:** Σ`/kpi/daily` == `/kpi/summary` exatamente.
3. **Telas idênticas:** summary = daily = funnel = sales-trend = financeiro = análise para o mesmo período.
4. **Catálogo completo:** todo campo de toda tela + todo endpoint interno + todo método do cliente ML
   com dono + fonte ML + check (zero órfãos sem justificativa).
5. **Ingestão provada:** DailyClose VERIFIED diário; dado parcial sinalizado na UI, nunca silencioso.
6. **Regressão bloqueada em 4 camadas:** pre-commit (núcleo+cross-screen) → CI (suíte+forbidden) →
   paridade semanal automática → spot-check Maxwell/manual mensal.
7. **Um fato, um dono** implementado; colunas duplicadas de snapshot deprecated e sem leitores.
8. Nada reescrito do zero; nenhuma feature removida; tudo registrado no vault.

---

## ESTRATÉGIA DE EXECUÇÃO: agentes e sub-agentes

> O Maikeo não é dev (5 meses de experiência com Claude Code). Esta seção existe para que quem
> executar o plano — outro modelo de IA — saiba COMO se organizar, não só O QUE fazer.

### Regra base (já é Regra Absoluta #6 deste projeto): **um agente por arquivo, nunca dois escrevendo ao mesmo tempo**
Isso não é preferência — é a regra que este projeto já aprendeu na marra em 4 meses. Dois agentes
editando o mesmo arquivo em paralelo é a receita para o "conserta um, quebra outro" voltar.

### Quando usar 1 agente sequencial (padrão recomendado para a maior parte do plano)
- Fases 0, 1, 3 e Bloco A + Fases 4, 5, 6 (quando arquivos se cruzam) e 7: tocam arquivos
  compartilhados (`metrics.py`, `constants.py`, `models.py`, `tasks_orders.py`) que TUDO depende.
  Um agente, um passo de cada vez, prova antes de avançar.
- Qualquer migration de banco (Alembic): sempre sequencial, sempre com `alembic current` conferido
  antes e depois.
- A troca de E52 (Order aditivo) em particular: é o ponto mais sensível do plano inteiro. Fazer com
  UM agente, em UMA sessão focada, com o modo sombra (E120) rodando antes de virar a chave.

### Quando subagentes em paralelo SÃO seguros (ganho real de velocidade)
- **Fases 1B, 2 e 2B (Auditoria do cliente ML + Catálogo por tela + Auditoria por endpoint):** são
  leitura/documentação, não escrita de código de produção. Pode rodar 2-3 agentes Explore em
  paralelo, cada um em métodos/telas/routers diferentes — zero risco de conflito porque nenhum edita
  código, só preenche `docs/data_catalog.md` (usar seções, não sobrescrever o arquivo inteiro).
- **Fase 6 (migração de telas), DESDE que os arquivos não se cruzem:** ex., migrar o Funnel
  (`vendas/service_analytics.py`) em paralelo com migrar o Financeiro (`financeiro/service.py`) —
  arquivos diferentes, seguro. NUNCA paralelizar duas etapas que tocam o MESMO arquivo (ex.: E69
  Funnel e E71 Heatmap são o MESMO arquivo `service_analytics.py` — sequenciais, mesmo "na mesma fase").
- **Fase 8, characterization tests por módulo (E94-E109):** cada etapa escreve testes NOVOS em
  arquivos distintos (`test_xxx.py`) — seguro paralelizar 2-3 por vez. Blocos B/C/D/E também são
  majoritariamente paralelizáveis entre si (frontend types, CI, Sentry, branch protection são áreas
  isoladas).
- Regra prática: antes de rodar 2 agentes em paralelo, checar se as etapas escrevem em arquivos
  diferentes (grep rápido). Se há QUALQUER dúvida, rodar sequencial — o custo de tempo é menor que
  o custo de destrinchar um conflito depois.

### Mapeamento por NECESSIDADE aos sub-agentes que o projeto já define
Este projeto tem 4 subagentes nomeados em `msm_pro/CLAUDE.md` (`/dev`, `/qa`, `/insights`, `/ml-api`).
Em vez de "agente genérico", use este mapa — é o que a Fase 1B já aplica na prática em cada etapa:

| Necessidade da etapa | Agente | Por quê |
|---|---|---|
| Validar endpoint/campo ML contra a documentação ANTES de codar | **`ml-api`** | É a função dele por definição — consulta `docs/ml_endpoints_canonical.md` como fonte da verdade |
| Implementar/editar código (fix, migration, refactor) | **`dev`** | Sempre 1 por arquivo, sequencial nas etapas que tocam núcleo compartilhado |
| Verificar/testar código já implementado, apontar bugs antes de prod | **`qa`** | Roda depois do `dev` na mesma etapa ou etapa seguinte — nunca no lugar da prova exigida |
| Decisão sobre manter/remover algo, ou classificar contra decisão arquitetural existente | **`insights`** ou relatório direto ao Maikeo | `insights` tem contexto de mercado/arquitetura; decisões de remoção SEMPRE voltam pro Maikeo, nunca autônomas |
| Exploração ampla de código para entender um módulo antes de mexer | **Explore** (genérico, read-only) | Não é subagente do projeto — é o agente de busca do Claude Code, seguro sempre |
| Pesquisa/consulta ao MCP `msm-database` ou `obsidian` | Sessão principal ou **Explore** | Não precisa de autenticação especial como o MCP do ML |

Regra prática: numa etapa típica de bug-fix (ex.: E9, estoque de variações), o fluxo é
`ml-api` (confirma o endpoint certo) → `dev` (implementa) → `qa` (testa e aponta furo) → você aprova
a prova. Isso já é o padrão que a Fase 1B usa explicitamente em cada uma das 12 etapas (EC1-EC12).

### Quando usar sub-agentes só para PESQUISA (não escrita) — sempre seguro
- Validar endpoint no MCP oficial do ML (mas ⚠️ só o agente PRINCIPAL tem o token autenticado —
  nunca delegar essa validação específica a um subagente).
- Explorar código para entender um módulo antes de mexer (agente tipo Explore, read-only).
- Investigar uma divergência específica via MCP `msm-database` (consulta, não escrita).

### Recomendação final para o Maikeo (não-dev)
Prefira o **agente único sequencial** como padrão, mesmo sendo mais lento. Você consegue acompanhar
"fez a etapa X, aqui a prova, próxima etapa" um passo de cada vez. Paralelismo é mais rápido mas
gera vários diffs simultâneos — mais difícil pra você auditar sem background técnico. Reserve
paralelismo só para as fases marcadas acima como seguras (1B, 2, 2B, partes da Fase 6, Fase 8 e
Blocos B-E), e mesmo assim peça ao executor para reportar cada agente separadamente, não um resumo
fundido.

---

## ORDEM E RITMO
- Fases sequenciais na ordem numérica: 0 → 1 → 1B → 2 → 2B → 3 → [Bloco A] → 4 → 5 → 6 → 7 → 8 →
  [Blocos B-E] → 9. **Exceção:** Fases 1B, 2 e 2B podem andar em paralelo entre si e com a Fase 1
  (são leituras, ver critério de paralelismo acima). Blocos B-E do fim podem começar assim que a
  Fase 7 estiver pronta, sem esperar a Fase 8 terminar.
- **E52 (a troca max→Order) é o passo mais sensível do plano inteiro** — só executar com Fases
  0-1-1B-2-2B-3 completas, Bloco A pronto, E49-E51 provados e golden master ativo. Nunca paralelizar
  esta etapa.
- Ritmo sugerido: Fases 0+1+1B = 2-3 sessões; Fases 2+2B = 2-3 sessões (paralelizável); Fase 3 = 1-2;
  Bloco A + Fase 4 = 2 sessões dedicadas; Fase 5 = 1-2; Fase 6 = 2-3; Fase 7 = 1; Fase 8 = 2-3;
  Blocos B-E = 2; Fase 9 = 1. Total: ~16-21 sessões de trabalho focado.
- Cada sessão termina com relatório curto ao Maikeo (usar o template de E126, assim que existir;
  antes disso, relatar manualmente: etapas feitas, prova de cada uma, paridade antes/depois).

## SE FOR PRECISO DIVIDIR EM ARQUIVOS SEPARADOS DEPOIS
Se em algum momento você (ou uma sessão futura) precisar entregar partes deste plano a execuções
isoladas, o corte recomendado por risco/dependência é: **Diagnóstico** (Fases 0, 1, 1B, 2, 2B, 3 —
baixo risco, sem pré-requisito) → **Reestruturação de Dados** (Bloco A, Fases 4-7 — alto risco,
exige o Diagnóstico completo) → **Operação Contínua** (Fase 8, Blocos B-E, Fase 9 — exige a
Reestruturação completa). É um corte mecânico pelos títulos `## FASE`/`## BLOCO` acima — os números
de etapa (E1-E131, EA1-EA18, EC1-EC12) não precisam ser renumerados, funcionam como IDs globais em
qualquer arranjo de arquivos.
