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
