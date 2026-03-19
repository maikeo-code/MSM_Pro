# Blueprint: Daily Intelligence Report + Price Suggestions

> Documento de arquitetura para aprovacao antes da implementacao.
> Data: 2026-03-19

---

## VISAO GERAL

Sistema de inteligencia diaria com 3 pilares:
1. **Daily Report** — email diario com conversoes, visitas e recomendacoes de preco
2. **Price Suggestions** — aba no frontend para visualizar e aplicar sugestoes
3. **AI Recommendation Engine** — pipeline de agentes IA especializados que alimentam ambos

```
┌─────────────────────────────────────────────────────────────────┐
│                    CELERY BEAT (08:00 BRT)                       │
│                                                                  │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────┐       │
│  │ Collector │──>│ AI Analyzer  │──>│ Report Builder    │       │
│  │  Agent    │   │ (3 sub-agents│   │ (HTML + images)   │       │
│  │ (Haiku)   │   │  Sonnet/Opus)│   │                   │       │
│  └──────────┘   └──────┬───────┘   └────────┬──────────┘       │
│                        │                     │                   │
│                        v                     v                   │
│              ┌─────────────────┐    ┌──────────────┐            │
│              │ price_           │    │ SMTP Email   │            │
│              │ recommendations │    │ maikeo@      │            │
│              │ (PostgreSQL)    │    │ msmrp.com    │            │
│              └────────┬────────┘    └──────────────┘            │
│                       │                                          │
│                       v                                          │
│              ┌─────────────────┐                                 │
│              │ Frontend Tab    │                                 │
│              │ "Sugestao de    │                                 │
│              │  Precos"        │                                 │
│              └─────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. DAILY REPORT — ARQUITETURA

### 1.1 Agentes de IA (Pipeline de 3 Etapas)

Cada agente tem responsabilidade unica e modelo adequado ao custo/capacidade:

#### Agente 1: COLLECTOR (sem IA — puro SQL)
- **Funcao**: Coleta dados brutos do banco
- **Modelo**: Nenhum (query SQL pura — mais rapido e barato)
- **Output**: JSON com metricas por anuncio

```python
# Dados coletados por anuncio:
{
    "mlb_id": "MLB1234567890",
    "sku": "SKU-001",
    "title": "Produto XYZ",
    "thumbnail": "https://...",
    "current_price": 149.90,
    "stock": 45,
    "cost": 60.00,  # do SKU vinculado
    "listing_type": "premium",
    "periods": {
        "today": {"visits": 120, "sales": 5, "conversion": 4.17, "avg_price": 149.90},
        "yesterday": {"visits": 98, "sales": 3, "conversion": 3.06, "avg_price": 149.90},
        "last_7d": {"visits": 750, "sales": 28, "conversion": 3.73, "avg_price": 148.50},
        "last_15d": {"visits": 1400, "sales": 52, "conversion": 3.71, "avg_price": 147.20},
    },
    "stock_days_projection": 11.25,  # stock / (avg_sales_7d)
    "competitor_prices": [139.90, 155.00, 142.50],
}
```

#### Agente 2: ANALYZER (IA — Claude Sonnet 4.6)
- **Funcao**: Analisa os dados e gera recomendacoes de preco
- **Modelo**: Claude Sonnet 4.6 (melhor custo-beneficio para analise numerica)
- **Por que Sonnet**: Analise de padroes numericos nao precisa de Opus; Haiku seria fraco para entender elasticidade
- **Input**: JSON do Collector
- **Output**: Recomendacao estruturada por anuncio

**Prompt do Analyzer (otimizado):**
```
Voce e um analista de pricing do Mercado Livre. Analise os dados de cada anuncio
e recomende ajuste de preco otimizando LUCRO TOTAL (nao apenas margem unitaria).

REGRAS DE DECISAO:

1. EQUILIBRIO LUCRO x VOLUME:
   - Lucro total = margem_unitaria × vendas_por_dia
   - Priorizar o preco que MAXIMIZA lucro_total, nao o maior preco possivel
   - Um preco 5% menor com 20% mais vendas pode ser mais lucrativo

2. SENSIBILIDADE DO ML A PRECOS:
   - O algoritmo do ML favorece anuncios com boa conversao
   - Reducao de preco > 10% de uma vez pode acionar review automatico
   - Aumento de preco > 5% pode derrubar ranking temporariamente
   - Ajustes graduais (2-3% por vez) sao mais seguros
   - Intervalo minimo entre ajustes: 24h (ML precisa indexar)

3. PESOS DA FORMULA DE RECOMENDACAO:
   - Tendencia de conversao (peso 35%): conversao subindo = pode aumentar preco
   - Tendencia de visitas (peso 25%): visitas subindo = demanda alta
   - Posicao vs concorrentes (peso 20%): se muito acima, perda de buybox
   - Estoque (peso 15%): estoque baixo + vendas altas = pode aumentar
   - Margem atual (peso 5%): se margem < 10%, priorizar aumento

4. ESTOQUE:
   - Se projecao de estoque < 5 dias: NAO reduzir preco (estoque ja vendendo rapido)
   - Se projecao de estoque > 30 dias: considerar reducao para girar

5. OUTPUT POR ANUNCIO:
   {
     "mlb_id": "MLB...",
     "action": "increase" | "decrease" | "hold",
     "suggested_price": 154.90,
     "price_change_pct": +3.3,
     "confidence": "high" | "medium" | "low",
     "reasoning": "Conversao subiu 15% nos ultimos 7 dias com visitas estaveis...",
     "estimated_daily_sales": 4.2,
     "estimated_daily_profit": 126.00,
     "risk_level": "low" | "medium" | "high",
     "urgency": "immediate" | "next_48h" | "monitor"
   }

Dados para analise:
{collector_json}
```

#### Agente 3: REPORT BUILDER (sem IA — template HTML)
- **Funcao**: Monta o email HTML visual com os dados do Analyzer
- **Modelo**: Nenhum (template Jinja2 puro)
- **Features visuais**:
  - Thumbnail do produto (img tag com URL do ML)
  - Setas coloridas para tendencia (verde subiu, vermelho desceu)
  - Badge de recomendacao (AUMENTAR / DIMINUIR / MANTER)
  - Ordenado por SKU do produto

### 1.2 Estrutura Visual do Email

```
┌──────────────────────────────────────────────────────┐
│  RELATORIO DIARIO DE CONVERSOES — MSM_Pro            │
│  19/03/2026 · 16 anuncios ativos                     │
├──────────────────────────────────────────────────────┤
│                                                       │
│  RESUMO DO DIA                                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Vendas  │ │ Visitas │ │Conversao│ │ Receita │   │
│  │ 42 ↑12% │ │ 1.2k ↑5│ │ 3.5% ↑  │ │R$6.2k   │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                       │
│  ─── ANUNCIOS (ordenados por SKU) ───                │
│                                                       │
│  ┌────────────────────────────────────────────────┐  │
│  │ [IMG] SKU-001 · MLB1234567890                   │  │
│  │ Cadeira Gamer Pro RGB - Preta                   │  │
│  │                                                  │  │
│  │ Preco Medio: R$ 489,90  │ Estoque: 45 un       │  │
│  │ Projecao Estoque: 11 dias                       │  │
│  │                                                  │  │
│  │ CONVERSAO:  3.06% → 4.17%  ↑ SUBIU             │  │
│  │ VISITAS:    98 → 120        ↑ SUBIU             │  │
│  │                                                  │  │
│  │ Comparativo:                                     │  │
│  │  Ontem: 3v/98vis  │ 7d: 4v/107vis  │ 15d: 3.5v │  │
│  │                                                  │  │
│  │ ┌──────────────────────────────────────────┐    │  │
│  │ │ RECOMENDACAO: ↑ AUMENTAR PRECO           │    │  │
│  │ │ Sugestao: R$ 509,90 (+4.1%)              │    │  │
│  │ │ Lucro estimado/dia: R$ 126,00            │    │  │
│  │ │ Confianca: ALTA · Risco: BAIXO           │    │  │
│  │ │ Motivo: Conversao subindo com demanda    │    │  │
│  │ │ estavel. Estoque saudavel para 11 dias.  │    │  │
│  │ └──────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────┘  │
│                                                       │
│  [... repete para cada anuncio ...]                   │
│                                                       │
│  ─── ALERTAS ───                                      │
│  ! Estoque critico: SKU-005 (2 unidades)             │
│  ! Conversao caiu 40%: SKU-012                        │
│                                                       │
│  [Acessar Dashboard →]                                │
├──────────────────────────────────────────────────────┤
│  MSM_Pro — Relatorio gerado por IA (Claude Sonnet)   │
└──────────────────────────────────────────────────────┘
```

### 1.3 Modelo de Dados — Novas Tabelas

```sql
-- Recomendacoes de preco geradas pela IA (historico)
CREATE TABLE price_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Dados do momento da recomendacao
    current_price DECIMAL(12,2) NOT NULL,
    suggested_price DECIMAL(12,2) NOT NULL,
    price_change_pct DECIMAL(8,2) NOT NULL,

    -- Analise da IA
    action VARCHAR(20) NOT NULL,            -- increase, decrease, hold
    confidence VARCHAR(10) NOT NULL,         -- high, medium, low
    risk_level VARCHAR(10) NOT NULL,         -- low, medium, high
    urgency VARCHAR(20) NOT NULL,            -- immediate, next_48h, monitor
    reasoning TEXT NOT NULL,                 -- explicacao da IA

    -- Metricas no momento
    conversion_today DECIMAL(8,4),
    conversion_7d DECIMAL(8,4),
    visits_today INTEGER,
    visits_7d INTEGER,
    sales_today INTEGER,
    sales_7d INTEGER,
    stock INTEGER,
    stock_days_projection DECIMAL(8,2),
    estimated_daily_sales DECIMAL(8,2),
    estimated_daily_profit DECIMAL(12,2),

    -- Concorrencia
    competitor_avg_price DECIMAL(12,2),
    competitor_min_price DECIMAL(12,2),

    -- Status de aplicacao
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, applied, dismissed, expired
    applied_at TIMESTAMPTZ,
    applied_price DECIMAL(12,2),
    price_change_log_id UUID REFERENCES price_change_logs(id),

    -- Metadados
    ai_model VARCHAR(50) NOT NULL DEFAULT 'claude-sonnet-4-6',
    report_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indices
    CONSTRAINT uq_recommendation_listing_date UNIQUE(listing_id, report_date)
);

CREATE INDEX idx_price_rec_user_date ON price_recommendations(user_id, report_date DESC);
CREATE INDEX idx_price_rec_status ON price_recommendations(status) WHERE status = 'pending';

-- Historico de reports enviados
CREATE TABLE daily_report_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    total_listings INTEGER NOT NULL,
    recommendations_count INTEGER NOT NULL,
    increase_count INTEGER NOT NULL DEFAULT 0,
    decrease_count INTEGER NOT NULL DEFAULT 0,
    hold_count INTEGER NOT NULL DEFAULT 0,
    email_sent BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent_at TIMESTAMPTZ,
    ai_cost_estimate DECIMAL(8,4),        -- custo estimado da chamada IA em USD
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_report_user_date UNIQUE(user_id, report_date)
);
```

### 1.4 Celery Schedule

```python
# Nova task diaria — 08:00 BRT (11:00 UTC)
# Roda DEPOIS do sync_all_snapshots (06:00) para ter dados frescos
"send-daily-intel-report": {
    "task": "app.jobs.tasks.send_daily_intel_report",
    "schedule": crontab(hour=11, minute=0),  # 08:00 BRT
    "options": {"expires": 3600},
},
```

### 1.5 Fluxo Sequencial

```
06:00 BRT — sync_all_snapshots (dados frescos do ML)
06:30 BRT — sync_reputation
07:00 BRT — sync_competitor_snapshots
08:00 BRT — send_daily_intel_report:
  1. Collector: busca dados de TODOS os anuncios ativos (SQL)
  2. Analyzer: envia JSON para Claude Sonnet → recebe recomendacoes
  3. Salva recomendacoes em price_recommendations (PostgreSQL)
  4. Report Builder: monta HTML com dados + recomendacoes
  5. Envia email para maikeo@msmrp.com via SMTP
  6. Registra log em daily_report_logs
```

---

## 2. ABA "SUGESTAO DE PRECOS" — FRONTEND

### 2.1 Rota e Navegacao

```
/precos (nova aba no menu lateral)
```

Menu lateral atualizado:
```
Dashboard
Anuncios
Pedidos (novo)
Sugestao de Precos (NOVO ★)
Concorrencia
Alertas
Financeiro
Reputacao
Produtos
Configuracoes
```

### 2.2 Layout da Pagina

```
┌──────────────────────────────────────────────────────────────┐
│  Sugestao de Precos                                          │
│  Recomendacoes baseadas em IA · Atualizado: hoje 08:00       │
│                                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ AUMENTAR: 5  │ │ DIMINUIR: 3 │ │ MANTER: 8   │            │
│  │ (verde)      │ │ (vermelho)  │ │ (cinza)     │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
│                                                               │
│  Filtros: [Todos ▼] [Alta confianca ▼] [Ordenar: SKU ▼]     │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ [IMG] SKU-001 · MLB1234567890                          │  │
│  │ Cadeira Gamer Pro RGB                                   │  │
│  │                                                         │  │
│  │ Preco Atual: R$ 489,90                                  │  │
│  │ Sugestao:    R$ 509,90 (+4.1%)  [AUMENTAR]             │  │
│  │                                                         │  │
│  │ Conversao: 3.06% → 4.17% ↑    Visitas: 98 → 120 ↑    │  │
│  │ Vendas 7d: 28 un              Estoque: 45 un (11d)     │  │
│  │                                                         │  │
│  │ Confianca: ALTA  Risco: BAIXO  Urgencia: Proximo 48h   │  │
│  │                                                         │  │
│  │ Motivo: "Conversao subindo com demanda estavel..."      │  │
│  │                                                         │  │
│  │ [Aplicar Preco] [Simular] [Ignorar] [Ver Historico]    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ [IMG] SKU-002 · MLB9876543210                          │  │
│  │ ...                                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ─── HISTORICO DE RECOMENDACOES ───                           │
│  │ Data       │ MLB          │ Acao    │ Resultado          │  │
│  │ 18/03      │ MLB12345...  │ +4.1%   │ Aplicado ✓        │  │
│  │ 17/03      │ MLB98765...  │ -2.5%   │ Ignorado          │  │
│  │ 17/03      │ MLB12345...  │ MANTER  │ —                 │  │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Acoes do Usuario

| Acao | O que faz |
|------|-----------|
| **Aplicar Preco** | Chama `PUT /items/{id}` na API ML + salva PriceChangeLog |
| **Simular** | Abre modal com simulate_price (ja existe) mostrando impacto |
| **Ignorar** | Marca recomendacao como `dismissed` |
| **Ver Historico** | Expande timeline de recomendacoes anteriores para aquele MLB |

### 2.4 Endpoints Backend (novos)

```python
# Listar recomendacoes pendentes do dia
GET /api/v1/intel/price-recommendations
  ?date=2026-03-19          # opcional (default: hoje)
  &action=increase          # opcional (filtro)
  &confidence=high          # opcional (filtro)
  &sort=sku                 # sku | confidence | price_change_pct

# Aplicar recomendacao (altera preco na API ML)
POST /api/v1/intel/price-recommendations/{id}/apply
  → Chama apply_price_suggestion() ja existente
  → Atualiza status para "applied"

# Ignorar recomendacao
POST /api/v1/intel/price-recommendations/{id}/dismiss

# Historico de recomendacoes por MLB
GET /api/v1/intel/price-recommendations/history/{mlb_id}
  ?days=30

# Forcar geracao de recomendacoes (manual, sem esperar Celery)
POST /api/v1/intel/price-recommendations/generate
```

---

## 3. SALVAMENTO DE DADOS PARA SISTEMA INTELIGENTE (1.4)

### 3.1 Por que salvar?

Cada recomendacao salva em `price_recommendations` cria um dataset para:
1. **Feedback loop**: se usuario aplicou e vendas melhoraram → IA aprendeu
2. **Calibracao**: comparar `estimated_daily_sales` vs real (apos aplicacao)
3. **Auto-pricing futuro**: alimentar RepricingRule com dados historicos
4. **Dashboard de performance**: "das 50 recomendacoes aplicadas, 42 melhoraram vendas"

### 3.2 Metricas de Aprendizado (futuro)

```sql
-- View materializada: performance das recomendacoes aplicadas
CREATE MATERIALIZED VIEW recommendation_performance AS
SELECT
    pr.id,
    pr.listing_id,
    pr.action,
    pr.suggested_price,
    pr.estimated_daily_sales,
    -- Vendas reais 7 dias apos aplicacao
    (SELECT AVG(ls.sales_today)
     FROM listing_snapshots ls
     WHERE ls.listing_id = pr.listing_id
       AND ls.captured_at BETWEEN pr.applied_at AND pr.applied_at + INTERVAL '7 days'
    ) as actual_avg_sales_7d,
    -- Precisao da previsao
    CASE WHEN pr.estimated_daily_sales > 0 THEN
        ABS(actual_sales - pr.estimated_daily_sales) / pr.estimated_daily_sales * 100
    END as prediction_error_pct
FROM price_recommendations pr
WHERE pr.status = 'applied'
  AND pr.applied_at < NOW() - INTERVAL '7 days';
```

### 3.3 Pipeline para Auto-Pricing

```
Fase 1 (ATUAL):  Report diario → Recomendacao → Usuario aplica manualmente
Fase 2 (FUTURO): Se confianca "high" E historico > 80% acerto → Aplica automatico
                  com limites de seguranca:
                  - max +/- 5% por dia
                  - min_price e max_price da RepricingRule
                  - cooldown 48h entre ajustes
                  - rollback automatico se vendas caem >70% em 24h
```

---

## 4. MELHORIAS NA FORMULA DE RECOMENDACAO

### 4.1 Problema Atual

A `_gerar_sugestao_ia()` no `tasks_digest.py` usa templates fixos (if/elif).
Nao leva em conta elasticidade real, concorrencia nem estoque.

### 4.2 Formula Proposta (Weighted Score)

```python
def calcular_score_recomendacao(anuncio: dict) -> dict:
    """
    Score composto que pondera multiplos fatores para decidir
    se deve aumentar, diminuir ou manter o preco.

    Score > 0.15  → AUMENTAR
    Score < -0.15 → DIMINUIR
    Score [-0.15, 0.15] → MANTER

    Os pesos foram calibrados para o ecossistema ML:
    """
    # 1. Tendencia de conversao (35%)
    conv_today = anuncio["periods"]["today"]["conversion"]
    conv_7d = anuncio["periods"]["last_7d"]["conversion"]
    conv_15d = anuncio["periods"]["last_15d"]["conversion"]

    # Compara media recente vs historica
    conv_trend = 0.0
    if conv_15d > 0:
        conv_trend = (conv_7d - conv_15d) / conv_15d  # ex: +0.15 = subiu 15%

    # 2. Tendencia de visitas (25%)
    visits_7d_avg = anuncio["periods"]["last_7d"]["visits"] / 7
    visits_15d_avg = anuncio["periods"]["last_15d"]["visits"] / 15

    visit_trend = 0.0
    if visits_15d_avg > 0:
        visit_trend = (visits_7d_avg - visits_15d_avg) / visits_15d_avg

    # 3. Posicao competitiva (20%)
    my_price = anuncio["current_price"]
    comp_prices = anuncio.get("competitor_prices", [])
    comp_score = 0.0
    if comp_prices:
        avg_comp = sum(comp_prices) / len(comp_prices)
        min_comp = min(comp_prices)
        # Se estou muito abaixo: posso subir
        # Se estou muito acima: preciso descer
        comp_score = (avg_comp - my_price) / my_price  # positivo = estou abaixo

    # 4. Pressao de estoque (15%)
    stock_days = anuncio.get("stock_days_projection", 15)
    stock_score = 0.0
    if stock_days < 5:
        stock_score = 0.3    # estoque acabando = pode subir preco
    elif stock_days > 30:
        stock_score = -0.3   # estoque encalhado = deve descer

    # 5. Margem atual (5%)
    margem_pct = _calcular_margem_pct(anuncio)
    margem_score = 0.0
    if margem_pct < 10:
        margem_score = 0.2   # margem muito baixa = precisa subir
    elif margem_pct > 40:
        margem_score = -0.1  # margem confortavel = pode reduzir para girar

    # Score final ponderado
    score = (
        conv_trend * 0.35 +
        visit_trend * 0.25 +
        comp_score * 0.20 +
        stock_score * 0.15 +
        margem_score * 0.05
    )

    # Determinar acao e magnitude do ajuste
    if score > 0.15:
        action = "increase"
        # Ajuste proporcional ao score, max 5% por dia
        pct = min(score * 10, 5.0)  # ex: score 0.3 → +3%
    elif score < -0.15:
        action = "decrease"
        pct = max(score * 10, -5.0)  # ex: score -0.25 → -2.5%
    else:
        action = "hold"
        pct = 0.0

    suggested_price = round(my_price * (1 + pct / 100), 2)

    return {
        "action": action,
        "suggested_price": suggested_price,
        "price_change_pct": round(pct, 2),
        "score": round(score, 4),
        "breakdown": {
            "conv_trend": round(conv_trend * 0.35, 4),
            "visit_trend": round(visit_trend * 0.25, 4),
            "comp_score": round(comp_score * 0.20, 4),
            "stock_score": round(stock_score * 0.15, 4),
            "margem_score": round(margem_score * 0.05, 4),
        },
    }
```

### 4.3 Papel da IA vs Formula

A formula acima gera o **baseline**. A IA (Claude Sonnet) **refina**:

| Etapa | Responsavel | O que faz |
|-------|------------|-----------|
| Calculo | Python puro | Score numerico + preco sugerido |
| Refinamento | Claude Sonnet | Ajusta com contexto (sazonalidade, promocoes ML, categoria) |
| Justificativa | Claude Sonnet | Gera texto explicativo legivel para o email |

A IA **NAO recalcula** os numeros — ela valida e contextualiza.
Isso reduz custo de tokens em ~70% vs enviar tudo para IA processar.

---

## 5. SUGESTOES ADICIONAIS

### 5.1 Melhorias Imediatas (podem ir junto)

| # | Ideia | Impacto | Esforco |
|---|-------|---------|---------|
| 1 | **Score de Saude por Anuncio** — combinar conversao + visitas + estoque + margem em 1 numero (0-100) | Alto | Baixo |
| 2 | **Alerta de Oportunidade** — "visitas subiram 30% mas conversao nao acompanhou" = problema no preco/titulo | Alto | Baixo |
| 3 | **Comparativo Semanal no Email** — mini-grafico sparkline de conversao 7 dias (usando base64 SVG inline) | Medio | Medio |
| 4 | **Destaque "Produto do Dia"** — anuncio com melhor melhoria de conversao ganha destaque | Baixo | Baixo |

### 5.2 Proximas Evolucoes (apos esta sprint)

| # | Ideia | Descricao |
|---|-------|-----------|
| 1 | **A/B Test de Precos** — alterar preco por 48h, medir impacto, reverter se piorou |
| 2 | **Sazonalidade** — ML tem picos em datas especificas (Black Friday, Dia das Maes). Salvar historico de 1 ano para prever |
| 3 | **Titulo Optimizer** — IA sugere melhorias no titulo baseado em CTR (visitas/impressoes) |
| 4 | **Bulk Apply** — aplicar todas as sugestoes "high confidence" de uma vez |
| 5 | **WhatsApp Report** — enviar resumo via WhatsApp Business API (alem do email) |
| 6 | **Notificacao Push** — alertas urgentes (estoque zerou, concorrente derrubou preco) via push no browser |
| 7 | **Dashboard de Acuracia** — "suas recomendacoes acertaram 78% das vezes no ultimo mes" |
| 8 | **Repricing Automatico** — Fase 2 do auto-pricing com aprovacao em lote |

### 5.3 Arquitetura de Custos IA

| Componente | Modelo | Tokens/dia (est.) | Custo/dia |
|-----------|--------|-------------------|-----------|
| Analyzer | Sonnet 4.6 | ~5k input + 2k output (16 anuncios) | ~$0.04 |
| Refinamento | Sonnet 4.6 | ~3k input + 1k output | ~$0.02 |
| Total | — | ~11k tokens | **~$0.06/dia** |

> Custo extremamente baixo porque: (1) a formula Python faz o trabalho pesado,
> (2) a IA so refina e justifica, (3) Sonnet e eficiente para esse tipo de tarefa.

---

## 6. PLANO DE IMPLEMENTACAO

### Fase 1: Backend (2 agentes dev em paralelo)

**Agente Dev #1 — Modelos + Collector + Task Celery:**
1. Migration: criar tabelas `price_recommendations` e `daily_report_logs`
2. Models: `PriceRecommendation`, `DailyReportLog`
3. Service: `collect_daily_data()` — SQL puro, coleta dados de todos anuncios
4. Service: `calculate_recommendation_score()` — formula Python pura
5. Task Celery: `send_daily_intel_report` — orquestra o pipeline

**Agente Dev #2 — IA Analyzer + Report Builder + Email:**
1. Service: `analyze_with_ai()` — chama Claude Sonnet via API
2. Service: `build_daily_report_html()` — template HTML do email
3. Endpoints: CRUD de `price_recommendations`
4. Integrar com `apply_price_suggestion()` ja existente

### Fase 2: Frontend (1 agente dev)
1. Pagina `/precos` — PriceSuggestions
2. Componentes: RecommendationCard, RecommendationHistory, ApplyModal
3. Service: `intelService.ts` — chamadas API
4. Integrar com simulador de preco ja existente

### Fase 3: QA + Deploy
1. Testar pipeline completo (collector → analyzer → email)
2. Testar aplicacao de sugestao (frontend → API ML)
3. Verificar email recebido em maikeo@msmrp.com
4. Deploy via git push

---

## 7. DECISOES ARQUITETURAIS

| Decisao | Escolha | Alternativa Descartada | Por que |
|---------|---------|----------------------|---------|
| Modelo IA para Analyzer | Sonnet 4.6 | Opus (caro demais para daily), Haiku (fraco para analise) | Custo-beneficio: $0.04/dia |
| Formula Python + IA | Hibrido | IA pura | Reduz custo 70%, mais previsivel |
| Report diario | Email SMTP | WebSocket push | Email e assincrono, nao precisa estar online |
| Horario | 08:00 BRT | 06:00 BRT | Apos TODOS os syncs (snapshots, concorrentes, reputacao) |
| Tabela separada | price_recommendations | Reusar alert_events | Semantica diferente, metricas proprias |
| Ordenacao | Por SKU | Por urgencia | Usuario pediu por SKU — mais facil achar produto |

---

## 8. PRE-REQUISITOS

Antes de implementar, verificar:

- [ ] SMTP configurado e funcionando (ja funciona para weekly digest?)
- [ ] `ANTHROPIC_API_KEY` configurada no Railway (para chamar Claude Sonnet)
- [ ] Dados de snapshots existentes (pelo menos 7 dias de historico)
- [ ] Ao menos 1 SKU vinculado a anuncios (para calcular margem)
- [ ] Concorrentes cadastrados (para score competitivo — opcional mas recomendado)

---

> **Aguardando aprovacao para iniciar implementacao.**
> Qualquer item pode ser ajustado antes de comecar.
