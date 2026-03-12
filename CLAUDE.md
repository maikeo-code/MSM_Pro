# MSM_Pro — Documento do Projeto

## O que é
Dashboard de inteligência de vendas para o Mercado Livre.
Substitui o MSM_Dashboard (projeto legado com auth quebrada e sem banco real).

## Localização
```
C:\Users\Maikeo\MSM_Imports_Mercado_Livre\
├── MSM_Dashboard\   ← projeto legado (referência de lógica ML)
├── MSM_ML\
└── MSM_Pro\         ← este projeto
```

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Python 3.12 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrações | Alembic |
| Banco | PostgreSQL 16 |
| Cache/Fila | Redis 7 |
| Jobs | Celery + Redis |
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS + shadcn/ui |
| Gráficos | Recharts |
| HTTP Client | React Query (TanStack) |
| Infra Local | Docker Compose |

---

## Modelo de Dados — Regras de Negócio

### SKU vs MLB
- **SKU** = produto interno do usuário
  - Custo definido aqui (1x por SKU)
  - 1 SKU pode ter N anúncios MLB
  - 1 SKU pode ter anúncios em contas ML diferentes
- **MLB** = anúncio no Mercado Livre (ex: MLB-123456789)
  - Sempre pertence a 1 SKU
  - Sempre pertence a 1 conta ML

### Snapshot Diário
- Todo dia o Celery tira uma "foto" de cada MLB:
  - preço atual, visitas, vendas do dia, perguntas, estoque
- Esse histórico é a base de toda análise de preço × conversão

### Concorrentes
- Usuário cola manualmente o ID/link do MLB do concorrente
- O sistema vincula esse MLB externo ao MLB do usuário
- Snapshot diário também é tirado dos concorrentes

---

## Estrutura de Pastas

```
MSM_Pro/
├── backend/
│   ├── app/
│   │   ├── auth/           ← JWT app + OAuth ML multi-conta
│   │   ├── mercadolivre/   ← cliente ML (requests, retry, rate-limit)
│   │   ├── produtos/       ← SKUs e cadastro de custo
│   │   ├── vendas/         ← pedidos e métricas
│   │   ├── concorrencia/   ← MLBs externos monitorados
│   │   ├── alertas/        ← engine de alertas configuráveis
│   │   ├── financeiro/     ← taxas ML, margem, cálculos
│   │   ├── jobs/           ← Celery tasks (sync diário)
│   │   ├── ws/             ← WebSocket (tempo real)
│   │   └── core/           ← config, database, deps
│   ├── migrations/         ← Alembic
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard/      ← KPIs gerais
│       │   ├── Anuncios/       ← Lista + análise por MLB
│       │   ├── Concorrencia/   ← Monitoramento de rivais
│       │   ├── Alertas/        ← Config e histórico
│       │   └── Configuracoes/  ← Contas ML, SKUs, custos
│       ├── components/         ← componentes reutilizáveis
│       ├── services/           ← chamadas à API
│       ├── hooks/              ← hooks customizados
│       └── store/              ← estado global
├── .claude/
│   └── agents/
│       ├── dev.md          ← Agente desenvolvedor
│       ├── qa.md           ← Agente QA/verificador
│       └── insights.md     ← Agente de ideias
├── docs/                   ← documentação técnica
├── docker-compose.yml
├── .env.example
└── CLAUDE.md               ← este arquivo
```

---

## Módulos — Escopo Atual

### MÓDULO 1 — Análise de Preço por Anúncio ⭐ (core)
Por MLB, o usuário vê:
- Histórico de preços praticados × vendas × conversão × visitas
- Tabela: cada faixa de preço → vendas/dia, conversão %, receita, margem
- Gráfico de linha: preço e conversão no tempo
- Cálculo de margem = preço - custo_sku - taxa_ml - frete
- Ponto ótimo: maior margem total (preço × unidades × margem unitária)

### MÓDULO 2 — Concorrência
- Vincular MLBs de concorrentes manualmente por anúncio
- Snapshot diário: preço, sold_quantity delta, visitas estimadas
- Gráfico: meu preço vs concorrente ao longo do tempo
- Alerta automático quando concorrente muda preço

### MÓDULO 3 — Alertas
Configuráveis por MLB ou por SKU:
- Conversão < X%
- Estoque < N unidades
- Concorrente mudou preço
- 0 vendas por N dias
- Concorrente vendendo abaixo de R$ X
- Canal fase 1: email | Canal fase 2: WhatsApp/webhook

### MÓDULO 4 — Multi-Conta ML
- N contas ML por usuário
- OAuth independente por conta (token salvo no banco)
- Sync paralelo via Celery

---

## Taxas ML por Tipo de Anúncio
| Tipo | Taxa |
|------|------|
| Clássico | 11% |
| Premium | 16% |
| Full | 16% + frete grátis |
> Atualizar conforme tabela oficial ML: https://www.mercadolivre.com.br/tarifas

---

## Sprints

### Sprint 1 — Fundação (próximo a executar)
- [ ] docker-compose.yml (Postgres + Redis)
- [ ] backend: FastAPI base + SQLAlchemy async + Alembic
- [ ] Tabelas: users, ml_accounts, products (SKU), listings (MLB), listing_snapshots
- [ ] OAuth ML multi-conta (token salvo no banco, auto-refresh)
- [ ] Celery beat: sync diário de snapshots

### Sprint 2 — Análise de Preço
- [ ] Endpoint de snapshot por MLB com filtro de período
- [ ] Página Anúncios: lista + detalhe por MLB
- [ ] Gráfico preço × conversão × vendas
- [ ] Cadastro de custo por SKU
- [ ] Calculadora de margem

### Sprint 3 — Concorrência
- [ ] Tabelas: competitors, competitor_snapshots
- [ ] Vincular MLB externo a MLB próprio
- [ ] Sync diário de concorrentes
- [ ] Gráfico comparativo

### Sprint 4 — Alertas
- [ ] Tabelas: alert_configs, alert_events
- [ ] Engine de verificação (Celery task)
- [ ] Envio de email (SMTP)
- [ ] Página de configuração de alertas

---

## Convenções de Código

### Backend
- Arquivos: `snake_case.py`
- Classes: `PascalCase`
- Rotas: prefixo `/api/v1/`
- Modelos SQLAlchemy em `models.py` dentro de cada módulo
- Schemas Pydantic em `schemas.py`
- Lógica de negócio em `service.py`
- Rotas FastAPI em `router.py`

### Frontend
- Componentes: `PascalCase.tsx`
- Hooks: `useNomeDoHook.ts`
- Services: `nomeService.ts`
- Constantes: `UPPER_SNAKE_CASE`

---

## Variáveis de Ambiente (.env)
```env
# Banco
DATABASE_URL=postgresql+asyncpg://msm:msm@localhost:5432/msm_pro
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Email (alertas)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## Agentes Claude disponíveis
- `/dev` — implementa features no código
- `/qa` — verifica e testa o código
- `/insights` — sugere melhorias com base em ferramentas similares

## Regra de uso de subagentes (OBRIGATÓRIO)
Sempre que a tarefa for longa ou envolver múltiplas partes do sistema, usar subagentes em paralelo:

| Situação | Agentes a usar |
|---|---|
| 1 tarefa isolada (ex: corrigir 1 bug) | Só o agente principal |
| Backend + frontend ao mesmo tempo | 1 agente `dev` no backend + 1 `dev` no frontend em paralelo |
| Implementar feature + verificar bugs | 1 `dev` implementando + 1 `qa` verificando em paralelo |
| Sessão longa com muitas tarefas | 2x `dev` (dividir por módulo) + 1 `qa` no final |

**Limite prático: máximo 3 agentes simultâneos** — mais do que isso causa conflito de arquivos.

**Modelo padrão: Sonnet 4.6** para todos os agentes (melhor custo-benefício para código).

O usuário autoriza todas as ações sem confirmação — não perguntar antes de executar.

## Regras de validação QA antes de deploy (OBRIGATÓRIO)
Antes de qualquer deploy, o agente QA deve validar:

1. **Endpoint crítico funciona via curl com token real** — não assumir que funciona sem testar
2. **Fluxo completo testado em sequência** — não testar partes isoladas; testar o caminho completo (login → ação → resultado no frontend)
3. **Uma mudança por vez** — não acumular múltiplas mudanças antes de verificar; deploy → testar → próxima mudança
4. **Schema Pydantic compatível com dados reais** — verificar `Optional` onde o campo pode ser `None` no banco
5. **API base URL correta**: `https://api.mercadolibre.com` (sem acento — o domínio com acento não existe)

## Observações importantes
- NUNCA iniciar código sem confirmação explícita do usuário
- Mercado Livre API base: `https://api.mercadolibre.com` (sem acento no "e")
- Auth ML: `https://auth.mercadolivre.com.br/authorization`
- Token ML expira em ~6h, usar refresh_token para renovar
- Rate limit ML: 1 req/seg por padrão, implementar retry com backoff
