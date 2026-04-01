# Análise de Produto — MSM_Pro
**Data:** 29/03/2026
**Versão:** 1.0

---

## Resumo Executivo (2 min)

MSM_Pro é um **dashboard de IA para Mercado Livre** com arquitetura sólida (FastAPI + React 18) mas **lacunas críticas** que impedem adoção total. O produto está 52% completo. Antes de pensar em escala, precisamos resolver 4 gaps P0 que impactam decisões diárias.

**Status:** ✅ Fundação OK | ❌ Features-gap críticas | ❌ UX confusa | ⚠️ Diferencial fraco

---

## 1. O Que Está Implementado (Bem)

### ✅ Features Funcionando
- Dashboard com KPI (Hoje/Ontem/Anteontem)
- Tabela de anúncios filtrada por período (7d, 15d, 30d, 60d)
- Histórico de preços com snapshots diários
- Financeiro (receita, taxa ML real, frete, margem)
- Alertas configuráveis (email funciona, mas pode estar em spam)
- Health score por anúncio
- Intel com IA (Pareto, previsão de vendas, insights)
- Sugestão de preços (via Claude API)
- Multi-conta Mercado Livre

**Força técnica:** Stack moderno (async, migrations, testes estruturados)

---

## 2. O Que FALTA (Gaps Críticos para Adoção)

### ❌ Gap 1: "Morning Routine" — O que mudou hoje?
**Impacto:** CRÍTICO — usuário abre o app e fica confuso

Cenário ideal (5 min, celular, pé da cama):
1. Vê card VERMELHO: "2 anúncios sem vendas há 3 dias"
2. Recomendação: "Reduzir preço 10-15% — pode recuperar conversão"
3. Vê: "Receita ontem R$ 850 (↑12% vs semana)"
4. Toma decisão e sai

Realidade atual:
1. Abre dashboard com 16 anúncios + 70 números
2. Fica confuso qual métrica olhar
3. Fecha app e volta ao Excel

**Solução:** Card destacado com "Mudanças 24h" + top 3 ações urgentes + comparação vs semana anterior.

---

### ❌ Gap 2: Repricing Automático Incompleto
**Impacto:** CRÍTICO — +10% margem = +R$ 3k/mês

Status atual:
- ✅ Backend sugere preço via IA
- ❌ Não aplica automaticamente
- ❌ Usuário ignora sugestão (confiabilidade 50-60%)

Deveria:
- Aplicar automático em horários otimizados
- A/B testing (vende 2 un a R$ 189, 2 un a R$ 199, mede conversão)
- Histórico: "Se tivesse aumentado preço no dia X, teria ganho +R$ 500"

---

### ❌ Gap 3: Gestão de Estoque Inteligente
**Impacto:** ALTO — evita stockout (perda vendas) e excesso (cash imobilizado)

Faltam:
- Projeção: "Suporte celular vai faltar em 8 dias"
- Alertas: "Encomendar agora para chegar antes"
- Integração com IA_geral para quantidade reposição

**ROI:** +R$ 1-2k/mês (evita stockout)

---

### ❌ Gap 4: Análise de Rentabilidade por Produto
**Impacto:** ALTO — decisão de descontinuar produtos

Usuário calcula em Excel: "Cadeira tem 5% margem, Acessório tem 45% — vou parar cadeira"

Deveria estar no dashboard:
- Tabela: SKU | Vendas | Receita | Custo | Taxa | Frete | Margem %
- Ranking: produtos mais/menos rentáveis
- Alerta: "Produto X tem conversão <1% — considere descontinuar"

---

## 3. Valor para o Negócio (Priorização)

| Feature | Valor | Esforço | ROI | Prazo |
|---------|-------|---------|-----|-------|
| **Morning Routine** | +insight decisão rápida | 3d | Alto | P0 |
| **Repricing Automático** | +R$ 3k/mês (margem) | 5d | Crítico | P0 |
| **Limpeza UX** | -confusão | 2d | Alto | P0 |
| **Estoque Inteligente** | +R$ 1-2k/mês | 4d | Alto | P1 |
| **Rentabilidade por SKU** | +decisão estratégica | 3d | Alto | P1 |
| **Notificações Mobile** | +responsividade | 3d | Médio | P2 |

**Conclusão:** Foco em P0 (próximas 2 semanas) resolve 80% do problema de adoção.

---

## 4. UX — O Problema Real

### Cenário Atual (confuso)
Dashboard exibe:
- Tabela 16 anúncios
- 10 KPI cards diferentes
- 4 gráficos
- 70+ números em simultâneo

Resultado: Usuário não sabe qual métrica é mais importante. **Paralisia por escolha.**

### Cenário Ideal (priorizado)
Dashboard exibe (hierarquia):

**ZONA VERMELHA (ação urgente):**
- 3 cards: anúncios sem vendas, estoque crítico, conversão em queda
- Call-to-action: "Reduza preço para R$ 189" (específico, não genérico)

**ZONA AMARELA (oportunidades):**
- Anúncio com conversão alta — pode aumentar preço
- Produto com vendas crescentes — aumentar estoque

**ZONA VERDE (tudo bem):**
- Anúncios em ritmo normal
- Estoque saudável
- Margens OK

---

## 5. Diferencial Competitivo

### Concorrentes
- **Nubimetrics:** Dashboard ML + alertas genéricos
- **Real Trends:** Analytics puro, sem recomendação
- **Plugg.to:** Automação de tarefas
- **ChatGPT:** Dá sugestão mas usuário não confia

### O que MSM_Pro TEM que outros NÃO
- ✅ IA especializada (Claude) para preços
- ✅ Multi-conta consolidada
- ✅ Snapshots históricos (dados não deletam)
- ✅ Health score proprietário
- ✅ Integração com IA_geral (automação)

### O que FALTA para ser diferencial real
- ❌ Repricing automático de VERDADE (não apenas sugestão)
- ❌ Insights específicos ("Aumentar MLB-XXX para R$ 189") vs genéricos
- ❌ Automação de estoque
- ❌ UX intuitiva (vs 70 números em simultâneo)

---

## 6. Proposta de Valor (Revisada)

**Atual:** "Dashboard para Mercado Livre"
**Revisada:** "Automação inteligente de preços e estoque. Ganhe 10-15% de margem sem aumentar volume"

**Prova:** Maikeo deveria ganhar +R$ 3-5k/mês após implementar features P0/P1.

---

## 7. Roadmap Priorizado (3 meses)

### Mês 1 (Abril) — Solidify Core
**Objetivo:** Dashboard que responde "O que fazer agora?"

- Semana 1-2: Morning routine card + dashboard redesign
- Semana 2-3: Repricing automático (aplicação, não apenas sugestão)
- Semana 3-4: Testes + polishing

**Resultado esperado:** Usuário abre app, vê 5 números importantes, toma decisão em 3 minutos.

---

### Mês 2 (Maio) — Add High-Value Features
**Objetivo:** Usuário economiza R$ 2-5k/mês

- Semana 1: Estoque inteligente (projeção + alertas)
- Semana 2: Rentabilidade por produto
- Semana 3: Integração automática custo SKU (via IA_geral)
- Semana 4: Push notifications + Whatsapp

---

### Mês 3 (Junho) — Diferencial + Community
**Objetivo:** Claro diferencial vs Nubimetrics

- Semana 1-2: Multi-marketplace (Shopee MVP)
- Semana 2-3: Análise concorrência inteligente + auto-repricing vs rivais
- Semana 4: Go-to-market (blog, vídeos, landing page)

---

## 8. Problemas Técnicos Críticos

| # | Problema | Severidade | Impacto | Fix |
|---|----------|-----------|--------|-----|
| 1 | service.py tem 2.109 linhas | Alta | Hard to maintain | Refactor em submódulos |
| 2 | Tokens OAuth plaintext no BD | Crítica | Security risk | Encrypt com Fernet |
| 3 | Asyncio.Lock entre workers | Alta | Race conditions | Redis lock |
| 4 | Testes: 2% cobertura | Crítica | Silent bugs | pytest suite |
| 5 | Sem CI/CD pipeline | Alta | Deploy manual | GitHub Actions |

**Urgência:** 1-2-4 devem ser resolvidos antes de oferecer SaaS público.

---

## 9. Métricas de Sucesso

### Product Metrics
- Adoption: >60% features usadas
- Engagement: 4-5 logins/semana (vs 2 atualmente)
- Retention: 85%+ após 30 dias
- NPS: >50

### Business Metrics (Maikeo pessoalmente)
- Margem atual: ~30% (estimado)
- Target: +10-15% via otimização = +R$ 3-5k/mês
- Break-even: Mês 2-3 após features P1 prontas

### SaaS (futuro)
- Price: R$ 99/mês (Pro), R$ 499/mês (Enterprise)
- Target: 10-20 usuários Pro em 12 meses = R$ 10-20k/ano
- CAC: <R$ 200 (referência comunidade importadores)

---

## 10. Recomendações Imediatas

### Decisão 1: Simplificar ou Expandir?
**→ Simplificar.** Hide módulos menos usados (Perguntas, Reputação, Atendimento). Foco em 5 métricas críticas.

### Decisão 2: Repricing Automático AGORA ou DEPOIS?
**→ AGORA.** +10% margem = R$ 3k/mês. Custo: 5 dias. ROI = 600x.

### Decisão 3: Multi-Marketplace ou Focar ML?
**→ Focar Mercado Livre.** Ter 1 coisa excelente que 2 coisas médias.

### Decisão 4: SaaS Público ou Produto Pessoal?
**→ SaaS público** (longo prazo) começando com 3-5 beta users importadores.

---

## 11. Próximos Passos

1. **Validar com Maikeo** (hoje/amanhã)
   - Confirmar prioridades (Morning Routine > Repricing > Estoque?)
   - Validar ROI estimado (R$ 3-5k/mês)
   - Confirmar timeline (Mês 1-2 vs Mês 1-3)

2. **Iniciar Sprint 3** (semana que vem)
   - Tarefa 1: Morning Routine card
   - Tarefa 2: Dashboard redesign
   - Tarefa 3: Repricing automático

3. **Teste em produção** (fim de abril)
   - Testar repricing com 3-5 anúncios
   - Medir conversão antes/depois
   - Documentar resultados

4. **Escala para SaaS** (maio-junho)
   - Beta com 3-5 importadores
   - Colher feedback
   - Iterar rapidamente

---

## 12. Análise Visual (Comparativo)

### Maturidade vs Concorrentes
```
Nubimetrics: ████████░░ (80%)  ← Dashboard + alertas + sugestão genérica
Real Trends: ████████░░ (80%)  ← Analytics puro, sem ação
MSM_Pro:     █████░░░░░ (50%)  ← Fundação OK, gaps críticos
```

### Roadmap Visual
```
Abril          Maio            Junho
Core Ready  → High Value   →  Diferencial
├─ Morning  ├─ Estoque    ├─ Multi-MM
├─ Repricing├─ Rent/SKU   ├─ AI Concor
├─ Clean UX└─ Push Notif  └─ Go2Market
```

---

## Conclusão

**MSM_Pro tem potencial**, mas precisa resolver feature gaps P0 **ANTES** de pensar em escala. As próximas 4 semanas são críticas:

1. Morning Routine card (usuário entende o que fazer)
2. Repricing automático (ganha R$ 3k/mês)
3. UX limpa (remove overwhelm)
4. Testes (confiança para produção)

**Prazo:** Maio 2026, 95% de maturidade na core.
**Upside:** R$ 50k+/ano em SaaS público se escalar para 50+ usuários.

