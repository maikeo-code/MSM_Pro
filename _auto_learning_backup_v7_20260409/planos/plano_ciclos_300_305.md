# Plano Estratégico — Ciclos 300-305

> Gerado: 2026-03-18 | Score Global: 82 | Ciclos Completos: 300

## Situação Atual

| Área | Score | Tendência |
|------|-------|-----------|
| code_quality | 85 | ↑ +5 (2 ciclos) |
| error_handling | 82 | ↑ +7 (2 ciclos) |
| security | 80 | ↑ +5 (2 ciclos) |
| architecture | 80 | ↑ +5 (2 ciclos) |
| features | 78 | = |
| deploy | 78 | = |
| frontend | 76 | +1 |
| testing | 75 | = |

## Plano

### Ciclo 301: Módulo de Reclamações (Claims)
- **Objetivo:** Implementar backend + frontend para Claims do ML
- **Endpoints ML:** `/v1/claims/search`, `/v1/claims/{id}`
- **Backend:** model, schemas, router, service em `backend/app/reclamacoes/`
- **Frontend:** página Reclamações com tabs (aberta/fechada/mediação)
- **Critério sucesso:** Claims listadas no frontend com dados reais
- **Risco:** API de Claims pode exigir scope OAuth diferente

### Ciclo 302: Testes de Integração Novos Módulos
- **Objetivo:** Testes para perguntas, repricing, digest, webhook
- **Cobertura alvo:** 25% → 35%
- **Foco:** Endpoints críticos (auth, sync, KPI, repricing CRUD)
- **Critério sucesso:** pytest passando com >35% coverage

### Ciclo 303: Frontend Polish
- **Objetivo:** UX improvements baseados em análise real
- **Foco:** Loading states, error boundaries, empty states consistentes
- **Badge de perguntas pendentes no sidebar
- **Critério sucesso:** Todas as páginas com loading/error/empty states

### Ciclo 304: Performance & Monitoring
- **Objetivo:** Query optimization + observability
- **Foco:** Slow queries, missing indexes, Sentry integration
- **Critério sucesso:** P95 latency < 500ms em endpoints KPI

### Ciclo 305: Consolidação & Documentação
- **Objetivo:** API docs completa, README atualizado, deploy checklist
- **Foco:** OpenAPI spec review, README, changelog
- **Critério sucesso:** Score global > 85

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Claims API scope diferente | Alta | Testar OAuth scopes antes de implementar |
| Testes quebram em CI | Média | Usar fixtures isoladas, não depender de DB real |
| Deploy falha com migration 0015 | Baixa | Index parcial é PostgreSQL-specific, verificar |

## Brainstorm Criativo (4 técnicas)

### 1. Inversão
E se em vez de BUSCAR dados do ML periodicamente, o ML nos NOTIFICASSE em tempo real?
→ Já temos webhook! Mas ele só faz sync. Poderia triggar push notification no frontend via SSE.

### 2. Transferência
Como o UpSeller resolve claims? → Provavelmente agrega claims + perguntas numa visão "Atendimento" unificada.
→ **Ideia:** Criar página "Atendimento" que unifica Perguntas + Reclamações + Devoluções.

### 3. Eliminação
O que podemos REMOVER? → `service_mock.py` (118 linhas) — dados mock que não são mais usados.
→ `ws/__init__.py` — placeholder vazio. Se WebSocket está adiado, remover a pasta.

### 4. Combinação
Combinar Alertas + Consultor IA → Quando alerta dispara, automaticamente gerar recomendação IA.
→ **Ideia:** Alert event → Claude Haiku analisa contexto → sugestão automática no email de alerta.
