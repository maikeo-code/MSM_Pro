# PLANO DE IMPLEMENTACAO — Nubimetrics Intel para MSM_Pro

> Versao: 1.0
> Data: 2026-03-18
> Status: Aprovado para execucao
> Autor: Architect Reviewer Agent

---

## VISAO GERAL DAS FASES

```
FASE 1              FASE 2              FASE 3              FASE 4              FASE 5
Reforco Base        Market Intel        Competitive Intel   Motor IA            Ferramentas Pro
(2-3 semanas)       (3-4 semanas)       (3-4 semanas)       (4-5 semanas)       (2-3 semanas)
|                   |                   |                   |                   |
+-- Projecao        +-- Categorias      +-- Monitor 20      +-- Otimizador      +-- Export CSV
+-- Pareto          +-- Rankings        +-- Dashboard       +-- Sugestao        +-- Alertas v2
+-- Distribuicao    +-- Keywords        +-- Est. vendas     +-- Preco IA        +-- Multi-conta
+-- Margem/lucro    +-- Sazonalidade    +-- Comparacao      +-- Previsao        +-- Relatorios
+-- Score basico    +-- Oportunidades   +-- Pareto conc.    +-- Visibilidade    +-- Reputacao
|                   |                   |                   +-- Recomendacoes   |
|                   |                   |                   |                   |
ENTREGA: Valor      ENTREGA: Diferencial ENTREGA: Vantagem  ENTREGA: IA como   ENTREGA: Polish
imediato com        unico - entender   competitiva real    diferencial         e conveniencia
dados que ja tem    o mercado                              estrategico
```

---

## FASE 1 — REFORCO DO "MEU NEGOCIO" (2-3 semanas)

### Objetivo
Fortalecer o dashboard existente com analytics avancadas usando dados que o MSM_Pro ja coleta.
Zero novas integracoes com ML API. Resultado: usuario ve valor imediato.

### Features

#### 1.1 Projecao de Vendas (Forecast)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Projetar vendas futuras (7d, 30d) por anuncio e total |
| **Algoritmo** | Linear regression sobre snapshots + weighted moving average (30d) |
| **Backend** | `intel/analytics/service_forecast.py` + endpoint GET |
| **Frontend** | Grafico de linha com area de confianca (Recharts) |
| **Dados** | `listing_snapshots` existentes (sem nova coleta) |
| **Complexidade** | Media |
| **Esforco** | 3-4 dias |
| **Dependencia** | Minimo 30 dias de snapshots historicos |
| **Prioridade** | P0 — entrega valor direto ao vendedor |

#### 1.2 Analise Pareto 80/20
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Identificar quais 20% dos anuncios geram 80% da receita |
| **Algoritmo** | Sort DESC por revenue, calculo de percentil acumulado |
| **Backend** | `intel/analytics/service_pareto.py` + endpoint GET |
| **Frontend** | Grafico de barras + linha acumulada (Recharts) |
| **Dados** | Snapshots + Orders existentes |
| **Complexidade** | Baixa |
| **Esforco** | 2 dias |
| **Dependencia** | Nenhuma |
| **Prioridade** | P0 |

#### 1.3 Distribuicao de Vendas por Anuncio
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Grafico de pizza/treemap mostrando participacao de cada anuncio |
| **Backend** | `intel/analytics/service.py` (funcao simples, sem service proprio) |
| **Frontend** | Treemap chart (Recharts) com drill-down |
| **Complexidade** | Baixa |
| **Esforco** | 1-2 dias |
| **Dependencia** | Nenhuma |
| **Prioridade** | P1 |

#### 1.4 Controle de Margem/Lucro por Produto
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Calculadora: preco - custo_sku - taxa_ml - frete = margem |
| **Backend** | Expande `vendas/service_calculations.py` existente |
| **Frontend** | Tabela com colunas de margem + grafico de margem vs volume |
| **Dados** | Products.cost + Listings.sale_fee_amount + avg_shipping_cost |
| **Complexidade** | Media |
| **Esforco** | 3 dias |
| **Dependencia** | Usuario deve cadastrar custo do SKU (feature ja planejada) |
| **Prioridade** | P0 |

#### 1.5 Score de Saude do Anuncio (Basico)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Nota 0-100 baseada em criterios objetivos (sem IA) |
| **Criterios** | Titulo > 40 chars, fotos >= 5, quality_score ML, conversao > 2%, etc |
| **Backend** | `intel/analytics/` ou `vendas/service_health.py` (ja existe parcial) |
| **Frontend** | Gauge component + checklist de gaps |
| **Complexidade** | Media |
| **Esforco** | 2-3 dias |
| **Dependencia** | Nenhuma |
| **Prioridade** | P1 |

### Entregaveis Fase 1
- [ ] Migrations Alembic para `analytics_cache`, `user_insights`
- [ ] 4 novos endpoints em `/api/v1/intel/analytics/`
- [ ] 4 novas paginas/componentes no frontend
- [ ] Testes unitarios para calculos de forecast e pareto
- [ ] Documentacao dos endpoints no Swagger

### Cronograma Fase 1

```
Semana 1:
  Dia 1-2: Setup modulo intel/analytics + migrations + schemas
  Dia 3-4: Pareto service + endpoint + frontend
  Dia 5:   Distribuicao service + frontend

Semana 2:
  Dia 1-3: Forecast service (algoritmo + cache) + endpoint + frontend
  Dia 4-5: Margem/lucro (backend + frontend)

Semana 3:
  Dia 1-2: Score basico de saude do anuncio
  Dia 3:   Testes + ajustes
  Dia 4-5: QA + deploy + documentacao
```

---

## FASE 2 — INTELIGENCIA DE MERCADO (3-4 semanas)

### Objetivo
Implementar o diferencial principal: entender o mercado alem das proprias vendas.
Novas integracoes com endpoints da ML API que o MSM_Pro ainda nao usa.

### Pre-requisitos
- Fase 1 concluida (analytics engine base funcional)
- Novos metodos em `client.py` validados pelo agente `ml-api`

### Features

#### 2.1 Explorador de Categorias (Drill-Down)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Navegar pela arvore de categorias do ML com stats por nivel |
| **ML API** | `GET /sites/MLB/categories`, `GET /categories/{id}` |
| **Backend** | `intel/market/service_categories.py` + tabela `ml_categories` |
| **Frontend** | Tree view com breadcrumb + stats por categoria selecionada |
| **Complexidade** | Alta |
| **Esforco** | 5-6 dias |
| **Prioridade** | P0 |

#### 2.2 Rankings de Demanda por Categoria
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Top produtos vendidos em cada categoria (estimativa) |
| **ML API** | `GET /sites/MLB/search?category={id}&sort=sold_quantity_desc` |
| **Backend** | `intel/market/service_demand.py` + tabela `category_snapshots` |
| **Frontend** | Tabela com ranking + evolucao temporal |
| **Complexidade** | Alta |
| **Esforco** | 4-5 dias |
| **Prioridade** | P0 |

#### 2.3 Rankings de Palavras-Chave
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Palavras mais buscadas em cada categoria |
| **ML API** | `GET /trends/MLB/search?category={id}`, search suggestions |
| **Backend** | `intel/market/service_keywords.py` + tabela `keyword_rankings` |
| **Frontend** | Tabela com volume, tendencia, resultados |
| **Complexidade** | Alta |
| **Esforco** | 4-5 dias |
| **Prioridade** | P0 |

#### 2.4 Ranking de Marcas por Categoria
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Quais marcas dominam cada categoria |
| **ML API** | Derivado de search results (atributo marca) |
| **Backend** | `intel/market/service_demand.py` (extende) |
| **Frontend** | Tabela + grafico de pizza de market share |
| **Complexidade** | Media |
| **Esforco** | 3 dias |
| **Prioridade** | P1 |

#### 2.5 Sazonalidade
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Padroes temporais de demanda por categoria (12 meses) |
| **Dados** | `category_snapshots` (requer 3+ meses de coleta) |
| **Backend** | `intel/analytics/service_seasonality.py` |
| **Frontend** | Heatmap mensal + grafico de linha |
| **Complexidade** | Media |
| **Esforco** | 3-4 dias |
| **Prioridade** | P1 |

#### 2.6 Oportunidades de Demanda Insatisfeita
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Cruzar alta busca com pouca oferta para encontrar nichos |
| **Algoritmo** | demand_supply_ratio = search_volume / supply_count |
| **Backend** | `intel/market/service_demand.py` + tabela `demand_opportunities` |
| **Frontend** | Cards de oportunidades + score |
| **Complexidade** | Alta |
| **Esforco** | 4-5 dias |
| **Prioridade** | P0 |

### Entregaveis Fase 2
- [ ] Migrations para `ml_categories`, `category_snapshots`, `keyword_rankings`, `demand_opportunities`
- [ ] 6+ novos metodos em `client.py` (validados por agente `ml-api`)
- [ ] Celery tasks: `sync_category_tree`, `sync_category_snapshots`, `sync_keyword_rankings`
- [ ] 12+ novos endpoints em `/api/v1/intel/market/`
- [ ] Pagina Market Intel completa no frontend
- [ ] Cache Redis para dados de categorias

### Cronograma Fase 2

```
Semana 1:
  Dia 1-2: Migrations + novos metodos client.py + validacao ml-api
  Dia 3-5: Explorador de categorias (backend + frontend)

Semana 2:
  Dia 1-3: Rankings de demanda (coleta + display + cache)
  Dia 4-5: Rankings de keywords (trends API + display)

Semana 3:
  Dia 1-2: Ranking de marcas
  Dia 3-4: Celery tasks de coleta automatica
  Dia 5:   Oportunidades de demanda (backend)

Semana 4:
  Dia 1-2: Oportunidades (frontend + scoring)
  Dia 3:   Sazonalidade (preparacao — dados reais em 3 meses)
  Dia 4-5: QA + testes + deploy + documentacao
```

---

## FASE 3 — INTELIGENCIA COMPETITIVA (3-4 semanas)

### Objetivo
Monitorar concorrentes sistematicamente: sellers, precos, vendas estimadas, estrategias.
Expande o modulo `concorrencia/` existente com capabilities empresariais.

### Pre-requisitos
- Fase 1 concluida
- `client.py` com metodos de seller/search (Fase 2)

### Features

#### 3.1 Monitoramento de Sellers (ate 20)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Adicionar sellers concorrentes e coletar dados diariamente |
| **ML API** | `GET /users/{id}`, `GET /users/{id}/items/search` |
| **Backend** | `intel/competitors/service.py` + tabelas `monitored_sellers`, `seller_snapshots` |
| **Frontend** | Lista de sellers + botao adicionar + status sync |
| **Complexidade** | Alta |
| **Esforco** | 5-6 dias |
| **Prioridade** | P0 |

#### 3.2 Dashboard por Concorrente
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Visao consolidada de um seller: vendas, precos, anuncios |
| **Backend** | `intel/competitors/service_analysis.py` |
| **Frontend** | Pagina com KPIs + graficos + lista de anuncios |
| **Complexidade** | Media |
| **Esforco** | 4 dias |
| **Prioridade** | P0 |

#### 3.3 Estimativa de Vendas do Concorrente
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Estimar vendas diarias pelo delta de `sold_quantity` |
| **Algoritmo** | sold_qty(hoje) - sold_qty(ontem) = vendas_estimadas_dia |
| **Backend** | `intel/competitors/service_analysis.py` |
| **Frontend** | Grafico de vendas estimadas + ranking de produtos |
| **Complexidade** | Alta (precisao do delta) |
| **Esforco** | 4-5 dias |
| **Prioridade** | P0 |

#### 3.4 Comparacao de Precos
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Meu preco vs concorrente ao longo do tempo, por anuncio similar |
| **Backend** | Cruza `listing_snapshots` + `competitor_snapshots` |
| **Frontend** | Grafico de linhas sobrepostas + delta |
| **Complexidade** | Media |
| **Esforco** | 3-4 dias |
| **Prioridade** | P0 |

#### 3.5 Tracking de Anuncios do Concorrente (ate 120)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Monitorar anuncios especificos de concorrentes |
| **Backend** | Expande `competitors` model + task de sync |
| **Dados** | Reutiliza `competitor_snapshots` existente |
| **Complexidade** | Alta |
| **Esforco** | 4 dias |
| **Prioridade** | P1 |

#### 3.6 Pareto 80/20 do Concorrente
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Quais 20% dos produtos do concorrente geram 80% das vendas |
| **Backend** | Reutiliza `service_pareto.py` da Fase 1 |
| **Frontend** | Mesmo chart, dados de outro seller |
| **Complexidade** | Media (logica ja pronta) |
| **Esforco** | 2 dias |
| **Prioridade** | P1 |

### Entregaveis Fase 3
- [ ] Migrations para `monitored_sellers`, `seller_snapshots`
- [ ] Celery task `sync_all_monitored_sellers` com fanout por seller
- [ ] 10+ novos endpoints em `/api/v1/intel/competitors/`
- [ ] Pagina Competitors Intel completa no frontend
- [ ] Integracao com alertas existentes (concorrente mudou preco)

### Cronograma Fase 3

```
Semana 1:
  Dia 1-2: Migrations + model + API de CRUD de sellers
  Dia 3-5: Celery task de sync + coleta de dados

Semana 2:
  Dia 1-3: Dashboard por concorrente (backend + frontend)
  Dia 4-5: Estimativa de vendas (algoritmo + display)

Semana 3:
  Dia 1-2: Comparacao de precos (grafico comparativo)
  Dia 3-4: Tracking de anuncios individuais
  Dia 5:   Pareto do concorrente

Semana 4:
  Dia 1:   Motor de descoberta automatica
  Dia 2-3: Integracao com alertas
  Dia 4-5: QA + testes + deploy
```

---

## FASE 4 — MOTOR DE IA E OTIMIZACAO (4-5 semanas)

### Objetivo
Usar Claude API para gerar recomendacoes inteligentes, otimizar titulos e sugerir precos.
Este e o diferencial estrategico que justifica o nome "Inteligencia".

### Pre-requisitos
- Fase 1 e 2 concluidas (dados de mercado + analytics disponiveis)
- Conta Anthropic com credito configurada
- `ANTHROPIC_API_KEY` na variavel de ambiente

### Features

#### 4.1 Otimizador de Anuncios (Claude AI)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Analise completa do anuncio com score e gaps |
| **IA** | Claude Haiku para scoring, Sonnet para recomendacoes |
| **Contexto enviado** | Titulo, preco, fotos, categoria, keywords top, concorrentes |
| **Backend** | `intel/optimizer/service_scoring.py` |
| **Frontend** | Pagina com gauge de score + lista de gaps + recomendacoes |
| **Custo estimado** | ~$0.01 por analise (Haiku) + ~$0.05 por otimizacao (Sonnet) |
| **Complexidade** | Alta |
| **Esforco** | 6-7 dias |
| **Prioridade** | P0 |

#### 4.2 Sugestao de Titulo Otimizado
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Gerar titulo ideal usando keywords da categoria + IA |
| **IA** | Claude Sonnet com context de keywords top da categoria |
| **Backend** | `intel/optimizer/service_titles.py` + tabela `title_suggestions` |
| **Frontend** | Preview do titulo atual vs sugerido + botao "Aplicar" |
| **Complexidade** | Media |
| **Esforco** | 4-5 dias |
| **Prioridade** | P0 |

#### 4.3 Sugestao de Preco Inteligente
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Recomendar faixa de preco ideal baseado em dados |
| **Algoritmo** | Cruzar: preco x conversao (proprios) + precos concorrentes + margem minima |
| **IA** | Opcional — Claude interpreta os dados e gera narrativa |
| **Backend** | `intel/optimizer/service_pricing.py` |
| **Frontend** | Slider de preco + grafico de impacto estimado |
| **Complexidade** | Alta |
| **Esforco** | 5-6 dias |
| **Prioridade** | P0 |

#### 4.4 Previsao de Demanda por Categoria (IA-enhanced)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Melhorar forecast da Fase 1 com dados de mercado |
| **Dados** | Category snapshots + seasonality + keyword trends |
| **Backend** | Estende `service_forecast.py` |
| **Complexidade** | Alta |
| **Esforco** | 4-5 dias |
| **Prioridade** | P1 |

#### 4.5 Visibilidade de Busca (Posicao no ML)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Em que posicao o anuncio aparece ao buscar a keyword |
| **ML API** | `GET /sites/MLB/search?q={keyword}` — verificar posicao do MLB |
| **Backend** | `intel/optimizer/` + campo `search_position` em listing_snapshots |
| **Frontend** | Badge de posicao + historico |
| **Complexidade** | Alta |
| **Esforco** | 4 dias |
| **Prioridade** | P0 |

#### 4.6 Recomendacoes Automaticas Diarias
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Celery task gera 3-5 insights diarios para o usuario |
| **IA** | Claude Haiku analisa dados e prioriza acoes |
| **Backend** | `tasks_optimizer.py` + `user_insights` |
| **Frontend** | Cards de insight no dashboard com acao sugerida |
| **Complexidade** | Media |
| **Esforco** | 3-4 dias |
| **Prioridade** | P1 |

### Entregaveis Fase 4
- [ ] Migrations para `optimization_reports`, `title_suggestions`
- [ ] Integracao com Anthropic API (SDK `anthropic` Python)
- [ ] Templates de prompts em `intel/optimizer/prompts.py`
- [ ] Celery tasks para otimizacao async
- [ ] Rate limiting de IA por usuario
- [ ] 8+ novos endpoints em `/api/v1/intel/optimizer/`
- [ ] Pagina Optimizer completa no frontend

### Cronograma Fase 4

```
Semana 1:
  Dia 1-2: Setup Anthropic SDK + prompts base + rate limiting
  Dia 3-5: Scoring engine (backend + task async)

Semana 2:
  Dia 1-3: Frontend do otimizador (score + gaps + recomendacoes)
  Dia 4-5: Sugestao de titulo (backend + preview)

Semana 3:
  Dia 1-2: Sugestao de titulo (apply via ML API + frontend)
  Dia 3-5: Sugestao de preco inteligente

Semana 4:
  Dia 1-2: Visibilidade de busca (coleta de posicao)
  Dia 3-4: Recomendacoes automaticas diarias
  Dia 5:   Previsao de demanda enhanced

Semana 5:
  Dia 1-2: Polish do frontend
  Dia 3-4: Testes + ajustes de prompts
  Dia 5:   QA + deploy
```

---

## FASE 5 — FERRAMENTAS PRO (2-3 semanas)

### Objetivo
Polir a plataforma com ferramentas de conveniencia que completam a experiencia.

### Features

#### 5.1 Exportacao CSV/Excel
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Exportar qualquer tabela para CSV |
| **Backend** | `intel/analytics/service_export.py` (streaming response) |
| **Frontend** | Botao "Exportar" em cada tabela |
| **Complexidade** | Baixa |
| **Esforco** | 2-3 dias |
| **Prioridade** | P1 |

#### 5.2 Sistema de Alertas v2
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Novos tipos: posicao caiu, oportunidade detectada, score baixo |
| **Backend** | Estende `alertas/` existente |
| **Frontend** | Expande pagina de alertas |
| **Complexidade** | Media |
| **Esforco** | 3-4 dias |
| **Prioridade** | P1 |

#### 5.3 Multi-conta/Operadores com Permissoes
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Adicionar sub-usuarios com roles (admin, viewer, operator) |
| **Backend** | Nova tabela `user_roles` + middleware de permissoes |
| **Frontend** | Pagina de gestao de usuarios |
| **Complexidade** | Media |
| **Esforco** | 4-5 dias |
| **Prioridade** | P2 |

#### 5.4 Relatorios Automaticos (PDF/Email)
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Relatorio semanal/mensal automatico enviado por email |
| **Backend** | Celery task + template HTML + SMTP |
| **Frontend** | Pagina de configuracao de relatorios |
| **Complexidade** | Media |
| **Esforco** | 4 dias |
| **Prioridade** | P2 |

#### 5.5 Monitoramento de Reputacao/Reclamacoes
| Aspecto | Detalhe |
|---------|---------|
| **Descricao** | Acompanhar score de reputacao e claims |
| **Backend** | Ja parcialmente em `reputacao/` (expandir) |
| **Frontend** | Dashboard de reputacao |
| **Complexidade** | Baixa |
| **Esforco** | 2-3 dias |
| **Prioridade** | P2 |

### Cronograma Fase 5

```
Semana 1:
  Dia 1-3: Exportacao CSV (backend streaming + frontend)
  Dia 4-5: Alertas v2 (novos tipos)

Semana 2:
  Dia 1-3: Multi-conta com RBAC
  Dia 4-5: Relatorios automaticos

Semana 3:
  Dia 1-2: Reputacao/reclamacoes
  Dia 3-5: QA geral + polish + deploy final
```

---

## DECISOES TECNICAS

### Stack — O que Adicionar

| Tecnologia | Proposito | Justificativa |
|------------|-----------|---------------|
| `anthropic` (Python SDK) | Integrar Claude API | SDK oficial, async, tipado |
| `numpy` | Calculos estatisticos (forecast, pareto) | Leve, sem overhead de pandas |
| `scipy.stats` | Regressao linear, intervalos de confianca | Necessario para forecast |
| Nenhum novo framework frontend | -- | Recharts + shadcn/ui ja cobrem tudo |
| Nenhum banco adicional | -- | PostgreSQL + Redis ja sao suficientes |

### Stack — O que NAO Adicionar

| Tecnologia | Motivo para NAO usar |
|------------|---------------------|
| Pandas | Pesado demais; numpy + SQL queries sao suficientes |
| Elasticsearch | Volume de dados nao justifica; PostgreSQL full-text search basta |
| MongoDB | Sem necessidade; JSONB no PostgreSQL resolve dados semi-estruturados |
| Kafka | Volume nao justifica; Redis pub/sub ja esta configurado |
| TensorFlow/PyTorch | Modelos ML complexos sao overkill; Claude API cobre a necessidade de IA |

---

## AVALIACAO DE RISCOS

### Riscos Tecnicos

| # | Risco | Probabilidade | Impacto | Mitigacao |
|---|-------|--------------|---------|-----------|
| R1 | ML API rate limit excedido com coleta de 20 sellers | Alta | Medio | Implementar queue com delay entre chamadas; cache agressivo |
| R2 | ML Trends API indisponivel ou dados incompletos | Media | Alto | Fallback para estimativa via search results; documentar limitacoes |
| R3 | Custo Claude API alto com muitas otimizacoes | Media | Medio | Rate limit por usuario; usar Haiku onde possivel; cache de reports |
| R4 | Forecast impreciso com poucos dados historicos | Alta | Baixo | Exibir intervalo de confianca; avisar usuario sobre precisao |
| R5 | vendas/service.py monolitico (2.109 linhas) dificulta alteracoes | Alta | Alto | Nao tocar nesse arquivo; novos modulos em intel/ isolado |
| R6 | Celery workers sobrecarregados com tasks intel | Media | Medio | Queues separadas; ajustar concurrency por worker |
| R7 | Estimativa de vendas do concorrente imprecisa | Alta | Medio | Documentar como estimativa; usar delta de sold_quantity como melhor proxy |

### Riscos de Negocio

| # | Risco | Probabilidade | Impacto | Mitigacao |
|---|-------|--------------|---------|-----------|
| R8 | Features de mercado requerem volume de dados ainda nao coletado | Alta | Alto | Iniciar coleta na Fase 1 mesmo que display seja Fase 2 |
| R9 | Usuario nao entende valor das novas features | Media | Alto | Tooltips explicativos; pagina de "como usar" |
| R10 | Concorrencia com Nubimetrics (preco vs feature) | Media | Medio | Foco em UX superior e integracao com vendas proprias |

### Riscos Operacionais

| # | Risco | Probabilidade | Impacto | Mitigacao |
|---|-------|--------------|---------|-----------|
| R11 | Banco PostgreSQL cresce rapido com snapshots diarios | Media | Medio | Politica de retencao: snapshots > 12 meses sao agregados |
| R12 | CI/CD inexistente (problema critico #8) pode causar deploys quebrados | Alta | Alto | Implementar GitHub Actions basico antes da Fase 2 |
| R13 | Testes a ~2% de cobertura podem esconder regressoes | Alta | Alto | Cada fase deve incluir testes para novos modulos (meta: 40%) |

---

## PONTOS DE INTEGRACAO COM MSM_PRO EXISTENTE

### Modulos Existentes que Alimentam Intel

```
vendas/models.py
  Listing ---------> intel/analytics (forecast, pareto, distribution)
  ListingSnapshot -> intel/analytics (dados historicos)
  Order -----------> intel/analytics (revenue, margem)

concorrencia/models.py
  Competitor ------> intel/competitors (base para monitoramento expandido)
  CompetitorSnapshot -> intel/competitors (dados de preco/vendas)

produtos/models.py
  Product ---------> intel/analytics (custo para calculo de margem)

alertas/models.py
  AlertConfig -----> intel/competitors (novos tipos de alerta)

mercadolivre/client.py
  MLClient --------> todos os modulos intel (fonte de dados)
```

### Modulos Intel que Alimentam Existentes

```
intel/analytics
  user_insights ----> Dashboard existente (cards de insight)
  pareto data ------> Pagina de Anuncios (destaque top 20%)

intel/optimizer
  health_score -----> Listing model (campo health_score)
  title suggestion -> Pagina de Anuncios (botao "Otimizar titulo")

intel/competitors
  price alerts -----> alertas/ (novos AlertEvents)
  seller data ------> Dashboard (widget de mercado)
```

---

## METRICAS DE SUCESSO POR FASE

| Fase | Metrica | Meta |
|------|---------|------|
| 1 | Endpoints funcionando + testes passando | 100% endpoints com curl |
| 1 | Cobertura de testes do modulo analytics | >= 60% |
| 2 | Categorias carregadas no banco | >= 100 categorias monitoradas |
| 2 | Cache hit rate (Redis) | >= 80% |
| 3 | Sellers monitorados com dados | >= 5 sellers com 7+ dias de snapshots |
| 3 | Estimativa de vendas com delta > 0 | >= 70% dos dias |
| 4 | Score de otimizacao calculado | 100% dos listings com score |
| 4 | Custo Claude API/mes | < R$50 |
| 5 | Exportacao CSV funcional | Todos os tipos |
| 5 | Alertas disparando corretamente | >= 90% de precisao |

---

## TIMELINE CONSOLIDADO

```
                Mar 2026        Abr 2026        Mai 2026        Jun 2026        Jul 2026
                |               |               |               |               |
Fase 1 ========|====>           |               |               |               |
    Reforco    |   (2-3 sem)   |               |               |               |
               |               |               |               |               |
Fase 2         |       ========|=======>       |               |               |
    Market     |               |  (3-4 sem)    |               |               |
               |               |               |               |               |
Fase 3         |               |       ========|=======>       |               |
    Compet.    |               |               |  (3-4 sem)    |               |
               |               |               |               |               |
Fase 4         |               |               |       ========|========>      |
    IA         |               |               |               | (4-5 sem)     |
               |               |               |               |               |
Fase 5         |               |               |               |       ========|===>
    Pro        |               |               |               |               | (2-3 sem)
```

**Estimativa total: 14-19 semanas (3.5 - 4.7 meses)**

---

*Fim do Plano de Implementacao*
