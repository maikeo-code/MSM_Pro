"""
============================================================
SWARM GENESIS v7.0 — ENGINE COMPLETO
Melhorias sobre v5: checkpoints de sessão, rastreamento de
mudanças de código com rollback, log de ações com contagem
de tokens, contexto e stats ampliados.
v7: metacognição avançada, auto-modificação, 56 comandos CLI.

Grupos de métodos:
  - Conexão          : __init__, _ensure_db, _conn
  - Ciclos           : start_cycle, end_cycle, get_current_cycle, get_cycle_history
  - Feedbacks        : register_feedback, get_feedbacks_by_topic, get_recent_feedbacks
  - Sucessos         : register_success, get_top_successes
  - Falhas           : register_failure, mark_failure_resolved, get_unresolved_failures
  - Perguntas        : save_question, answer_question, get_unanswered_questions
  - Regras           : create_rule, update_rule_stats, deprecate_rule,
                       get_active_rules, get_deprecated_rules
  - Consensos        : register_consensus, get_recent_consensus
  - Agentes          : register_agent, update_agent_fitness, retire_agent,
                       get_agent_fitness, get_all_agents, get_retired_agents,
                       rewrite_agent_prompt
  - Debates          : open_debate, vote_debate, close_debate
  - Experimentos     : create_experiment, close_experiment
  - HIP              : save_human_question, answer_human_question,
                       skip_human_question, get_pending_human_questions,
                       save_human_preference, get_human_preferences
  - DNA              : get_dna_rules, update_dna_rule
  - Memória Episódica: save_episode, get_episodes
  - Memória Semântica: save_knowledge, get_knowledge
  - Memória Padrões  : save_pattern, get_patterns, deprecate_pattern
  - Scores por Área  : save_area_score, get_area_scores, get_area_evolution
  - Checkpoints [v6] : save_checkpoint, get_last_checkpoint, mark_checkpoint_resumed
  - Mudanças Código  : register_code_change, mark_change_tested, rollback_change,
    [v6]               get_pending_changes, get_change_history
  - Log de Ações[v6] : log_action, get_action_log, get_token_usage
  - Contexto         : get_context
  - Stats            : get_stats
  - Exportação       : export_all
============================================================
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR    = Path(__file__).parent
DB_PATH     = BASE_DIR / "db" / "learning.db"
LOGS_DIR    = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"


class SwarmDB:
    """Motor de banco de dados SWARM GENESIS v7."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path) if not isinstance(db_path, Path) else db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    def _ensure_db(self):
        """Carrega o schema SQL e aplica ao banco se o arquivo existir."""
        schema_path = BASE_DIR / "db" / "schema.sql"
        if not schema_path.exists():
            return
        with self._conn() as conn:
            conn.executescript(schema_path.read_text(encoding="utf-8"))

    @contextmanager
    def _conn(self):
        """Gerenciador de contexto de conexão com WAL e foreign keys ativados."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ================================================================
    # CICLOS
    # ================================================================
    def start_cycle(self) -> int:
        """Inicia um novo ciclo de aprendizado e retorna o ID."""
        with self._conn() as conn:
            cur = conn.execute("INSERT INTO cycles (status) VALUES ('running')")
            return cur.lastrowid

    def end_cycle(self, cycle_id: int, summary: str = "",
                  score_global: float = None):
        """Finaliza um ciclo com resumo e pontuação global."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE cycles SET ended_at=CURRENT_TIMESTAMP, status='completed',
                summary=?, score_global=? WHERE id=?
            """, (summary, score_global, cycle_id))

    def get_current_cycle(self) -> Optional[dict]:
        """Retorna o ciclo em execução ou None se nenhum estiver ativo."""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM cycles WHERE status='running'
                ORDER BY started_at DESC LIMIT 1
            """).fetchone()
            return dict(row) if row else None

    def get_cycle_history(self, limit: int = 20) -> list:
        """Retorna histórico dos ciclos completados mais recentes."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM cycles WHERE status='completed'
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # FEEDBACKS
    # ================================================================
    def register_feedback(self, source: str, topic: str, question: str,
                          answer: str, feedback_text: str = "",
                          sentiment: str = "neutro", confidence: float = 0.5,
                          cycle_id: int = None, parent_id: int = None,
                          tags: list = None) -> int:
        """Registra um feedback e incrementa o contador do ciclo ativo."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO feedbacks
                    (source,topic,question,answer,feedback_text,sentiment,
                     confidence,cycle_id,parent_id,tags)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (source, topic, question, answer, feedback_text, sentiment,
                  confidence, cycle_id, parent_id, json.dumps(tags or [])))
            fid = cur.lastrowid
            if cycle_id:
                conn.execute("""
                    UPDATE cycles SET total_feedbacks=total_feedbacks+1
                    WHERE id=? AND status='running'
                """, (cycle_id,))
            return fid

    def get_feedbacks_by_topic(self, topic: str, limit: int = 50) -> list:
        """Retorna feedbacks filtrando por tópico (busca parcial)."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM feedbacks WHERE topic LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (f"%{topic}%", limit)).fetchall()
            return [dict(r) for r in rows]

    def get_recent_feedbacks(self, limit: int = 10) -> list:
        """Retorna os feedbacks mais recentes."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM feedbacks ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # SUCESSOS
    # ================================================================
    def register_success(self, feedback_id: int, topic: str, insight: str,
                         evidence: str = "", relevance_score: float = 0.5,
                         tags: list = None, cycle_id: int = None) -> int:
        """
        Registra um sucesso com deduplicação.
        Se o insight já existe para o tópico, incrementa times_confirmed.
        """
        with self._conn() as conn:
            existing = conn.execute("""
                SELECT id, times_confirmed FROM sucessos WHERE topic=? AND insight=?
            """, (topic, insight)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE sucessos SET times_confirmed=times_confirmed+1,
                    relevance_score=MIN(1.0, relevance_score+0.1) WHERE id=?
                """, (existing["id"],))
                sid = existing["id"]
            else:
                cur = conn.execute("""
                    INSERT INTO sucessos (feedback_id,topic,insight,evidence,relevance_score,tags)
                    VALUES (?,?,?,?,?,?)
                """, (feedback_id, topic, insight, evidence, relevance_score,
                      json.dumps(tags or [])))
                sid = cur.lastrowid
            if cycle_id:
                conn.execute("""
                    UPDATE cycles SET insights_generated=insights_generated+1
                    WHERE id=? AND status='running'
                """, (cycle_id,))
            return sid

    def get_top_successes(self, limit: int = 20) -> list:
        """Retorna os sucessos mais relevantes ordenados por score e confirmações."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM sucessos
                ORDER BY relevance_score DESC, times_confirmed DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # FALHAS
    # ================================================================
    def register_failure(self, feedback_id: int, topic: str, what_failed: str,
                         why_failed: str = "", tags: list = None,
                         cycle_id: int = None) -> int:
        """
        Registra uma falha com deduplicação.
        Se a falha já existe para o tópico, incrementa times_failed.
        """
        with self._conn() as conn:
            existing = conn.execute("""
                SELECT id FROM falhas WHERE topic=? AND what_failed=?
            """, (topic, what_failed)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE falhas SET times_failed=times_failed+1 WHERE id=?
                """, (existing["id"],))
                return existing["id"]
            cur = conn.execute("""
                INSERT INTO falhas (feedback_id,topic,what_failed,why_failed,tags)
                VALUES (?,?,?,?,?)
            """, (feedback_id, topic, what_failed, why_failed,
                  json.dumps(tags or [])))
            return cur.lastrowid

    def mark_failure_resolved(self, failure_id: int, fix: str):
        """Marca uma falha como resolvida, registrando a correção aplicada."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE falhas SET still_unresolved=FALSE, attempted_fix=?, fix_worked=TRUE
                WHERE id=?
            """, (fix, failure_id))

    def get_unresolved_failures(self, limit: int = 20) -> list:
        """Retorna falhas ainda não resolvidas, ordenadas por recorrência."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM falhas WHERE still_unresolved=TRUE
                ORDER BY times_failed DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # PERGUNTAS GERADAS
    # ================================================================
    def save_question(self, question: str, context: str = "",
                      category: str = "exploratoria", cycle_id: int = None,
                      priority: int = 0) -> int:
        """
        Salva uma pergunta gerada com deduplicação.
        Se a pergunta já existe sem resposta, retorna o ID existente.
        """
        with self._conn() as conn:
            existing = conn.execute("""
                SELECT id FROM generated_questions WHERE question=? AND answered=FALSE
            """, (question,)).fetchone()
            if existing:
                return existing["id"]
            cur = conn.execute("""
                INSERT INTO generated_questions (cycle_id,question,context,category,priority)
                VALUES (?,?,?,?,?)
            """, (cycle_id, question, context, category, priority))
            qid = cur.lastrowid
            if cycle_id:
                conn.execute("""
                    UPDATE cycles SET total_questions=total_questions+1
                    WHERE id=? AND status='running'
                """, (cycle_id,))
            return qid

    def answer_question(self, question_id: int, answer: str,
                        was_relevant: bool = None,
                        relevance_reason: str = ""):
        """Registra a resposta de uma pergunta e incrementa o contador do ciclo."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE generated_questions
                SET answered=TRUE, answer=?, was_relevant=?, relevance_reason=?
                WHERE id=?
            """, (answer, was_relevant, relevance_reason, question_id))
            row = conn.execute("""
                SELECT cycle_id FROM generated_questions WHERE id=?
            """, (question_id,)).fetchone()
            if row and row["cycle_id"]:
                conn.execute("""
                    UPDATE cycles SET total_answers=total_answers+1
                    WHERE id=? AND status='running'
                """, (row["cycle_id"],))

    def get_unanswered_questions(self, limit: int = 10) -> list:
        """Retorna perguntas ainda sem resposta, priorizadas por priority e data."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM generated_questions WHERE answered=FALSE
                ORDER BY priority DESC, created_at ASC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # REGRAS APRENDIDAS
    # ================================================================
    def create_rule(self, rule_text: str, source: str, confidence: float = 0.5,
                    tags: list = None) -> int:
        """Cria uma nova regra aprendida e retorna o ID."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO learned_rules (rule_text,source,confidence,tags)
                VALUES (?,?,?,?)
            """, (rule_text, source, confidence, json.dumps(tags or [])))
            return cur.lastrowid

    def update_rule_stats(self, rule_id: int, succeeded: bool):
        """
        Atualiza estatísticas de aplicação de uma regra.
        Auto-depreca a regra se times_failed >= 3 e confidence < 0.3.
        """
        with self._conn() as conn:
            if succeeded:
                conn.execute("""
                    UPDATE learned_rules SET times_applied=times_applied+1,
                    times_succeeded=times_succeeded+1,
                    confidence=MIN(1.0, confidence+0.05) WHERE id=?
                """, (rule_id,))
            else:
                conn.execute("""
                    UPDATE learned_rules SET times_applied=times_applied+1,
                    times_failed=times_failed+1,
                    confidence=MAX(0.0, confidence-0.1) WHERE id=?
                """, (rule_id,))
                conn.execute("""
                    UPDATE learned_rules SET active=FALSE,
                    deprecated_reason='Falhou 3+ vezes — auto-deprecada'
                    WHERE id=? AND times_failed>=3 AND confidence<0.3
                """, (rule_id,))

    def deprecate_rule(self, rule_id: int, reason: str = "Deprecada manualmente"):
        """Depreca manualmente uma regra com motivo informado."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE learned_rules SET active=FALSE, deprecated_reason=? WHERE id=?
            """, (reason, rule_id))

    def get_active_rules(self) -> list:
        """Retorna todas as regras ativas ordenadas por confiança."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM learned_rules WHERE active=TRUE ORDER BY confidence DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_deprecated_rules(self, limit: int = 20) -> list:
        """Retorna regras deprecadas mais recentes."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM learned_rules WHERE active=FALSE
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # CONSENSOS
    # ================================================================
    def register_consensus(self, topic: str, agents: list, positions: dict,
                           verdict: str, agreement: float,
                           reasoning: str) -> int:
        """Registra um consenso alcançado entre agentes."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO consensus
                    (topic,agents_involved,positions,final_verdict,agreement_level,reasoning)
                VALUES (?,?,?,?,?,?)
            """, (topic, json.dumps(agents), json.dumps(positions),
                  verdict, agreement, reasoning))
            return cur.lastrowid

    def get_recent_consensus(self, limit: int = 10) -> list:
        """Retorna os consensos mais recentes."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM consensus ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # AGENTES
    # ================================================================
    def register_agent(self, name: str, role: str,
                       group_name: str = "development",
                       authority_level: int = 1, prompt_file: str = None,
                       parent_agent_id: int = None,
                       created_by_cycle: int = None,
                       fitness_score: float = 50.0) -> int:
        """
        Registra um agente. Se já existir, retorna o ID existente sem duplicar.
        fitness_score define o score inicial de aptidão.
        """
        with self._conn() as conn:
            existing = conn.execute("SELECT id FROM agents WHERE name=?",
                                    (name,)).fetchone()
            if existing:
                return existing["id"]
            cur = conn.execute("""
                INSERT INTO agents
                    (name,role,group_name,authority_level,fitness_score,
                     prompt_file,parent_agent_id,created_by_cycle)
                VALUES (?,?,?,?,?,?,?,?)
            """, (name, role, group_name, authority_level, fitness_score,
                  prompt_file, parent_agent_id, created_by_cycle))
            return cur.lastrowid

    def update_agent_fitness(self, agent_name: str, delta: float,
                             outcome: str, action: str,
                             cycle_id: int = None, notes: str = ""):
        """
        Atualiza o fitness de um agente e promove/rebaixa o status automaticamente:
          >= 85 → ELITE | >= 70 → SENIOR | < 30 → WEAK | demais → ACTIVE
        """
        with self._conn() as conn:
            row = conn.execute("SELECT id, fitness_score FROM agents WHERE name=?",
                               (agent_name,)).fetchone()
            if not row:
                return
            agent_id = row["id"]
            new_score = max(0.0, min(100.0, row["fitness_score"] + delta))
            if new_score >= 85:
                status = "ELITE"
            elif new_score >= 70:
                status = "SENIOR"
            elif new_score < 30:
                status = "WEAK"
            else:
                status = "ACTIVE"
            conn.execute("""
                UPDATE agents SET fitness_score=?, status=?,
                cycles_active=cycles_active+1 WHERE id=?
            """, (new_score, status, agent_id))
            conn.execute("""
                INSERT INTO agent_performance
                    (agent_id,cycle_id,action,outcome,score_delta,notes)
                VALUES (?,?,?,?,?,?)
            """, (agent_id, cycle_id, action, outcome, delta, notes))

    def retire_agent(self, agent_name: str,
                     reason: str = "Aposentado por baixo fitness"):
        """Aposenta um agente, registrando motivo e timestamp."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE agents SET status='RETIRED',
                retired_at=CURRENT_TIMESTAMP, retired_reason=?
                WHERE name=?
            """, (reason, agent_name))

    def get_agent_fitness(self, agent_name: str) -> Optional[dict]:
        """Retorna dados completos de um agente pelo nome."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM agents WHERE name=?",
                               (agent_name,)).fetchone()
            return dict(row) if row else None

    def get_all_agents(self) -> list:
        """Retorna todos os agentes não aposentados, ordenados por fitness."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM agents WHERE status != 'RETIRED'
                ORDER BY fitness_score DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_retired_agents(self) -> list:
        """Retorna todos os agentes aposentados."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM agents WHERE status='RETIRED'
                ORDER BY retired_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def rewrite_agent_prompt(self, agent_name: str, reason: str,
                             new_version: str):
        """Registra uma reescrita de prompt para o agente indicado."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE agents SET prompt_version=?,
                last_rewrite=CURRENT_TIMESTAMP, rewrite_reason=?
                WHERE name=?
            """, (new_version, reason, agent_name))

    # ================================================================
    # DEBATES / PARLAMENTO
    # ================================================================
    def open_debate(self, topic: str, proposal: str, proposed_by: str,
                    requires_dna_change: bool = False,
                    cycle_id: int = None) -> int:
        """Abre um novo debate parlamentar."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO debates
                    (topic,proposal,proposed_by,requires_dna_change,cycle_id)
                VALUES (?,?,?,?,?)
            """, (topic, proposal, proposed_by, requires_dna_change, cycle_id))
            return cur.lastrowid

    def vote_debate(self, debate_id: int, agent_name: str, vote: str,
                    argument: str = "", weight: float = 1.0):
        """
        Registra um voto ponderado em um debate.
        vote aceita: 'for', 'against', 'veto'.
        """
        valid_votes = ("for", "against", "veto")
        if vote not in valid_votes:
            raise ValueError(f"Invalid vote '{vote}'. Must be one of: {valid_votes}")
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO debate_votes (debate_id,agent_name,vote,argument,weight)
                VALUES (?,?,?,?,?)
            """, (debate_id, agent_name, vote, argument, weight))
            if vote == "for":
                conn.execute("UPDATE debates SET votes_for=votes_for+1 WHERE id=?",
                             (debate_id,))
            elif vote in ("against", "veto"):
                conn.execute("UPDATE debates SET votes_against=votes_against+1 WHERE id=?",
                             (debate_id,))

    def close_debate(self, debate_id: int, verdict: str):
        """Fecha um debate com o veredicto final."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE debates SET status='DECIDED', verdict=?,
                decided_at=CURRENT_TIMESTAMP WHERE id=?
            """, (verdict, debate_id))

    # ================================================================
    # EXPERIMENTOS
    # ================================================================
    def create_experiment(self, title: str, hypothesis: str,
                          proposed_by: str = "", branch_name: str = "",
                          started_cycle: int = None) -> int:
        """Cria um novo experimento controlado."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO experiments
                    (title,hypothesis,proposed_by,branch_name,started_cycle)
                VALUES (?,?,?,?,?)
            """, (title, hypothesis, proposed_by, branch_name, started_cycle))
            return cur.lastrowid

    def close_experiment(self, experiment_id: int, status: str,
                         metrics_after: dict, conclusion: str,
                         became_rule_id: int = None, ended_cycle: int = None):
        """Encerra um experimento registrando métricas e conclusão."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE experiments SET status=?, metrics_after=?, conclusion=?,
                became_rule_id=?, ended_cycle=? WHERE id=?
            """, (status, json.dumps(metrics_after), conclusion,
                  became_rule_id, ended_cycle, experiment_id))

    # ================================================================
    # PERGUNTAS PARA O HUMANO — Módulo HIP
    # ================================================================
    def save_human_question(self, question: str, level: str = "IMPORTANTE",
                            theme: str = "", context: str = "",
                            impact: str = "", options: list = None,
                            agent_name: str = "",
                            cycle_id: int = None) -> int:
        """
        Salva uma pergunta destinada ao humano com deduplicação.
        level aceita: 'BLOQUEANTE', 'IMPORTANTE', 'CURIOSIDADE'.
        """
        with self._conn() as conn:
            existing = conn.execute("""
                SELECT id FROM human_questions WHERE question=? AND status='PENDING'
            """, (question,)).fetchone()
            if existing:
                return existing["id"]
            cur = conn.execute("""
                INSERT INTO human_questions
                    (cycle_id,agent_name,level,theme,question,context,
                     impact_if_unanswered,suggested_options)
                VALUES (?,?,?,?,?,?,?,?)
            """, (cycle_id, agent_name, level, theme, question, context,
                  impact, json.dumps(options or [])))
            return cur.lastrowid

    def answer_human_question(self, question_id: int, answer: str):
        """Registra a resposta do humano para uma pergunta pendente."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE human_questions
                SET status='ANSWERED', answer=?, answered_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (answer, question_id))

    def skip_human_question(self, question_id: int):
        """Marca uma pergunta humana como ignorada."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE human_questions SET status='SKIPPED' WHERE id=?
            """, (question_id,))

    def get_pending_human_questions(self) -> dict:
        """
        Retorna perguntas pendentes agrupadas por nível de urgência.
        Ordem: BLOQUEANTE → IMPORTANTE → CURIOSIDADE.
        """
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM human_questions WHERE status='PENDING'
                ORDER BY
                    CASE level
                        WHEN 'BLOQUEANTE'  THEN 1
                        WHEN 'IMPORTANTE'  THEN 2
                        WHEN 'CURIOSIDADE' THEN 3
                    END, created_at ASC
            """).fetchall()
            result = {"BLOQUEANTE": [], "IMPORTANTE": [], "CURIOSIDADE": []}
            for r in rows:
                level = r["level"]
                if level in result:
                    result[level].append(dict(r))
            return result

    def save_human_preference(self, category: str, key: str, value: str,
                              confidence: float = 0.5,
                              source: str = "inferred"):
        """Salva ou atualiza (upsert) uma preferência aprendida do humano."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO human_preferences (category,key,value,confidence,source)
                VALUES (?,?,?,?,?)
                ON CONFLICT(category,key) DO UPDATE SET
                    value=excluded.value, confidence=excluded.confidence,
                    source=excluded.source, updated_at=CURRENT_TIMESTAMP
            """, (category, key, value, confidence, source))

    def get_human_preferences(self) -> dict:
        """Retorna todas as preferências humanas agrupadas por categoria."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM human_preferences ORDER BY category"
            ).fetchall()
            result = {}
            for r in rows:
                result.setdefault(r["category"], {})[r["key"]] = {
                    "value": r["value"], "confidence": r["confidence"]
                }
            return result

    # ================================================================
    # DNA DO SISTEMA
    # ================================================================
    def get_dna_rules(self) -> list:
        """Retorna todas as regras do DNA, imutáveis primeiro."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dna_rules ORDER BY immutable DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_dna_rule(self, rule_key: str, new_text: str,
                        changed_by: str, reason: str):
        """
        Atualiza uma regra DNA mutável.
        Lança ValueError se a regra não existir.
        Lança PermissionError se a regra for imutável (Constituição).
        """
        with self._conn() as conn:
            old = conn.execute(
                "SELECT rule_text, immutable FROM dna_rules WHERE rule_key=?",
                (rule_key,)
            ).fetchone()
            if not old:
                raise ValueError(f"Regra DNA '{rule_key}' não encontrada")
            if old["immutable"]:
                raise PermissionError(
                    f"Regra '{rule_key}' é imutável — Constituição do sistema")
            conn.execute("""
                UPDATE dna_rules SET rule_text=?, version=version+1,
                changed_by=?, change_reason=?, previous_value=?
                WHERE rule_key=?
            """, (new_text, changed_by, reason, old["rule_text"], rule_key))

    # ================================================================
    # MEMÓRIA EPISÓDICA
    # ================================================================
    def save_episode(self, agent_name: str, action: str, target: str = "",
                     result: str = "unknown", impact: str = "",
                     details: str = "", cycle_id: int = None) -> int:
        """Salva um episódio na memória de curto/longo prazo do agente."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO memory_episodic
                    (cycle_id,agent_name,action,target,result,impact,details)
                VALUES (?,?,?,?,?,?,?)
            """, (cycle_id, agent_name, action, target, result, impact, details))
            return cur.lastrowid

    def get_episodes(self, limit: int = 50, cycle_id: int = None,
                     agent_name: str = None) -> list:
        """Retorna episódios da memória com filtros opcionais por ciclo e agente."""
        with self._conn() as conn:
            query = "SELECT * FROM memory_episodic WHERE 1=1"
            params = []
            if cycle_id is not None:
                query += " AND cycle_id=?"
                params.append(cycle_id)
            if agent_name is not None:
                query += " AND agent_name=?"
                params.append(agent_name)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # MEMÓRIA SEMÂNTICA
    # ================================================================
    def save_knowledge(self, category: str, key: str, value: str,
                       confidence: float = 0.5, discovered_at: str = None,
                       last_verified: str = None):
        """Salva ou atualiza (upsert) um conhecimento na memória semântica."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO memory_semantic
                    (category,key,value,confidence,discovered_at,last_verified)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(category,key) DO UPDATE SET
                    value=excluded.value, confidence=excluded.confidence,
                    last_verified=excluded.last_verified,
                    updated_at=CURRENT_TIMESTAMP
            """, (category, key, value, confidence, discovered_at, last_verified))

    def get_knowledge(self, category: str = None) -> list:
        """Retorna conhecimentos semânticos, filtráveis por categoria."""
        with self._conn() as conn:
            if category:
                rows = conn.execute("""
                    SELECT * FROM memory_semantic WHERE category=?
                    ORDER BY confidence DESC
                """, (category,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM memory_semantic ORDER BY category, confidence DESC
                """).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # MEMÓRIA DE PADRÕES
    # ================================================================
    def save_pattern(self, pattern_type: str, description: str,
                     standard_fix: str = "", affected_files: str = "",
                     discovered_cycle: int = None) -> int:
        """
        Salva um padrão recorrente com deduplicação.
        Se o padrão já existe, incrementa occurrences e aumenta confiança.
        """
        with self._conn() as conn:
            existing = conn.execute("""
                SELECT id, occurrences FROM memory_patterns
                WHERE description=? AND active=TRUE
            """, (description,)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE memory_patterns SET occurrences=occurrences+1,
                    confidence=MIN(1.0, confidence+0.1),
                    last_seen_cycle=? WHERE id=?
                """, (discovered_cycle, existing["id"]))
                return existing["id"]
            cur = conn.execute("""
                INSERT INTO memory_patterns
                    (pattern_type,description,standard_fix,affected_files,
                     discovered_cycle,last_seen_cycle)
                VALUES (?,?,?,?,?,?)
            """, (pattern_type, description, standard_fix, affected_files,
                  discovered_cycle, discovered_cycle))
            return cur.lastrowid

    def get_patterns(self, pattern_type: str = None,
                     active_only: bool = True) -> list:
        """Retorna padrões filtráveis por tipo e status ativo."""
        with self._conn() as conn:
            query = "SELECT * FROM memory_patterns WHERE 1=1"
            params = []
            if active_only:
                query += " AND active=TRUE"
            if pattern_type:
                query += " AND pattern_type=?"
                params.append(pattern_type)
            query += " ORDER BY occurrences DESC, confidence DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def deprecate_pattern(self, pattern_id: int,
                          reason: str = "Padrão não se aplica mais"):
        """Depreca um padrão marcando-o como inativo."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE memory_patterns SET active=FALSE WHERE id=?
            """, (pattern_id,))

    # ================================================================
    # SCORES POR ÁREA
    # ================================================================
    def save_area_score(self, cycle_id: int, area_name: str, score: float,
                        notes: str = ""):
        """Salva ou atualiza (upsert) o score de uma área para um ciclo."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO area_scores (cycle_id,area_name,score,notes)
                VALUES (?,?,?,?)
                ON CONFLICT(cycle_id,area_name) DO UPDATE SET
                    score=excluded.score, notes=excluded.notes
            """, (cycle_id, area_name, score, notes))

    def get_area_scores(self, cycle_id: int = None) -> list:
        """
        Retorna scores por área.
        Se cycle_id informado, retorna scores daquele ciclo.
        Sem cycle_id, retorna agregação histórica por área.
        """
        with self._conn() as conn:
            if cycle_id is not None:
                rows = conn.execute("""
                    SELECT * FROM area_scores WHERE cycle_id=?
                    ORDER BY score DESC
                """, (cycle_id,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT area_name,
                           GROUP_CONCAT(score) as scores_history,
                           MAX(cycle_id) as last_cycle,
                           AVG(score) as avg_score
                    FROM area_scores
                    GROUP BY area_name
                    ORDER BY avg_score DESC
                """).fetchall()
            return [dict(r) for r in rows]

    def get_area_evolution(self, area_name: str) -> list:
        """Retorna a evolução histórica do score de uma área por ciclo."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT cycle_id, score, notes FROM area_scores
                WHERE area_name=? ORDER BY cycle_id ASC
            """, (area_name,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # CHECKPOINTS DE SESSÃO [NOVO v6]
    # ================================================================
    def save_checkpoint(self, cycle_id: int, phase: str,
                        current_agent: str = "",
                        progress: dict = None) -> int:
        """
        Salva o estado atual da sessão para capacidade de retomada.
        progress é um dicionário serializado como JSON.
        Retorna o ID do checkpoint criado.
        """
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO session_checkpoints
                    (cycle_id, phase, current_agent, progress_json)
                VALUES (?, ?, ?, ?)
            """, (cycle_id, phase, current_agent,
                  json.dumps(progress or {})))
            return cur.lastrowid

    def get_last_checkpoint(self) -> Optional[dict]:
        """Retorna o checkpoint mais recente ainda não retomado."""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM session_checkpoints
                WHERE resumed=FALSE
                ORDER BY created_at DESC LIMIT 1
            """).fetchone()
            return dict(row) if row else None

    def mark_checkpoint_resumed(self, checkpoint_id: int):
        """Marca um checkpoint como retomado, registrando o timestamp."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE session_checkpoints
                SET resumed=TRUE, resumed_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (checkpoint_id,))

    # ================================================================
    # MUDANÇAS DE CÓDIGO COM BACKUP/ROLLBACK [NOVO v6]
    # ================================================================
    def register_code_change(self, cycle_id: int, agent_name: str,
                             file_path: str, change_type: str,
                             backup_path: str = "",
                             description: str = "") -> int:
        """
        Registra uma mudança de código realizada no projeto.
        change_type exemplos: 'create', 'modify', 'delete', 'refactor'.
        Retorna o ID da mudança criada.
        """
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO code_changes
                    (cycle_id, agent_name, file_path, change_type,
                     backup_path, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cycle_id, agent_name, file_path, change_type,
                  backup_path, description))
            return cur.lastrowid

    def mark_change_tested(self, change_id: int, test_passed: bool):
        """Registra se os testes passaram após uma mudança de código."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE code_changes SET test_passed=? WHERE id=?
            """, (test_passed, change_id))

    def rollback_change(self, change_id: int,
                        reason: str = "Testes falharam"):
        """
        Marca uma mudança como revertida (rolled back).
        Registra motivo e timestamp do rollback.
        """
        with self._conn() as conn:
            conn.execute("""
                UPDATE code_changes
                SET rolled_back=TRUE,
                    rolled_back_at=CURRENT_TIMESTAMP,
                    rollback_reason=?
                WHERE id=?
            """, (reason, change_id))

    def get_pending_changes(self, cycle_id: int = None) -> list:
        """
        Retorna mudanças que ainda não foram testadas e não foram revertidas.
        Filtrável por cycle_id.
        """
        with self._conn() as conn:
            query = """
                SELECT * FROM code_changes
                WHERE test_passed IS NULL AND rolled_back=FALSE
            """
            params = []
            if cycle_id is not None:
                query += " AND cycle_id=?"
                params.append(cycle_id)
            query += " ORDER BY created_at ASC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_change_history(self, limit: int = 50) -> list:
        """Retorna o histórico recente de mudanças de código."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM code_changes
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # LOG DE AÇÕES [NOVO v6]
    # ================================================================
    def log_action(self, cycle_id: int, agent_name: str, action_type: str,
                   target: str = "", result: str = "success",
                   details: str = "", duration_ms: int = 0,
                   tokens_used: int = 0) -> int:
        """
        Registra qualquer ação executada pelo sistema.
        tokens_used permite rastrear consumo de tokens por ação.
        Retorna o ID do registro criado.
        """
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO action_log
                    (cycle_id, agent_name, action_type, target,
                     result, details, duration_ms, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cycle_id, agent_name, action_type, target,
                  result, details, duration_ms, tokens_used))
            return cur.lastrowid

    def get_action_log(self, cycle_id: int = None, agent_name: str = None,
                       action_type: str = None, limit: int = 100) -> list:
        """Retorna o log de ações com filtros opcionais por ciclo, agente e tipo."""
        with self._conn() as conn:
            query = "SELECT * FROM action_log WHERE 1=1"
            params = []
            if cycle_id is not None:
                query += " AND cycle_id=?"
                params.append(cycle_id)
            if agent_name:
                query += " AND agent_name=?"
                params.append(agent_name)
            if action_type:
                query += " AND action_type=?"
                params.append(action_type)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_token_usage(self, cycle_id: int = None) -> dict:
        """
        Retorna resumo de uso de tokens.
        Inclui total geral, totais por agente e totais por ciclo.
        Se cycle_id informado, filtra apenas aquele ciclo.
        """
        with self._conn() as conn:
            base_filter = "WHERE 1=1"
            params_base: list = []
            if cycle_id is not None:
                base_filter = "WHERE cycle_id=?"
                params_base = [cycle_id]

            total_row = conn.execute(
                f"SELECT COALESCE(SUM(tokens_used),0) FROM action_log {base_filter}",
                params_base
            ).fetchone()
            total_tokens = total_row[0] if total_row else 0

            by_agent_rows = conn.execute(f"""
                SELECT agent_name, SUM(tokens_used) as tokens
                FROM action_log {base_filter}
                GROUP BY agent_name ORDER BY tokens DESC
            """, params_base).fetchall()

            by_cycle_rows = conn.execute("""
                SELECT cycle_id, SUM(tokens_used) as tokens
                FROM action_log
                GROUP BY cycle_id ORDER BY cycle_id DESC
                LIMIT 20
            """).fetchall()

            return {
                "total_tokens": total_tokens,
                "by_agent": {r["agent_name"]: r["tokens"] for r in by_agent_rows},
                "by_cycle": {r["cycle_id"]: r["tokens"] for r in by_cycle_rows},
            }

    # ================================================================
    # CONTEXTO COMPLETO (atualizado v6)
    # ================================================================
    def get_context(self) -> dict:
        """
        Retorna um dicionário completo com o estado atual do sistema.
        Inclui dados novos do v6: último checkpoint, mudanças pendentes,
        log de ações recente e uso de tokens.
        """
        return {
            "stats":                self.get_stats(),
            "current_cycle":        self.get_current_cycle(),
            "top_successes":        self.get_top_successes(10),
            "unresolved_failures":  self.get_unresolved_failures(10),
            "unanswered_questions": self.get_unanswered_questions(10),
            "active_rules":         self.get_active_rules(),
            "recent_feedbacks":     self.get_recent_feedbacks(10),
            "recent_consensus":     self.get_recent_consensus(5),
            "all_agents":           self.get_all_agents(),
            "human_questions":      self.get_pending_human_questions(),
            "human_preferences":    self.get_human_preferences(),
            "dna_rules":            self.get_dna_rules(),
            "patterns":             self.get_patterns(),
            "knowledge_summary":    self.get_knowledge(),
            "area_scores":          self.get_area_scores(),
            # --- v6 ---
            "last_checkpoint":      self.get_last_checkpoint(),
            "pending_code_changes": self.get_pending_changes(),
            "recent_action_log":    self.get_action_log(limit=20),
            "token_usage":          self.get_token_usage(),
        }

    # ================================================================
    # ESTATÍSTICAS (atualizado v6)
    # ================================================================
    def get_stats(self) -> dict:
        """
        Retorna contagens de todos os objetos no banco.
        v6 adiciona: mudanças de código, rollbacks, ações, tokens e checkpoints.
        """
        with self._conn() as conn:
            def c(q: str) -> int:
                return conn.execute(q).fetchone()[0]

            total_tokens_row = conn.execute(
                "SELECT COALESCE(SUM(tokens_used),0) FROM action_log"
            ).fetchone()

            return {
                # --- v5 ---
                "total_feedbacks":              c("SELECT COUNT(*) FROM feedbacks"),
                "total_sucessos":               c("SELECT COUNT(*) FROM sucessos"),
                "total_falhas":                 c("SELECT COUNT(*) FROM falhas"),
                "falhas_nao_resolvidas":        c("SELECT COUNT(*) FROM falhas WHERE still_unresolved=TRUE"),
                "total_perguntas":              c("SELECT COUNT(*) FROM generated_questions"),
                "perguntas_respondidas":        c("SELECT COUNT(*) FROM generated_questions WHERE answered=TRUE"),
                "total_consensos":              c("SELECT COUNT(*) FROM consensus"),
                "regras_ativas":                c("SELECT COUNT(*) FROM learned_rules WHERE active=TRUE"),
                "regras_deprecadas":            c("SELECT COUNT(*) FROM learned_rules WHERE active=FALSE"),
                "total_ciclos":                 c("SELECT COUNT(*) FROM cycles"),
                "ciclos_completos":             c("SELECT COUNT(*) FROM cycles WHERE status='completed'"),
                "total_agentes":                c("SELECT COUNT(*) FROM agents WHERE status!='RETIRED'"),
                "agentes_elite":                c("SELECT COUNT(*) FROM agents WHERE status='ELITE'"),
                "agentes_aposentados":          c("SELECT COUNT(*) FROM agents WHERE status='RETIRED'"),
                "debates_abertos":              c("SELECT COUNT(*) FROM debates WHERE status='OPEN'"),
                "experimentos_rodando":         c("SELECT COUNT(*) FROM experiments WHERE status='RUNNING'"),
                "perguntas_humano_pendentes":   c("SELECT COUNT(*) FROM human_questions WHERE status='PENDING'"),
                "total_episodios":              c("SELECT COUNT(*) FROM memory_episodic"),
                "total_conhecimentos":          c("SELECT COUNT(*) FROM memory_semantic"),
                "total_padroes":                c("SELECT COUNT(*) FROM memory_patterns WHERE active=TRUE"),
                # --- v6 ---
                "total_code_changes":           c("SELECT COUNT(*) FROM code_changes"),
                "code_changes_rolled_back":     c("SELECT COUNT(*) FROM code_changes WHERE rolled_back=TRUE"),
                "total_actions_logged":         c("SELECT COUNT(*) FROM action_log"),
                "total_tokens_used":            total_tokens_row[0] if total_tokens_row else 0,
                "active_checkpoints":           c("SELECT COUNT(*) FROM session_checkpoints WHERE resumed=FALSE"),
            }

    # ================================================================
    # EXPORTAÇÃO (atualizado v6)
    # ================================================================
    def export_all(self, output_dir: Path = EXPORTS_DIR) -> str:
        """
        Exporta todas as tabelas para um arquivo JSON com timestamp.
        v6 inclui as tabelas novas: session_checkpoints, code_changes, action_log.
        Retorna o caminho absoluto do arquivo gerado.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            _VALID_TABLES = {
                "cycles", "feedbacks", "sucessos", "falhas", "learned_rules",
                "consensus", "agents", "agent_performance", "debates",
                "experiments", "human_questions", "dna_rules", "memory_episodic",
                "memory_semantic", "memory_patterns", "area_scores",
                "session_checkpoints", "code_changes", "action_log",
            }

            def all_rows(table: str) -> list:
                if table not in _VALID_TABLES:
                    raise ValueError(f"Invalid table: {table}")
                return [dict(r) for r in conn.execute(
                    f"SELECT * FROM {table}").fetchall()]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export = {
                "exported_at":          timestamp,
                "version":              "7.0",
                "stats":                self.get_stats(),
                # --- v5 ---
                "cycles":               all_rows("cycles"),
                "feedbacks":            all_rows("feedbacks"),
                "sucessos":             all_rows("sucessos"),
                "falhas":               all_rows("falhas"),
                "learned_rules":        all_rows("learned_rules"),
                "consensus":            all_rows("consensus"),
                "agents":               all_rows("agents"),
                "agent_performance":    all_rows("agent_performance"),
                "debates":              all_rows("debates"),
                "experiments":          all_rows("experiments"),
                "human_questions":      all_rows("human_questions"),
                "dna_rules":            all_rows("dna_rules"),
                "memory_episodic":      all_rows("memory_episodic"),
                "memory_semantic":      all_rows("memory_semantic"),
                "memory_patterns":      all_rows("memory_patterns"),
                "area_scores":          all_rows("area_scores"),
                # --- v6 ---
                "session_checkpoints":  all_rows("session_checkpoints"),
                "code_changes":         all_rows("code_changes"),
                "action_log":           all_rows("action_log"),
            }
        filepath = output_dir / f"export_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)
        return str(filepath)
