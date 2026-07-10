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
