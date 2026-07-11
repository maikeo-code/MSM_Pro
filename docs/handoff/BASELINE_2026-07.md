# BASELINE de partida — Plano Definitivo MSM_Pro (Etapa E5)

> Números REAIS de partida contra o painel do ML, medidos antes de qualquer correção do plano.
> Toda fase seguinte compara contra estes números. Registrado em 2026-07-09.

## Como foi medido
```bash
TOKEN="<jwt>" scripts/check_parity.sh          # via GET /api/v1/listings/audit/parity
```
- Endpoint: `GET /api/v1/listings/audit/parity?sample_items=2`
- Dia auditado: **2026-07-08** (D-1)
- Tempo de resposta: ~22s (bate na API real do ML por anúncio)
- ⚠️ `sample_items=2` (amostra pequena de anúncios para visitas/estoque/preço). Os checks de
  vendas/receita/reputação são por conta, independem da amostra.

## Placar de partida: **73,1% de paridade** (19 PASS / 7 FAIL de 26 checks)

### MSM_PRIME (ml_user_id 2050442871) — 8 PASS / 5 FAIL
| Métrica | ML (verdade) | App | Divergência |
|---|---|---|---|
| pedidos_dia | 27 | 28 | app conta **+1 pedido** |
| unidades_dia | 28 | 29 | app conta **+1 unidade** |
| receita_dia | R$ 1.689,42 | R$ 1.712,29 | app **+R$ 22,87** |
| visitas[MLB4152674593] | 8 | 6 | timing (−2) |
| reputacao_vendas_60d | 2195 | 2149 | app subconta (−46) |

### MSMPRIME (ml_user_id 90599588) — 11 PASS / 2 FAIL
| Métrica | ML (verdade) | App | Divergência |
|---|---|---|---|
| visitas[MLB5388214492] | 0 | 3 | timing / acúmulo (+3) |
| reputacao_vendas_60d | 1326 | 1312 | app subconta (−14) |

## Leitura dos FAILs (mapeia para as etapas do plano)
1. **Vendas/receita da MSM_PRIME sobrecontam em 1 pedido/dia** (28 vs 27, +R$22,87). É a divergência
   mais séria — o app mostra MAIS venda do que o painel. Causa provável: reconciliação `max()` não-
   aditiva ou janela BRT/edge de status. **→ Resolvido na Fase 4 (E52, Order como fonte aditiva).**
2. **Reputação 60d subconta nas 2 contas** (−46 e −14). Bug conhecido: prefere contagem local de
   Order que não cobre 60d completos. **→ Fase 1 (E13 preferir metrics.sales.completed + E14 sync 3h).**
3. **Visitas divergem por timing** (pequenas, ±2-3). **→ Fase 3 (E43, auditar D-1 fechado, tol=0;
   dia corrente vira INFO não FAIL).**
4. **PASS:** estoque, preço, comissão da amostra; e a MSMPRIME bate em vendas/receita/pedidos.

## Suíte de testes (baseline)
- Núcleo de métricas (golden master + paridade): **9 passed em ~4,2s** (verificado 2026-07-09).
- Suíte completa esperada (plano): 1865 passed (não re-executada aqui; roda no CI).

## Meta do plano
- Paridade ≥98% nos checks estáveis (dias fechados/VERIFIED). Partida: **73,1%** nesta amostra.
- Prioridade P0: eliminar a sobrecontagem de vendas da MSM_PRIME e a subcontagem de reputação.

---

## Medição 2 — 2026-07-10 (após E9/E11/E12/E14, dia auditado 2026-07-09, sample_items=5)

**Paridade: 76,0%** (50 checks, 38 PASS, 12 FAIL) — subiu de 73,1%.

### Vitórias validadas em prod (o trabalho da sessão funcionou)
- **comissão 10/10 PASS · preço 10/10 PASS**
- **reputação 4/4 PASS** — E14 (sync 3h) eliminou a subcontagem de reputação da medição 1.
- **estoque 9/10 PASS** — E9 (soma de variações) eliminou 3 dos 4 FAILs de estoque. O único
  restante (MLB5276909636: ml=109 app=110) é ±1 de timing (venda entre captura e auditoria).
- **E12 backfill rodou sem IntegrityError** → prova do upsert E11 (reprocessou 7 dias de orders
  já existentes; sob o código antigo cada duplicata dispararia IntegrityError).

### Os 12 FAILs restantes = 2 problemas estruturais já mapeados
1. **Sobrecontagem de vendas (6 FAIL)** — app conta **+1 pedido / +1 unidade** que o painel ML não
   conta, nas DUAS contas, com receita a mais:
   - MSM_PRIME: pedidos 51 vs 50 · unidades 55 vs 54 · receita R$3.485,62 vs R$3.433,81 (+51,81)
   - MSMPRIME: pedidos 21 vs 20 · unidades 21 vs 20 · receita R$2.263,03 vs R$2.023,36 (+239,67)
   → **Fase 4 (E52 — Order como fonte única)**, gated por Bloco A (backup+staging+shadow). É o bug
   central do plano. Hipóteses a investigar em E49: fronteira de fuso BRT, status incluído a mais
   (refunded conta no app), ou pack/carrinho contado como 2. NÃO corrigir fora da Fase 4.
2. **Timing de visitas (5 FAIL)** — app conta a MENOS no D-1 (captura incompleta do dia): ex.
   MLB6838273884 ml=9 app=7. → **Fase 3 (E43)**: tratar D-1 com tolerância/INFO, não FAIL.

### Nota operacional (achado desta sessão)
Dados de prod NÃO estão congelados — `/health/sync` mostra sync_orders + sync_all_snapshots
rodando de hora em hora hoje. O "last_sync 07-07" que aparecia em `/ml/accounts` era bug de leitura
(E18 filtrava ml_account_id NOT NULL, ignorando os syncs globais); corrigido no commit ba72c6b.

---

## Medição 3 — 2026-07-11 (amostra DETERMINÍSTICA, dia 07-09, sample_items=5)

⚠️ **Correção metodológica:** a medição 2 (76%) NÃO era reproduzível — a amostra de anúncios usava
`LIMIT 5` sem `ORDER BY`, então o Postgres devolvia anúncios diferentes a cada chamada e o número
oscilava (medi 66%, 72%, 76% no MESMO dia). Corrigido no commit be0e574 (`order_by(mlb_id)`).
**Número canônico agora é REPRODUTÍVEL** — auditei 2× e deu 60,0% idêntico.

**Paridade reproduzível dia 07-09 = 60,0%** (30 PASS / 20 FAIL / 50 checks, amostra fixa 5 anúncios/conta).

### Decomposição por bloco (honesta e reproduzível)
| Bloco | PASS | FAIL | Leitura |
|-------|------|------|---------|
| comissao | 10 | 0 | ✅ perfeito |
| preco | 10 | 0 | ✅ perfeito |
| reputacao_claims | 2 | 0 | ✅ |
| estoque | 6 | 4 | os 5 primeiros anúncios/conta (por mlb_id) têm mais divergência de estoque que a amostra aleatória de antes |
| visitas | 2 | 8 | timing/captura D-1 — E43 só trata dia corrente; captura incompleta de D-1 é E63 (close_day) |
| pedidos_dia | 0 | 2 | sobrecontagem estrutural → Fase 4/E52 |
| unidades_dia | 0 | 2 | idem |
| receita_dia | 0 | 2 | idem |
| reputacao_vendas_60d | 0 | 2 | ⚠️ ver achado |

### 3 achados desta medição
1. **Amostra não-determinística** (harness) — JÁ CORRIGIDO (be0e574). O gate agora é reproduzível;
   pré-requisito para comparar antes/depois na Fase 4.
2. **`reputacao_vendas_60d` diverge ±0,07-0,8%** (MSM_PRIME ml=2214 app=2232; MSMPRIME ml=1353
   app=1354). É janela deslizante de ~2000 vendas contra snapshot periódico + tolerância ZERO no
   harness. NÃO mexer na tolerância ainda (mascararia o achado 3). Candidato a tol~1% DEPOIS de
   confirmar o sync.
3. **`sync_reputation` não grava SyncLog** — `_sync_reputation_async` não chama `_create_sync_log`,
   então some do `/health/sync` (aparece "(nenhum)"). É lacuna de OBSERVABILIDADE (não prova que
   parou, mas impede confirmar que roda). Pendência: adicionar SyncLog à task (igual às outras) para
   tornar o E14 auditável. Prioridade média.

### Nota de método
O número de paridade depende de `sample_items` e do dia. Para comparação válida, fixar SEMPRE
`sample_items=5&date_iso=<dia fechado>`. Baseline canônico reproduzível: **60,0% (07-09, sample 5)**.
