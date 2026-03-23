# Checklist de Testes — Alertas com Severidade

## Backend

### 1. Migrations
- [ ] Executar `alembic upgrade head` sem erros
- [ ] Verificar `alembic current` mostra revisão 0018
- [ ] Coluna `severity` existe na tabela `alert_configs`
- [ ] Default de `severity` é "warning"

### 2. Severidade Automática

#### Stock Below Crítico (≤3)
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "stock_below",
    "listing_id": "seu-uuid",
    "threshold": 2,
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "critical"

#### Stock Below Warning (≤10)
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "stock_below",
    "listing_id": "seu-uuid",
    "threshold": 8,
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "warning"

#### No Sales Days Crítico (≥5)
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "no_sales_days",
    "listing_id": "seu-uuid",
    "threshold": 5,
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "critical"

#### Competitor Price Change (padrão warning)
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "competitor_price_change",
    "listing_id": "seu-uuid",
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "warning"

### 3. Novos Tipos de Alerta

#### Visits Spike
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "visits_spike",
    "listing_id": "seu-uuid",
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "info"
- [ ] Campo `threshold` = null (não obrigatório)

#### Conversion Improved
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "conversion_improved",
    "listing_id": "seu-uuid",
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "info"
- [ ] Campo `threshold` = null

#### Stockout Forecast
```bash
curl -X POST http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_type": "stockout_forecast",
    "listing_id": "seu-uuid",
    "threshold": 7,
    "channel": "email"
  }'
```
- [ ] Resposta HTTP 201
- [ ] Campo `severity` = "warning"
- [ ] Campo `threshold` = 7

### 4. Listar Alertas
```bash
curl -s http://localhost:8000/api/v1/alertas/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```
- [ ] Todos os alertas têm campo `severity`
- [ ] Valores são válidos: "critical", "warning", "info"

### 5. Atualizar Severity Manual
```bash
curl -X PUT http://localhost:8000/api/v1/alertas/{alert_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"severity": "critical"}'
```
- [ ] Resposta HTTP 200
- [ ] Campo `severity` atualizado

---

## Frontend

### 1. Page Alertas — Layout

- [ ] Página `/alertas` carrega sem erros
- [ ] Título "Alertas" presente
- [ ] Botão "Novo Alerta" visível
- [ ] Tabela com colunas: Tipo, Anúncio, Limite, **Severidade**, Canal, Status, Ações

### 2. Badges de Severidade

- [ ] Badges na coluna "Severidade":
  - [ ] Crítico: fundo vermelho, borda vermelha
  - [ ] Aviso: fundo amarelo, borda amarela
  - [ ] Info: fundo azul, borda azul

### 3. Filtro por Severidade

- [ ] 4 botões de filtro acima da tabela
  - [ ] Botão "Todos" (cinza)
  - [ ] Botão "Críticos" (vermelho)
  - [ ] Botão "Avisos" (amarelo)
  - [ ] Botão "Info" (azul)

- [ ] Clicar em "Críticos" filtra apenas alertas com severity="critical"
- [ ] Clicar em "Avisos" filtra apenas alertas com severity="warning"
- [ ] Clicar em "Info" filtra apenas alertas com severity="info"
- [ ] Clicar em "Todos" mostra todos os alertas

### 4. Criar Novo Alerta

#### Visits Spike
- [ ] Tipo "Pico de Visitas" aparece no dropdown
- [ ] Sem campo de threshold (disabled ou hidden)
- [ ] Ao salvar: severity automático = "info"
- [ ] Alerta aparece na tabela com badge azul "Info"

#### Conversion Improved
- [ ] Tipo "Conversao Melhorou" aparece no dropdown
- [ ] Sem campo de threshold
- [ ] Ao salvar: severity automático = "info"
- [ ] Alerta aparece com badge azul "Info"

#### Stockout Forecast
- [ ] Tipo "Previsao de Estoque" aparece no dropdown
- [ ] Campo threshold com label "Dias ate stockout"
- [ ] Ao salvar com threshold=7: severity automático = "warning"
- [ ] Alerta aparece com badge amarelo "Aviso"

### 5. TypeScript Compilation
- [ ] Sem erros em `npm run build` (ou `npx vite build`)
- [ ] Tipos Severity exportados corretamente
- [ ] Tipos AlertType incluem novos 3 tipos

---

## Celery / Tasks

### 1. Disparar Alertas

- [ ] Rodar `python backend/app/jobs/tasks_alerts.py` (ou task Celery)
- [ ] Alertas válidos são avaliados sem crashes
- [ ] Cada tipo dispara apenas quando condição atendida
- [ ] Emails são enviados se channel="email"

### 2. Visits Spike

- [ ] Anúncio com >150% visitas dispara alerta
- [ ] Mensagem contém visitas de hoje e média 7d
- [ ] Cooldown de 24h funciona (não duplica)

### 3. Conversion Improved

- [ ] Anúncio com >20% melhoria dispara alerta
- [ ] Mensagem mostra conversão de hoje vs média
- [ ] Cooldown de 24h funciona

### 4. Stockout Forecast

- [ ] Anúncio com dias_até_stockout < threshold dispara
- [ ] Mensagem: "X dias no ritmo atual (Y un/dia, Z restantes)"
- [ ] Cooldown de 24h funciona

---

## End-to-End

### 1. Fluxo Completo
1. [ ] Criar alerta stock_below threshold=3
2. [ ] Verificar no Frontend: badge "Crítico" vermelho
3. [ ] Filtrar por "Críticos": alerta aparece
4. [ ] Filtrar por "Avisos": alerta desaparece
5. [ ] Clicar em "Todos": alerta volta
6. [ ] Deletar alerta: desaparece da lista

### 2. Múltiplos Alertas
1. [ ] Criar 3 alertas com severidades diferentes
2. [ ] Tabela mostra 3 linhas
3. [ ] Cores de severidade corretas
4. [ ] Filtros funcionam para cada severidade

### 3. Responsividade
- [ ] Tabela não quebra em mobile (scroll horizontal)
- [ ] Badges de severidade visíveis em mobile
- [ ] Botões de filtro responsivos

---

## Sign-off

| Item | Status | Responsável |
|------|--------|------------|
| Migrations aplicadas | ✓/✗ | QA |
| Backend testes | ✓/✗ | QA |
| Frontend testes | ✓/✗ | QA |
| Celery avaliação | ✓/✗ | QA |
| E2E | ✓/✗ | QA |
| Deploy em produção | ✓/✗ | DevOps |

---

## Bugs Encontrados

(Preencher durante teste)

1. Issue #...
   - Descrição:
   - Severidade: Critical/High/Medium/Low
   - Status: Aberto/Fechado

---

## Notes

- Lembrar de atualizar MEMORY.md ao final com status
- Se algum teste falhar, ver ALERTS_IMPROVEMENTS.md para referência
- Contatar @dev se encontrar erros no backend
