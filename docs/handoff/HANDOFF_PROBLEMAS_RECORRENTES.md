# Handoff — Problemas Recorrentes do MSM_Pro (para planejamento com Fable 5)

> **Propósito deste arquivo:** dar ao modelo Fable 5 (ou qualquer IA que vá planejar)
> o mapa COMPLETO do que sempre voltou a quebrar em ~4 meses, quantas vezes mexemos,
> a causa-raiz de cada um, e **a solução que o Maikeo apresentou** para cada tema.
> É a memória dura do projeto — para o plano nascer sabendo onde estão as minas.
>
> Base: 358 commits (2026-03-10 → 2026-07-08). Contagem de `fix` por tema (msg de commit):
> `sync 30 · kpi 25 · railway 21 · token 20 · backfill 16 · orders 15 · celery 15 ·
> snapshot 14 · visit 11 · frete 8 · sale_price 5 · paridade 4 · timezone/brt 5`.
>
> Contexto do produto: **MSM_Pro é um ESPELHO do painel do vendedor do Mercado Livre.**
> Fonte da verdade = ML. Divergência = bug do MSM_Pro, nunca o contrário.

---

## 0. O padrão-mãe (por que tudo isto recorreu)

A causa-raiz nunca foi um bug isolado — foi **método**:
1. Tarefa declarada "pronta" sem provar o número contra o painel do ML.
2. Sem rede de regressão nos números do núcleo → conserta A, quebra B **em silêncio**.
3. Mesma métrica calculada em vários lugares → conserta um, os outros ficam errados.

Em 2026-07-07 foi montada a blindagem (golden master + gate de paridade + pre-commit).
Este handoff é para o Fable 5 planejar **o que blindar/consertar A SEGUIR** com esse mapa.

---

## 1. Clusters de problemas recorrentes

Cada cluster: **sintoma → causa-raiz → solução que o Maikeo apresentou → status → arquivos**.

### CLUSTER A — KPI / métricas divergindo do painel do ML  ⭐ (25 commits `kpi` + 5 `metric`)
- **Sintoma:** vendas/receita/conversão do app ≠ painel do ML; telas divergindo entre si
  (summary vs daily vs funnel); conversão absurda (4400%); "ontem" zerado.
- **Causa-raiz:** agregação reimplementada em cada rota; `max(Order)` não-aditivo; snapshot
  parcial contaminando; contagem por `snapshot.id` em vez de `DISTINCT listing_id`.
- **Solução apresentada:** (1) **fonte única** `metrics.py::aggregate_metrics` — toda rota consome
  ela; (2) **`COUNT(DISTINCT listing_id)`** (Regra Absoluta #7); (3) **1 snapshot/dia por anúncio**
  (constraint `uq_listing_snapshot_day`); (4) fallback para tabela `Order` quando snapshot zera;
  (5) reembolsadas contam no total (espelha ML).
- **Status:** 🟡 núcleo blindado (golden master 2026-07-07); FALTA migrar funnel/sales-trend/
  financeiro/analytics para `metrics.py` (ainda reimplementam).
- **Arquivos:** `backend/app/vendas/metrics.py`, `service_kpi.py`, `tests/test_metrics_parity.py`,
  `tests/test_metrics_characterization.py`. Vault: `08 - Bugs e Fixes/Bug KPI inconsistência multi-tela`.

### CLUSTER B — Visitas (semântica acumulado × dia; inflação)  (11 `visit` + 16 `backfill`)
- **Sintoma:** visitas sempre zero; depois visitas absurdas (>10k/dia); conversão contaminada.
- **Causa-raiz:** endpoint de visitas retorna **acumulado/lifetime**, não visitas do dia; backfill
  somava errado; cobertura de snapshots incompleta (~87,8%) subcontava.
- **Solução apresentada:** usar **`/items/{id}/visits/time_window`** (visitas DO dia); safeguards
  (descarta >3k/dia); preservar visita anterior quando bulk falha; guarda anti-corrupção
  (`0 < visitas < vendas` → indisponível).
- **Status:** 🟡 corrigido no fluxo principal; cobertura de snapshots ainda <100%.
- **Arquivos:** `backend/app/jobs/tasks_listings.py`, `mercadolivre/client.py` (`get_item_visits_on_day`),
  endpoint `POST /listings/backfill-snapshots`.

### CLUSTER C — Frete e comissão do vendedor  (8 `frete` + 3 `shipment` + 3 `comiss`)
- **Sintoma:** "você recebe" e lucro errados; frete do vendedor errado; comissão errada.
- **Causa-raiz:** pegadinhas da API ML — `list_cost` já vem líquido; frete real é `senders.cost`;
  comissão vem de `order_items[].sale_fee` (não `marketplace_fee`); precisa header `x-format-new`.
- **Solução apresentada:** frete real via **`/shipments/{id}/costs` → `senders.cost`**; frete grátis
  usa **`list_cost` já líquido** (não subtrair discount); comissão via `listing_prices` +
  `logistic_type` + `shipping_mode`; preço via **`sale_price`**.
- **Status:** 🟢 corrigido 2026-06-30/07-08 (inclui na paridade). Risco de regressão alto — travar.
- **Arquivos:** `backend/app/mercadolivre/client.py`, `app/vendas/service_parity_audit.py`.
  Vault: `08 - Bugs e Fixes/Bugs de Endpoints ML (Auditoria ARCH-014)`.

### CLUSTER D — Preço: campo `price` depreciado  (5 `sale_price`)
- **Sintoma:** preço/`voce_recebe` desatualizado; preço promocional errado.
- **Causa-raiz:** campo `price` do `/items` está **depreciado**; o efetivo é `/items/{id}/sale_price`.
- **Solução apresentada:** migrar TODA leitura de preço para **`/items/{id}/sale_price`**; erradicar
  uso de `price` cru. (Regra registrada em `feedback_price_api.md`.)
- **Status:** 🟢 corrigido; vigiar reintrodução. Vault: `08 - Bugs e Fixes/Fix Preço sale_price`.

### CLUSTER E — Sync / Celery / async loop / conexões Postgres  (30 `sync` + 15 `celery`)
- **Sintoma:** sync paralisado por dias; `Event loop is closed`; `TooManyConnections`; timeout 300s.
- **Causa-raiz:** singleton aioredis entre loops; objetos ORM acessados após fechar sessão; frete
  sequencial estourando time limit; concurrency/pool alto demais para o Postgres do Railway.
- **Solução apresentada:** **sessão isolada por conta** no sync; extrair atributos locais antes do
  loop; **remover singleton aioredis**; Redis SETNX lock (não `asyncio.Lock`); reduzir
  concurrency 4→3 e pool_size; time limit 20-27min em `sync_orders/backfill`.
- **Status:** 🟡 estabilizado, mas frágil — é o hotspot #1 (30 commits). Candidato a refatoração.
- **Arquivos:** `backend/app/jobs/tasks.py`, `tasks_listings.py`, `tasks_tokens.py`,
  `app/mercadolivre/client.py`, config de Celery/pool.

### CLUSTER F — Fuso horário BRT  (3 `timezone` + 2 `brt`)
- **Sintoma:** -2 pedidos/dia; "ontem" com janela errada; comparações UTC×BRT furando.
- **Causa-raiz:** dia do painel ML é **BRT (-03:00)**; código misturava UTC.
- **Solução apresentada:** **ancorar todo "dia" no início do dia BRT**; `Order.order_date` comparado
  em UTC convertido de BRT; `snapshot_day` = data BRT.
- **Status:** 🟢 corrigido nos fluxos conhecidos; qualquer nova agregação por dia precisa repetir o padrão.

### CLUSTER G — OAuth token refresh / reauth / backfill pós-reconexão  (20 `token`)
- **Sintoma:** token expira em silêncio; race condition no refresh; pedidos faltando após reconectar.
- **Solução apresentada:** auto-refresh antes de chamadas; `needs_reauth` visível; **backfill
  automático de pedidos após reconexão**; tokens criptografados (Fernet `EncryptedString`);
  notificação in-app + e-mail em falha.
- **Status:** 🟢 resolvido em grande parte.

### CLUSTER H — Deploy Railway  (21 `railway` + 4 `deploy`)
- **Sintoma:** build falha; código antigo volta; frontend não serve na porta certa; precisa forçar rebuild.
- **Causa-raiz:** confusão Dockerfile×nixpacks; `PORT` dinâmico; cache do Docker; `railway up` sobe temporário.
- **Solução apresentada:** **`git push origin main` → auto-deploy** (NUNCA `railway up`); `start.sh`
  roda `alembic upgrade head`; frontend via `Dockerfile.frontend` + Express SPA; `npx vite build`
  (evita erro de path alias do tsc); esperar 60s em 500 (rate limit). Deadlock de conexões:
  `railway down` + `up` da raiz + `RAILWAY_API_TOKEN`.
- **Status:** 🟢 fluxo estável hoje (Regra Absoluta #1). Vault: `project-deploy-railway-deadlock-conexoes`.

### CLUSTER I — Cards zerados / dados ML indisponíveis  (7 `cards`)
- **Sintoma:** cards do dashboard zerados quando o ML não retorna dado.
- **Solução apresentada:** **cards honestos** — mostrar "indisponível" em vez de 0 mentiroso.
- **Status:** 🟢 resolvido (decisão de UX honesta).

### CLUSTER J — Paridade com Mercado Turbo (aba "Vendas MT")  (3 `turbo` + 4 `paridade`)
- **Sintoma:** réplica do Mercado Turbo divergia (diff 20/20 → 0).
- **Solução apresentada:** cadeia ML correta — tarifa de `order_items[].sale_fee`; cupom no valor
  pago; Lucro Bruto só com custo cadastrado; auditoria diff item a item até bater 20/20.
- **Status:** 🟢 paridade fina atingida 2026-06-11. Base: `mercadoturbo_research/`.

### CLUSTER K — Product Ads (API não pública)  (3 `ads`)
- **Sintoma:** ACOS/ROAS não confiáveis; endpoint mudando.
- **Causa-raiz:** **API de Ads do ML não é pública/estável.**
- **Solução apresentada (decisão arquitetural):** fallback + UX honesta; não prometer o que a API não dá.
- **Status:** 🟡 aceito como limitação. Ver `docs/ml_architecture_blueprint.md`.

---

## 2. As soluções/princípios que o Maikeo SEMPRE apresenta

Estes são os "moldes de solução" recorrentes — o Fable 5 deve tratá-los como **axiomas**:

1. **Espelho do painel do ML.** Todo dado deve ser idêntico ao painel/relatório do vendedor.
   ML = fonte da verdade; divergência = bug do MSM_Pro. *(princípio mestre)*
2. **Provar antes de declarar pronto.** Validar número real em produção (curl + token) contra o
   painel ANTES de fechar. É o "erro recorrente nº 1". Hoje: `scripts/check_parity.sh`.
3. **Endpoints canônicos do MCP oficial do ML** (não inventar): vendas/receita=`/orders/search`;
   visitas-dia=`/items/{id}/visits/time_window`; reputação=`/users/{id}`; tendências=`/trends`;
   mais-vendidos=`/highlights`. Fonte: `backend/docs/ml_endpoints_canonical.md` + vault `02 - API ML`.
4. **Comparar com ferramentas de referência:** UpSeller, Nubimetrics, Mercado Turbo, Bling.
5. **`COUNT(DISTINCT listing_id)`** — nunca `COUNT(snapshot.id)`. *(Regra Absoluta #7)*
6. **Fonte única de agregação** — não reimplementar cálculo em cada tela.
7. **Git primeiro, deploy depois** — `git push origin main`, nunca `railway up`. *(Regra Absoluta #1)*
8. **Só blindar, sem podar (decisão 2026-07-07)** — estabilizar o que existe com rede de segurança
   antes de expandir ou reescrever. Reescrever do zero foi descartado.
9. **Registrar tudo no vault Obsidian** ao terminar (Plano Mestre + bugs + ADR).

---

## 3. Problemas AINDA em aberto (candidatos para o plano do Fable 5)

| # | Problema | Sev. | Onde |
|---|----------|------|------|
| 1 | Telas de vendas/receita ainda divergem (funnel/sales-trend/financeiro/analytics NÃO usam `metrics.py`) | Alta | `vendas/`, `financeiro/`, `analytics/` |
| 2 | Reputação `completed_sales_60d` pegava histórico all-time, não `metrics.sales.completed` | Média | `reputacao/service.py:125` (corrigido 06-30 — validar) |
| 3 | Cobertura de snapshots <100% (~87,8%) → visitas subcontadas | Média | jobs de sync |
| 4 | `/trends` e `/highlights` do ML NÃO implementados | Média | novo |
| 5 | Multi-conta inconsistente (MSM_PRIME + MSMPRIME) | Média | filtros multi-conta |
| 6 | Variação financeira +817% (base vazia gera % absurdo) | Baixa | `financeiro/` |
| 7 | Sync/Celery frágil (hotspot #1, 30 commits) — candidato a refatoração dura | Alta | `jobs/` |
| 8 | MCP Server sem autenticação | Alta | `mcp/` |
| 9 | Cobertura de testes ~32% (fora do núcleo) | Média | global |
| 10 | `list_listings` grande (dívida) | Média | `vendas/service_kpi.py` |
| 11 | SMTP prod bloqueado em ação humana (App Password) | Baixa | infra |
| 12 | WebSocket adiado | Baixa | `ws/` |

---

## 4. Cheat-sheet de pegadinhas da API do ML (conhecimento duro)

> Cada linha custou pelo menos um ciclo de retrabalho. O Fable 5 deve respeitar como fato.

- URL correta: **`api.mercadolibre.com`** (libre, com "b", `.com`). Nunca "livre".
- Preço efetivo: **`/items/{id}/sale_price`**. O campo `price` do `/items` está **depreciado**.
- Visitas do dia: **`/items/{id}/visits/time_window`** (o endpoint padrão devolve acumulado/lifetime).
- Frete real do vendedor: **`/shipments/{id}/costs` → `senders.cost`**.
- Frete grátis: **`list_cost` já vem líquido** — não subtrair desconto de novo.
- Comissão de venda: **`order_items[].sale_fee`** (não `marketplace_fee`); depende de
  `listing_type` (`gold_special`=clássico, `gold_pro`+fulfillment=full), `logistic_type`, `shipping_mode`.
- Shipment novo formato: enviar header **`x-format-new`**.
- Aplicar preço: via **`seller-promotions`**, não `PUT /items/{id}`.
- Taxas ML de referência usadas: **11% / 16%**.
- Reputação vendas 60d reais: **`seller_reputation.metrics.sales.completed`** (não somar histórico).
- Fuso do painel: **BRT (-03:00)** — ancorar todo "dia" em BRT.
- Ads: **API não pública/estável** — usar fallback honesto.
- Status de venda: `refunded`/`reembolsado` **conta** como venda (o painel conta); `cancelled`/`rejected` não.

---

## 5. O que o plano do Fable 5 deveria decidir

Perguntas abertas que um bom plano precisa resolver (não estão decididas):
1. **Ordem de ataque:** migrar todas as telas para `metrics.py` primeiro (mata Cluster A de vez) ou
   refatorar o sync/Celery (hotspot #1, Cluster E)?
2. **Refatorar o sync** vale o risco agora, ou blindar com testes de integração antes?
3. **Podar** (decisão adiada): quais features desligar? (Ads? WebSocket? módulos pouco usados?)
4. Implementar **`/trends` e `/highlights`** para fechar o espelho do painel?
5. Como garantir **cobertura de snapshots 100%** (raiz da subcontagem de visitas)?

### Antes de planejar, o Fable 5 deve ler:
- `msm_pro/CLAUDE.md` (Acordo de Trabalho / Definition of Done)
- `Cerebro_Obsidian/.../06 - Regras/Acordo de Trabalho com o Claude.md`
- `Cerebro_Obsidian/.../08 - Bugs e Fixes/Auditoria total — MSM_Pro vs paineis do ML (2026-06-27).md`
- `backend/docs/ml_endpoints_canonical.md` (endpoints canônicos)
- `backend/app/vendas/metrics.py` (fonte única) + `service_parity_audit.py` (harness de paridade)

---

## 6. Ferramentas de IA e dados disponíveis (o Fable 5 deve USAR estas)

Config real em `msm_pro/.mcp.json`. Ativar via `/mcp` no Claude Code.

### 6.1 Assistente de IA OFICIAL do Mercado Livre  ⭐ (MCP `mercadolibre-official`)
- **O que é:** o assistente/ferramenta oficial do ML — HTTP `https://mcp.mercadolibre.com/mcp`.
  Dá para **conversar/consultar a documentação oficial do ML**, validar endpoints, campos,
  formatos de resposta e parâmetros **contra a fonte da verdade, antes de implementar**.
- **Como usar:** ativar via `/mcp`; autenticar (`authenticate` → `complete_authentication`).
  **⚠️ Só autentica na SESSÃO PRINCIPAL — subagentes NÃO herdam o token.** Por isso a validação
  de endpoint ML deve ser feita pelo agente principal, nunca delegada a subagente sem token.
- **Quando usar (obrigatório):** ANTES de mexer em qualquer chamada ML (frete, comissão, preço,
  visitas, orders, reputação). É a ferramenta que teria evitado quase toda a seção 4 (o cheat-sheet
  de pegadinhas). Regra: nunca inventar endpoint/campo — perguntar ao MCP oficial.
- **Fonte canônica derivada:** `backend/docs/ml_endpoints_canonical.md` (ADR `14 - ADR/ARCH-2026-06-03`).

### 6.2 Banco de dados real (MCP `msm-database`)
- Consulta o Postgres do MSM_Pro sem escrever SQL à mão. Ferramentas: `query_snapshots`,
  `db_summary`, `list_accounts`, `list_products`, `check_competitors`, `get_alert_configs`.
- Usar para **inspecionar o dado real** ao investigar divergência (o que o app persistiu de fato).

### 6.3 Vault Obsidian (MCP `obsidian`)
- Ler/escrever/buscar o "Cérebro". Fonte de regras, bugs, ADRs e o Plano Mestre.
  Regra do projeto: **ler antes de mexer, registrar ao terminar.**

---

## 7. Protocolo de testes / verificação (O QUE RODAR)

> Definition of Done: **nada é "pronto" sem prova.** Em tarefa de dados, o número tem que
> bater com o painel do ML, comprovado. Detalhe em `msm_pro/CLAUDE.md` (Acordo de Trabalho).

**a) Núcleo de métricas (rápido, ~5s) — rode SEMPRE antes de commitar:**
```bash
cd backend && python -m pytest tests/test_metrics_characterization.py tests/test_metrics_parity.py -q
```
Golden master (trava o dicionário KPI inteiro) + paridade entre rotas. 9 testes.
Isto é o que impede "conserta um, quebra outro" **em silêncio**.

**b) Suíte completa (CI / antes de PR, ~5min):**
```bash
cd backend && python -m pytest tests/ -q
```
Baseline verde 2026-07-09: **1865 passed, 6 skipped, 6 xfailed, 1 xpassed**. É a base do gate do CI (`.github/workflows/ci.yml`, `--cov-fail-under=55`).

**c) Gate de paridade contra o ML REAL (portão de pronto p/ dados):**
```bash
TOKEN="<jwt>" scripts/check_parity.sh [YYYY-MM-DD]
```
Chama `GET /api/v1/vendas/audit/parity` (harness `service_parity_audit.py`) e **sai com erro se
qualquer métrica divergir** do painel do ML. É o "prove o número" automatizado.

**d) Pre-commit (automático):** `.git/hooks/pre-commit` roda o núcleo (a) e **bloqueia commit com
regressão** (exit 1). Rápido de propósito para não ser burlado; a suíte completa fica no CI.

**e) Token real para curl (Regra Absoluta #2):**
```bash
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

**Regra de ouro dos testes:** mudou um número de propósito? Atualize o golden master
(`test_metrics_characterization.py`) no MESMO commit, justificando. Quebrou sem querer? É regressão — reverta.

---

## 8. O que foi feito nesta sessão (blindagem 2026-07-07 → 07-09)

**Diagnóstico aceito pelo Maikeo:** em 4 meses (151 `fix` vs 90 `feat`) a sensação de "acerto 5%"
e "conserta um, quebra outro" vinha do **método**, não do código — pronto sem prova + sem rede de
regressão. As regras certas já existiam (memória: "erro recorrente nº 1"), mas dependiam de boa
vontade e não colavam.

**Decisões tomadas:**
- **Só blindar, sem podar** (estabilizar antes de expandir). Reescrever do zero foi **descartado**
  (perderia 151 correções de pegadinhas reais do ML).
- **Bloqueio mecânico** (não checklist opcional): teste que bloqueia, hook que força.
- Acordo de Trabalho **nos dois lugares**: curto executável no `CLAUDE.md` + explicativo no vault.

**Construído (tudo aditivo — nenhum código de produção alterado):**
- `backend/tests/test_metrics_characterization.py` — golden master do núcleo (rede de regressão).
- `scripts/check_parity.sh` — gate de paridade contra o ML real (portão de pronto).
- `.git/hooks/pre-commit` — robustecido (path do repo dinâmico; roda o núcleo; bloqueia regressão).
- `msm_pro/CLAUDE.md` — seção "Acordo de Trabalho (Definition of Done)".
- Vault `06 - Regras/Acordo de Trabalho com o Claude.md` — versão didática (regressão, anti-reescrita,
  strangler fig, 6 práticas, o que o Maikeo deve fazer).

**Provado (não assumido):**
- Sabotei `metrics.py` de propósito → o golden master **falhou** apontando `preco_medio 101≠100` → revertido.
- Pre-commit **bloqueia** regressão (exit 1) e **libera** estado limpo (~5s).
- Suíte completa **verde**: 1865 passed.

**Handoff (2026-07-09):** este documento, para o plano no Fable 5.

**⚠️ Pendente de decisão do Maikeo:** commitar a blindagem (nada foi commitado ainda) e, quando
quiser, a **poda** que foi adiada.

---

*Gerado em 2026-07-09 a partir do histórico git completo (358 commits) + `.mcp.json` + vault + memória do projeto.*
