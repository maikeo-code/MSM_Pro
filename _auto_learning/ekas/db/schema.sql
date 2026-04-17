-- =============================================================================
-- EKAS v1.0 — External Knowledge Acquisition System
-- Schema para coleta de inteligencia externa multi-projeto
--
-- Objetivo: rastrear fontes externas (YouTube, docs, GitHub, marketplaces),
-- mapear concorrentes, funcionalidades, tutoriais, oportunidades e alertas
-- de monitoramento, de forma agnóstica ao projeto (escalável para qualquer
-- projeto do ecossistema MSM Imports / Swarm Genesis v6).
--
-- Compatibilidade: SQLite 3.37+ (suporte a GENERATED COLUMNS e WAL)
-- Criado em: 2024
-- =============================================================================

PRAGMA journal_mode=WAL;       -- Write-Ahead Logging: melhor concorrência de leitura
PRAGMA foreign_keys=ON;        -- Garante integridade referencial

-- =============================================================================
-- VERSAO DO SCHEMA
-- Rastreia migrações futuras; usar INSERT OR IGNORE para reaplicações seguras
-- =============================================================================
CREATE TABLE IF NOT EXISTS ekas_schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT    DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO ekas_schema_version (version, description)
    VALUES (1, 'EKAS v1.0 — External Knowledge Acquisition System');

-- =============================================================================
-- PROJECTS — Registro de projetos (suporte multi-projeto)
--
-- Cada projeto tem um slug único (id), keywords padrão para buscas e um
-- caminho base opcional para referência. project_id NULL em outras tabelas
-- significa que o registro se aplica a TODOS os projetos.
-- =============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT    PRIMARY KEY,                         -- slug: "msm_pro", "emails", "ia_geral"
    name        TEXT    NOT NULL,
    description TEXT,
    base_path   TEXT,                                        -- caminho raiz do projeto no sistema de arquivos
    keywords    TEXT,                                        -- JSON: palavras-chave padrão para buscas ["erp","ml","fiscal"]
    is_active   INTEGER NOT NULL DEFAULT 1,                  -- 1=ativo, 0=arquivado
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- =============================================================================
-- SOURCES — Conteúdo bruto coletado de fontes externas
--
-- Armazena o material coletado antes e depois do processamento por IA.
-- O campo status reflete o ciclo de vida: RAW → PROCESSING → PROCESSED.
-- Um mesmo URL não pode ser coletado duas vezes (UNIQUE source_type + source_url).
-- =============================================================================
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT,                                    -- NULL = aplica-se a todos os projetos
    source_type     TEXT    NOT NULL
                    CHECK(source_type IN (
                        'youtube',       -- vídeos e canais do YouTube
                        'docs',          -- documentação oficial de produtos
                        'manual',        -- inserção manual pelo usuário
                        'github',        -- repositórios e issues GitHub
                        'web',           -- páginas web genéricas
                        'marketplace'    -- listagens de marketplaces (ML, Shopify, etc)
                    )),
    source_url      TEXT    NOT NULL,                        -- URL canônica da fonte
    source_id       TEXT,                                    -- ID da plataforma (video_id, repo slug, etc)
    title           TEXT    NOT NULL,
    author          TEXT,                                    -- nome do autor/canal/empresa
    author_channel  TEXT,                                    -- handle ou URL do canal/perfil
    published_at    TEXT,                                    -- data de publicação no formato ISO-8601
    language        TEXT    NOT NULL DEFAULT 'pt-BR',
    raw_text        TEXT,                                    -- transcrição ou conteúdo bruto
    summary_short   TEXT,                                    -- resumo ~100 palavras gerado por IA
    summary_medium  TEXT,                                    -- resumo ~300 palavras gerado por IA
    summary_full    TEXT,                                    -- resumo completo gerado por IA
    relevance_score REAL    NOT NULL DEFAULT 0,              -- 0.0 a 1.0; calculado pelo agente analisador
    metadata        TEXT,                                    -- JSON: {views, likes, duration, pages, stars, forks, etc}
    tags            TEXT,                                    -- JSON: ["fiscal","nota_fiscal","xml"]
    status          TEXT    NOT NULL DEFAULT 'RAW'
                    CHECK(status IN (
                        'RAW',           -- coletado, aguardando processamento
                        'PROCESSING',    -- em processamento por IA agora
                        'PROCESSED',     -- processamento concluído com sucesso
                        'FAILED',        -- falha no processamento (ver metadata.error)
                        'ARCHIVED'       -- desativado / irrelevante
                    )),
    collected_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    processed_at    TEXT,                                    -- preenchido ao concluir processamento
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(source_type, source_url)                          -- impede coleta duplicada
);

-- =============================================================================
-- COMPETITORS — Mapa de concorrentes por projeto
--
-- Agrupa informações sobre cada concorrente: categoria de mercado, pontos
-- fortes/fracos, integrações e sentimento geral extraído das fontes.
-- =============================================================================
CREATE TABLE IF NOT EXISTS competitors (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          TEXT,
    name                TEXT    NOT NULL,
    category            TEXT,                                -- ERP, marketplace, logística, fiscal, IA, etc
    website             TEXT,
    pricing_info        TEXT,                                -- descrição livre de preços/planos
    target_audience     TEXT,                               -- público-alvo identificado
    integrations        TEXT,                               -- JSON: ["Mercado Livre","TOTVS","Bling","NFe"]
    strengths           TEXT,                               -- JSON: lista de pontos fortes detectados
    weaknesses          TEXT,                               -- JSON: lista de pontos fracos / reclamações
    overall_sentiment   REAL    NOT NULL DEFAULT 0,         -- média ponderada: -1 (negativo) a 1 (positivo)
    source_count        INTEGER NOT NULL DEFAULT 0,         -- total de fontes que mencionam este concorrente
    last_updated        TEXT    NOT NULL DEFAULT (datetime('now')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(project_id, name)                                -- nome único por projeto
);

-- =============================================================================
-- COMPETITOR_SOURCES — Relacionamento N:N entre concorrentes e fontes
--
-- Permite rastrear quais fontes mencionam qual concorrente, sem duplicação
-- de dados. Útil para auditoria e recálculo de métricas.
-- =============================================================================
CREATE TABLE IF NOT EXISTS competitor_sources (
    competitor_id   INTEGER NOT NULL,
    source_id       INTEGER NOT NULL,
    PRIMARY KEY (competitor_id, source_id),
    FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id)     REFERENCES sources(id)     ON DELETE CASCADE
);

-- =============================================================================
-- FEATURES — Funcionalidades de mercado detectadas
--
-- Registra funcionalidades mencionadas nas fontes externas, com score de
-- importância baseado em frequência de menção, complexidade estimada de
-- implementação e status no projeto atual.
-- =============================================================================
CREATE TABLE IF NOT EXISTS features (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id                  TEXT,
    name                        TEXT    NOT NULL,
    category                    TEXT,                        -- fiscal, estoque, vendas, logística, IA, relatórios, etc
    description                 TEXT,
    importance_score            REAL    NOT NULL DEFAULT 0,  -- 0.0 a 1.0; baseado em frequência de menção
    implementation_complexity   TEXT
                                CHECK(implementation_complexity IN (
                                    'low',        -- dias
                                    'medium',     -- semanas
                                    'high',       -- meses
                                    'very_high'   -- trimestres / requer arquitetura nova
                                )),
    project_status              TEXT    NOT NULL DEFAULT 'NOT_PLANNED'
                                CHECK(project_status IN (
                                    'NOT_PLANNED',   -- ainda não considerada
                                    'PLANNED',       -- no backlog
                                    'IN_PROGRESS',   -- em desenvolvimento
                                    'IMPLEMENTED',   -- já existe no produto
                                    'REJECTED'       -- decidido não implementar
                                )),
    created_at                  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(project_id, name)
);

-- =============================================================================
-- FEATURE_IMPLEMENTATIONS — Como cada concorrente implementa uma funcionalidade
--
-- Captura o "como funciona" de cada concorrente para uma feature específica,
-- incluindo passos detalhados, prós, contras e a fonte de onde foi extraído.
-- =============================================================================
CREATE TABLE IF NOT EXISTS feature_implementations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_id      INTEGER NOT NULL,
    competitor_id   INTEGER NOT NULL,
    how_it_works    TEXT,                                    -- descrição em prosa de como o concorrente implementa
    steps           TEXT,                                    -- JSON: [{step: 1, action: "...", detail: "..."}]
    pros            TEXT,                                    -- JSON: pontos positivos desta implementação
    cons            TEXT,                                    -- JSON: limitações / críticas identificadas
    source_id       INTEGER,                                 -- fonte de onde foi extraído (pode ser NULL se manual)
    extracted_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (feature_id)    REFERENCES features(id)     ON DELETE CASCADE,
    FOREIGN KEY (competitor_id) REFERENCES competitors(id)  ON DELETE CASCADE,
    FOREIGN KEY (source_id)     REFERENCES sources(id)      ON DELETE SET NULL
);

-- =============================================================================
-- TUTORIALS — Passo a passo extraído das fontes
--
-- Registra tutoriais identificados por IA nas fontes coletadas. Cada tutorial
-- está ligado a uma fonte, e opcionalmente a um concorrente e uma feature,
-- permitindo cruzar "como o concorrente X ensina a usar feature Y".
-- =============================================================================
CREATE TABLE IF NOT EXISTS tutorials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    source_id       INTEGER,
    competitor_id   INTEGER,
    feature_id      INTEGER,
    project_id      TEXT,
    steps           TEXT    NOT NULL,                        -- JSON: [{step: N, action: "...", detail: "...", screenshot_desc: "..."}]
    prerequisites   TEXT,                                    -- JSON: o que o usuário precisa saber/ter antes
    difficulty      TEXT
                    CHECK(difficulty IN (
                        'beginner',       -- sem conhecimento prévio
                        'intermediate',   -- alguma familiaridade com o sistema
                        'advanced'        -- usuário experiente / técnico
                    )),
    estimated_time  TEXT,                                    -- ex: "15 minutos", "2 horas"
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id)     REFERENCES sources(id)      ON DELETE SET NULL,
    FOREIGN KEY (competitor_id) REFERENCES competitors(id)  ON DELETE SET NULL,
    FOREIGN KEY (feature_id)    REFERENCES features(id)     ON DELETE SET NULL,
    FOREIGN KEY (project_id)    REFERENCES projects(id)
);

-- =============================================================================
-- OPPORTUNITIES — Lacunas, tendências e diferenciais detectados
--
-- Registra oportunidades identificadas pela IA a partir da análise das fontes.
-- O campo priority_score é calculado automaticamente como impacto * (1 - esforço),
-- favorecendo oportunidades de alto impacto e baixo esforço.
-- =============================================================================
CREATE TABLE IF NOT EXISTS opportunities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      TEXT,
    type            TEXT    NOT NULL
                    CHECK(type IN (
                        'gap',              -- funcionalidade ausente em todos os concorrentes
                        'complaint',        -- reclamação recorrente de usuários sobre concorrentes
                        'trend',            -- tendência de mercado emergente
                        'differentiator',   -- diferencial competitivo possível
                        'unserved_need'     -- necessidade de usuários não atendida por ninguém
                    )),
    title           TEXT    NOT NULL,
    description     TEXT,
    evidence        TEXT,                                    -- JSON: [{source_id, excerpt, relevance}]
    impact_score    REAL    NOT NULL DEFAULT 0,              -- 0.0 (baixo) a 1.0 (alto)
    effort_score    REAL    NOT NULL DEFAULT 0,              -- 0.0 (fácil) a 1.0 (muito difícil)
    -- Coluna gerada: prioridade = impacto * (1 - esforço). Maior = melhor ROI.
    priority_score  REAL    GENERATED ALWAYS AS
                    (ROUND(impact_score * (1.0 - effort_score), 4)) STORED,
    status          TEXT    NOT NULL DEFAULT 'DETECTED'
                    CHECK(status IN (
                        'DETECTED',      -- identificada automaticamente
                        'VALIDATED',     -- confirmada pelo time
                        'PLANNED',       -- no roadmap
                        'IN_PROGRESS',   -- em desenvolvimento
                        'IMPLEMENTED',   -- entregue
                        'DISMISSED'      -- descartada (ver dismiss_reason)
                    )),
    dismiss_reason  TEXT,                                    -- obrigatório quando status = DISMISSED
    project_ticket  TEXT,                                    -- URL ou ID do ticket/issue criado
    detected_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- =============================================================================
-- WATCHLIST — Alvos de monitoramento contínuo
--
-- Define o que deve ser verificado periodicamente: canais, keywords,
-- concorrentes ou autores específicos. O agente coletor usa esta tabela
-- para saber o que checar em cada execução agendada.
-- =============================================================================
CREATE TABLE IF NOT EXISTS watchlist (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id              TEXT,
    watch_type              TEXT    NOT NULL
                            CHECK(watch_type IN (
                                'channel',      -- canal YouTube ou perfil de rede social
                                'keyword',      -- termo de busca genérico
                                'competitor',   -- página / nome de concorrente
                                'feature',      -- menções a uma funcionalidade
                                'author'        -- publicações de um autor específico
                            )),
    target                  TEXT    NOT NULL,                -- URL, keyword ou nome do alvo
    filters                 TEXT,                            -- JSON: filtros específicos {lang, min_views, date_from, etc}
    check_interval_hours    INTEGER NOT NULL DEFAULT 168,    -- intervalo de verificação (padrão: 1 semana)
    last_checked            TEXT,                            -- última vez que foi verificado (ISO-8601)
    new_items_count         INTEGER NOT NULL DEFAULT 0,      -- novos itens encontrados na última verificação
    is_active               INTEGER NOT NULL DEFAULT 1,      -- 1=monitorando, 0=pausado
    created_at              TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- =============================================================================
-- COLLECTION_RUNS — Log de auditoria de todas as operações de coleta
--
-- Cada execução do coletor registra um run, permitindo rastrear custo de
-- tokens, tempo de execução, volume coletado e falhas para debugging.
-- =============================================================================
CREATE TABLE IF NOT EXISTS collection_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          TEXT,
    run_type            TEXT
                        CHECK(run_type IN (
                            'manual',      -- disparado manualmente pelo usuário
                            'scheduled',   -- agendado (Task Scheduler / cron)
                            'watchlist',   -- originado por item da watchlist
                            'batch'        -- processamento em lote de múltiplas fontes
                        )),
    source_type         TEXT,                                -- tipo de fonte sendo coletada
    query               TEXT,                                -- termo de busca ou URL usada
    items_found         INTEGER NOT NULL DEFAULT 0,          -- total de itens retornados pela API
    items_new           INTEGER NOT NULL DEFAULT 0,          -- itens realmente novos (não duplicados)
    items_processed     INTEGER NOT NULL DEFAULT 0,          -- itens que passaram por processamento IA
    tokens_used         INTEGER NOT NULL DEFAULT 0,          -- tokens Anthropic consumidos neste run
    duration_ms         INTEGER,                             -- duração total em milissegundos
    status              TEXT    NOT NULL DEFAULT 'RUNNING'
                        CHECK(status IN (
                            'RUNNING',    -- em execução
                            'COMPLETED',  -- concluído sem erros
                            'FAILED',     -- falha total
                            'PARTIAL'     -- concluído com erros parciais
                        )),
    error               TEXT,                                -- mensagem de erro se status = FAILED/PARTIAL
    started_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at         TEXT,                                -- preenchido ao finalizar
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- =============================================================================
-- INDEXES — Otimizações de performance para queries frequentes
--
-- Cobrindo: filtragem por projeto, status, relevância, categoria e ordenação
-- por data e score. Indexes compostos nas queries mais críticas dos agentes.
-- =============================================================================

-- sources: filtragem e ordenação principal
CREATE INDEX IF NOT EXISTS idx_sources_type        ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_status      ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_relevance   ON sources(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_sources_author      ON sources(author_channel);
CREATE INDEX IF NOT EXISTS idx_sources_project     ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_sources_collected   ON sources(collected_at DESC);
-- index composto: buscar fontes não processadas por projeto (uso frequente do processador)
CREATE INDEX IF NOT EXISTS idx_sources_pending     ON sources(project_id, status, collected_at DESC);

-- competitors
CREATE INDEX IF NOT EXISTS idx_competitors_project  ON competitors(project_id);
CREATE INDEX IF NOT EXISTS idx_competitors_category ON competitors(category);

-- features
CREATE INDEX IF NOT EXISTS idx_features_project    ON features(project_id);
CREATE INDEX IF NOT EXISTS idx_features_category   ON features(category);
CREATE INDEX IF NOT EXISTS idx_features_importance ON features(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_features_status     ON features(project_status);
-- index composto: painel de backlog por projeto
CREATE INDEX IF NOT EXISTS idx_features_backlog    ON features(project_id, project_status, importance_score DESC);

-- tutorials
CREATE INDEX IF NOT EXISTS idx_tutorials_feature    ON tutorials(feature_id);
CREATE INDEX IF NOT EXISTS idx_tutorials_competitor ON tutorials(competitor_id);
CREATE INDEX IF NOT EXISTS idx_tutorials_project    ON tutorials(project_id);

-- opportunities
CREATE INDEX IF NOT EXISTS idx_opportunities_project  ON opportunities(project_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_priority ON opportunities(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_status   ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_type     ON opportunities(type);
-- index composto: painel de oportunidades ativas por projeto e prioridade
CREATE INDEX IF NOT EXISTS idx_opportunities_active   ON opportunities(project_id, status, priority_score DESC);

-- watchlist
CREATE INDEX IF NOT EXISTS idx_watchlist_active   ON watchlist(is_active, last_checked);
CREATE INDEX IF NOT EXISTS idx_watchlist_project  ON watchlist(project_id);

-- collection_runs
CREATE INDEX IF NOT EXISTS idx_collection_runs_status  ON collection_runs(status);
CREATE INDEX IF NOT EXISTS idx_collection_runs_project ON collection_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_collection_runs_started ON collection_runs(started_at DESC);
