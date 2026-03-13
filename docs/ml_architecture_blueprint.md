<!-- 
  Documento gerado por: Antigravity (Google Gemini — Agente de Código Avançado)
  Data de criação: 12 de março de 2026, 22:30 BRT
  Contexto: Consolidação das Missões 1–7 de extração de dados do Mercado Livre
             + análise completa do código-fonte existente do MSM_Pro
  Fonte: Extração real do painel do vendedor + API pública do ML + modelos SQLAlchemy do projeto
-->

# 🏗️ Arquitetura Completa — MSM_Pro (Mercado Livre Intelligence Platform)

> Documento de referência técnica consolidando **toda a extração de dados** (Missões 1–7), o **modelo de dados real do projeto**, os **endpoints da API do ML**, e a **estrutura visual do dashboard**. Construído para que qualquer IA ou desenvolvedor consiga reproduzir e expandir o sistema com total clareza.

---

## 1. Visão Geral do Sistema

```mermaid
graph TB
    subgraph "🌐 Mercado Livre (Fonte)"
        ML_API["API Pública<br>api.mercadolibre.com"]
        ML_PANEL["Painel do Vendedor<br>mercadolivre.com.br"]
    end

    subgraph "⚙️ Backend (FastAPI + Python 3.12)"
        AUTH["Auth Module<br>JWT + OAuth ML"]
        ML_CLIENT["ML Client<br>async + retry + rate-limit"]
        VENDAS["Módulo Vendas<br>Listings + Snapshots"]
        FINANCEIRO["Módulo Financeiro<br>Taxas + Margem"]
        ADS["Módulo Ads<br>Product Ads + ACOS"]
        REPUTACAO["Módulo Reputação<br>Termômetro + KPIs"]
        CONCORRENCIA["Módulo Concorrência<br>Competitors + Snapshots"]
        ALERTAS["Módulo Alertas<br>Configs + Events"]
        PRODUTOS["Módulo Produtos<br>SKU + Custo"]
        JOBS["Celery Jobs<br>Cron diário 06:00 BRT"]
        WS["WebSocket<br>Tempo Real"]
    end

    subgraph "💾 Infraestrutura"
        PG[("PostgreSQL 16")]
        REDIS[("Redis 7<br>Cache + Fila Celery")]
    end

    subgraph "🖥️ Frontend (React 18 + TypeScript + Vite)"
        DASH["Dashboard"]
        PG_ANUNCIOS["Anúncios"]
        PG_CONC["Concorrência"]
        PG_ALERT["Alertas"]
        PG_CONFIG["Configurações"]
        PG_REP["Reputação"]
        PG_PROD["Produtos"]
        PG_LOGIN["Login"]
    end

    ML_API --> ML_CLIENT
    ML_CLIENT --> VENDAS
    ML_CLIENT --> FINANCEIRO
    ML_CLIENT --> ADS
    ML_CLIENT --> REPUTACAO
    ML_CLIENT --> CONCORRENCIA

    AUTH --> PG
    VENDAS --> PG
    FINANCEIRO --> PG
    ADS --> PG
    REPUTACAO --> PG
    CONCORRENCIA --> PG
    ALERTAS --> PG
    PRODUTOS --> PG
    JOBS --> REDIS
    WS --> REDIS

    DASH --> VENDAS
    PG_ANUNCIOS --> VENDAS
    PG_CONC --> CONCORRENCIA
    PG_ALERT --> ALERTAS
    PG_CONFIG --> AUTH
    PG_REP --> REPUTACAO
    PG_PROD --> PRODUTOS
```

### Tech Stack Completa

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| **Backend** | FastAPI + Python | 3.12 |
| **ORM** | SQLAlchemy 2.0 (async) | — |
| **Migrações** | Alembic | — |
| **Banco** | PostgreSQL | 16 |
| **Cache / Fila** | Redis | 7 |
| **Jobs Agendados** | Celery + Redis | — |
| **Frontend** | React + TypeScript + Vite | 18 |
| **UI Kit** | Tailwind CSS + shadcn/ui | — |
| **Gráficos** | Recharts | — |
| **HTTP Client** | TanStack React Query | — |
| **Deploy** | Railway (GitHub auto-deploy) | — |

---

## 2. Modelo de Dados Completo (Banco de Dados Real)

### 2.1 Diagrama Entidade-Relacionamento

```mermaid
erDiagram
    USERS ||--o{ ML_ACCOUNTS : "1:N contas ML"
    USERS ||--o{ PRODUCTS : "1:N produtos/SKUs"
    USERS ||--o{ LISTINGS : "1:N anúncios"
    USERS ||--o{ ALERT_CONFIGS : "1:N alertas"

    ML_ACCOUNTS ||--o{ LISTINGS : "1:N anúncios por conta"

    PRODUCTS ||--o{ LISTINGS : "1:N anúncios por SKU"
    PRODUCTS ||--o{ ALERT_CONFIGS : "0:N alertas por SKU"

    LISTINGS ||--o{ LISTING_SNAPSHOTS : "1:N fotos diárias"
    LISTINGS ||--o{ COMPETITORS : "1:N concorrentes vinculados"
    LISTINGS ||--o{ ALERT_CONFIGS : "0:N alertas por MLB"

    COMPETITORS ||--o{ COMPETITOR_SNAPSHOTS : "1:N fotos diárias"

    ALERT_CONFIGS ||--o{ ALERT_EVENTS : "1:N disparos"

    USERS {
        UUID id PK
        string email UK
        string hashed_password
        bool is_active
        timestamp created_at
        timestamp updated_at
    }

    ML_ACCOUNTS {
        UUID id PK
        UUID user_id FK
        string ml_user_id
        string nickname
        string email
        string access_token
        string refresh_token
        timestamp token_expires_at
        bool is_active
        timestamp created_at
    }

    PRODUCTS {
        UUID id PK
        UUID user_id FK
        string sku UK
        string name
        decimal cost
        string unit
        text notes
        bool is_active
        timestamp created_at
        timestamp updated_at
    }

    LISTINGS {
        UUID id PK
        UUID user_id FK
        UUID product_id FK_nullable
        UUID ml_account_id FK
        string mlb_id UK
        string title
        string listing_type
        decimal price
        decimal original_price_nullable
        decimal sale_price_nullable
        string status
        string category_id
        string seller_sku
        decimal sale_fee_amount
        decimal sale_fee_pct
        decimal avg_shipping_cost
        text permalink
        text thumbnail
        int quality_score
        timestamp created_at
        timestamp updated_at
    }

    LISTING_SNAPSHOTS {
        UUID id PK
        UUID listing_id FK
        decimal price
        int visits
        int sales_today
        int questions
        int stock
        decimal conversion_rate
        int orders_count
        decimal revenue
        decimal avg_selling_price
        int cancelled_orders
        decimal cancelled_revenue
        int returns_count
        decimal returns_revenue
        timestamp captured_at
    }

    COMPETITORS {
        UUID id PK
        UUID listing_id FK
        string mlb_id
        string title
        string seller_id
        bool is_active
        timestamp created_at
    }

    COMPETITOR_SNAPSHOTS {
        UUID id PK
        UUID competitor_id FK
        decimal price
        int visits
        int sales_delta
        timestamp captured_at
    }

    ALERT_CONFIGS {
        UUID id PK
        UUID user_id FK
        UUID listing_id FK_nullable
        UUID product_id FK_nullable
        string alert_type
        decimal threshold
        string channel
        bool is_active
        timestamp created_at
    }

    ALERT_EVENTS {
        UUID id PK
        UUID alert_config_id FK
        text message
        timestamp triggered_at
        timestamp sent_at
    }
```

### 2.2 Detalhamento das Tabelas

#### `users` — Conta do App
| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Login |
| `hashed_password` | VARCHAR(255) | NOT NULL | Bcrypt |
| `is_active` | BOOLEAN | NOT NULL | Ativo/Bloqueado |
| `created_at` | TIMESTAMPTZ | NOT NULL | Auto |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Auto |

#### `ml_accounts` — Contas do Mercado Livre (Multi-conta)
| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `user_id` | UUID FK→users | NOT NULL | Dono |
| `ml_user_id` | VARCHAR(100) | NOT NULL | ID ML (ex: 2050442871) |
| `nickname` | VARCHAR(255) | NOT NULL | Ex: MSM_PRIME |
| `email` | VARCHAR(255) | NULL | Email ML |
| `access_token` | VARCHAR(2000) | NULL | Token OAuth (6h exp) |
| `refresh_token` | VARCHAR(2000) | NULL | Refresh Token (rotativo) |
| `token_expires_at` | TIMESTAMPTZ | NULL | Quando expira |
| `is_active` | BOOLEAN | NOT NULL | — |

#### `products` — Cadastro de SKU com Custo
| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `user_id` | UUID FK→users | NOT NULL | Dono |
| `sku` | VARCHAR(100) | NOT NULL | SKU interno (1 SKU → N MLB) |
| `name` | VARCHAR(500) | NOT NULL | Nome do produto |
| `cost` | DECIMAL(12,2) | NOT NULL | Custo de aquisição/importação |
| `unit` | VARCHAR(50) | NOT NULL | Unidade (un, cx, kg) |
| `notes` | TEXT | NULL | Observações |
| `is_active` | BOOLEAN | NOT NULL | — |
| **Constraint** | `UNIQUE(user_id, sku)` | — | SKU único por usuário |

#### `listings` — Anúncios (MLB) no Mercado Livre
*Fonte: Missões 1, 3 e dados reais da API*

| Coluna | Tipo | Nullable | Descrição / Origem ML |
|--------|------|----------|----------------------|
| `id` | UUID | PK | — |
| `user_id` | UUID FK→users | NOT NULL | Dono do app |
| `product_id` | UUID FK→products | **NULL** | Vínculo com SKU (opcional) |
| `ml_account_id` | UUID FK→ml_accounts | NOT NULL | Conta ML que publicou |
| `mlb_id` | VARCHAR(50) | NOT NULL, UNIQUE | Ex: MLB1234567890 |
| `title` | VARCHAR(500) | NOT NULL | `GET /items/{id}` → `title` |
| `listing_type` | VARCHAR(20) | NOT NULL | `classico` / `premium` / `full` |
| `price` | DECIMAL(12,2) | NOT NULL | Preço atual de venda (já com desconto) |
| `original_price` | DECIMAL(12,2) | NULL | Preço sem desconto do vendedor |
| `sale_price` | DECIMAL(12,2) | NULL | Preço promocional do marketplace |
| `status` | VARCHAR(20) | NOT NULL | `active` / `paused` / `closed` |
| `category_id` | VARCHAR(50) | NULL | Categoria ML (Ex: MLB189462) |
| `seller_sku` | VARCHAR(100) | NULL | SKU original do vendedor no ML |
| `sale_fee_amount` | DECIMAL(12,2) | NULL | Taxa ML real em R$ |
| `sale_fee_pct` | DECIMAL(8,6) | NULL | Taxa ML real em % (via API) |
| `avg_shipping_cost` | DECIMAL(10,2) | NULL | Frete médio real extraído das orders |
| `permalink` | TEXT | NULL | URL pública do anúncio |
| `thumbnail` | TEXT | NULL | URL da miniatura (HTTPS) |
| `quality_score` | INTEGER | NULL | Score de 0–100 (Missão 3) |

#### `listing_snapshots` — Foto Diária de Cada Anúncio
*Fonte: Missões 1, 2 e 3 — Celery captura diariamente às 06:00 BRT*

| Coluna | Tipo | Nullable | Descrição / Origem |
|--------|------|----------|--------------------|
| `id` | UUID | PK | — |
| `listing_id` | UUID FK→listings | NOT NULL | Anúncio fotografado |
| `price` | DECIMAL(12,2) | NOT NULL | Preço naquele momento |
| `visits` | INTEGER | NOT NULL | Visitas do dia (`/items/{id}/visits/time_window`) |
| `sales_today` | INTEGER | NOT NULL | Vendas do dia |
| `questions` | INTEGER | NOT NULL | Perguntas do dia (`/questions/search`) |
| `stock` | INTEGER | NOT NULL | Estoque disponível |
| `conversion_rate` | DECIMAL(8,4) | NULL | `sales / visits × 100` |
| `orders_count` | INTEGER | NULL | Nº de pedidos (≠ unidades) |
| `revenue` | DECIMAL(12,2) | NULL | Receita bruta do dia |
| `avg_selling_price` | DECIMAL(10,2) | NULL | Preço médio de venda |
| `cancelled_orders` | INTEGER | NULL | Cancelamentos no dia |
| `cancelled_revenue` | DECIMAL(12,2) | NULL | Valor cancelado |
| `returns_count` | INTEGER | NULL | Devoluções no dia |
| `returns_revenue` | DECIMAL(12,2) | NULL | Valor devolvido |
| `captured_at` | TIMESTAMPTZ | NOT NULL | Timestamp da captura |

#### `competitors` — Concorrentes Vinculados
*Fonte: Missão 7*

| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `listing_id` | UUID FK→listings | NOT NULL | Meu anúncio que ele concorre |
| `mlb_id` | VARCHAR(50) | NOT NULL | MLB externo do concorrente |
| `title` | VARCHAR(500) | NULL | Título do concorrente |
| `seller_id` | VARCHAR(100) | NULL | ID do vendedor concorrente |
| `is_active` | BOOLEAN | NOT NULL | Monitorando ou não |

#### `competitor_snapshots` — Foto Diária do Concorrente
| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `competitor_id` | UUID FK→competitors | NOT NULL | Concorrente fotografado |
| `price` | DECIMAL(12,2) | NOT NULL | Preço do concorrente naquele momento |
| `visits` | INTEGER | NOT NULL | Visitas estimadas |
| `sales_delta` | INTEGER | NOT NULL | Variação de `sold_quantity` (público) |
| `captured_at` | TIMESTAMPTZ | NOT NULL | — |

#### `alert_configs` — Configuração de Alertas
*Fonte: Missão 4 (thresholds de reputação)*

| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `user_id` | UUID FK→users | NOT NULL | Dono |
| `listing_id` | UUID FK→listings | NULL | Alerta por MLB (opcional) |
| `product_id` | UUID FK→products | NULL | Alerta por SKU (opcional) |
| `alert_type` | VARCHAR(50) | NOT NULL | Tipo (ver lista abaixo) |
| `threshold` | DECIMAL(12,4) | NULL | Limiar de disparo |
| `channel` | VARCHAR(20) | NOT NULL | `email` / `webhook` / `whatsapp` |
| `is_active` | BOOLEAN | NOT NULL | — |

**Tipos de alerta suportados:**
- `conversion_below` — Conversão abaixo de X%
- `stock_below` — Estoque abaixo de N unidades
- `competitor_price_change` — Concorrente mudou de preço
- `no_sales_days` — Zero vendas por N dias
- `competitor_price_below` — Concorrente vendendo abaixo de R$ X
- `reputation_risk` — KPI de reputação se aproximando do limite (Missão 4)

#### `alert_events` — Histórico de Disparos
| Coluna | Tipo | Nullable | Descrição |
|--------|------|----------|-----------|
| `id` | UUID | PK | — |
| `alert_config_id` | UUID FK→alert_configs | NOT NULL | Configuração que disparou |
| `message` | TEXT | NOT NULL | Mensagem descritiva |
| `triggered_at` | TIMESTAMPTZ | NOT NULL | Quando houve detecção |
| `sent_at` | TIMESTAMPTZ | NULL | Quando notificação foi enviada (NULL = pendente) |

---

## 3. Módulos — Dados Extraídos vs. Implementação

### 3.1 Módulo Dashboard / Visão Geral (Missão 1)

**Dados mapeados no painel do ML:**
- Visitas únicas, Intenção de compra, Vendas brutas (R$ + qtd), Conversão (%)
- Filtros: 7, 15, 30, 60 dias com comparativo do período anterior
- Heat Map de vendas: Dia da semana × Faixa horária
- Banner de "Recuperação de Carrinho" com cupons

**Endpoints ML utilizados:**
| Endpoint | Endpoint API | Uso |
|----------|-------------|-----|
| Visitas total seller | `GET /users/{id}/items_visits/time_window?last=N&unit=day` | KPI geral de tráfego |
| Visitas por item | `GET /items/{id}/visits/time_window?last=1&unit=day` | Snapshot individual |
| Visitas em bulk | `GET /visits/items?ids=MLB1,MLB2&date_from=X&date_to=Y` | Batch até 50 IDs |
| Pedidos/Vendas | `GET /orders/search?seller={id}&order.status=paid&order.date_created.from=X` | Vendas do período |

**Métricas que o ML calcula (extraído do HAR):**
```
gross_sales       = Σ(unit_price × quantity)     de todos pedidos
sell_quantity      = nº de pedidos (≠ unidades)
sold_units         = nº de unidades vendidas
average_price_by_unit = gross_sales / sold_units
conversion         = sell_quantity / visits × 100
cancelled_gross_sales = valor R$ dos cancelamentos
returns_gross_sales   = valor R$ das devoluções
```

**Tela proposta (Frontend):**
- 4 Cards KPI (Visitas, Intenção, Vendas Brutas, Conversão)
- Filtro global de período com chips comparativos
- Gráfico de linha temporal (Recharts)
- Mini-tabela "Concentração de Vendas" (dia+hora)

---

### 3.2 Módulo Vendas e Pedidos (Missão 2)

**Dados mapeados no painel do ML:**
- **Tabela:**  Pack ID, Timestamp, Comprador (nome + CPF), SKU, Tag FULL, Status
- **Drill-down financeiro por pedido:**
  - Produto: R$ 498,00 | Tarifa de Venda: -R$ 84,66 (~17%) | Frete: -R$ 106,95 | **Líquido: R$ 306,39**
  - ID Pagamento, Data Aprovação, Prazo de Liquidação (D+8)

**Endpoints ML utilizados:**
| Endpoint | Endpoint API | Uso |
|----------|-------------|-----|
| Buscar pedidos | `GET /orders/search?seller={id}&order.date_created.from=X&order.date_created.to=Y` | Tabela de vendas |
| Item detail | `GET /items/{item_id}` | Dados do item vendido |
| Taxas reais | `GET /sites/MLB/listing_prices?price=X&category_id=Y&listing_type_id=Z` | Comissão exata |
| Frete seller | `GET /users/{id}/shipping_options/free?item_id=MLB&item_price=X` | Custo frete real |

**Fórmula de Margem Líquida (por transação):**
```
margem = preço_venda - taxa_ML - frete_seller - custo_SKU
       = R$ 498.00  - R$ 84.66 - R$ 106.95 - custo_importação
```

**Tela proposta:**
- Tabela paginada com sorteamento (Pack ID, Data, Valor, Status)
- Modal drill-down com waterfall: Bruto → Taxa → Frete → **Líquido**
- Badge de impacto de reputação
- Filtros: período, status (`paid`/`cancelled`/`returned`), conta ML

---

### 3.3 Módulo Anúncios / Catálogo (Missão 3)

**Dados mapeados na Missão 3:**
- Grid de anúncios: Imagem, Título, MLB ID, SKU, Tag ⚡FULL, Estoque no CD
- Faixa de Preços: Preço promocional vs. Clássico vs. Atacado
- Quality Score: 0–100 ("Profissional" = 86)
- Experiência de compra: Score separado (100/100)
- Tarifas: 11.5% clássico, Frete (R$ 8,55 comprador)

**Drill-down de Performance (por MLB):**
- Vendas brutas (R$ 14.193, ▲213%) | Visitas (1.138) | Conversão (4.8%)
- Unidades vendidas × Compradores únicos

**Endpoints ML utilizados:**
| Endpoint | Endpoint API | Uso |
|----------|-------------|-----|
| Listar MLBs | `GET /users/{id}/items/search?status=active` | IDs dos anúncios |
| Detalhe item | `GET /items/{item_id}` | Preço, estoque, SKU, thumbnail |
| Promoções | `GET /seller-promotions/items/{item_id}?app_version=v2` | Desconto ativo |
| Perguntas | `GET /questions/search?item={id}` | Total de perguntas |
| SKU | `items.seller_custom_field` ou `attributes[SELLER_SKU]` | Extração priorizada |

**Mapeamento `listing_type_id` → Tarifa:**
| `listing_type_id` | Nome | Taxa Estimada |
|----|------|------|
| `gold_special` | Clássico | ~11.5% |
| `gold_pro` | Premium | ~17% (inclui parcelamento) |
| `gold_pro` + `fulfillment` | Full | ~17% + frete grátis |

**Tela proposta:**
- Grid responsivo de cards (imagem, título, preço, badge FULL, score)
- Sidebar de filtros (status, conta ML, faixa de preço)
- Modal detalhado: gráfico preco × conversão × vendas (Recharts)

---

### 3.4 Módulo Reputação e Saúde da Conta (Missão 4)

**Dados mapeados na Missão 4:**
- Medalha: **MercadoLíder Gold** | Cor: **Verde Escuro** (nível superior)
- Período: Últimos 60 dias (2.545 vendas → R$ 252.977)

**KPIs do Termômetro com limites:**
| KPI | Valor Atual | Teto "Verde" |
|-----|-------------|-------------|
| Reclamações | 0% | < 1% |
| Mediações | 0% | < 0.5% |
| Canceladas por você | 0.07% | < 0.5% |
| Despacho com atraso | 2.46% | < 6% |

**Endpoint ML:**
```
GET /users/{SELLER_ID}
→ seller_reputation.level_id: "5_green"
→ seller_reputation.power_seller_status: "gold"
→ seller_reputation.metrics.claims.rate: 0.0
→ seller_reputation.metrics.delayed_handling_time.rate: 0.0246
→ seller_reputation.metrics.cancellations.rate: 0.0007
```

> [!IMPORTANT]
> As taxas vêm como **decimal** (0.0007 = 0.07%). Multiplicar por 100 para exibir como percentual no frontend.

**Tela proposta:**
- Termômetro visual com gauge colorido (Verde/Amarelo/Vermelho)
- Indicadores com barra de progresso: Atual vs. Teto (% visual)
- Card de medalha (MercadoLíder Gold/Platinum/Silver)
- Alertas automáticos se próximo do limite

---

### 3.5 Módulo Product Ads / Publicidade (Missão 5)

**Dados mapeados na Missão 5:**
- **Lista de Campanhas:** Diagnóstico algorítmico, Orçamento diário, ROAS objetivo
- **Métricas que o ML expõe por campanha:**

| Métrica | Exemplo Real | Descrição |
|---------|-------------|-----------|
| Vendas por Ads | 49 unid (▲188%) | Unidades convertidas via patrocínio |
| Vendas Orgânicas | 58 unidades | Vendas sem Ads no mesmo período |
| ROAS Realizado | 18.02x (▲32%) | Receita ÷ Investimento |
| **ACOS** | **5.55%** | Investimento ÷ Receita (métrica vital) |
| Cliques | 2.193 | Total de cliques pagos |
| Receita | R$ 17.386 | Receita atribuída ao Ads |
| Investimento | R$ 964,63 | Gasto total da campanha |

**Fórmulas derivadas (calcular no backend):**
```
CPC (Custo por Clique) = Investimento / Cliques
    = R$ 964.63 / 2193 = R$ 0.44

ACOS = Investimento / Receita × 100
     = R$ 964.63 / R$ 17.386 × 100 = 5.55%

ROAS = Receita / Investimento
     = R$ 17.386 / R$ 964.63 = 18.02x
```

> [!NOTE]
> O API público do ML **não expõe** dados de Product Ads. A coleta atual é via scraping do painel. Para integração futura, verificar se há API pública de Ads disponível.

**Tabelas sugeridas (NOVAS — ainda não implementadas):**

```sql
-- Campanhas de Publicidade
CREATE TABLE ads_campaigns (
    id UUID PRIMARY KEY,
    ml_account_id UUID REFERENCES ml_accounts(id),
    name VARCHAR(255) NOT NULL,
    daily_budget DECIMAL(10,2),
    target_roas DECIMAL(8,2),
    status VARCHAR(20),            -- active, paused
    diagnosis VARCHAR(50),         -- excellent, needs_budget
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Métricas Diárias de Ads
CREATE TABLE ads_metrics_daily (
    id UUID PRIMARY KEY,
    campaign_id UUID REFERENCES ads_campaigns(id),
    date DATE NOT NULL,
    clicks INTEGER DEFAULT 0,
    investment DECIMAL(10,2) DEFAULT 0,
    revenue DECIMAL(12,2) DEFAULT 0,
    acos DECIMAL(8,4),             -- Investimento / Receita × 100
    roas DECIMAL(8,2),             -- Receita / Investimento
    units_sold_ads INTEGER DEFAULT 0,
    units_sold_organic INTEGER DEFAULT 0,
    UNIQUE(campaign_id, date)
);
```

---

### 3.6 Módulo Financeiro e Faturamento (Missão 6)

**Dados mapeados na Missão 6:**

**3 Quadrantes do Painel Financeiro:**
| Quadrante | Valor Real | Descrição |
|-----------|-----------|-----------|
| Vendas Brutas (7d) | R$ 46.154 (-2.4%) | Total transacionado vs. semana anterior |
| Dinheiro Disponível | R$ 20.052 | Saldo livre para saque imediato (D+0) |
| A Receber / Antecipar | R$ 45.656 | Retido por prazo D+X ou sujeito a antecipação |

**Endpoints ML para financeiro:**
| Endpoint | API | Uso |
|----------|-----|-----|
| Taxas por categoria | `GET /sites/MLB/listing_prices?price=X&category_id=Y&listing_type_id=Z` | Comissão real em centavos |
| Frete do seller | `GET /users/{id}/shipping_options/free?item_id=MLB&item_price=X` | Custo de frete real |
| Orders com breakdown | `GET /orders/search` → `order_items.unit_price`, cross com taxas | P&L por transação |

**Waterfall Financeiro (por transação):**
```
Receita Bruta    R$ 498,00   (100%)
(-) Taxa ML      R$  84,66   (17%)     → sale_fee_amount
(-) Frete Seller R$ 106,95   (21%)     → avg_shipping_cost
(-) Custo SKU    R$   X,XX   (var.)    → products.cost
(=) Margem Líquida R$ XXX,XX
```

**Tabela sugerida (NOVA — consolidação financeira diária):**

```sql
-- Resumo Financeiro Diário
CREATE TABLE financial_daily_summary (
    id UUID PRIMARY KEY,
    ml_account_id UUID REFERENCES ml_accounts(id),
    date DATE NOT NULL,
    gross_sales DECIMAL(14,2),        -- Vendas brutas do dia
    total_fees DECIMAL(12,2),         -- Soma taxas ML
    total_shipping DECIMAL(12,2),     -- Soma frete descontado
    net_revenue DECIMAL(14,2),        -- Líquido
    available_balance DECIMAL(14,2),  -- Saldo disponível
    pending_balance DECIMAL(14,2),    -- A receber
    UNIQUE(ml_account_id, date)
);
```

---

### 3.7 Módulo Inteligência de Concorrência (Missão 7)

**Dados mapeados na Missão 7 (Cadeira Gamer — Concorrente de Alta Conversão):**

| Driver de Decisão | Dado Extraído | Impacto |
|----|-----|------|
| Vendedor | Loja Oficial LuvinCo (MercadoLíder) | Credibilidade |
| Prova Social | ⭐ 4.7 estrelas / 968+ opiniões | Conversão |
| Badge | 🏆 MAIS VENDIDO (#5 Cadeiras p/ Escritório) | Ranking |
| Preço Cash/PIX | R$ 531,76 | Isca de preço |
| Preço Cartão | R$ 899,90 | Margem real |
| Logística | ⚡ Grátis Amanhã (Full) | UX |
| Up-sell | "Comprar em maior quantidade" | AOV |

**Dados do concorrente que a API pública expõe:**
```
GET /items/{COMPETITOR_MLB_ID}
→ price, original_price, sold_quantity, available_quantity
→ seller_id, shipping.logistic_type

GET /items/{COMPETITOR_MLB_ID}/visits/time_window?last=7&unit=day
→ Visitas por dia (PÚBLICO — funciona sem token do dono)

GET /users/{COMPETITOR_SELLER_ID}
→ seller_reputation.level_id, power_seller_status, ratings
```

---

## 4. Fluxo de Dados Completo (Pipeline)

```mermaid
sequenceDiagram
    participant CRON as Celery Beat (06:00 BRT)
    participant WORKER as Celery Worker
    participant ML as API Mercado Livre
    participant DB as PostgreSQL
    participant CACHE as Redis
    participant FE as Frontend React

    Note over CRON: Diariamente às 06:00 BRT
    CRON->>WORKER: Disparar sync_all_accounts

    loop Para cada MLAccount ativa
        WORKER->>ML: GET /users/{id}/items/search?status=active
        ML-->>WORKER: Lista de MLB IDs

        loop Para cada MLB ID (max 1 req/s)
            WORKER->>ML: GET /items/{mlb_id}
            ML-->>WORKER: Dados do anúncio (preço, estoque, status)

            WORKER->>ML: GET /items/{mlb_id}/visits/time_window?last=1&unit=day
            ML-->>WORKER: Visitas do dia

            WORKER->>ML: GET /orders/search?seller={id}&date_from=hoje
            ML-->>WORKER: Pedidos do dia
        end

        WORKER->>ML: GET /users/{seller_id} (reputação)
        ML-->>WORKER: Métricas de saúde

        loop Para cada Competitor ativo
            WORKER->>ML: GET /items/{competitor_mlb}
            WORKER->>ML: GET /items/{competitor_mlb}/visits/time_window
            ML-->>WORKER: Preço + visitas do concorrente
        end

        WORKER->>DB: INSERT listing_snapshots (1 row por MLB)
        WORKER->>DB: INSERT competitor_snapshots (1 row por concorrente)
        WORKER->>DB: UPDATE listings (preço, estoque, status)
        WORKER->>DB: UPDATE account_health (reputação)

        WORKER->>WORKER: Verificar alert_configs vs. snapshots
        alt Threshold ultrapassado
            WORKER->>DB: INSERT alert_events
            WORKER->>FE: WebSocket push (via Redis pub/sub)
        end
    end

    FE->>DB: GET /api/v1/listings/ (via Backend)
    FE->>DB: GET /api/v1/listings/kpi/summary
    DB-->>FE: Dados renderizados no Dashboard
```

---

## 5. Mapa Completo de Endpoints da API do ML

| # | Método | Endpoint | Auth | Uso no MSM_Pro |
|---|--------|----------|------|---------------|
| 1 | GET | `/items/{ITEM_ID}` | Público | Dados completos do anúncio |
| 2 | GET | `/items/{ID}/visits/time_window?last=N&unit=day` | Público | Visitas diárias de 1 item |
| 3 | GET | `/visits/items?ids=X,Y&date_from=D&date_to=D` | Público | Visitas em bulk (até 50) |
| 4 | GET | `/users/{ID}/items_visits/time_window?last=N&unit=day` | Token | Visitas totais do seller |
| 5 | GET | `/orders/search?seller={ID}&order.date_created.from=D` | Token | Pedidos/vendas do período |
| 6 | GET | `/users/{ID}/items/search?status=active` | Token | Listar MLBs do vendedor |
| 7 | GET | `/seller-promotions/items/{ID}?app_version=v2` | Token | Promoções ativas |
| 8 | GET | `/questions/search?item={ID}` | Token | Perguntas do anúncio |
| 9 | POST | `/oauth/token` | App | Refresh token (6h exp) |
| 10 | PUT | `/items/{ITEM_ID}` | Token | Alterar preço |
| 11 | GET | `/sites/MLB/listing_prices?price=X&category_id=Y&listing_type_id=Z` | Público | Taxa real ML (centavos!) |
| 12 | GET | `/users/{ID}/shipping_options/free?item_id=MLB&item_price=X` | Token | Custo frete do seller |
| 13 | GET | `/users/{SELLER_ID}` | Parcial | Reputação e dados do vendedor |

> [!WARNING]
> **Rate Limit:** 1 req/s por app. Respeitar header `Retry-After` em 429.
> **URL Correta:** `https://api.mercadolibre.com` (sem acento, `.com` e **não** `.com.br`).
> **Token expira em 6h.** Refresh token também muda — sempre salvar o novo.

---

## 6. Estrutura Completa do Projeto (Backend + Frontend)

```
MSM_Pro/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    ← FastAPI app factory
│   │   ├── auth/                      ← JWT + OAuth ML Multi-Conta
│   │   │   ├── models.py             (User, MLAccount)
│   │   │   ├── router.py             (/login, /register, /ml/callback)
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── mercadolivre/
│   │   │   └── client.py             ← Cliente HTTP (async + retry + rate-limit)
│   │   ├── vendas/                    ← Listings + Snapshots
│   │   │   ├── models.py             (Listing, ListingSnapshot)
│   │   │   ├── router.py             (/listings, /listings/sync, /kpi/summary)
│   │   │   ├── schemas.py
│   │   │   └── service.py            (sync_listings_from_ml, get_kpi_by_period)
│   │   ├── produtos/                  ← SKU + Custo
│   │   │   ├── models.py             (Product)
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── financeiro/                ← Taxas + Margem
│   │   │   └── service.py            (calcular_margem, buscar_taxa_real)
│   │   ├── concorrencia/              ← Competitors
│   │   │   ├── models.py             (Competitor, CompetitorSnapshot)
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── reputacao/                 ← Saúde da Conta
│   │   │   └── (a implementar — usa GET /users/{id})
│   │   ├── alertas/                   ← Engine de Alertas
│   │   │   ├── models.py             (AlertConfig, AlertEvent)
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── consultor/                 ← IA Consultora (futuro)
│   │   ├── jobs/
│   │   │   └── tasks.py              ← Celery tasks (sync 06:00 BRT)
│   │   ├── ws/                        ← WebSocket (tempo real)
│   │   └── core/
│   │       ├── config.py             ← Variáveis de ambiente
│   │       ├── database.py           ← async_session_maker
│   │       └── celery_app.py         ← Beat schedule
│   ├── migrations/versions/           ← Alembic migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── start.sh                       ← alembic upgrade head + uvicorn
│   └── railway.json
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    ← Router principal
│   │   ├── main.tsx                   ← Entry point
│   │   ├── index.css                  ← Global styles
│   │   ├── pages/
│   │   │   ├── Dashboard/             ← KPIs + tabela resumo
│   │   │   ├── Anuncios/              ← Grid de MLBs + métricas
│   │   │   ├── Concorrencia/          ← Monitoramento de rivais
│   │   │   ├── Alertas/               ← Config + histórico
│   │   │   ├── Configuracoes/         ← Contas ML (OAuth connect)
│   │   │   ├── Reputacao/             ← Termômetro + KPIs
│   │   │   ├── Produtos/              ← Cadastro de SKU + custo
│   │   │   └── Login/                 ← Autenticação
│   │   ├── components/
│   │   │   └── ProtectedRoute.tsx
│   │   ├── services/
│   │   │   ├── api.ts                 ← Axios + interceptor JWT
│   │   │   └── listingsService.ts
│   │   ├── hooks/
│   │   ├── store/
│   │   │   └── authStore.ts           ← Zustand
│   │   └── lib/
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── package.json
│
├── docs/
│   ├── ml_api_reference.md            ← Fonte da verdade dos endpoints
│   ├── CRONOGRAMA.md
│   └── insights_historico.md
│
├── server.js                          ← Express SPA routing (Railway)
├── docker-compose.yml                 ← PostgreSQL + Redis local
├── CLAUDE.md                          ← Documento master do projeto
└── railway.json                       ← Deploy config
```

---

## 7. Deploy e Infraestrutura

```mermaid
graph LR
    subgraph "GitHub"
        REPO["origin/main"]
    end

    subgraph "Railway"
        BE["Backend Service<br>Dockerfile<br>FastAPI + Celery"]
        FE["Frontend Service<br>Express SPA<br>React build"]
        PG_R[("PostgreSQL 16<br>Managed")]
        REDIS_R[("Redis 7<br>Managed")]
    end

    REPO -->|"auto-deploy<br>on push"| BE
    REPO -->|"auto-deploy<br>on push"| FE
    BE --> PG_R
    BE --> REDIS_R
    FE -->|"API calls"| BE
```

| Item | Valor |
|------|-------|
| Backend URL | `https://msmpro-production.up.railway.app` |
| Frontend URL | `https://msmprofrontend-production.up.railway.app` |
| API Docs | `https://msmpro-production.up.railway.app/docs` |
| Conta ML | MSM_PRIME (`ml_user_id: 2050442871`) |
| Deploy | Git push → Railway auto-deploy |
| Healthcheck | `GET /health` |

---

## 8. Roadmap de Implementação (Sprints)

| Sprint | Módulo | Status | Principais Entregas |
|--------|--------|--------|-------------------|
| **1** | Fundação | ✅ Concluído | Docker, FastAPI, SQLAlchemy, Alembic, OAuth ML, Celery beat |
| **2** | Análise de Preço | 🔄 Em Progresso | Dashboard, KPIs, Snapshot, Lista de anúncios, Valor estoque |
| **3** | Concorrência | ⏳ Pendente | Tabelas competitors, Vincular MLB externo, Sync diário, Gráfico comparativo |
| **4** | Alertas | ⏳ Pendente | Engine Celery, Email SMTP, Configuração de thresholds |
| **5** | Product Ads | 🆕 Novo | Tabelas ads_campaigns/metrics, Dashboard ACOS/ROAS |
| **6** | Financeiro V2 | 🆕 Novo | Resumo diário, Waterfall de margem, Saldo/Antecipação |
| **7** | Reputação | 🆕 Novo | Termômetro visual, Gauge de KPIs, Alertas de risco |

**Tarefas pendentes do Sprint 2:**
- [ ] Gráfico preço × conversão × vendas por MLB
- [ ] Cadastro de custo por SKU
- [ ] Calculadora de margem

---

## 9. Variáveis de Ambiente

```env
# Banco de Dados
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/msm_pro

# Cache e Fila
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/1
CELERY_RESULT_BACKEND=redis://host:6379/2

# JWT
SECRET_KEY=<chave-secreta>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# OAuth Mercado Livre
ML_CLIENT_ID=<app_id>
ML_CLIENT_SECRET=<app_secret>
ML_REDIRECT_URI=https://msmpro-production.up.railway.app/api/v1/auth/ml/callback

# Frontend
FRONTEND_URL=https://msmprofrontend-production.up.railway.app

# Email (Alertas)
SMTP_HOST=<smtp-server>
SMTP_PORT=587
SMTP_USER=<email>
SMTP_PASS=<senha>
```

---

## 10. Regras Críticas para Qualquer IA/Dev

> [!CAUTION]
> Estas regras são absolutas e foram criadas após 10+ bugs críticos no projeto.

1. **Git Primeiro, Sempre** — NUNCA fazer deploy sem `git push origin main`
2. **URL da API:** `https://api.mercadolibre.com` (sem acento, `.com`)
3. **Testar com curl** antes de declarar pronto
4. **Um agente por arquivo** — nunca editar o mesmo arquivo em paralelo
5. **Tokens sincronizados:** `authStore.setAuth()` DEVE chamar `setStoredToken()`
6. **Migrations:** sempre verificar `alembic current` antes de rodar
7. **KPI:** usar `COUNT(DISTINCT listing_id)`, não contar snapshots
8. **Preços:** `price` = atual (já com desconto), `original_price` = cheio, `sale_price` = marketplace (raro)
9. **Taxas ML:** valores vêm em **centavos** → dividir por 100
10. **Reputação:** `rate` vem como decimal (0.0007) → multiplicar por 100 para %
