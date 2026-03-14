# MSM_Pro — Arquitetura Visual (Diagramas Mermaid)

> Abra este arquivo no GitHub para ver os diagramas renderizados automaticamente.
> Alternativa: cole os blocos em [mermaid.live](https://mermaid.live/edit)

---

## 1. Arquitetura Geral do Sistema

```mermaid
graph TB
    subgraph USUARIO["Usuario"]
        BROWSER["Browser"]
    end

    subgraph RAILWAY["Railway Cloud"]
        subgraph FRONT["Frontend Service"]
            NGINX["Nginx + SPA"]
            REACT["React 18 + TypeScript + Vite"]
        end

        subgraph BACK["Backend Service"]
            FASTAPI["FastAPI + Uvicorn"]
            subgraph MODULOS["Modulos API /api/v1/"]
                AUTH["/auth"]
                VENDAS["/listings"]
                PRODUTOS["/products"]
                CONCORRENCIA["/competitors"]
                ALERTAS["/alertas"]
                FINANCEIRO["/financeiro"]
                REPUTACAO["/reputation"]
                ADS["/ads"]
                CONSULTOR["/consultor"]
            end
        end

        subgraph WORKERS["Workers"]
            CELERY_W["Celery Worker"]
            CELERY_B["Celery Beat Scheduler"]
        end

        subgraph DATA["Data Layer"]
            PG[("PostgreSQL 16 - 15 tabelas")]
            REDIS[("Redis 7 - Cache + Fila")]
        end
    end

    subgraph EXTERNAS["APIs Externas"]
        ML_API["Mercado Libre API"]
        ML_AUTH["ML OAuth"]
        CLAUDE_API["Claude API - Anthropic"]
    end

    BROWSER -->|HTTPS| NGINX
    NGINX --> REACT
    REACT -->|REST API| FASTAPI
    FASTAPI --> PG
    FASTAPI --> REDIS
    FASTAPI -->|OAuth + Data| ML_API
    FASTAPI -->|OAuth Flow| ML_AUTH
    CONSULTOR -->|AI Analysis| CLAUDE_API
    CELERY_B -->|Schedule| CELERY_W
    CELERY_W --> PG
    CELERY_W --> REDIS
    CELERY_W -->|Sync Diario| ML_API

    style AUTH fill:#22c55e,color:#fff
    style VENDAS fill:#22c55e,color:#fff
    style PRODUTOS fill:#22c55e,color:#fff
    style CONCORRENCIA fill:#22c55e,color:#fff
    style ALERTAS fill:#f59e0b,color:#000
    style FINANCEIRO fill:#ef4444,color:#fff
    style REPUTACAO fill:#22c55e,color:#fff
    style ADS fill:#f59e0b,color:#000
    style CONSULTOR fill:#22c55e,color:#fff
```

**Legenda de cores:**
- Verde = Producao (100% funcional)
- Amarelo = Parcial (logica OK, falta integracao)
- Vermelho = Esqueleto (endpoints existem, sem implementacao real)

---

## 2. Modelo de Dados (ERD) — 15 Tabelas

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string hashed_password
        bool is_active
        datetime created_at
    }

    ML_ACCOUNTS {
        uuid id PK
        uuid user_id FK
        string ml_user_id
        string nickname
        string access_token
        string refresh_token
        datetime token_expires_at
        bool is_active
    }

    PRODUCTS {
        uuid id PK
        uuid user_id FK
        string sku UK
        string name
        decimal cost
        string unit
        bool is_active
    }

    LISTINGS {
        uuid id PK
        uuid user_id FK
        uuid product_id FK
        uuid ml_account_id FK
        string mlb_id UK
        string title
        string listing_type
        decimal price
        decimal original_price
        decimal sale_price
        string status
        decimal sale_fee_pct
        int quality_score
    }

    LISTING_SNAPSHOTS {
        uuid id PK
        uuid listing_id FK
        decimal price
        int visits
        int sales_today
        int stock
        decimal conversion_rate
        int orders_count
        decimal revenue
        int cancelled_orders
        int returns_count
        datetime captured_at
    }

    ORDERS {
        uuid id PK
        string ml_order_id UK
        uuid ml_account_id FK
        uuid listing_id FK
        string mlb_id
        int quantity
        decimal unit_price
        decimal total_amount
        decimal sale_fee
        decimal shipping_cost
        decimal net_amount
        string payment_status
        string shipping_status
        datetime order_date
    }

    PRICE_CHANGE_LOGS {
        uuid id PK
        uuid listing_id FK
        uuid user_id FK
        decimal old_price
        decimal new_price
        text justification
        string source
        bool success
    }

    COMPETITORS {
        uuid id PK
        uuid listing_id FK
        string mlb_id
        string title
        bool is_active
    }

    COMPETITOR_SNAPSHOTS {
        uuid id PK
        uuid competitor_id FK
        decimal price
        int visits
        int sales_delta
        int sold_quantity
        datetime captured_at
    }

    ALERT_CONFIGS {
        uuid id PK
        uuid user_id FK
        uuid listing_id FK
        uuid product_id FK
        string alert_type
        decimal threshold
        string channel
        bool is_active
    }

    ALERT_EVENTS {
        uuid id PK
        uuid alert_config_id FK
        text message
        datetime triggered_at
        datetime sent_at
    }

    AD_CAMPAIGNS {
        uuid id PK
        uuid ml_account_id FK
        string campaign_id
        string name
        string status
        decimal daily_budget
        decimal roas_target
    }

    AD_SNAPSHOTS {
        uuid id PK
        uuid campaign_id FK
        date date
        int impressions
        int clicks
        decimal spend
        int attributed_sales
        decimal attributed_revenue
        decimal roas
        decimal acos
    }

    REPUTATION_SNAPSHOTS {
        uuid id PK
        uuid ml_account_id FK
        string seller_level
        string power_seller_status
        decimal claims_rate
        decimal mediations_rate
        decimal cancellations_rate
        decimal late_shipments_rate
        int total_sales_60d
        decimal total_revenue_60d
    }

    SYNC_LOGS {
        uuid id PK
        string task_name
        uuid ml_account_id FK
        string status
        int items_processed
        int items_failed
        datetime started_at
        datetime finished_at
    }

    USERS ||--o{ ML_ACCOUNTS : "possui N contas"
    USERS ||--o{ PRODUCTS : "possui N SKUs"
    USERS ||--o{ LISTINGS : "possui N anuncios"
    USERS ||--o{ ALERT_CONFIGS : "configura alertas"
    ML_ACCOUNTS ||--o{ LISTINGS : "publica anuncios"
    ML_ACCOUNTS ||--o{ AD_CAMPAIGNS : "possui campanhas"
    ML_ACCOUNTS ||--o{ REPUTATION_SNAPSHOTS : "historico reputacao"
    ML_ACCOUNTS ||--o{ ORDERS : "recebe pedidos"
    PRODUCTS ||--o{ LISTINGS : "1 SKU = N MLBs"
    LISTINGS ||--o{ LISTING_SNAPSHOTS : "snapshot diario"
    LISTINGS ||--o{ COMPETITORS : "N concorrentes"
    LISTINGS ||--o{ ORDERS : "N pedidos"
    LISTINGS ||--o{ PRICE_CHANGE_LOGS : "historico precos"
    LISTINGS ||--o{ ALERT_CONFIGS : "alertas por MLB"
    PRODUCTS ||--o{ ALERT_CONFIGS : "alertas por SKU"
    COMPETITORS ||--o{ COMPETITOR_SNAPSHOTS : "snapshot diario"
    ALERT_CONFIGS ||--o{ ALERT_EVENTS : "N disparos"
    AD_CAMPAIGNS ||--o{ AD_SNAPSHOTS : "snapshot diario"
```

---

## 3. Fluxo de Sync Diario (Celery Beat)

```mermaid
flowchart TD
    START["Celery Beat - 06:00 BRT"] --> SYNC_ALL

    subgraph SYNC["sync_all_snapshots - 06:00"]
        SYNC_ALL["Buscar ML Accounts ativas"]
        SYNC_ALL --> LOOP_ACC["Para cada conta ML"]
        LOOP_ACC --> GET_ITEMS["GET /users/id/items/search"]
        GET_ITEMS --> GET_VISITS["GET /users/id/items_visits\n1 chamada = todos itens"]
        GET_VISITS --> LOOP_ITEM["Para cada item"]
        LOOP_ITEM --> GET_DETAIL["GET /items/mlb_id"]
        GET_DETAIL --> GET_ORDERS["GET /orders/search\nseller=id date_from=hoje"]
        GET_ORDERS --> GET_FEES["GET /sites/MLB/listing_prices"]
        GET_FEES --> SAVE_SNAP["Salvar ListingSnapshot\n+ atualizar Listing"]
        SAVE_SNAP --> SYNC_LOG["Criar SyncLog"]
    end

    subgraph REP["sync_reputation - 06:15"]
        REP_START["Buscar ML Accounts"] --> REP_API["GET /users/seller_id"]
        REP_API --> REP_SAVE["Salvar ReputationSnapshot"]
    end

    subgraph ALERT["evaluate_alerts - 06:30"]
        ALERT_START["Buscar AlertConfigs ativas"] --> ALERT_LOOP["Para cada alerta"]
        ALERT_LOOP --> ALERT_CHECK{"Tipo do alerta?"}
        ALERT_CHECK -->|conversion_below| CHECK_CONV["Conversao 7d < threshold?"]
        ALERT_CHECK -->|stock_below| CHECK_STOCK["Estoque < threshold?"]
        ALERT_CHECK -->|no_sales_days| CHECK_SALES["0 vendas por N dias?"]
        ALERT_CHECK -->|competitor_price| CHECK_COMP["Concorrente mudou preco?"]
        CHECK_CONV --> FIRE["Criar AlertEvent"]
        CHECK_STOCK --> FIRE
        CHECK_SALES --> FIRE
        CHECK_COMP --> FIRE
    end

    subgraph COMP["sync_competitors - 07:00"]
        COMP_START["Buscar Competitors ativos"] --> COMP_API["GET /items/mlb_id"]
        COMP_API --> COMP_SAVE["Salvar CompetitorSnapshot"]
    end

    subgraph TOKEN["refresh_tokens - 23:00"]
        TOKEN_START["Buscar tokens expirando"] --> TOKEN_API["POST /oauth/token\nrefresh_token"]
        TOKEN_API --> TOKEN_SAVE["Atualizar MLAccount"]
    end

    SYNC_LOG --> REP_START
    REP_SAVE --> ALERT_START
    FIRE --> COMP_START
    COMP_SAVE -.-> TOKEN_START

    style SYNC_ALL fill:#22c55e,color:#fff
    style REP_START fill:#22c55e,color:#fff
    style ALERT_START fill:#f59e0b,color:#000
    style COMP_START fill:#22c55e,color:#fff
    style TOKEN_START fill:#22c55e,color:#fff
```

---

## 4. Status Backend vs Frontend

```mermaid
graph LR
    subgraph BACKEND["BACKEND - Status"]
        B_AUTH["AUTH\n100%"]
        B_VENDAS["VENDAS\n17 endpoints\n95%"]
        B_PRODUTOS["PRODUTOS\nCRUD\n100%"]
        B_CONC["CONCORRENCIA\n6 endpoints\n100%"]
        B_ALERTAS["ALERTAS\n7 endpoints\n70%\nfalta email"]
        B_FIN["FINANCEIRO\n4 endpoints\n20%\nfalta P&L"]
        B_REP["REPUTACAO\n4 endpoints\n100%"]
        B_ADS["ADS\n3 endpoints\n50%\nfalta sync"]
        B_CONSUL["CONSULTOR\nClaude API\n100%"]
        B_JOBS["CELERY\n7 tasks\n100%"]
    end

    subgraph FRONTEND["FRONTEND - Status"]
        F_LOGIN["Login\n100%"]
        F_DASH["Dashboard\n100%"]
        F_ANUN["Anuncios\n100%"]
        F_PROD["Produtos\n100%"]
        F_CONC["Concorrencia\n85%"]
        F_ALERT["Alertas\n100%"]
        F_FIN["Financeiro\n100% UI\naguarda backend"]
        F_REP["Reputacao\n100%"]
        F_ADS["Publicidade\n100% UI\nsem dados"]
        F_CONF["Config\n90%"]
    end

    B_AUTH --- F_LOGIN
    B_AUTH --- F_CONF
    B_VENDAS --- F_DASH
    B_VENDAS --- F_ANUN
    B_PRODUTOS --- F_PROD
    B_CONC --- F_CONC
    B_ALERTAS --- F_ALERT
    B_FIN --- F_FIN
    B_REP --- F_REP
    B_ADS --- F_ADS
    B_CONSUL --- F_DASH

    style B_AUTH fill:#22c55e,color:#fff
    style B_VENDAS fill:#22c55e,color:#fff
    style B_PRODUTOS fill:#22c55e,color:#fff
    style B_CONC fill:#22c55e,color:#fff
    style B_ALERTAS fill:#f59e0b,color:#000
    style B_FIN fill:#ef4444,color:#fff
    style B_REP fill:#22c55e,color:#fff
    style B_ADS fill:#f59e0b,color:#000
    style B_CONSUL fill:#22c55e,color:#fff
    style B_JOBS fill:#22c55e,color:#fff

    style F_LOGIN fill:#22c55e,color:#fff
    style F_DASH fill:#22c55e,color:#fff
    style F_ANUN fill:#22c55e,color:#fff
    style F_PROD fill:#22c55e,color:#fff
    style F_CONC fill:#22c55e,color:#fff
    style F_ALERT fill:#22c55e,color:#fff
    style F_FIN fill:#3b82f6,color:#fff
    style F_REP fill:#22c55e,color:#fff
    style F_ADS fill:#3b82f6,color:#fff
    style F_CONF fill:#22c55e,color:#fff
```

---

## 5. Gaps e Prioridades

```mermaid
graph TD
    subgraph ALTA["PRIORIDADE ALTA - Funcionalidade quebrada"]
        GAP1["FINANCEIRO BACKEND\nget_resumo sem implementacao\nget_detalhado sem implementacao\nget_timeline sem implementacao\nget_cashflow sem implementacao"]
        GAP2["ENVIO DE ALERTAS\nSMTP nao conectado\nWebhook nao implementado"]
    end

    subgraph MEDIA["PRIORIDADE MEDIA - Feature incompleta"]
        GAP3["ADS SYNC\nML API nao fornece\ndados publicitarios"]
        GAP4["GRAFICO CONCORRENTE\nFrontend nao mostra\nhistorico de precos"]
        GAP5["PAGINACAO REAL\nListings retorna tudo\nsem limit/offset"]
    end

    subgraph BAIXA["PRIORIDADE BAIXA - Nice to have"]
        GAP6["WebSocket tempo real"]
        GAP7["Trocar Senha"]
        GAP8["Import/Export SKU"]
        GAP9["Testes Unitarios"]
    end

    GAP1 -->|"~3 dias"| FIX1["Agregar Orders +\nSnapshots no\nfinanceiro/service.py"]
    GAP2 -->|"~3 dias"| FIX2["Conectar SMTP +\nimplementar\nwebhook POST"]

    style GAP1 fill:#ef4444,color:#fff
    style GAP2 fill:#ef4444,color:#fff
    style GAP3 fill:#f59e0b,color:#000
    style GAP4 fill:#f59e0b,color:#000
    style GAP5 fill:#f59e0b,color:#000
    style GAP6 fill:#86efac,color:#000
    style GAP7 fill:#86efac,color:#000
    style GAP8 fill:#86efac,color:#000
    style GAP9 fill:#86efac,color:#000
    style FIX1 fill:#3b82f6,color:#fff
    style FIX2 fill:#3b82f6,color:#fff
```

---

## 6. Roadmap de Implementacao

```mermaid
gantt
    title MSM_Pro - Roadmap
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m

    section Sprint 2 - Finalizar
    Financeiro backend P&L real          :crit, fin1, 2026-03-15, 3d
    Grafico preco x conversao x vendas   :chart1, after fin1, 2d

    section Sprint 3 - Concorrencia
    Grafico comparativo de precos        :comp1, after chart1, 2d
    Alerta concorrente via email         :comp2, after comp1, 1d

    section Sprint 4 - Alertas
    Conectar SMTP envio email            :alert1, after comp2, 2d
    Implementar webhook POST             :alert2, after alert1, 1d
    Testar fluxo completo                :alert3, after alert2, 1d

    section Sprint 5 - Qualidade
    Testes unitarios backend             :test1, after alert3, 3d
    Paginacao real em listings           :pag1, after test1, 1d
    WebSocket notificacoes               :ws1, after pag1, 3d

    section Sprint 6 - UX
    Mobile responsive                    :mob1, after ws1, 3d
    Trocar senha                         :pwd1, after mob1, 1d
    Import/Export SKU                    :imp1, after pwd1, 2d
```

---

## 7. Jornada do Usuario

```mermaid
flowchart LR
    subgraph SETUP["Setup Inicial"]
        S1["Login email+senha"] --> S2["Conectar conta ML\nOAuth"]
        S2 --> S3["Cadastrar SKUs\ncom custo"]
        S3 --> S4["Vincular MLBs\naos SKUs"]
    end

    subgraph DIARIO["Uso Diario"]
        D1["Ver Dashboard\nKPIs do dia"] --> D2["Analisar\nanuncio individual"]
        D2 --> D3["Consultar IA\nsobre preco"]
        D3 --> D4["Ajustar preco\nvia sistema"]
    end

    subgraph MONITOR["Monitoramento"]
        M1["Configurar alertas\nestoque/conversao"] --> M2["Adicionar\nconcorrentes"]
        M2 --> M3["Ver reputacao\ne riscos"]
        M3 --> M4["Analisar\nfinanceiro P&L"]
    end

    S4 --> D1
    D4 --> M1

    style S1 fill:#22c55e,color:#fff
    style S2 fill:#22c55e,color:#fff
    style S3 fill:#22c55e,color:#fff
    style S4 fill:#22c55e,color:#fff
    style D1 fill:#22c55e,color:#fff
    style D2 fill:#22c55e,color:#fff
    style D3 fill:#22c55e,color:#fff
    style D4 fill:#22c55e,color:#fff
    style M1 fill:#22c55e,color:#fff
    style M2 fill:#22c55e,color:#fff
    style M3 fill:#22c55e,color:#fff
    style M4 fill:#ef4444,color:#fff
```

**Legenda:** Verde = funcional | Vermelho = backend incompleto

---

## 8. Resumo Executivo

| Metrica | Valor |
|---------|-------|
| Tabelas no banco | 15 |
| Endpoints API | ~55 |
| Paginas frontend | 11 |
| Migrations Alembic | 13 |
| Celery tasks | 7 |
| Chamadas ML API | 14 |
| Modulos backend | 10 |
| **Completude geral** | **~80%** |

### Status por Area

| Area | Backend | Frontend | Status |
|------|---------|----------|--------|
| Auth + OAuth ML | 100% | 100% | Producao |
| Sync de dados ML | 100% | - | Producao |
| Dashboard + KPIs | 100% | 100% | Producao |
| Analise por MLB | 95% | 100% | Producao |
| Cadastro SKU | 100% | 100% | Producao |
| Concorrencia | 100% | 85% | Falta grafico |
| Alertas | 70% | 100% | Falta email/webhook |
| **Financeiro** | **20%** | **100%** | **Gap critico** |
| Reputacao | 100% | 100% | Producao |
| Publicidade | 50% | 100% | API ML indisponivel |
| Consultor IA | 100% | 100% | Producao |
