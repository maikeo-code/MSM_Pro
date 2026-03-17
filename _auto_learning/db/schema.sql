-- ============================================================
-- SWARM GENESIS v6.0 — SCHEMA COMPLETO
-- Fusão final: Auto-Learning + SWARM v3.1 + memória em 3
-- camadas + checkpoints de sessão + rastreamento de código
-- ============================================================
-- Histórico de versões:
--   v1-v4  Aprendizado básico e swarm inicial
--   v5     Memória episódica/semântica/padrões, DNA, HIP, evolução
--   v6     Checkpoints de sessão, rastreamento de alterações de
--          código, log de ações completo e constituição ampliada
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ========== VERSÃO DO SCHEMA ==========
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
INSERT OR IGNORE INTO schema_version (version, description)
    VALUES (6, 'SWARM GENESIS v6.0 — checkpoints de sessão, rastreamento de código e log de ações');

-- ========== CICLOS ==========
-- Representa uma execução completa do loop de aprendizado.
-- Cada ciclo percorre as fases: exploração, validação, síntese e evolução.
CREATE TABLE IF NOT EXISTS cycles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at            TIMESTAMP,
    status              TEXT CHECK(status IN ('running','completed','cancelled','error')) DEFAULT 'running',
    total_questions     INTEGER DEFAULT 0,
    total_answers       INTEGER DEFAULT 0,
    total_feedbacks     INTEGER DEFAULT 0,
    insights_generated  INTEGER DEFAULT 0,
    bugs_fixed          INTEGER DEFAULT 0,
    tests_created       INTEGER DEFAULT 0,
    score_global        REAL,
    summary             TEXT
);

-- ========== FEEDBACKS ==========
-- Armazena cada par pergunta/resposta com avaliação de qualidade.
-- Os feedbacks alimentam a geração de regras e padrões aprendidos.
CREATE TABLE IF NOT EXISTS feedbacks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source        TEXT NOT NULL,
    topic         TEXT NOT NULL,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    feedback_text TEXT,
    sentiment     TEXT CHECK(sentiment IN ('positivo','negativo','neutro','inconclusivo')),
    confidence    REAL DEFAULT 0.5,
    cycle_id      INTEGER,
    parent_id     INTEGER,
    tags          TEXT,
    FOREIGN KEY (parent_id) REFERENCES feedbacks(id),
    FOREIGN KEY (cycle_id)  REFERENCES cycles(id)
);

-- ========== SUCESSOS ==========
-- Registra insights e descobertas confirmadas com evidência.
-- Sucessos com alta relevância podem ser promovidos a regras aprendidas.
CREATE TABLE IF NOT EXISTS sucessos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback_id      INTEGER NOT NULL,
    topic            TEXT NOT NULL,
    insight          TEXT NOT NULL,
    evidence         TEXT,
    times_confirmed  INTEGER DEFAULT 1,
    relevance_score  REAL DEFAULT 0.5,
    promoted_to_rule BOOLEAN DEFAULT FALSE,
    rule_id          INTEGER,
    tags             TEXT,
    FOREIGN KEY (feedback_id) REFERENCES feedbacks(id),
    FOREIGN KEY (rule_id)     REFERENCES learned_rules(id)
);

-- ========== FALHAS ==========
-- Registra erros, tentativas de correção e resolução.
-- Falhas recorrentes não resolvidas disparam debate no parlamento.
CREATE TABLE IF NOT EXISTS falhas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback_id      INTEGER NOT NULL,
    topic            TEXT NOT NULL,
    what_failed      TEXT NOT NULL,
    why_failed       TEXT,
    attempted_fix    TEXT,
    fix_worked       BOOLEAN,
    times_failed     INTEGER DEFAULT 1,
    still_unresolved BOOLEAN DEFAULT TRUE,
    tags             TEXT,
    FOREIGN KEY (feedback_id) REFERENCES feedbacks(id)
);

-- ========== PERGUNTAS GERADAS ==========
-- Perguntas criadas pelo agente "curiosa" para explorar o codebase.
-- Prioridade 0-10: quanto maior, mais urgente.
CREATE TABLE IF NOT EXISTS generated_questions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id         INTEGER,
    question         TEXT NOT NULL,
    context          TEXT,
    category         TEXT,
    priority         INTEGER DEFAULT 0,
    answered         BOOLEAN DEFAULT FALSE,
    answer           TEXT,
    was_relevant     BOOLEAN,
    relevance_reason TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== REGRAS APRENDIDAS ==========
-- Regras extraídas de padrões confirmados e promovidas de sucessos.
-- confidence aumenta a cada aplicação bem-sucedida.
CREATE TABLE IF NOT EXISTS learned_rules (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rule_text         TEXT NOT NULL,
    source            TEXT,
    confidence        REAL DEFAULT 0.5,
    times_applied     INTEGER DEFAULT 0,
    times_succeeded   INTEGER DEFAULT 0,
    times_failed      INTEGER DEFAULT 0,
    active            BOOLEAN DEFAULT TRUE,
    deprecated_reason TEXT,
    tags              TEXT
);

-- ========== CONSENSOS ==========
-- Resultado de deliberações multi-agente sobre temas contestados.
-- applied_to_project=TRUE indica que o consenso gerou ação concreta.
CREATE TABLE IF NOT EXISTS consensus (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic              TEXT NOT NULL,
    agents_involved    TEXT NOT NULL,
    positions          TEXT NOT NULL,
    final_verdict      TEXT,
    agreement_level    REAL,
    reasoning          TEXT,
    applied_to_project BOOLEAN DEFAULT FALSE
);

-- ========== AGENTES ==========
-- Registro de todos os agentes do swarm, fundadores e criados dinamicamente.
-- fitness_score determina a influência do agente nos debates e decisões.
CREATE TABLE IF NOT EXISTS agents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    name             TEXT NOT NULL UNIQUE,
    role             TEXT NOT NULL,
    group_name       TEXT,
    authority_level  INTEGER DEFAULT 1,
    fitness_score    REAL DEFAULT 50.0,
    status           TEXT DEFAULT 'ACTIVE',
    cycles_active    INTEGER DEFAULT 0,
    prompt_version   INTEGER DEFAULT 1,
    prompt_file      TEXT,
    last_rewrite     TIMESTAMP,
    rewrite_reason   TEXT,
    parent_agent_id  INTEGER,
    created_by_cycle INTEGER,
    retired_at       TIMESTAMP,
    retired_reason   TEXT,
    tags             TEXT,
    FOREIGN KEY (parent_agent_id) REFERENCES agents(id)
);

-- ========== PERFORMANCE DOS AGENTES ==========
-- Histórico de desempenho por agente e por ciclo.
-- score_delta positivo aumenta fitness; negativo reduz.
CREATE TABLE IF NOT EXISTS agent_performance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_id    INTEGER NOT NULL,
    cycle_id    INTEGER,
    action      TEXT NOT NULL,
    outcome     TEXT CHECK(outcome IN ('success','failure','neutral')),
    score_delta REAL DEFAULT 0,
    notes       TEXT,
    FOREIGN KEY (agent_id)  REFERENCES agents(id),
    FOREIGN KEY (cycle_id)  REFERENCES cycles(id)
);

-- ========== DEBATES / PARLAMENTO ==========
-- Propostas submetidas ao parlamento de agentes para votação.
-- requires_dna_change=TRUE exige maioria qualificada (>= 2/3).
CREATE TABLE IF NOT EXISTS debates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic               TEXT NOT NULL,
    proposal            TEXT NOT NULL,
    proposed_by         TEXT NOT NULL,
    requires_dna_change BOOLEAN DEFAULT FALSE,
    status              TEXT DEFAULT 'OPEN',
    votes_for           INTEGER DEFAULT 0,
    votes_against       INTEGER DEFAULT 0,
    verdict             TEXT,
    decided_at          TIMESTAMP,
    cycle_id            INTEGER,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- Votos individuais de cada agente em cada debate.
-- weight representa o peso do voto baseado no fitness_score do agente.
CREATE TABLE IF NOT EXISTS debate_votes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    voted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    debate_id  INTEGER NOT NULL,
    agent_name TEXT NOT NULL,
    vote       TEXT CHECK(vote IN ('for','against','veto')),
    argument   TEXT,
    weight     REAL DEFAULT 1.0,
    FOREIGN KEY (debate_id) REFERENCES debates(id)
);

-- ========== EXPERIMENTOS ==========
-- Hipóteses testadas de forma controlada com métricas antes/depois.
-- became_rule_id indica quando o experimento gerou uma regra permanente.
CREATE TABLE IF NOT EXISTS experiments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    title          TEXT NOT NULL,
    hypothesis     TEXT NOT NULL,
    proposed_by    TEXT,
    branch_name    TEXT,
    status         TEXT DEFAULT 'PROPOSED',
    started_cycle  INTEGER,
    ended_cycle    INTEGER,
    metrics_before TEXT,
    metrics_after  TEXT,
    conclusion     TEXT,
    became_rule_id INTEGER,
    FOREIGN KEY (became_rule_id) REFERENCES learned_rules(id)
);

-- ========== PERGUNTAS PARA O HUMANO (HIP) ==========
-- Perguntas que o sistema não consegue responder sozinho e escala ao humano.
-- BLOQUEANTE: bloqueia o ciclo; IMPORTANTE: aguarda janela; CURIOSIDADE: oportunística.
CREATE TABLE IF NOT EXISTS human_questions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id             INTEGER,
    agent_name           TEXT,
    level                TEXT CHECK(level IN ('BLOQUEANTE','IMPORTANTE','CURIOSIDADE')),
    theme                TEXT,
    question             TEXT NOT NULL,
    context              TEXT,
    impact_if_unanswered TEXT,
    suggested_options    TEXT,
    status               TEXT DEFAULT 'PENDING',
    answered_at          TIMESTAMP,
    answer               TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== PREFERÊNCIAS DO HUMANO ==========
-- Modelo de preferências do usuário inferidas a partir de feedbacks e respostas HIP.
-- UNIQUE(category, key) garante upsert atômico por UPDATE OR REPLACE.
CREATE TABLE IF NOT EXISTS human_preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category   TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source     TEXT,
    UNIQUE(category, key)
);

-- ========== DNA DO SISTEMA ==========
-- Regras constitucionais que definem o comportamento fundamental do swarm.
-- immutable=TRUE significa que apenas o humano pode alterar a regra.
CREATE TABLE IF NOT EXISTS dna_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rule_key       TEXT NOT NULL UNIQUE,
    rule_text      TEXT NOT NULL,
    version        INTEGER DEFAULT 1,
    immutable      BOOLEAN DEFAULT FALSE,
    changed_by     TEXT,
    change_reason  TEXT,
    previous_value TEXT
);

-- ========== MEMÓRIA EPISÓDICA ==========
-- O que aconteceu: ações concretas com resultado confirmado.
-- Funciona como o diário de bordo do agente: "eu fiz X no alvo Y e obtive Z".
CREATE TABLE IF NOT EXISTS memory_episodic (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id   INTEGER,
    agent_name TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    result     TEXT CHECK(result IN ('success','failure','partial','unknown')),
    impact     TEXT,
    details    TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== MEMÓRIA SEMÂNTICA ==========
-- O que o sistema sabe sobre o projeto: fatos e conhecimento estruturado.
-- Ex: category='arquitetura', key='banco_principal', value='PostgreSQL 16'.
CREATE TABLE IF NOT EXISTS memory_semantic (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category      TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         TEXT NOT NULL,
    confidence    REAL DEFAULT 0.5,
    discovered_at INTEGER,
    last_verified INTEGER,
    UNIQUE(category, key)
);

-- ========== MEMÓRIA DE PADRÕES ==========
-- Padrões recorrentes de bugs, soluções e comportamentos identificados.
-- standard_fix é preenchido quando o padrão tem solução conhecida e validada.
CREATE TABLE IF NOT EXISTS memory_patterns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pattern_type     TEXT CHECK(pattern_type IN ('bug','success','correlation','anti_pattern')),
    description      TEXT NOT NULL,
    occurrences      INTEGER DEFAULT 1,
    confidence       REAL DEFAULT 0.5,
    standard_fix     TEXT,
    affected_files   TEXT,
    discovered_cycle INTEGER,
    last_seen_cycle  INTEGER,
    active           BOOLEAN DEFAULT TRUE
);

-- ========== SCORES POR ÁREA ==========
-- Rastreamento de score por área do projeto ao longo dos ciclos.
-- Permite gráficos de evolução e identificação de áreas em declínio.
CREATE TABLE IF NOT EXISTS area_scores (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id  INTEGER NOT NULL,
    area_name TEXT NOT NULL,
    score     REAL NOT NULL,
    notes     TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id),
    UNIQUE(cycle_id, area_name)
);

-- ============================================================
-- TABELAS NOVAS — v6.0
-- ============================================================

-- ========== CHECKPOINTS DE SESSÃO (NOVO v6) ==========
-- Salva o estado exato do sistema no momento em que a sessão é encerrada.
-- Permite retomar de onde parou sem repetir trabalho já realizado.
-- progress_json: objeto JSON com estado detalhado (ex: questões pendentes,
--   agentes em execução, resultados parciais, fila de ações).
-- resumed=TRUE indica que este checkpoint foi efetivamente retomado.
CREATE TABLE IF NOT EXISTS session_checkpoints (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id      INTEGER,
    phase         TEXT CHECK(phase IN ('exploration','validation','synthesis','evolution','correction')),
    current_agent TEXT,
    progress_json TEXT,
    resumed       BOOLEAN DEFAULT FALSE,
    resumed_at    TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== RASTREAMENTO DE ALTERAÇÕES DE CÓDIGO (NOVO v6) ==========
-- Registra toda modificação feita pelo sistema em arquivos do projeto.
-- backup_path: caminho para a cópia de segurança criada antes da edição.
-- test_passed: NULL = não testado; TRUE = passou; FALSE = falhou.
-- rolled_back=TRUE indica que a alteração foi revertida ao backup.
-- rollback_reason: motivo da reversão (ex: 'testes falharam', 'humano solicitou').
CREATE TABLE IF NOT EXISTS code_changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id        INTEGER,
    agent_name      TEXT,
    file_path       TEXT NOT NULL,
    change_type     TEXT CHECK(change_type IN ('create','edit','delete','rename','modify','refactor')),
    backup_path     TEXT,
    description     TEXT,
    test_passed     BOOLEAN,
    rolled_back     BOOLEAN DEFAULT FALSE,
    rolled_back_at  TIMESTAMP,
    rollback_reason TEXT,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ========== LOG DE AÇÕES (NOVO v6) ==========
-- Log abrangente de cada ação tomada por qualquer agente do swarm.
-- action_type: tipo canônico da ação executada.
--   Exemplos: read_file, edit_file, run_test, git_commit, debate,
--             create_agent, query_db, call_api, generate_question,
--             apply_rule, rollback_change, checkpoint_save.
-- target: arquivo, endpoint, tabela ou entidade afetada pela ação.
-- result: resultado imediato da ação — 'skipped' indica ação suprimida
--   por regra do DNA ou por decisão de outro agente.
-- details: JSON ou texto livre com contexto adicional (ex: diff, stack trace).
-- duration_ms: tempo de execução em milissegundos para profiling.
-- tokens_used: tokens consumidos na chamada LLM que gerou a ação (quando aplicável).
CREATE TABLE IF NOT EXISTS action_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cycle_id    INTEGER,
    agent_name  TEXT,
    action_type TEXT NOT NULL,
    target      TEXT,
    result      TEXT CHECK(result IN ('success','failure','skipped')),
    details     TEXT,
    duration_ms INTEGER,
    tokens_used INTEGER,
    FOREIGN KEY (cycle_id) REFERENCES cycles(id)
);

-- ============================================================
-- CONSTITUIÇÃO DO SISTEMA (DNA)
-- ============================================================
-- Regras herdadas do v5
INSERT OR IGNORE INTO dna_rules (rule_key, rule_text, immutable) VALUES
    ('no_delete_tests',    'NUNCA apagar testes existentes', TRUE),
    ('no_break_working',   'NUNCA quebrar funcionalidade que já funciona', TRUE),
    ('no_commit_untest',   'NUNCA commitar código sem rodar os testes antes', TRUE),
    ('no_irreversible',    'NUNCA tomar decisão irreversível sem registrar no consensus', TRUE),
    ('preserve_claude_md', 'SEMPRE preservar o CLAUDE.md original do projeto', TRUE),
    ('log_why',            'SEMPRE documentar o motivo de cada decisão importante', TRUE),
    ('register_new_agents','SEMPRE registrar novos agentes na tabela agents', TRUE);

-- Novas regras adicionadas no v6 para rastreamento de alterações de código
INSERT OR IGNORE INTO dna_rules (rule_key, rule_text, immutable) VALUES
    ('backup_before_edit', 'SEMPRE criar backup antes de editar arquivo do projeto', TRUE),
    ('test_after_edit',    'SEMPRE rodar testes após editar código do projeto', TRUE),
    ('rollback_on_fail',   'SEMPRE reverter edição se os testes falharem', TRUE);

-- ============================================================
-- AGENTES FUNDADORES (20 agentes do v5 — preservados integralmente)
-- ============================================================
INSERT OR IGNORE INTO agents (name, role, group_name, authority_level, fitness_score, prompt_file) VALUES
    ('curiosa',          'Geradora de Perguntas',      'learning',    1, 50.0, 'agents/curiosa.md'),
    ('respondedora',     'Pesquisa e Responde',         'learning',    1, 50.0, 'agents/respondedora.md'),
    ('confrontadora',    'Validação por Confronto',     'learning',    2, 50.0, 'agents/confrontadora.md'),
    ('analista',         'Síntese e Regras',            'learning',    3, 50.0, 'agents/analista.md'),
    ('orchestrator',     'Coordenador Central',         'development', 3, 50.0, 'agents/orchestrator.md'),
    ('critic',           'Revisão de Código',           'development', 2, 50.0, 'agents/critic.md'),
    ('developer',        'Implementador',               'development', 1, 50.0, 'agents/developer.md'),
    ('tester',           'Validador de Testes',         'development', 1, 50.0, 'agents/tester.md'),
    ('researcher',       'Pesquisador de Soluções',     'development', 1, 50.0, 'agents/researcher.md'),
    ('documenter',       'Documentador',                'development', 1, 50.0, 'agents/documenter.md'),
    ('founder',          'Validador de APIs',           'development', 2, 50.0, 'agents/founder.md'),
    ('api-specialist',   'Especialista em APIs',        'development', 1, 50.0, 'agents/api-specialist.md'),
    ('security-agent',   'Auditor de Segurança',        'development', 2, 50.0, 'agents/security-agent.md'),
    ('meta-agente',      'Melhora outros agentes',      'evolution',   3, 70.0, 'agents/meta-agente.md'),
    ('criador',          'Cria novos agentes',          'evolution',   2, 60.0, 'agents/criador.md'),
    ('mediador',         'Conduz debates',              'evolution',   2, 65.0, 'agents/mediador.md'),
    ('cientista',        'Experimentos',                'evolution',   1, 55.0, 'agents/cientista.md'),
    ('destilador',       'Destila sabedoria',           'evolution',   2, 65.0, 'agents/destilador.md'),
    ('interrogador-hip', 'Perguntas ao humano',         'evolution',   2, 65.0, 'agents/interrogador-hip.md'),
    ('orquestrador-v5',  'Decide ciclo e evolução',     'evolution',   3, 80.0, 'agents/orquestrador-v5.md');

-- ============================================================
-- ÍNDICES
-- ============================================================

-- Tabelas herdadas do v5
CREATE INDEX IF NOT EXISTS idx_feedbacks_topic      ON feedbacks(topic);
CREATE INDEX IF NOT EXISTS idx_feedbacks_cycle      ON feedbacks(cycle_id);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created    ON feedbacks(created_at);
CREATE INDEX IF NOT EXISTS idx_sucessos_topic       ON sucessos(topic);
CREATE INDEX IF NOT EXISTS idx_sucessos_relevance   ON sucessos(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_falhas_unresolved    ON falhas(still_unresolved);
CREATE INDEX IF NOT EXISTS idx_falhas_topic         ON falhas(topic);
CREATE INDEX IF NOT EXISTS idx_questions_priority   ON generated_questions(priority DESC, answered, created_at);
CREATE INDEX IF NOT EXISTS idx_rules_active         ON learned_rules(active, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_agents_status        ON agents(status, fitness_score DESC);
CREATE INDEX IF NOT EXISTS idx_agent_perf_agent     ON agent_performance(agent_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_debates_status       ON debates(status);
CREATE INDEX IF NOT EXISTS idx_experiments_status   ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_human_q_pending      ON human_questions(status, level);
CREATE INDEX IF NOT EXISTS idx_mem_episodic_cycle   ON memory_episodic(cycle_id);
CREATE INDEX IF NOT EXISTS idx_mem_semantic_cat     ON memory_semantic(category);
CREATE INDEX IF NOT EXISTS idx_mem_patterns_type    ON memory_patterns(pattern_type, active);
CREATE INDEX IF NOT EXISTS idx_area_scores_cycle    ON area_scores(cycle_id);

-- Novas tabelas v6
CREATE INDEX IF NOT EXISTS idx_checkpoints_cycle    ON session_checkpoints(cycle_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_resumed  ON session_checkpoints(resumed);
CREATE INDEX IF NOT EXISTS idx_code_changes_cycle   ON code_changes(cycle_id);
CREATE INDEX IF NOT EXISTS idx_code_changes_file    ON code_changes(file_path);
CREATE INDEX IF NOT EXISTS idx_code_changes_rolled  ON code_changes(rolled_back);
CREATE INDEX IF NOT EXISTS idx_action_log_cycle     ON action_log(cycle_id);
CREATE INDEX IF NOT EXISTS idx_action_log_agent     ON action_log(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_log_type      ON action_log(action_type, result);
CREATE INDEX IF NOT EXISTS idx_action_log_created   ON action_log(created_at DESC);
