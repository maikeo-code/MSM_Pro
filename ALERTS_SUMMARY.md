# Resumo das 3 Melhorias no Módulo de Alertas

## Commit Principal
```
feat: add severity levels and opportunity alerts to alert system
f71944d — 2026-03-23
```

---

## 1️⃣ Severidade de Alertas (CRÍTICO/AVISO/INFO)

### Backend
- Modelo: Campo `severity: String(20)` com default "warning"
- Cálculo automático baseado em tipo e threshold:
  - **CRITICAL** ⛔
    - `stock_below` ≤ 3 un
    - `no_sales_days` ≥ 5 dias
  - **WARNING** ⚠️
    - `stock_below` ≤ 10 un
    - `competitor_price_change`
    - padrão
  - **INFO** ℹ️
    - `visits_spike`
    - `conversion_improved`

### Frontend
- Badges coloridos na coluna "Severidade"
- Filtro por severidade (botões: Críticos, Avisos, Info)

### Files Modified
- `backend/app/alertas/models.py` — +1 campo
- `backend/app/alertas/schemas.py` — +Severity type
- `backend/app/alertas/service.py` — +_calculate_severity()
- `backend/migrations/versions/0018_add_severity_to_alerts.py` — migration
- `frontend/src/pages/Alertas/index.tsx` — +SeverityBadge, filtro
- `frontend/src/services/alertasService.ts` — +Severity type

---

## 2️⃣ Alertas de Oportunidade

### Tipo: `visits_spike` (Pico de Visitas)
**O que:** Detecta quando visitas > 150% da média de 7 dias
**Severity:** `info` (azul/verde)
**Threshold:** Nenhum (automático)
**Mensagem:** "Oportunidade: MLB-XYZ com pico de visitas! 150 visitas hoje (média: 100)"

### Tipo: `conversion_improved` (Conversão Melhorou)
**O que:** Detecta quando conversão > 20% acima da média de 7 dias
**Severity:** `info` (azul/verde)
**Threshold:** Nenhum (automático)
**Mensagem:** "Oportunidade: MLB-XYZ com conversão melhorada! 8.50% hoje vs 7.00% (+21.4%)"

### Implementation
- `backend/app/alertas/service.py`:
  - `_check_visits_spike()` — compara média 7 dias com hoje
  - `_check_conversion_improved()` — calcula melhoria percentual

---

## 3️⃣ Previsão de Stockout

### Tipo: `stockout_forecast` (Previsão de Estoque)
**O que:** Estima dias até acabar o estoque
**Severity:** `warning` (automático, pode ser crítico se < 2 dias)
**Threshold:** Dias limite (ex: 7 para alertar com 7 dias de antecedência)
**Lógica:**
```
velocidade = vendas_total_14d / 14
dias_até_stockout = estoque_atual / velocidade
if dias_até_stockout < threshold:
  → dispara alerta
```
**Mensagem:** "Previsão de estoque: MLB-XYZ acabará em 5 dias no ritmo atual (2.5 un/dia, 13 restantes)"

### Implementation
- `backend/app/alertas/service.py`:
  - `_check_stockout_forecast()` — calcula velocidade e dias

---

## Tabela de Mudanças

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Tipos de alerta | 5 | **8** (+ visits_spike, conversion_improved, stockout_forecast) |
| Campo severity | ❌ | ✅ (critical/warning/info) |
| Cálculo automático de severidade | ❌ | ✅ Baseado em tipo + threshold |
| Alertas de oportunidade | ❌ | ✅ Pico de visitas + conversão |
| Previsão de estoque | ❌ | ✅ Estimativa de dias até fim |
| Frontend — Filtro severidade | ❌ | ✅ 4 botões (Todos/Críticos/Avisos/Info) |
| Frontend — Badges coloridos | ❌ | ✅ Red/Yellow/Blue |

---

## API Endpoints (Unchanged)

```
GET    /api/v1/alertas/               → Lista alertas (agora com severity)
POST   /api/v1/alertas/               → Cria alerta (severity automático)
GET    /api/v1/alertas/{id}           → Detalhe do alerta
PUT    /api/v1/alertas/{id}           → Atualiza alerta (pode ajustar severity)
DELETE /api/v1/alertas/{id}           → Deleta alerta

GET    /api/v1/alertas/events/        → Histórico eventos (30 dias)
GET    /api/v1/alertas/events/{id}    → Eventos de um alerta
```

---

## Arquivos Adicionados/Modificados

### Backend (4 files)
```
✏️ backend/app/alertas/models.py          (1 campo adicionado)
✏️ backend/app/alertas/schemas.py         (tipos e severidade)
✏️ backend/app/alertas/service.py         (3 novos checkers + severidade)
✨ backend/migrations/versions/0018_add_severity_to_alerts.py
```

### Frontend (2 files)
```
✏️ frontend/src/pages/Alertas/index.tsx   (badges, filtro)
✏️ frontend/src/services/alertasService.ts (tipos)
```

### Documentation (2 files)
```
✨ docs/ALERTS_IMPROVEMENTS.md      (especificação completa)
✨ docs/ALERTS_TEST_CHECKLIST.md    (QA testing)
```

---

## Linhas de Código

| Componente | LoC | Mudança |
|-----------|-----|--------|
| models.py | 47 | +1 |
| schemas.py | 96 | +30 |
| service.py | 680 | +230 (novos checkers) |
| migration | 35 | +35 |
| Frontend | 530 | +70 |
| **Total** | **1388** | **+366** |

---

## Testing

### Smoke Tests
```bash
# 1. Backend compilação
cd backend && python -m py_compile app/alertas/*.py

# 2. Migration
alembic upgrade head && alembic current

# 3. Frontend TypeScript
npx tsc --noEmit frontend/src/services/alertasService.ts
```

### Integration Tests
Ver `docs/ALERTS_TEST_CHECKLIST.md` para:
- Criar alertas com severidades automáticas
- Testar novos 3 tipos
- Validar filtros no Frontend
- Verificar Celery dispara corretamente

---

## Deploy

### Steps
1. ✅ Commit + Push (feito)
2. ⏳ Railway auto-deploy em produção
3. 🔄 Testar endpoints em https://msmpro-production.up.railway.app
4. 📊 Validar com QA usando checklist

### Rollback
```bash
git revert f71944d  # ou 5d24f5c
alembic downgrade 0017
```

---

## Status do Projeto

- [x] Severidade de Alertas — COMPLETO
- [x] Alertas de Oportunidade (2 tipos) — COMPLETO
- [x] Previsão de Stockout — COMPLETO
- [x] Migration Alembic — COMPLETO
- [x] Frontend UI — COMPLETO
- [x] Documentação — COMPLETO
- [ ] QA Testing — ⏳ PENDENTE
- [ ] Deploy em Produção — ⏳ PENDENTE

---

## Próximas Fases

1. **Fase 1** (atual): Severidade + Oportunidades + Previsão
2. **Fase 2**: Auto-pricing baseado em picos de visitas
3. **Fase 3**: Notificações em tempo real (WebSocket)
4. **Fase 4**: Análise de histórico de alertas (analytics)

---

## Suporte / Questions?

- Docs: `docs/ALERTS_IMPROVEMENTS.md`
- Testes: `docs/ALERTS_TEST_CHECKLIST.md`
- Código backend: `backend/app/alertas/`
- Código frontend: `frontend/src/pages/Alertas/`
