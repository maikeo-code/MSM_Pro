-- ============================================================
-- SISTEMA DE AUTO-APRENDIZADO - SCHEMA DO BANCO DE DADOS
-- ============================================================
-- Dois bancos lógicos: SUCESSOS e FALHAS
-- Tudo em SQLite para portabilidade
-- ============================================================

-- ========== FEEDBACKS RECEBIDOS ==========
CREATE TABLE IF NOT EXISTS feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,              -- 'user', 'agent_curiosa', 'agent_analista', 'confronto'
    topic TEXT NOT NULL,               -- tema do feedback
    question TEXT NOT NULL,            -- pergunta original
    answer TEXT NOT NULL,              -- resposta dada
    feedback_text TEXT,                -- feedback recebido (se houver)
    sentiment TEXT CHECK(sentiment IN ('positivo', 'negativo', 'neutro', 'inconclusivo')),
    confidence REAL DEFAULT 0.5,       -- 0.0 a 1.0
    cycle_id INTEGER,                  -- em qual ciclo foi gerado
    parent_id INTEGER,                 -- referencia ao feedback que gerou este (confronto)
    tags TEXT,                         -- JSON array de tags
    FOREIGN KEY (parent_id) REFERENCES feedbacks(id)
);

-- ========== BANCO DE SUCESSOS ==========
CREATE TABLE IF NOT EXISTS sucessos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    insight TEXT NOT NULL,              -- o que deu certo
    evidence TEXT,                      -- evidencia/prova
    times_confirmed INTEGER DEFAULT 1, -- quantas vezes foi confirmado
    relevance_score REAL DEFAULT 0.5,  -- 0.0 a 1.0 (atualizado pela analista)
    promoted_to_rule BOOLEAN DEFAULT FALSE,
    rule_text TEXT,                     -- se virou regra, qual é
    tags TEXT,                          -- JSON array
    FOREIGN KEY (feedback_id) REFERENCES feedbacks(id)
);

-- ========== BANCO DE FALHAS ==========
CREATE TABLE IF NOT EXISTS falhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    what_failed TEXT NOT NULL,          -- o que falhou
    why_failed TEXT,                    -- por que falhou (análise)
    attempted_fix TEXT,                 -- tentativa de correção
    fix_worked BOOLEAN,                -- a correção funcionou?
    times_failed INTEGER DEFAULT 1,    -- quantas vezes falhou
    still_unresolved BOOLEAN DEFAULT TRUE,
    tags TEXT,                          -- JSON array
    FOREIGN KEY (feedback_id) REFERENCES feedbacks(id)
);

-- ========== CICLOS DE APRENDIZADO ==========
CREATE TABLE IF NOT EXISTS cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT CHECK(status IN ('running', 'completed', 'cancelled', 'error')) DEFAULT 'running',
    total_questions INTEGER DEFAULT 0,
    total_answers INTEGER DEFAULT 0,
    total_feedbacks INTEGER DEFAULT 0,
    insights_generated INTEGER DEFAULT 0,
    summary TEXT                        -- resumo do ciclo
);

-- ========== PERGUNTAS GERADAS (pela IA Curiosa) ==========
CREATE TABLE IF NOT EXISTS generated_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id INTEGER,
    question TEXT NOT NULL,
    context TEXT,                       -- contexto que gerou a pergunta
    category TEXT,                      -- 'exploratoria', 'confronto', 'aprofundamento', 'criativa'
    answered BOOLEAN DEFAULT FALSE,
    answer TEXT,
    was_relevant BOOLEAN,              -- avaliado pela IA Analista
    relevance_reason TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== CONSENSO ENTRE IAs ==========
CREATE TABLE IF NOT EXISTS consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic TEXT NOT NULL,
    agents_involved TEXT NOT NULL,      -- JSON array dos agentes
    positions TEXT NOT NULL,            -- JSON object {agent: position}
    final_verdict TEXT,                 -- decisão final
    agreement_level REAL,              -- 0.0 a 1.0
    reasoning TEXT,                     -- raciocínio do consenso
    applied_to_project BOOLEAN DEFAULT FALSE
);

-- ========== REGRAS APRENDIDAS ==========
CREATE TABLE IF NOT EXISTS learned_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rule_text TEXT NOT NULL,
    source TEXT,                        -- 'sucesso_repetido', 'consenso', 'feedback_direto'
    confidence REAL DEFAULT 0.5,
    times_applied INTEGER DEFAULT 0,
    times_succeeded INTEGER DEFAULT 0,
    times_failed INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    deprecated_reason TEXT,
    tags TEXT
);

-- ========== ÍNDICES PARA PERFORMANCE ==========
CREATE INDEX IF NOT EXISTS idx_feedbacks_topic ON feedbacks(topic);
CREATE INDEX IF NOT EXISTS idx_feedbacks_sentiment ON feedbacks(sentiment);
CREATE INDEX IF NOT EXISTS idx_feedbacks_cycle ON feedbacks(cycle_id);
CREATE INDEX IF NOT EXISTS idx_sucessos_topic ON sucessos(topic);
CREATE INDEX IF NOT EXISTS idx_sucessos_relevance ON sucessos(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_falhas_topic ON falhas(topic);
CREATE INDEX IF NOT EXISTS idx_falhas_unresolved ON falhas(still_unresolved);
CREATE INDEX IF NOT EXISTS idx_questions_cycle ON generated_questions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_questions_relevant ON generated_questions(was_relevant);
CREATE INDEX IF NOT EXISTS idx_rules_active ON learned_rules(active);
