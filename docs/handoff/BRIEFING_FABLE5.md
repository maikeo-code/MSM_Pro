# MSM_Pro — Briefing Completo para Planejamento com Fable 5

> Gerado em: 2026-07-09
> Propósito: documento honesto de todos os problemas recorrentes, tentativas, o que funcionou e o que não funcionou. Para criar um plano de ação robusto.

---

## 1. O QUE É O MSM_Pro

Dashboard de vendas do Mercado Livre (ML). O **princípio mestre** é: o MSM_Pro deve ser um espelho exato do painel do vendedor ML. Qualquer divergência é bug do MSM_Pro, não "tolerância aceitável".

**Stack:** FastAPI + PostgreSQL + Redis + Celery (backend) | React 18 + TypeScript + Vite (frontend) | Deploy Railway (auto via git push).

**Dados:** 2 contas ML (MSM_PRIME: ml_user_id 2050442871 | MSMPRIME: ml_user_id 90599588), 31 anúncios ativos, 39 SKUs cadastrados.

---

## 2. AUDIT DE PARIDADE ATUAL (2026-07-07, 134 checks)

### O que está 100% correto
| Métrica | Resultado | Como foi corrigido |
|---------|-----------|-------------------|
| Preço de venda | 31/31 PASS | Usar `/items/{id}/sale_price` em vez de `item["price"]` (depreciado) |
| Comissão por anúncio | 31/31 PASS | `/sites/MLB/listing_prices` com `logistic_type + shipping_mode=me2` |
| Pedidos do dia | 2/2 PASS | Comparar Orders DB vs `/orders/search` com filtro BRT |
| Unidades vendidas | 2/2 PASS | Idem |
| Receita do dia | 2/2 PASS | R$ 3.082,51 (MSM_PRIME) + R$ 6.495,71 (MSMPRIME) — exatos |
| Reclamações | 2/2 PASS | |

### Bugs confirmados ainda abertos
| Métrica | Resultado | Divergência |
|---------|-----------|------------|
| Estoque | 27/31 PASS, 4 FAIL | MLB5276909636: ML=69, App=19 (72%); MLB7118364802: ML=69, App=19 (72%); MLB6620170054: ML=33, App=5 (84%) |
| Visitas | 12/31 PASS, 19 FAIL | MLB5982716652: ML=1, App=7 (600%); 14 outros com diff de timing (1-5 visitas, inevitável) |
| Reputação vendas 60d | 0/2 PASS | MSM_PRIME: ML=2150, App=2034 (5.4%); MSMPRIME: ML=1285, App=1082 (15.8%) |

---

## 3. HISTÓRICO COMPLETO DE BUGS E TENTATIVAS

---

### BUG #1 — Snapshots duplicados / dados inflados
**Status:** ✅ RESOLVIDO (mas levou 4+ meses e várias tentativas)

**Sintoma:** Mesma venda contada múltiplas vezes. Visitas infladas. Um dia de dados tinha 651 vendas quando a realidade era 119.

**Tentativas que NÃO funcionaram:**
- Sprint 1-4: sem nenhuma proteção → qualquer rerun do Celery duplicava dados
- Safeguard `if visitas > 3000: rejeitar` → gambiarra, não resolve causa raiz
- Filtrar por UTC ao fazer upsert → timezone errada, ainda duplicava

**O que o usuário propôs:** "Não pode ter mais de 1 snapshot por anúncio por dia."

**Fix que funcionou (Fase 1, commit f1fe453):**
- Coluna `snapshot_day` (date BRT) na tabela `ListingSnapshot`
- `UniqueConstraint("listing_id", "snapshot_day")` no banco
- Listener `before_insert` que faz upsert (não insert) filtrado por `snapshot_day`
- Migration 0033 defensiva com backup table para dados antigos
- Resultado: visitas 128.487 → 16.489 (correto), vendas 651 → 119 (== Orders reais)

**Lição:** O problema não era código, era arquitetura de dados. Sem constraint no banco, qualquer código pode duplicar.

---

### BUG #2 — Campo `item["price"]` depreciado (ML descontinuou em março/2026)
**Status:** ✅ RESOLVIDO em dois lugares diferentes (regressão no segundo)

**Sintoma:** Preço exibido era R$ 869,05 quando o produto estava em promoção por R$ 446,77. Parecia certo mas estava errado.

**Causa:** O ML descontinuou `GET /items/{id} → price` em março/2026. Para itens em promoção, `item["price"]` retorna o preço original (sem desconto), não o preço real que o comprador paga.

**Primeira ocorrência (Sprint 8, março/2026):**
- Descoberta: MLB6205732214 retornava price=50.70 mas vitrine mostrava R$57.38
- Fix: `tasks_listings.py` passou a usar `GET /items/{id}/sale_price` como fonte primária
- Resultado: preço correto no sync diário

**Segunda ocorrência (2026-07-07):** O `service_parity_audit.py` (arquivo criado depois) também usava `item.get("price")` — causava 18 FAILs falsos de preço no harness de paridade.
- Fix: usar `get_item_sale_price()` também no audit (commit 64dd13c)

**Lição recorrente:** O campo depreciado está em vários lugares. Toda vez que se cria um arquivo novo que lê itens ML, tende-se a usar `item["price"]` por ser o campo mais óbvio. Precisaria de busca em todo o código e documentação explícita proibindo o campo.

---

### BUG #3 — Visitas lifetime vs visitas do dia
**Status:** ✅ RESOLVIDO (Fase 3, commit fccbf48)

**Sintoma:** Visitas infladas absurdamente. Totais impossíveis (> 100.000 visitas por dia).

**Causa:** O endpoint `/visits/items?ids={id}&date_from=X&date_to=Y` ignora os parâmetros de data e retorna **LIFETIME** (acumulado de 2 anos). Isso não está documentado claramente.

**Tentativas que NÃO funcionaram:**
- Passar date_from/date_to no `/visits/items?ids=` → ignorado, retorna lifetime mesmo assim
- Safeguard para rejeitar visitas > 3.000 → gambiarra

**Fix que funcionou:**
- Endpoint correto para visitas de 1 dia: `/items/{id}/visits/time_window?last=1&ending={dia+1T00:00:00-03:00}`
- Parâmetro `ending` é **exclusivo** (não inclusivo)
- Novo método `client.get_item_visits_on_day(mlb, day)` encapsula a lógica
- Sync diário e backfill migrados para o novo método

**Lição:** A documentação oficial do ML às vezes omite comportamentos críticos. Testar com token real é obrigatório antes de declarar funcionando.

---

### BUG #4 — KPI inconsistente entre telas (4 números diferentes para o mesmo período)
**Status:** 🟡 PARCIALMENTE RESOLVIDO

**Sintoma (detectado 2026-06-27):** Para os ÚLTIMOS 7 DIAS, vendas/pedidos/receita divergem:
| Endpoint | Vendas | Receita |
|----------|--------|---------|
| /kpi/summary (7d) | 355 | R$ 38.833,58 |
| /kpi/daily (soma 7 dias) | 358 | R$ 38.978,02 |
| /analytics/funnel (7d) | 327 | R$ 36.750,46 |
| /sales-trend (7d) | — | R$ 37.529,61 |

**Causas raiz:**
1. **Reconciliação `max()` é não-aditiva:** `summary` usa 1 chamada de 7d (max(Σsnap, Σorder)); `daily` soma 7 chamadas de 1 dia cada (Σ max(snapᵢ, orderᵢ)). Matematicamente: Σmax ≥ max(Σ,Σ) sempre → daily sempre maior
2. **Funnel nunca migrado para metrics.py:** ainda tem agregação própria
3. **Sales-trend tem cálculo próprio:** mesma duplicidade

**Fix parcial (Fase 2, commit metrics.py):**
- Criado `backend/app/vendas/metrics.py` como fonte única com `aggregate_metrics()`
- `_kpi_single_day` e `_kpi_date_range` viram wrappers
- summary e daily agora usam metrics.py

**O que ainda falta:**
- Funnel (`service_analytics.py`) ainda com lógica própria
- Sales-trend ainda com lógica própria
- A reconciliação `max()` é matematicamente errada para múltiplos dias
- Fix definitivo: tornar `Order` a fonte única e aditiva de vendas/pedidos/receita. `Snapshot` apenas para visitas e estoque.

---

### BUG #5 — Frete errado nas orders (R$0 ou valor incorreto)
**Status:** ✅ RESOLVIDO (commit 4fc4ba1, 2026-06-30)

**Sintoma:** Custo de frete nas orders aparecia como R$0 mesmo para produtos com frete pago.

**Tentativas que NÃO funcionaram:**
- Usar `order["shipping"]["cost"]` → campo presente mas incorreto/zero para frete ME2
- Usar campo direto do order response → ML não expõe custo real do vendedor no order

**Fix que funcionou:**
- Endpoint correto: `GET /shipments/{id}/costs → senders[].cost`
- O custo que o vendedor paga fica em `senders[0].cost` (não em outros campos do order)
- Novo método `fetch_seller_shipping_cost()` no client

**Lição:** ML tem endpoints diferentes para dados do comprador vs dados do vendedor. O custo de frete do vendedor não está no order — precisa de chamada adicional.

---

### BUG #6 — Comissão calculada errada (taxas hardcoded)
**Status:** ✅ RESOLVIDO

**Sintoma:** Comissão de 11% aplicada quando era 16%, ou vice-versa, dependendo do tipo de anúncio.

**Causa:** Código tinha taxas hardcoded (11% Clássico, 16% Premium) sem considerar categoria, logística, ou o tipo real do anúncio.

**Fix que funcionou:**
- Endpoint correto: `GET /sites/MLB/listing_prices?price={preco}&category_id={cat}&listing_type_id={lt}&logistic_type={full|me2}&shipping_mode=me2`
- Resposta tem `sale_fee_amount` (valor exato em reais)
- Parâmetro `logistic_type` é obrigatório para resultado correto

---

### BUG #7 — Reputação usando all-time em vez de 60 dias
**Status:** ✅ RESOLVIDO (commit anterior)

**Sintoma:** Vendas para cálculo de reputação mostrava número inflado (histórico de 2+ anos), não os 60 dias que o ML usa para calcular o nível de vendedor.

**Causa:** Código usava `transactions.completed` (acumulado total) em vez de `metrics.sales.completed` (60 dias — o campo que o painel do ML usa).

**Fix:**
- `reputacao/service.py:125`: usar `sr["metrics"]["sales"]["completed"]` como fonte primária
- Fallback para `transactions.completed` apenas se o campo estiver ausente

---

### BUG #8 — Estoque errado em produtos com variações (ABERTO)
**Status:** 🔴 ABERTO — identificado na auditoria 2026-07-07

**Sintoma:**
- MLB5276909636: ML=69, App=19 (72% diferença)
- MLB7118364802: ML=69, App=19 (72% diferença — coincidência: mesmos números)
- MLB6620170054: ML=33, App=5 (84% diferença)

**Hipótese:** Esses são produtos com variações (tamanho/cor). O sync atual lê `item["available_quantity"]` que retorna o estoque de **uma variação específica** (a padrão ou a primeira). O ML exibe a **soma de todas as variações** no painel do vendedor.

**Fix proposto (não implementado):**
- Em `tasks_listings.py`: verificar se o item tem `variations`
- Se sim: somar `available_quantity` de cada variação via `/items/{id}` campo `variations[].available_quantity`
- Ou: usar `/items/{id}/variations` para buscar todas as variações e somar

**Arquivos a modificar:** `backend/app/jobs/tasks_listings.py`

---

### BUG #9 — Reputação vendas 60d desatualizada (ABERTO)
**Status:** 🔴 ABERTO — identificado na auditoria 2026-07-07

**Divergência medida:**
- MSM_PRIME: ML=2150, App=2034 (5.4% off)
- MSMPRIME: ML=1285, App=1082 (15.8% off)

**Causa:** `ReputationSnapshot.completed_sales_60d` fica desatualizado entre syncs. A frequência atual de sync de reputação não é suficiente.

**Fix proposto:**
- Opção A: aumentar frequência do sync de reputação (atualmente baixa)
- Opção B: calcular `vendas_60d` diretamente da tabela `Order` (últimos 60 dias, payment_status não cancelado) — mais preciso e não depende de sync externo

---

### BUG #10 — Visitas acumuladas em MLB5982716652 (ABERTO)
**Status:** 🔴 ABERTO — identificado na auditoria 2026-07-07

**Divergência:** ML=1 visita, App=7 visitas (600% diff)

**Hipótese:** O snapshot acumulou visitas de dias anteriores em vez de resetar. Pode ser um caso onde o `before_insert` não fez upsert corretamente ou o `snapshot_day` ficou errado.

**Fix proposto:** Investigar se `snapshot_day` está sendo gravado corretamente em BRT para esse anúncio específico.

---

### BUG #11 — `period=30d` retorna mesmo que `period=7d` (ABERTO)
**Status:** 🔴 ABERTO — identificado em 2026-07-07

**Sintoma:** KPI endpoint com `period=30d` retorna `dias_no_periodo=7`, dados idênticos ao período de 7 dias.

**Causa provável:** Pouco histórico de orders/snapshots no banco para preencher 30 dias, ou bug no endpoint de filtro de período.

**Impacto:** Usuário não consegue ver tendência de 30 dias.

---

### BUG #12 — Celery para silenciosamente (RECORRENTE, ABERTO)
**Status:** 🔴 ABERTO — parou em 27/06, depois 02/07

**Padrão:**
1. Token ML expira (tokens duram ~6h sem renovação)
2. Celery tenta fazer sync → 401 Unauthorized
3. Celery registra erro mas continua agendado
4. Dados param de atualizar — usuário não percebe
5. Usuário vê dados "congelados" mas não tem alerta

**Sprint 10 implementou "Token Resilience"** (refresh, notificações, diagnóstico) mas tokens ainda expiram e param o sync sem alerta visível.

**Fix proposto:**
- Alerta no frontend quando `last_sync` for > 2h atrás
- Celery task que verifica health dos tokens antes de sync e notifica se expirado
- Ou: configurar renovação automática via refresh token (OAuth 2.0 já prevê isso)

---

### BUG #13 — IntegrityError no backfill de orders (ABERTO)
**Status:** 🔴 ABERTO

**Sintoma:** Ao rodar backfill de orders, erro: `duplicate key value violates unique constraint "ix_orders_ml_order_id"`

**Causa:** O backfill faz INSERT em vez de upsert. Se o order já existe, falha.

**Fix proposto:** Em `tasks_orders.py`, trocar INSERT por `INSERT ... ON CONFLICT (ml_order_id) DO UPDATE SET ...` (upsert).

---

### BUG #14 — Financeiro/Analise ainda com agregação própria (PENDENTE)
**Status:** 🟡 PENDENTE — dívida técnica da Fase 2

**Arquivos afetados:**
- `financeiro/service.py`: P&L, cashflow — lógica própria de agregação
- `analise/service.py`: análise de preço — lógica própria
- `service_analytics.py`: funnel, heatmap — lógica própria
- `service_dashboard_cards.py`: cards do dashboard — lógica própria

**Risco:** Esses módulos podem retornar números diferentes de `metrics.py`, recriando o problema de inconsistência entre telas.

---

## 4. CICLO RECORRENTE "CONSERTA UM, QUEBRA OUTRO"

Este é o problema meta do projeto. Aconteceu pelo menos 5 vezes documentadas:

| Ocorrência | O que foi consertado | O que quebrou |
|-----------|---------------------|---------------|
| Sprint 5 | Orders e heatmap implementados | N+1 queries, timezone errada |
| Sprint 8 | sale_price no sync | audit.py ainda usava item["price"] |
| Fase 2 (metrics.py) | summary e daily passaram a bater | funnel e sales-trend ficaram divergentes |
| Fase 3 (time_window) | visitas do dia corretas | snapshot_day em UTC em vez de BRT (corrigido depois) |
| Reputação 60d | cálculo de reputação correto | audit mostrou snapshot desatualizado |

**Causa raiz:** ausência de testes de regressão automáticos que rodem a cada mudança. O pré-commit roda pytest mas a cobertura é ~32% — os casos críticos de paridade não estão cobertos.

**O que o usuário propôs:** Criar "golden master" dos números reais e bloquear commit se divergir. Está documentado em `backend/tests/test_metrics_characterization.py` mas incompleto.

---

## 5. PRINCÍPIOS/DECISÕES ARQUITETURAIS (que moldaram o estado atual)

### Decidido e implementado
- `Order` é fonte de verdade para vendas/receita/pedidos
- `ListingSnapshot` é fonte de verdade para visitas e estoque (posição pontual)
- `metrics.py` é a função única de agregação (summary, daily usam ela)
- `snapshot_day` em BRT, 1 snapshot/dia por anúncio (constraint banco)
- Frete via `/shipments/{id}/costs → senders[].cost`
- Preço via `/items/{id}/sale_price`
- Comissão via `/sites/MLB/listing_prices` com `logistic_type`
- Visitas via `/items/{id}/visits/time_window`

### Decidido mas NÃO implementado
- `Order` como fonte única de receita também nos módulos financeiro/analise/analytics
- Funnel migrado para metrics.py
- Estoque por variações somadas
- Alerta de Celery parado

### Descartado / API não disponível
- Ads API: ML não expõe dados publicamente → fallback gracioso implementado
- WebSocket: adiado indefinidamente
- Mercado Pago integração direta: adiado

---

## 6. ESTADO ATUAL DOS TESTES

| Tipo | Quantidade | Cobertura |
|------|-----------|-----------|
| Backend total | 875 testes | ~32% |
| Testes de paridade KPI | 7 testes (test_metrics_parity.py) | Apenas 1 dia |
| Frontend | 120 testes | — |
| Testes de regressão de números reais | 0 | 0% |

**Gap crítico:** não existe nenhum teste que rode contra a API real do ML e verifique se os números batem. O harness `/audit/parity` faz isso manualmente mas não está no CI.

---

## 7. PLANO DE AÇÃO SUGERIDO (priorizado por impacto)

### Prioridade P0 (bugs com impacto direto na confiabilidade dos dados)
1. **Estoque de variações** — modificar `tasks_listings.py` para somar variações
2. **Upsert no backfill** — `tasks_orders.py` INSERT → ON CONFLICT DO UPDATE
3. **Alerta de Celery parado** — monitoramento de `last_sync` no frontend

### Prioridade P1 (inconsistência entre telas)
4. **Migrar funnel para metrics.py** — eliminar 4ª fonte de verdade
5. **Migrar sales-trend para metrics.py** — eliminar 5ª fonte de verdade
6. **Reconciliação aditiva** — mudar de `max(Σsnap, Σorder)` para apenas `Σorder` (Order é aditivo)

### Prioridade P2 (precisão de dados secundários)
7. **Reputação 60d** — calcular da tabela Order em vez de snapshot
8. **period=30d** — corrigir ou investigar por que retorna dados de 7d
9. **Visitas MLB5982716652** — investigar reset de snapshot

### Prioridade P3 (qualidade / blindagem)
10. **Golden master de paridade** — testes que rodam mensalmente contra ML real e bloqueiam deploy se divergência > 5%
11. **Buscar e eliminar `item["price"]` restante** — grep no projeto todo
12. **Migrar financeiro/analise para metrics.py**

---

## 8. INFORMAÇÕES TÉCNICAS CRÍTICAS

### Endpoints ML que funcionam (validados com token real)
```
GET /items/{id}/sale_price          → preço real (não item["price"])
GET /items/{id}/visits/time_window  → visitas de 1 dia (não /visits/items?ids=)
GET /sites/MLB/listing_prices       → comissão (com logistic_type obrigatório)
GET /shipments/{id}/costs           → frete real (senders[0].cost)
GET /users/{id}/items/search        → listings ativos
GET /orders/search                  → orders por período
GET /users/{id}/seller_reputation   → reputação (metrics.sales.completed = 60d)
```

### Endpoints ML que NÃO funcionam como esperado
```
GET /visits/items?ids=X&date_from=Y  → ignora datas, retorna LIFETIME
GET /items/{id}[price]               → depreciado, retorna preço original (sem desconto)
GET /users/{id}/items_ads            → API de ads não pública
PUT /items/{id}/price                → retorna 400 desde março/2026 (mudança ML)
```

### Variáveis de ambiente críticas (Railway)
```
DATABASE_URL        → PostgreSQL managed Railway
REDIS_URL           → Redis Railway
SECRET_KEY          → JWT signing
ML_TOKEN_KEY        → Fernet encryption para tokens OAuth
```

### Contas ML em produção
```
MSM_PRIME:  ml_user_id=2050442871  (conta principal)
MSMPRIME:   ml_user_id=90599588    (segunda conta)
```

### Arquivos mais críticos (modificar com cuidado)
```
backend/app/vendas/metrics.py         → FONTE ÚNICA de KPI (não duplicar lógica)
backend/app/vendas/constants.py       → NON_SALE_PAYMENT_STATUSES, CANCEL_STATUSES
backend/app/mercadolivre/client.py    → todos os métodos de chamada ML
backend/app/jobs/tasks_listings.py    → sync de snapshots (1/dia via constraint)
backend/app/jobs/tasks_orders.py      → sync de orders (janela BRT)
backend/app/vendas/service_parity_audit.py → harness de auditoria
```

---

## 9. TIMELINE DOS CICLOS DE CORREÇÃO

```
Sprint 1-4 (jan-fev/2026): Base, auth, KPI inicial — sem proteção de dados
Sprint 5 (mar/2026):       Orders, heatmap, financeiro — N+1 queries corrigidas
Sprint 8 (mar/2026):       Fix sale_price (1ª ocorrência do campo depreciado)
Sprint 9 (mar/2026):       Filtros de período, chatbot IA
Sprint 10 (abr/2026):      Token resilience, backfill
Sprint 12 (abr/2026):      QA profunda: 875 testes, 23 bugs críticos
Ciclo Fase 1 (jun/2026):   Snapshots duplicados → constraint banco (FIM do principal ciclo)
Ciclo Fase 2 (jun/2026):   metrics.py como fonte única
Ciclo Fase 3 (jun/2026):   visitas time_window (não lifetime)
Auditoria ARCH-014 (jun):  45 endpoints validados
Auditoria paridade (jul):  134 checks — 81.3% paridade → bugs de estoque/reputação/visitas
```

---

## 10. ASSISTENTE DE IA DO MERCADO LIVRE (MAXWELL) — O QUE TENTAMOS

### O que é
O ML tem um assistente de IA próprio em `mercadolivre.com.br/maxwell/new-chat`. É um chatbot treinado nos dados do vendedor — responde perguntas sobre vendas, anúncios, reputação, reclamações. É **operacional** (para o vendedor), não técnico.

### O que tentamos fazer
Durante a auditoria de paridade, a ideia era usar o Maxwell para confirmar dado por dado se os números do MSM_Pro estavam corretos — anúncio por anúncio, métrica por métrica. O plano:

1. Gerar relatório com todos os dados do MSM_Pro (31 anúncios, KPIs de todos os períodos)
2. Perguntar ao Maxwell: "anúncio MLB123: qual a comissão? quantas visitas ontem? qual o estoque atual?"
3. Comparar resposta do Maxwell com o que o MSM_Pro mostra
4. Marcar divergências e criar lista de bugs

### O que funcionou
- O Maxwell **responde perguntas operacionais** sobre vendas, anúncios específicos, estoque
- Ele acessa dados reais da conta do vendedor em tempo real
- Pode servir como "oráculo humano" para confirmar se um número bate ou não

### O que NÃO funcionou
**Problema 1 — Chrome sem porta de debug:**
- Tentamos usar `dev-browser --connect` (Playwright) para abrir o Maxwell no Chrome e automatizar as perguntas
- O Chrome precisaria estar rodando com `--remote-debugging-port=9222`
- Chrome do usuário não tinha esse flag → conexão falhou
- Alternativa usada: ML API diretamente (mais preciso, mas requer token e é mais trabalhoso)

**Problema 2 — Maxwell recusou dados técnicos:**
- Quando perguntamos sobre **endpoints específicos da API** ("qual o endpoint para buscar visitas?", "como funciona o campo sale_price?") → Maxwell recusou, dizendo que não fornece informações técnicas sobre a API
- Ele só responde perguntas do ponto de vista do vendedor, não do desenvolvedor

**Problema 3 — Escala manual inviável:**
- Com 31 anúncios e múltiplas métricas por anúncio, fazer as perguntas manualmente no chat levaria horas
- A automação via Playwright teria resolvido isso, mas esbarrou no problema 1

### Como o Maxwell PODE ser usado no futuro
- Verificação spot-check: para 3-5 anúncios aleatórios, confirmar se estoque/visitas/comissão batem
- Validação de edge cases: anúncio específico que parece ter dado estranho
- Não serve para auditoria em massa automatizada

### Script de perguntas criado (mas não executado no Maxwell)
Geramos o arquivo `BRIEFING_FABLE5.md` com todos os dados do MSM_Pro formatados para comparação. O script de perguntas sugeridas era:
```
"Anúncio {MLB_ID}: qual a comissão atual em reais? qual o frete que você está pagando?
 Quantas visitas ontem? Quantas vendas hoje e nos últimos 7 dias? Qual a receita? Qual o estoque?"
```

---

## 11. METODOLOGIA DE TESTES QUE USAMOS

### Abordagem geral
A estratégia foi comparar o MSM_Pro diretamente contra a API real do ML usando o token OAuth do usuário. **Sem mock, sem simulação** — dados reais em produção.

### Ferramenta 1: Harness de Paridade (`/api/v1/listings/audit/parity`)
**Arquivo:** `backend/app/vendas/service_parity_audit.py`

**Como funciona:**
```
GET /api/v1/listings/audit/parity?sample_items=40&date_iso=2026-07-07
```
1. Para cada conta ML ativa do usuário, abre um `MLClient` com o token real
2. Chama a API do ML para buscar orders, visitas, estoque, preço, comissão, reputação
3. Compara com o que está armazenado no banco do MSM_Pro
4. Retorna `{metric, ml, app, verdict: PASS/FAIL/NO_DATA/ERROR}` para cada check

**Checks implementados (4 blocos):**
| Bloco | O que testa | Endpoint ML usado |
|-------|-------------|------------------|
| `_audit_sales` | pedidos/unidades/receita do dia | `/orders/search` com janela BRT |
| `_audit_visits_stock_price` | visitas, estoque, preço, comissão por anúncio | `/items/{id}/visits/time_window`, `/items/{id}`, `/items/{id}/sale_price`, `/sites/MLB/listing_prices` |
| `_audit_reputation` | vendas 60d, reclamações | `/users/{id}/seller_reputation` |

**Tolerâncias usadas:**
- Preço: ±5% (arredondamentos)
- Comissão: ±10% (variações de frete grátis)
- Receita: ±1% (casas decimais)
- Visitas, estoque, pedidos: 0% (exato)

**Resultado da última rodada (2026-07-07, 134 checks):**
- PASS: 109 (81.3%)
- FAIL: 25 (18.7%)
- Tempo de execução: ~45 segundos (31 anúncios × 4 chamadas ML cada)

**Bug crítico encontrado e corrigido no próprio harness:**
O harness usava `item.get("price")` (campo depreciado) para comparar preço → causava 18 FAILs falsos. Fix: usar `get_item_sale_price()`. Commit: `64dd13c`. Após o fix: preços 0/31 FAILs → 0 FAILs.

### Ferramenta 2: Relatório de Validação Manual
**Arquivo gerado:** `scratchpad/validacao_2026-07-08_0201.md`

**Como foi gerado:**
1. Chamadas diretas ao MSM_Pro (`/api/v1/listings/`, `/api/v1/listings/kpi/summary?period=7d`, etc.)
2. Salvou listings.json, kpi7.json, kpi30.json no scratchpad
3. Script Python gerou relatório Markdown com todos os dados formatados por anúncio
4. Tabelas prontas para preencher com dados do ML Painel ao lado

**Conteúdo:** 31 anúncios, cada um com preço/comissão/frete/visitas/vendas/estoque do MSM_Pro + coluna vazia "ML Real" para preenchimento manual.

**Limitação:** Exige que o usuário abra o painel ML e preencha manualmente. Não há automação.

### Ferramenta 3: Relatório de Paridade Final
**Arquivo gerado:** `scratchpad/relatorio_paridade_final.md` + `parity_full.json`

**Gerado automaticamente** a partir do harness de paridade. Contém:
- Resumo executivo com placar por categoria
- Tabela de anúncios com estoque errado (4 FAILs críticos)
- Tabela de anúncios com visitas divergentes (19, maioria timing)
- Reputação desatualizada (2 contas)
- Plano de ação priorizado

### Ferramenta 4: Script de Chamada Direta à API ML
**Usado para:** verificar endpoint por endpoint se a implementação estava correta.

Exemplo de sequência de validação:
```bash
# 1. Login no MSM_Pro
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | jq -r '.access_token')

# 2. Rodar auditoria de paridade completa
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/audit/parity?sample_items=40" \
  -H "Authorization: Bearer $TOKEN" | jq .

# 3. Buscar KPI por período
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/kpi/summary?period=7d" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### O que falta na metodologia de testes
| Lacuna | Impacto | Proposta |
|--------|---------|----------|
| Harness não roda no CI | Ninguém avisa quando paridade cai | Adicionar ao GitHub Actions (mensal ou semanal) |
| Sem golden master de números | "Correto" é subjetivo | Gravar snapshot dos números reais, comparar a cada PR |
| Testes de regressão = 32% cobertura | Conserta um, quebra outro | Elevar para 60% com foco em metrics.py |
| Visitas têm timing inerente | 14 FAILs "inevitáveis" | Aumentar tolerância de visitas para 25% no harness |
| Sem teste do período 30d | Bug silencioso | Adicionar check de `dias_no_periodo` no harness |
| Sem teste de produtos com variações | Estoque errado em 3 anúncios | Adicionar check de soma de variações |

### Como rodar os testes hoje
```bash
# Testes unitários backend
cd backend && python -m pytest tests/ -v --timeout=30

# Testes de paridade (prod, requer internet + conta ML ativa)
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/audit/parity?sample_items=40" \
  -H "Authorization: Bearer $TOKEN" | python -c "
import json,sys
d=json.load(sys.stdin)
s=d['summary']
print(f\"Paridade: {s['parity_pct']}% | {s['passed']} PASS | {s['failed']} FAIL\")
for acc in d['accounts']:
    fails=[c for c in acc['checks'] if c['verdict']=='FAIL']
    print(f\"  {acc['nickname']}: {len(fails)} FAILs\")
    for f in fails:
        print(f\"    FAIL {f['metric']}: ML={f['ml']} App={f['app']}\")
"
```

---

## 12. O QUE O MODELO FABLE 5 PRECISA RESOLVER

**Questão central:** Como quebrar definitivamente o ciclo "conserta um, quebra outro" sem precisar de testes manuais a cada mudança?

**Questões específicas:**
1. Como tornar `Order` a fonte única e aditiva de vendas/receita em TODOS os módulos (financeiro, analytics, funnel, sales-trend)?
2. Como garantir que toda mudança em metrics.py não quebre os módulos que dependem dela?
3. Como detectar automaticamente quando o Celery para de sincronizar dados?
4. Como lidar com produtos que têm variações no estoque (somar ou não)?
5. Como garantir que campos depreciados do ML não reapareçam em novos arquivos?

**Contexto de negócio:** O usuário vende no ML, usa o dashboard para tomar decisões. Se os dados estiverem errados, toma decisão errada de precificação, estoque, promoção. A confiabilidade dos dados é mais importante que novas features.
