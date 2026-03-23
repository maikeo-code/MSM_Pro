# Melhorias no Módulo de Alertas (Sprint 7)

Data: 2026-03-23

## Resumo

Implementação de 3 melhorias principais no sistema de alertas do MSM_Pro:

1. **Severidade de Alertas** — classificação automática (crítico/aviso/info)
2. **Alertas de Oportunidade** — detecção de picos de visitas e conversão melhorada
3. **Previsão de Stockout** — estimativa de dias até acabar o estoque

---

## 1. Severidade de Alertas

### Campo Adicionado
- `severity: String(20)` em `AlertConfig`
- Valores: `"critical"`, `"warning"`, `"info"`
- Padrão: `"warning"`

### Lógica Automática de Severidade

Ao criar um alerta, o backend calcula automaticamente o nível de severidade:

| Condição | Severidade |
|----------|-----------|
| `stock_below` com threshold ≤ 3 unidades | **critical** |
| `stock_below` com threshold ≤ 10 unidades | **warning** |
| `no_sales_days` com threshold ≥ 5 dias | **critical** |
| `competitor_price_change` | **warning** |
| `visits_spike`, `conversion_improved` | **info** |
| Outros | **warning** (padrão) |

### Frontend — Badges Coloridos

Cada alerta exibe um badge com a severidade:
- **Crítico** (vermelho): `bg-red-100 text-red-700`
- **Aviso** (amarelo): `bg-yellow-100 text-yellow-700`
- **Info** (azul): `bg-blue-100 text-blue-700`

### Filtro por Severidade

Nova funcionalidade na página `/alertas`:
- Botões de filtro: "Todos", "Críticos", "Avisos", "Info"
- Filtra a tabela de alertas em tempo real

### API Changes

**Schema Pydantic:**
```python
class AlertConfigOut:
    ...
    severity: str  # adicionado
```

**Migrations:**
- `0018_add_severity_to_alerts.py`: adiciona coluna `severity` com default "warning"

---

## 2. Alertas de Oportunidade

### Novo Tipo: `visits_spike`

**O que detecta:** Picos de visitas (oportunidade para aumentar preço/estoque)

**Lógica:**
- Compara visitas de hoje com a média dos últimos 7 dias
- Se visitas > **150%** da média → dispara alerta
- Severity: `info` (verde/azul — não é problema, é oportunidade)

**Mensagem:**
```
Oportunidade: MLB-123456 com pico de visitas!
150 visitas hoje (média: 100 visitas/dia)
```

**Threshold:** Nenhum threshold necessário (detecção automática)

---

### Novo Tipo: `conversion_improved`

**O que detecta:** Melhoria na conversão após mudança de preço

**Lógica:**
- Compara conversão de hoje com a média dos últimos 7 dias
- Se conversão subiu > **20%** vs média → dispara alerta
- Severity: `info` (confirmação de que a mudança de preço funcionou)

**Mensagem:**
```
Oportunidade: MLB-123456 com conversão melhorada!
8.50% hoje vs 7.00% (média dos 7 dias) (+21.4%)
```

**Threshold:** Nenhum threshold necessário

---

## 3. Previsão de Stockout

### Novo Tipo: `stockout_forecast`

**O que detecta:** Estimativa de dias até o estoque acabar

**Lógica:**
1. Calcula a velocidade média de vendas dos últimos 14 dias
2. Divide o estoque atual pela velocidade: `dias_até_stockout = estoque / vendas_por_dia`
3. Se `dias_até_stockout < threshold` → dispara alerta
4. Severity: automática (urgência baseada no tempo restante)

**Fórmula:**
```
velocidade_venda = vendas_totais_14d / 14
dias_até_stockout = estoque_atual / velocidade_venda

Se dias_até_stockout < threshold_configurado:
  → dispara alerta
```

**Mensagem:**
```
Previsão de estoque: MLB-123456 acabará em 5 dias
no ritmo atual (2.5 un/dia, 13 restantes)
```

**Threshold:** Dias mínimos até stockout (ex: 7, 14, 30)

**Exemplo de Configuração:**
```json
{
  "alert_type": "stockout_forecast",
  "listing_id": "uuid-do-anuncio",
  "threshold": 7,  // alertar se acabar em < 7 dias
  "channel": "email"
}
```

---

## Backend Changes

### Models (`backend/app/alertas/models.py`)
- Adicionado campo `severity: String(20)` com default "warning"

### Schemas (`backend/app/alertas/schemas.py`)
- `AlertType`: adicionados 3 novos tipos
- Nova tipo `Severity = Literal["critical", "warning", "info"]`
- `AlertConfigCreate` e `AlertConfigOut`: adicionado campo `severity`
- Documentação atualizada em THRESHOLD_LABELS

### Service (`backend/app/alertas/service.py`)
- Nova função `_calculate_severity()`: lógica automática de severidade
- `create_alert_config()`: agora calcula severity automaticamente
- `update_alert_config()`: permite atualizar severity manualmente
- `_check_condition()`: dispatch para novos tipos
- Implementação de `_check_visits_spike()`: pico > 150% média 7d
- Implementação de `_check_conversion_improved()`: melhoria > 20%
- Implementação de `_check_stockout_forecast()`: previsão com base em velocidade

### Migrations
- `0018_add_severity_to_alerts.py`: coluna severity (nullable=False, default="warning")

---

## Frontend Changes

### Service (`frontend/src/services/alertasService.ts`)
- `AlertType`: adicionados novos 3 tipos
- Nova tipo `Severity = Literal["critical", "warning", "info"]`
- `AlertConfigOut` e `AlertConfigCreate`: adicionado `severity`

### Página Alertas (`frontend/src/pages/Alertas/index.tsx`)

**Novos componentes:**
- `SeverityBadge`: exibe severity com cores padronizadas

**Novos maps:**
- `ALERT_TYPE_LABELS`: adicionados labels dos 3 novos tipos
- `ALERT_TYPE_COLORS`: cores verdes/azuis para oportunidades
- `SEVERITY_COLORS`: cores por severidade (crítico/aviso/info)
- `THRESHOLD_LABELS`: labels para novo tipo `stockout_forecast`

**Tabela de alertas:**
- Nova coluna "Severidade" entre "Limite" e "Canal"
- Exibe badge colorido com nível de severidade

**Filtro por severidade:**
- 4 botões de filtro: "Todos", "Críticos", "Avisos", "Info"
- Filtra alertas em tempo real na tabela

---

## Testes Recomendados

### 1. Severidade Automática

```bash
# Criar alerta stock_below com threshold 2
POST /api/v1/alertas/
{
  "alert_type": "stock_below",
  "listing_id": "uuid",
  "threshold": 2,
  "channel": "email"
}
# Esperado: severity = "critical"

# Criar alerta stock_below com threshold 8
POST /api/v1/alertas/
{
  "alert_type": "stock_below",
  "listing_id": "uuid",
  "threshold": 8,
  "channel": "email"
}
# Esperado: severity = "warning"
```

### 2. Pico de Visitas

```bash
# Criar alerta visits_spike
POST /api/v1/alertas/
{
  "alert_type": "visits_spike",
  "listing_id": "uuid",
  "channel": "email"
}
# Esperado: severity = "info"
# Dispara quando visitas_hoje > 150% * media_7d
```

### 3. Previsão de Stockout

```bash
# Criar alerta com previsão
POST /api/v1/alertas/
{
  "alert_type": "stockout_forecast",
  "listing_id": "uuid",
  "threshold": 7,  # alertar com 7 dias de antecedência
  "channel": "email"
}
# Dispara quando dias_até_stockout < 7
```

### 4. Frontend — Filtro de Severidade

1. Navegar para `/alertas`
2. Verificar se aparecem os botões de filtro
3. Clicar em "Críticos" → tabela mostra apenas alertas críticos
4. Clicar em "Avisos" → tabela mostra apenas avisos
5. Clicar em "Todos" → mostra todos os alertas

---

## Arquivos Modificados

### Backend
- `backend/app/alertas/models.py` — campo severity
- `backend/app/alertas/schemas.py` — tipos e schemas
- `backend/app/alertas/service.py` — lógica dos 3 novos tipos
- `backend/migrations/versions/0018_add_severity_to_alerts.py` — migration

### Frontend
- `frontend/src/services/alertasService.ts` — tipos TypeScript
- `frontend/src/pages/Alertas/index.tsx` — UI com badges e filtro

---

## Próximos Passos

1. **Testar Celery**: Rodar avaliação de alertas para validar disparos
2. **Configurar SMTP**: Emails dos alertas funcionarem
3. **Refinar thresholds**: Ajustar 150%, 20%, 7 dias conforme dados reais
4. **Analytics**: Acompanhar quais alertas disparam mais
5. **Oportunidades**: Implementar sugestões automáticas de preço baseadas em picos

---

## Referências

- Modelo anterior: `backend/app/alertas/models.py`
- Lógica de alertas: `backend/app/alertas/service.py`
- Avaliação Celery: `backend/app/jobs/tasks_alerts.py`
- UI: `frontend/src/pages/Alertas/index.tsx`
