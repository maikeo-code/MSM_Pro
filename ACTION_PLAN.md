# Plano de Ação — MSM_Pro Next Steps
**Data:** 29/03/2026
**Proprietário:** Maikeo (decisões) + Team (execução)

---

## Contexto Rápido

Análise revelou: **MSM_Pro tem fundação sólida mas está faltando features críticas que impedem adoção**. Usuário (Maikeo) abre o dashboard e fica confuso com 70 números. Não sabe o que fazer.

Recomendação: **2 semanas focadas em 4 tarefas P0** que mudam tudo.

---

## Decisões Necessárias (Maikeo)

### Decisão 1: Qual é a MAIOR dor de uso do dashboard?
**Opções:**
- [ ] A: "Abro o app e não sei qual métrica olhar" (falta priorização)
- [ ] B: "Sugestão de preço é confusa" (não confio na IA)
- [ ] C: "Não consigo dizer quanto vou vender próxima semana" (falta previsão)
- [ ] D: "Não sei qual produto descontinuar" (falta rentabilidade)

**Resposta recomendada:** A (Morning Routine)
**Razão:** Resolve 80% do problema de adoção. As outras virão depois.

---

### Decisão 2: Repricing automático — quer AGORA ou DEPOIS?
**Opções:**
- [ ] AGORA: Investe 5 dias agora, ganha R$ 3k/mês já
- [ ] DEPOIS: Foca em UX/Morning Routine primeiro (mais seguro)

**Resposta recomendada:** AGORA (paralelo com Morning Routine)
**Razão:** ROI = 600x (R$ 3k/mês ÷ 5 dias). Não há melhor investimento.

---

### Decisão 3: Confiança em repricing automático — qual % quer?
**Opções:**
- [ ] 70%+: "Se sistema diz aumentar preço, aumento direto"
- [ ] 90%+: "Quero teste antes (A/B)" (mais seguro, mais lento)
- [ ] 50-60%: "Prefiro sugestão, eu decido" (status quo)

**Resposta recomendada:** 70%+
**Razão:** 70% de acerto = +8% margem. 90% de acerto = +10% mas leva mais 2 semanas.

---

### Decisão 4: SaaS público ou produto pessoal?
**Opções:**
- [ ] Produto pessoal: Maikeo usa, fim da história
- [ ] SaaS público: Beta com 3-5 importadores, depois escala
- [ ] Vendor da comunidade: Vende para 100+ vendedores ML

**Resposta recomendada:** SaaS público (longo prazo)
**Razão:** Potencial R$ 50k+/ano. Maikeo já quer isso.

---

## Tarefas Imediatas (Próximas 2 Semanas)

### Sprint 3A — Core Fix (Semana 1)
**Objetivo:** Dashboard que responde "O que fazer agora em 3 minutos"

#### Tarefa 1.1: Morning Routine Card (Front-end)
**Descrição:** Card destacado no topo do dashboard com:
- "Mudanças 24h": Receita (↑ ou ↓ %), Conversão (↑ ou ↓ pp), Estoque (↑ ou ↓ un)
- Top 3 ações urgentes (cada uma com ícone + recomendação):
  - 🔴 Anúncio sem vendas há 3 dias
  - 🟡 Estoque crítico (< 10 unidades)
  - 🟢 Oportunidade: aumentar preço de MLB-XXX
- Comparação com semana anterior (mesma métrica, % mudança)

**Tempo estimado:** 3 dias (design + front-end)
**Dépendencia:** Nenhuma (usa dados já disponíveis no backend)
**Owner:** Frontend dev
**Success criteria:**
- [ ] Card visível no topo do dashboard (acima de tudo)
- [ ] Mostra 3 ações com recomendação específica (não genérica)
- [ ] Comparação 24h visible e clara
- [ ] Testado em mobile + desktop

---

#### Tarefa 1.2: Dashboard Redesign (Simplificação)
**Descrição:** Reorganizar dashboard para focar em 5 métricas críticas:

**Remover/hide:**
- Módulos: Perguntas, Reputação, Atendimento (mover para abas/drawer)
- Gráficos menos relevantes (heatmap de vendas por hora)

**Manter visível:**
- KPI cards: Receita, Conversão, Estoque, Visitas, Margens
- Tabela anúncios (filtrada por período)
- Morning Routine card (nova)
- Alertas ativos

**Tempo estimado:** 2 dias
**Owner:** Frontend/UX
**Success criteria:**
- [ ] Dashboard carrega em <2 segundos
- [ ] Usuário vê 5 números principais em < 3 segundos
- [ ] Menos de 10 cliques para acessar funcionalidade específica

---

#### Tarefa 1.3: Backend KPI Optimization
**Descrição:** Assegurar que backend calcula mudanças 24h rapidamente

**Checklist:**
- [ ] Endpoint `/api/v1/kpi/summary?period=1d&compare=7d` existente e testado
- [ ] Query usa `COUNT(DISTINCT listing_id)` (não snapshots)
- [ ] Calcula variação % correta: (hoje - ontem) / ontem × 100
- [ ] Performance: <500ms mesmo com 50+ anúncios
- [ ] Cache em Redis para 5 minutos

**Tempo estimado:** 1 dia
**Owner:** Backend dev
**Success criteria:**
- [ ] curl testa endpoint e retorna dados corretos
- [ ] Variação 24h é precisa
- [ ] Performance aceitável

---

### Sprint 3B — High ROI Features (Semana 2)
**Objetivo:** Repricing automático funcional + confiança >70%

#### Tarefa 2.1: Repricing Automático — Aplicação
**Descrição:** Completar lógica de repricing automático (aplicar preço, não apenas sugerir)

**Status atual:**
- ✅ Backend sugere preço via IA
- ❌ Não aplica automaticamente
- ❌ Frontend mostra sugestão, usuário ignora

**O que fazer:**
1. Criar API `POST /api/v1/listings/{mlb_id}/reprice` que:
   - Recebe sugestão de preço
   - Valida (confiança >70%)
   - Aplica NO MERCADO LIVRE (via API ML, não localmente)
   - Loga mudança (tabela `price_change_logs`)
   - Notifica usuário (email/push)

2. Scheduler (Celery task) que roda a cada 6 horas:
   - Calcula sugestão de preço para anúncios ativos
   - Filtra por confiança >70%
   - Aplica automático
   - Limita: máx 5 mudanças por dia por anúncio (evita thrashing)

3. Rules de segurança:
   - [ ] Nunca aumenta preço >20% em 1 dia
   - [ ] Nunca diminui preço <30% da margem esperada
   - [ ] Respeita limites de stock (não vender o que não tem)
   - [ ] Desabilita se concorrente mudou preço (evita guerra de preços)

**Tempo estimado:** 5 dias
**Owner:** Backend dev
**Testes:**
- [ ] Manual: aplicar repricing em 1 anúncio teste, verificar no ML
- [ ] Produção light: 3-5 anúncios com repricing automático, medir conversão antes/depois
- [ ] Documentar histórico de mudanças (X anúncios, Y mudanças, Z% acertos)

**Success criteria:**
- [ ] Repricing automático aplicado no ML (não apenas sugestão)
- [ ] Confiança calculada corretamente
- [ ] Histórico rastreável (audit trail)
- [ ] Segurança: não pode quebrar margem do usuário

---

#### Tarefa 2.2: UX para Repricing (Front-end)
**Descrição:** Interface para usuário comfiar e gerenciar repricing automático

**Telas:**
1. Modal de confirmação: "Sistema sugere aumentar MLB-XXX de R$ 189 para R$ 209 (confiança: 75%). Aplicar automático?"
2. Dashboard repricing: histórico de mudanças (quais, quando, resultado)
3. Settings: habilitar/desabilitar repricing automático por anúncio
4. Análise: "Se tivesse repriced no dia X, teria ganho +R$ 500"

**Tempo estimado:** 2 dias
**Owner:** Frontend dev
**Success criteria:**
- [ ] Usuário vê confiança da sugestão (não apenas número)
- [ ] Pode ver histórico de mudanças
- [ ] Pode desabilitar repricing por anúncio
- [ ] Análise retrospectiva mostra impacto

---

#### Tarefa 2.3: Testing + Validation
**Descrição:** Validar repricing em produção antes de 100% rollout

**Plano:**
1. Semana 2: Testar com 3-5 anúncios de teste
2. Medir: conversão antes/depois, margem antes/depois
3. Documento: resultados reais (screenshot, números)
4. Decisão: full rollout ou iterate

**Tempo estimado:** 3 dias (execução + análise)
**Owner:** Maikeo (validação) + Dev (instrumentação)

---

## Timeline Visual

```
Semana 1 (Abril 1-7)          Semana 2 (Abril 8-14)
├─ Morning Routine (3d)       ├─ Repricing Automático (5d)
├─ Dashboard Redesign (2d)    ├─ Repricing UX (2d)
└─ KPI Backend (1d)           ├─ Testing & Validation (3d)
                               └─ Buffer para bugs (2d)

Semana 3-4 (Abril 15-30)
├─ Bug fixes from testing
├─ Production monitoring
└─ Prepare Phase 2 (Estoque, Rentabilidade)
```

---

## Definição de Sucesso (Fim de Abril)

### Product
- [ ] Morning Routine card exibe top 3 ações de forma clara
- [ ] Dashboard carrega em <2s, mostra 5 métricas críticas em <3s
- [ ] Repricing automático aplicado com confiança >70%
- [ ] Histórico de mudanças rastreável
- [ ] Zero segurança issues (margens protegidas)

### Business
- [ ] Maikeo usa dashboard 5x/semana (vs 2x antes)
- [ ] Repricing aplica em 10+ anúncios em abril
- [ ] Margem média dos anúncios repriced: +5-8% (medindo)
- [ ] NPS feedback: "Agora entendo o que fazer" (qualitativo)

### Technical
- [ ] Testes: 20%+ cobertura (vs 2%)
- [ ] Deploys: zero downtime via GitHub Actions
- [ ] Monitoring: Sentry para erros, logs estruturados
- [ ] Performance: p95 latência < 500ms

---

## Próxima Fase (Maio — Phase 2)

Após sucesso em abril, iniciar:

1. **Estoque Inteligente** (4 dias)
   - Projeção de demanda 30 dias
   - Alerta: "Vai faltar em 8 dias"

2. **Rentabilidade por Produto** (3 dias)
   - Tabela SKU ranking
   - Decisão: descontinuar ou não

3. **Integração IA_geral** (2 dias)
   - Custo SKU automático via IA_geral
   - Elimina Excel do workflow

4. **Push Notifications** (3 dias)
   - Alertas no celular (não apenas email)
   - Whatsapp Business opcional

---

## Comunicação & Alinhamento

### Com Maikeo
- **Check-in:** Seg/Qua (15 min)
  - Progresso na semana
  - Bloqueadores
  - Feedback de UX
- **Demo:** Sexta (30 min)
  - Live build
  - Validação antes de merge

### Com Team
- **Daily standup:** 10 min (Seg-Sexta)
- **Blockers:** async no Slack
- **Code review:** antes de merge (todo código novo)

---

## Contingency (Se algo quebrar)

| Problema | Plano B |
|----------|---------|
| Repricing demora >5 dias | Fazer sugestão com UX melhor, repricing automático é Phase 2 |
| Morning Routine card complexo demais | MVP: apenas 3 KPI mudanças + top 1 ação (não 3) |
| API ML rejeitando repricing | Implementar via web scraping (mais lento, menos confiável) |
| Tempo pra testes insuficiente | Testar com 2 anúncios apenas (não 5) |
| Maikeo indisponível para validação | Usar dados históricos para medir impacto |

---

## Orçamento (Estimado)

| Item | Custo | Notas |
|------|-------|-------|
| Dev time (10 dias × R$ 300/h × 8h) | R$ 24k | Salário/contractor |
| Cloud infra (Railway, dados) | R$ 500 | Já pago |
| Ferramentas (Sentry, etc) | R$ 200 | Já pago |
| **Total** | **R$ 24.7k** | Break-even em 8 meses (repricing ROI) |

---

## Assinatura

- [ ] **Maikeo** — Aprova prioridades e timeline?
- [ ] **Tech Lead** — Aprova tarefas e estimativas?
- [ ] **Frontend Lead** — Aprova UX/design simplificação?
- [ ] **Backend Lead** — Aprova repricing automático roadmap?

**Data de início recomendada:** Segunda, 01/04/2026

---

## Referências Rápidas

- Análise completa: `/MSM_Pro/PRODUCT_ANALYSIS.md`
- Doc técnico: `/MSM_Pro/CLAUDE.md`
- IA_geral integration: `/IA_geral_processos_dados/CLAUDE.md`
- Roadmap: `/MSM_Pro/PRODUCT_ANALYSIS.md` (seção 7)

