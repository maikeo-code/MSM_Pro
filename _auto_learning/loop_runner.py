"""
============================================================
SWARM GENESIS v7.0 — LOOP RUNNER
CLI com 56 comandos para todas as operações do sistema.
============================================================
Uso: python _auto_learning/loop_runner.py <comando> [json_data]
============================================================
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Encoding safety for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).parent))
from engine import SwarmDB

db = SwarmDB()

# ============================================================
# VALIDACAO
# ============================================================
REQUIRED = {
    # Ciclos
    "end-cycle":                ["cycle_id"],
    # Feedbacks
    "register-feedback":        ["source", "topic", "question", "answer"],
    "get-feedback":             ["feedback_id"],
    # Sucessos e falhas
    "register-success":         ["feedback_id", "topic", "insight"],
    "register-failure":         ["feedback_id", "topic", "what_failed"],
    "mark-resolved":            ["failure_id", "fix"],
    # Perguntas
    "save-question":            ["question"],
    "answer-question":          ["question_id", "answer"],
    # Regras
    "create-rule":              ["rule_text"],
    "update-rule":              ["rule_id", "succeeded"],
    "deprecate-rule":           ["rule_id"],
    # Consenso
    "register-consensus":       ["topic", "agents", "positions", "verdict", "agreement", "reasoning"],
    # Agentes
    "register-agent":           ["name", "role"],
    "update-fitness":           ["agent_name", "delta", "outcome", "action"],
    "retire-agent":             ["agent_name"],
    "rewrite-agent":            ["agent_name", "reason", "new_version"],
    # Debates
    "open-debate":              ["topic", "proposal", "proposed_by"],
    "vote-debate":              ["debate_id", "agent_name", "vote"],
    "close-debate":             ["debate_id", "verdict"],
    # Experimentos
    "create-experiment":        ["title", "hypothesis"],
    "close-experiment":         ["experiment_id", "status", "conclusion"],
    # HIP
    "save-human-question":      ["question", "level"],
    "answer-human-question":    ["question_id", "answer"],
    "skip-human-question":      ["question_id"],
    "save-preference":          ["category", "key", "value"],
    # DNA
    "update-dna":               ["rule_key", "new_text", "changed_by", "reason"],
    # Memoria episodica
    "save-episode":             ["agent_name", "action"],
    # Memoria semantica
    "save-knowledge":           ["category", "key", "value"],
    # Padroes
    "save-pattern":             ["pattern_type", "description"],
    # Scores por area
    "save-area-score":          ["cycle_id", "area_name", "score"],
    # v6 — Checkpoints
    "save-checkpoint":          ["cycle_id", "phase"],
    "resume-checkpoint":        ["checkpoint_id"],
    # v6 — Code Changes
    "register-change":          ["file_path", "change_type"],
    "mark-change-tested":       ["change_id", "test_passed"],
    "rollback-change":          ["change_id"],
    # v6 — Action Log
    "log-action":               ["action_type"],
}


def validate(command, data):
    required = REQUIRED.get(command, [])
    if not required:
        return None
    if data is None:
        return f"Comando '{command}' requer JSON. Campos: {', '.join(required)}"
    missing = [f for f in required if f not in data]
    if missing:
        return f"Campos ausentes: {', '.join(missing)}"
    return None


def out(obj):
    print(json.dumps(obj, ensure_ascii=False, default=str))


# ============================================================
# CICLOS
# ============================================================
def cmd_start_cycle(_):
    out({"cycle_id": db.start_cycle()})


def cmd_end_cycle(d):
    db.end_cycle(d["cycle_id"], d.get("summary", ""), d.get("score_global"))
    out({"ok": True, "cycle_id": d["cycle_id"]})


# ============================================================
# FEEDBACKS
# ============================================================
def cmd_register_feedback(d):
    fid = db.register_feedback(
        source=d["source"], topic=d["topic"],
        question=d["question"], answer=d["answer"],
        feedback_text=d.get("feedback_text", ""),
        sentiment=d.get("sentiment", "neutro"),
        confidence=d.get("confidence", 0.5),
        cycle_id=d.get("cycle_id"),
        parent_id=d.get("parent_id"), tags=d.get("tags", []))
    out({"feedback_id": fid})


def cmd_get_feedback(d):
    with db._conn() as conn:
        row = conn.execute(
            "SELECT * FROM feedbacks WHERE id=?", (d["feedback_id"],)
        ).fetchone()
    out(dict(row) if row else {"error": "Nao encontrado"})


def cmd_get_feedbacks(d):
    out(db.get_feedbacks_by_topic(d.get("topic", "") if d else "", d.get("limit", 20) if d else 20))


# ============================================================
# SUCESSOS E FALHAS
# ============================================================
def cmd_register_success(d):
    sid = db.register_success(
        feedback_id=d["feedback_id"], topic=d["topic"], insight=d["insight"],
        evidence=d.get("evidence", ""),
        relevance_score=d.get("relevance_score", 0.5),
        tags=d.get("tags", []), cycle_id=d.get("cycle_id"))
    out({"success_id": sid})


def cmd_register_failure(d):
    fid = db.register_failure(
        feedback_id=d["feedback_id"], topic=d["topic"],
        what_failed=d["what_failed"], why_failed=d.get("why_failed", ""),
        tags=d.get("tags", []), cycle_id=d.get("cycle_id"))
    out({"failure_id": fid})


def cmd_mark_resolved(d):
    db.mark_failure_resolved(d["failure_id"], d["fix"])
    out({"ok": True})


# ============================================================
# PERGUNTAS
# ============================================================
def cmd_save_question(d):
    qid = db.save_question(
        question=d["question"], context=d.get("context", ""),
        category=d.get("category", "exploratoria"),
        cycle_id=d.get("cycle_id"), priority=d.get("priority", 0))
    out({"question_id": qid})


def cmd_answer_question(d):
    db.answer_question(
        question_id=d["question_id"], answer=d["answer"],
        was_relevant=d.get("was_relevant"),
        relevance_reason=d.get("relevance_reason", ""))
    out({"ok": True})


# ============================================================
# REGRAS
# ============================================================
def cmd_create_rule(d):
    rid = db.create_rule(
        rule_text=d["rule_text"], source=d.get("source", "consenso"),
        confidence=d.get("confidence", 0.5), tags=d.get("tags", []))
    out({"rule_id": rid})


def cmd_update_rule(d):
    db.update_rule_stats(d["rule_id"], d["succeeded"])
    out({"ok": True})


def cmd_deprecate_rule(d):
    db.deprecate_rule(d["rule_id"], d.get("reason", "Deprecada manualmente"))
    out({"ok": True})


# ============================================================
# CONSENSO
# ============================================================
def cmd_register_consensus(d):
    cid = db.register_consensus(
        topic=d["topic"], agents=d["agents"], positions=d["positions"],
        verdict=d["verdict"], agreement=d["agreement"],
        reasoning=d["reasoning"])
    out({"consensus_id": cid})


# ============================================================
# AGENTES
# ============================================================
def cmd_register_agent(d):
    aid = db.register_agent(
        name=d["name"], role=d["role"],
        group_name=d.get("group_name", "development"),
        authority_level=d.get("authority_level", 1),
        prompt_file=d.get("prompt_file"),
        parent_agent_id=d.get("parent_agent_id"),
        created_by_cycle=d.get("created_by_cycle"),
        fitness_score=d.get("fitness_score", 50.0))
    out({"agent_id": aid})


def cmd_update_fitness(d):
    db.update_agent_fitness(
        agent_name=d["agent_name"], delta=d["delta"],
        outcome=d["outcome"], action=d["action"],
        cycle_id=d.get("cycle_id"), notes=d.get("notes", ""))
    out({"ok": True})


def cmd_get_agent(d):
    info = db.get_agent_fitness(d.get("agent_name", "") if d else "")
    out(info if info else {"error": "Agente nao encontrado"})


def cmd_retire_agent(d):
    db.retire_agent(d["agent_name"], d.get("reason", "Aposentado por baixo fitness"))
    out({"ok": True, "agent": d["agent_name"], "status": "RETIRED"})


def cmd_rewrite_agent(d):
    db.rewrite_agent_prompt(d["agent_name"], d["reason"], d["new_version"])
    out({"ok": True})


# ============================================================
# DEBATES
# ============================================================
def cmd_open_debate(d):
    did = db.open_debate(
        topic=d["topic"], proposal=d["proposal"],
        proposed_by=d["proposed_by"],
        requires_dna_change=d.get("requires_dna_change", False),
        cycle_id=d.get("cycle_id"))
    out({"debate_id": did})


def cmd_vote_debate(d):
    db.vote_debate(d["debate_id"], d["agent_name"], d["vote"],
                   d.get("argument", ""), d.get("weight", 1.0))
    out({"ok": True})


def cmd_close_debate(d):
    db.close_debate(d["debate_id"], d["verdict"])
    out({"ok": True})


# ============================================================
# EXPERIMENTOS
# ============================================================
def cmd_create_experiment(d):
    eid = db.create_experiment(
        title=d["title"], hypothesis=d["hypothesis"],
        proposed_by=d.get("proposed_by", ""),
        branch_name=d.get("branch_name", ""),
        started_cycle=d.get("started_cycle"))
    out({"experiment_id": eid})


def cmd_close_experiment(d):
    db.close_experiment(
        experiment_id=d["experiment_id"], status=d["status"],
        metrics_after=d.get("metrics_after", {}),
        conclusion=d["conclusion"],
        became_rule_id=d.get("became_rule_id"),
        ended_cycle=d.get("ended_cycle"))
    out({"ok": True})


# ============================================================
# MODULO HIP
# ============================================================
def cmd_save_human_question(d):
    qid = db.save_human_question(
        question=d["question"], level=d["level"],
        theme=d.get("theme", ""), context=d.get("context", ""),
        impact=d.get("impact", ""), options=d.get("options"),
        agent_name=d.get("agent_name", ""),
        cycle_id=d.get("cycle_id"))
    out({"question_id": qid})


def cmd_answer_human_question(d):
    db.answer_human_question(d["question_id"], d["answer"])
    out({"ok": True})


def cmd_skip_human_question(d):
    db.skip_human_question(d["question_id"])
    out({"ok": True})


def cmd_get_human_questions(_):
    out(db.get_pending_human_questions())


def cmd_save_preference(d):
    db.save_human_preference(
        category=d["category"], key=d["key"], value=d["value"],
        confidence=d.get("confidence", 0.5),
        source=d.get("source", "inferred"))
    out({"ok": True})


# ============================================================
# DNA
# ============================================================
def cmd_update_dna(d):
    try:
        db.update_dna_rule(d["rule_key"], d["new_text"],
                           d["changed_by"], d["reason"])
        out({"ok": True})
    except (PermissionError, ValueError) as e:
        out({"error": str(e)})


def cmd_get_dna(_):
    out(db.get_dna_rules())


# ============================================================
# MEMORIA EPISODICA (v5)
# ============================================================
def cmd_save_episode(d):
    eid = db.save_episode(
        agent_name=d["agent_name"], action=d["action"],
        target=d.get("target", ""), result=d.get("result", "unknown"),
        impact=d.get("impact", ""), details=d.get("details", ""),
        cycle_id=d.get("cycle_id"))
    out({"episode_id": eid})


def cmd_get_episodes(d):
    out(db.get_episodes(
        limit=d.get("limit", 50) if d else 50,
        cycle_id=d.get("cycle_id") if d else None,
        agent_name=d.get("agent_name") if d else None))


# ============================================================
# MEMORIA SEMANTICA (v5)
# ============================================================
def cmd_save_knowledge(d):
    db.save_knowledge(
        category=d["category"], key=d["key"], value=d["value"],
        confidence=d.get("confidence", 0.5),
        discovered_at=d.get("discovered_at"),
        last_verified=d.get("last_verified"))
    out({"ok": True})


def cmd_get_knowledge(d):
    out(db.get_knowledge(d.get("category") if d else None))


# ============================================================
# PADROES (v5)
# ============================================================
def cmd_save_pattern(d):
    pid = db.save_pattern(
        pattern_type=d["pattern_type"],
        description=d["description"],
        standard_fix=d.get("standard_fix", ""),
        affected_files=d.get("affected_files", ""),
        discovered_cycle=d.get("discovered_cycle"))
    out({"pattern_id": pid})


def cmd_get_patterns(d):
    out(db.get_patterns(
        pattern_type=d.get("pattern_type") if d else None))


# ============================================================
# SCORES POR AREA (v5)
# ============================================================
def cmd_save_area_score(d):
    db.save_area_score(
        cycle_id=d["cycle_id"], area_name=d["area_name"],
        score=d["score"], notes=d.get("notes", ""))
    out({"ok": True})


def cmd_get_area_scores(d):
    out(db.get_area_scores(d.get("cycle_id") if d else None))


def cmd_get_area_evolution(d):
    out(db.get_area_evolution(d.get("area_name", "") if d else ""))


# ============================================================
# STATUS E CONTEXTO
# ============================================================
def cmd_get_context(_):
    out(db.get_context())


def cmd_status(_):
    stats  = db.get_stats()
    cycle  = db.get_current_cycle()
    agents = db.get_all_agents()
    areas  = db.get_area_scores()
    result = {
        "version": "7.0",
        "stats": stats,
        "current_cycle": cycle,
        "agents_summary": [
            {"name": a["name"], "fitness": a["fitness_score"],
             "status": a["status"], "group": a["group_name"]}
            for a in agents
        ],
    }
    if areas:
        result["area_scores_summary"] = areas[:10]
    # v6: append checkpoint and token info to status
    try:
        result["last_checkpoint"] = db.get_last_checkpoint()
    except Exception:
        result["last_checkpoint"] = None
    try:
        result["token_usage_total"] = db.get_token_usage()
    except Exception:
        result["token_usage_total"] = None
    out(result)


def cmd_export(_):
    out({"exported_to": db.export_all()})


# ============================================================
# v6 — CHECKPOINTS
# ============================================================
def cmd_save_checkpoint(d):
    cid = db.save_checkpoint(
        cycle_id=d["cycle_id"],
        phase=d["phase"],
        current_agent=d.get("current_agent", ""),
        progress=d.get("progress"))
    out({"checkpoint_id": cid})


def cmd_get_checkpoint(d):
    checkpoint = db.get_last_checkpoint()
    out(checkpoint if checkpoint else {"error": "Nenhum checkpoint encontrado"})


def cmd_resume_checkpoint(d):
    db.mark_checkpoint_resumed(d["checkpoint_id"])
    out({"ok": True, "checkpoint_id": d["checkpoint_id"], "status": "resumed"})


# ============================================================
# v6 — CODE CHANGES
# ============================================================
def cmd_register_change(d):
    change_id = db.register_code_change(
        cycle_id=d.get("cycle_id"),
        agent_name=d.get("agent_name", ""),
        file_path=d["file_path"],
        change_type=d["change_type"],
        backup_path=d.get("backup_path", ""),
        description=d.get("description", ""))
    out({"change_id": change_id})


def cmd_mark_change_tested(d):
    db.mark_change_tested(
        change_id=d["change_id"],
        test_passed=d["test_passed"])
    out({"ok": True, "change_id": d["change_id"], "test_passed": d["test_passed"]})


def cmd_rollback_change(d):
    db.rollback_change(
        change_id=d["change_id"],
        reason=d.get("reason", "Revertido manualmente"))
    out({"ok": True, "change_id": d["change_id"], "status": "ROLLED_BACK"})


def cmd_get_pending_changes(d):
    out(db.get_pending_changes(
        cycle_id=d.get("cycle_id") if d else None))


def cmd_get_change_history(d):
    out(db.get_change_history(
        limit=d.get("limit", 50) if d else 50))


# ============================================================
# v6 — ACTION LOG
# ============================================================
def cmd_log_action(d):
    log_id = db.log_action(
        cycle_id=d.get("cycle_id"),
        agent_name=d.get("agent_name", ""),
        action_type=d["action_type"],
        target=d.get("target", ""),
        result=d.get("result", "success"),
        details=d.get("details", ""),
        duration_ms=d.get("duration_ms", 0),
        tokens_used=d.get("tokens_used", 0))
    out({"log_id": log_id})


def cmd_get_action_log(d):
    out(db.get_action_log(
        agent_name=d.get("agent_name") if d else None,
        action_type=d.get("action_type") if d else None,
        cycle_id=d.get("cycle_id") if d else None,
        limit=d.get("limit", 100) if d else 100))


def cmd_get_token_usage(d):
    out(db.get_token_usage(
        cycle_id=d.get("cycle_id") if d else None))


# ============================================================
# RELATORIO COMPLETO (v6 — MELHORADO)
# ============================================================
def cmd_generate_report(_):
    stats    = db.get_stats()
    hq       = db.get_pending_human_questions()
    agents   = db.get_all_agents()
    rules    = db.get_active_rules()
    patterns = db.get_patterns()
    areas    = db.get_area_scores()
    cycles   = db.get_cycle_history(10)
    knowledge = db.get_knowledge()

    bloqueantes  = hq.get("BLOQUEANTE", [])
    importantes  = hq.get("IMPORTANTE", [])
    curiosidades = hq.get("CURIOSIDADE", [])

    # v6 extras — gracefully degrade if engine methods are absent
    last_checkpoint = None
    checkpoint_resumed = False
    try:
        last_checkpoint = db.get_last_checkpoint()
        if last_checkpoint:
            checkpoint_resumed = last_checkpoint.get("was_resumed", False)
    except Exception:
        pass

    code_changes_summary = {"total": 0, "rolled_back": 0, "pending_test": 0}
    try:
        all_changes = db.get_change_history(limit=500)
        code_changes_summary["total"] = len(all_changes)
        code_changes_summary["rolled_back"] = sum(
            1 for c in all_changes if c.get("status") == "ROLLED_BACK")
        code_changes_summary["pending_test"] = sum(
            1 for c in all_changes if c.get("status") == "PENDING_TEST")
    except Exception:
        pass

    token_usage_summary = {}
    try:
        token_usage_summary = db.get_token_usage()
    except Exception:
        pass

    action_log_summary = {}
    try:
        action_log = db.get_action_log(limit=1000)
        for entry in action_log:
            agent = entry.get("agent_name") or "unknown"
            action_log_summary[agent] = action_log_summary.get(agent, 0) + 1
    except Exception:
        pass

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        "# SWARM GENESIS v7.0 — RELATORIO COMPLETO",
        f"Gerado em: {now}",
        "",
    ]

    # --- Saude do sistema ---
    lines += [
        "## SAUDE DO SISTEMA",
        f"  Ciclos completos: {stats['ciclos_completos']}",
        f"  Regras: {stats['regras_ativas']} ativas | {stats['regras_deprecadas']} deprecadas",
        f"  Feedbacks: {stats['total_feedbacks']} | Sucessos: {stats['total_sucessos']} | Falhas abertas: {stats['falhas_nao_resolvidas']}",
        f"  Agentes: {stats['total_agentes']} ativos | {stats['agentes_elite']} elite | {stats['agentes_aposentados']} aposentados",
        f"  Memoria: {stats['total_episodios']} episodios | {stats['total_conhecimentos']} fatos | {stats['total_padroes']} padroes",
        "",
    ]

    # --- v6: Checkpoint da sessao ---
    lines += ["## CHECKPOINT DA SESSAO (v6)", ""]
    if last_checkpoint:
        cp_id    = last_checkpoint.get("id", "?")
        cp_cycle = last_checkpoint.get("cycle_id", "?")
        cp_phase = last_checkpoint.get("phase", "?")
        cp_ts    = last_checkpoint.get("created_at", "?")
        lines.append(f"  Ultimo checkpoint: ID={cp_id} | Ciclo={cp_cycle} | Fase={cp_phase}")
        lines.append(f"  Registrado em: {cp_ts}")
        lines.append(f"  Sessao retomada de checkpoint: {'SIM' if checkpoint_resumed else 'NAO'}")
    else:
        lines.append("  Nenhum checkpoint registrado nesta sessao.")
    lines.append("")

    # --- v6: Resumo de mudancas de codigo ---
    lines += ["## MUDANCAS DE CODIGO (v6)", ""]
    lines.append(f"  Total de mudancas registradas: {code_changes_summary['total']}")
    lines.append(f"  Revertidas (rollback):          {code_changes_summary['rolled_back']}")
    lines.append(f"  Aguardando teste:               {code_changes_summary['pending_test']}")
    lines.append("")

    # --- v6: Uso de tokens ---
    lines += ["## USO DE TOKENS (v6)", ""]
    if token_usage_summary:
        if isinstance(token_usage_summary, dict):
            total_tokens = token_usage_summary.get("total_tokens", 0)
            by_model = token_usage_summary.get("by_model", {})
            by_agent = token_usage_summary.get("by_agent", {})
            lines.append(f"  Total de tokens consumidos: {total_tokens}")
            if by_model:
                lines.append("  Por modelo:")
                for model, count in by_model.items():
                    lines.append(f"    {model}: {count} tokens")
            if by_agent:
                lines.append("  Por agente (top 5):")
                top_agents = sorted(by_agent.items(), key=lambda x: -x[1])[:5]
                for agent, count in top_agents:
                    lines.append(f"    {agent}: {count} tokens")
        elif isinstance(token_usage_summary, list):
            total = sum(r.get("tokens_used", 0) for r in token_usage_summary)
            lines.append(f"  Total de tokens consumidos: {total}")
            by_agent_local = {}
            for r in token_usage_summary:
                a = r.get("agent_name") or "unknown"
                by_agent_local[a] = by_agent_local.get(a, 0) + r.get("tokens_used", 0)
            for agent, count in sorted(by_agent_local.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"    {agent}: {count} tokens")
    else:
        lines.append("  Nenhum dado de uso de tokens disponivel.")
    lines.append("")

    # --- v6: Resumo do action log ---
    lines += ["## LOG DE ACOES — RESUMO POR AGENTE (v6)", ""]
    if action_log_summary:
        total_actions = sum(action_log_summary.values())
        lines.append(f"  Total de acoes registradas: {total_actions}")
        for agent, count in sorted(action_log_summary.items(), key=lambda x: -x[1]):
            bar = "#" * min(count, 30)
            lines.append(f"  {agent:<30} {bar} ({count})")
    else:
        lines.append("  Nenhuma acao registrada no log.")
    lines.append("")

    # --- Perguntas bloqueantes ---
    if bloqueantes:
        lines += [
            f"## BLOQUEANTE — Preciso de voce AGORA ({len(bloqueantes)})",
            "",
        ]
        for i, q in enumerate(bloqueantes, 1):
            lines += [
                f"### Pergunta {i} — {q.get('theme', 'Sem tema')}",
                f"Agente: {q.get('agent_name', '?')} | Ciclo: {q.get('cycle_id', '?')}",
                "",
                f"{q['question']}",
                "",
                f"Por que: {q.get('context', '—')}",
                f"Se nao responder: {q.get('impact_if_unanswered', '—')}",
                "",
                f"Responder: answer-human-question {{\"question_id\":{q['id']},\"answer\":\"...\"}}",
                "",
            ]

    if importantes:
        lines += [f"## IMPORTANTES — Quando puder ({len(importantes)})", ""]
        for q in importantes:
            lines.append(f"  [Q{q['id']}] {q.get('theme','?')}: {q['question']}")
        lines.append("")

    if curiosidades:
        lines += [f"## CURIOSIDADES ({len(curiosidades)})", ""]
        for q in curiosidades:
            lines.append(f"  [Q{q['id']}] {q['question']}")
        lines.append("")

    # --- Scores por area ---
    if areas:
        lines += ["## SCORES POR AREA", ""]
        for a in areas:
            if isinstance(a.get("avg_score"), (int, float)):
                bar = "#" * int(a["avg_score"] / 10)
                lines.append(f"  {bar:10} {a['avg_score']:5.1f} | {a['area_name']}")
            elif isinstance(a.get("score"), (int, float)):
                bar = "#" * int(a["score"] / 10)
                lines.append(f"  {bar:10} {a['score']:5.1f} | {a['area_name']}")
        lines.append("")

    # --- Evolucao entre ciclos ---
    if len(cycles) >= 2:
        lines += ["## EVOLUCAO ENTRE CICLOS", ""]
        for cy in reversed(cycles[:5]):
            sg = cy.get("score_global")
            sg_str = f"{sg:.0f}" if sg else "?"
            lines.append(
                f"  Ciclo {cy['id']:3} | Score: {sg_str:>3} | "
                f"Q:{cy['total_questions']} F:{cy['total_feedbacks']} "
                f"I:{cy['insights_generated']} | {(cy.get('summary') or '—')[:60]}"
            )
        lines.append("")

    # --- Performance dos agentes ---
    lines += ["## PERFORMANCE DOS AGENTES", ""]
    for a in sorted(agents, key=lambda x: -x["fitness_score"])[:15]:
        bar = "#" * int(a["fitness_score"] / 10)
        lines.append(
            f"  {a['status']:7} | {bar:10} {a['fitness_score']:5.1f} | "
            f"{a['name']} ({a['group_name']})"
        )
    lines.append("")

    # --- Padroes descobertos ---
    if patterns:
        lines += ["## PADROES DESCOBERTOS", ""]
        type_labels = {
            "bug":          "[BUG]",
            "success":      "[SUCESSO]",
            "correlation":  "[CORRELACAO]",
            "anti_pattern": "[ANTI-PADRAO]",
        }
        for p in patterns[:10]:
            label = type_labels.get(p["pattern_type"], "[PADRAO]")
            lines.append(
                f"  {label} [{p['occurrences']}x] {p['description'][:80]}"
            )
        lines.append("")

    # --- Top regras ---
    if rules:
        lines += ["## TOP REGRAS APRENDIDAS", ""]
        for r in rules[:7]:
            lines.append(f"  [{r['confidence']:.2f}] {r['rule_text'][:80]}")
        lines.append("")

    # --- Conhecimento semantico ---
    if knowledge:
        lines += ["## CONHECIMENTO SOBRE O PROJETO", ""]
        by_cat = {}
        for k in knowledge:
            by_cat.setdefault(k["category"], []).append(k)
        for cat, items in list(by_cat.items())[:5]:
            lines.append(f"  [{cat}]")
            for item in items[:3]:
                lines.append(f"    {item['key']}: {item['value'][:60]}")
        lines.append("")

    report = "\n".join(lines)

    report_path = Path(__file__).parent / "docs" / "RELATORIO_ATUAL.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n[Salvo em: {report_path}]")


# ============================================================
# DISPATCH
# ============================================================
COMMANDS = {
    # Ciclos
    "start-cycle":              cmd_start_cycle,
    "end-cycle":                cmd_end_cycle,
    # Feedbacks
    "register-feedback":        cmd_register_feedback,
    "get-feedback":             cmd_get_feedback,
    "get-feedbacks":            cmd_get_feedbacks,
    # Sucessos e falhas
    "register-success":         cmd_register_success,
    "register-failure":         cmd_register_failure,
    "mark-resolved":            cmd_mark_resolved,
    # Perguntas
    "save-question":            cmd_save_question,
    "answer-question":          cmd_answer_question,
    # Regras
    "create-rule":              cmd_create_rule,
    "update-rule":              cmd_update_rule,
    "deprecate-rule":           cmd_deprecate_rule,
    # Consenso
    "register-consensus":       cmd_register_consensus,
    # Agentes
    "register-agent":           cmd_register_agent,
    "update-fitness":           cmd_update_fitness,
    "get-agent":                cmd_get_agent,
    "retire-agent":             cmd_retire_agent,
    "rewrite-agent":            cmd_rewrite_agent,
    # Debates
    "open-debate":              cmd_open_debate,
    "vote-debate":              cmd_vote_debate,
    "close-debate":             cmd_close_debate,
    # Experimentos
    "create-experiment":        cmd_create_experiment,
    "close-experiment":         cmd_close_experiment,
    # HIP
    "save-human-question":      cmd_save_human_question,
    "answer-human-question":    cmd_answer_human_question,
    "skip-human-question":      cmd_skip_human_question,
    "get-human-questions":      cmd_get_human_questions,
    "save-preference":          cmd_save_preference,
    # DNA
    "update-dna":               cmd_update_dna,
    "get-dna":                  cmd_get_dna,
    # Memoria episodica (v5)
    "save-episode":             cmd_save_episode,
    "get-episodes":             cmd_get_episodes,
    # Memoria semantica (v5)
    "save-knowledge":           cmd_save_knowledge,
    "get-knowledge":            cmd_get_knowledge,
    # Padroes (v5)
    "save-pattern":             cmd_save_pattern,
    "get-patterns":             cmd_get_patterns,
    # Scores por area (v5)
    "save-area-score":          cmd_save_area_score,
    "get-area-scores":          cmd_get_area_scores,
    "get-area-evolution":       cmd_get_area_evolution,
    # Status
    "get-context":              cmd_get_context,
    "status":                   cmd_status,
    "export":                   cmd_export,
    "report":                   cmd_generate_report,
    # v6 — Checkpoints
    "save-checkpoint":          cmd_save_checkpoint,
    "get-checkpoint":           cmd_get_checkpoint,
    "resume-checkpoint":        cmd_resume_checkpoint,
    # v6 — Code Changes
    "register-change":          cmd_register_change,
    "mark-change-tested":       cmd_mark_change_tested,
    "rollback-change":          cmd_rollback_change,
    "get-pending-changes":      cmd_get_pending_changes,
    "get-change-history":       cmd_get_change_history,
    # v6 — Action Log
    "log-action":               cmd_log_action,
    "get-action-log":           cmd_get_action_log,
    "get-token-usage":          cmd_get_token_usage,
}

# ============================================================
# HELP
# ============================================================
HELP_TEXT = {
    "start-cycle":              "Inicia um novo ciclo de aprendizado. Retorna cycle_id.",
    "end-cycle":                "Encerra ciclo. Requer: cycle_id. Opcional: summary, score_global.",
    "register-feedback":        "Registra feedback. Requer: source, topic, question, answer.",
    "get-feedback":             "Busca feedback por ID. Requer: feedback_id.",
    "get-feedbacks":            "Lista feedbacks por topico. Opcional: topic, limit.",
    "register-success":         "Registra sucesso. Requer: feedback_id, topic, insight.",
    "register-failure":         "Registra falha. Requer: feedback_id, topic, what_failed.",
    "mark-resolved":            "Marca falha como resolvida. Requer: failure_id, fix.",
    "save-question":            "Salva pergunta gerada. Requer: question.",
    "answer-question":          "Responde pergunta. Requer: question_id, answer.",
    "create-rule":              "Cria regra aprendida. Requer: rule_text.",
    "update-rule":              "Atualiza stats da regra. Requer: rule_id, succeeded (bool).",
    "deprecate-rule":           "Depreca regra. Requer: rule_id. Opcional: reason.",
    "register-consensus":       "Registra consenso entre agentes. Requer: topic, agents, positions, verdict, agreement, reasoning.",
    "register-agent":           "Registra novo agente. Requer: name, role.",
    "update-fitness":           "Atualiza fitness do agente. Requer: agent_name, delta, outcome, action.",
    "get-agent":                "Busca dados de agente. Opcional: agent_name.",
    "retire-agent":             "Aposenta agente. Requer: agent_name. Opcional: reason.",
    "rewrite-agent":            "Reescreve prompt do agente. Requer: agent_name, reason, new_version.",
    "open-debate":              "Abre debate. Requer: topic, proposal, proposed_by.",
    "vote-debate":              "Vota em debate. Requer: debate_id, agent_name, vote.",
    "close-debate":             "Fecha debate. Requer: debate_id, verdict.",
    "create-experiment":        "Cria experimento. Requer: title, hypothesis.",
    "close-experiment":         "Fecha experimento. Requer: experiment_id, status, conclusion.",
    "save-human-question":      "Salva pergunta para o humano. Requer: question, level (BLOQUEANTE|IMPORTANTE|CURIOSIDADE).",
    "answer-human-question":    "Responde pergunta humana. Requer: question_id, answer.",
    "skip-human-question":      "Pula pergunta humana. Requer: question_id.",
    "get-human-questions":      "Lista perguntas pendentes para o humano.",
    "save-preference":          "Salva preferencia do humano. Requer: category, key, value.",
    "update-dna":               "Atualiza regra de DNA. Requer: rule_key, new_text, changed_by, reason.",
    "get-dna":                  "Retorna todas as regras de DNA do sistema.",
    "save-episode":             "Salva episodio na memoria episodica. Requer: agent_name, action.",
    "get-episodes":             "Lista episodios. Opcional: limit, cycle_id, agent_name.",
    "save-knowledge":           "Salva fato na memoria semantica. Requer: category, key, value.",
    "get-knowledge":            "Lista conhecimento semantico. Opcional: category.",
    "save-pattern":             "Salva padrao descoberto. Requer: pattern_type, description.",
    "get-patterns":             "Lista padroes. Opcional: pattern_type.",
    "save-area-score":          "Salva score de area. Requer: cycle_id, area_name, score.",
    "get-area-scores":          "Lista scores por area. Opcional: cycle_id.",
    "get-area-evolution":       "Evolucao de area ao longo dos ciclos. Opcional: area_name.",
    "get-context":              "Retorna contexto completo do sistema.",
    "status":                   "Status resumido: stats, ciclo atual, agentes, areas.",
    "export":                   "Exporta todos os dados para JSON.",
    "report":                   "Gera relatorio completo em Markdown e salva em docs/.",
    # v6
    "save-checkpoint":          "[v6] Salva checkpoint da sessao. Requer: cycle_id, phase.",
    "get-checkpoint":           "[v6] Retorna ultimo checkpoint. Opcional: cycle_id.",
    "resume-checkpoint":        "[v6] Retoma a partir de checkpoint. Requer: checkpoint_id.",
    "register-change":          "[v6] Registra mudanca de codigo. Requer: file_path, change_type.",
    "mark-change-tested":       "[v6] Marca mudanca como testada. Requer: change_id, test_passed (bool).",
    "rollback-change":          "[v6] Reverte mudanca de codigo. Requer: change_id.",
    "get-pending-changes":      "[v6] Lista mudancas pendentes de teste. Opcional: cycle_id.",
    "get-change-history":       "[v6] Historico de mudancas. Opcional: file_path, limit.",
    "log-action":               "[v6] Registra acao no log. Requer: action_type.",
    "get-action-log":           "[v6] Lista log de acoes. Opcional: agent_name, action_type, cycle_id, limit.",
    "get-token-usage":          "[v6] Retorna resumo de uso de tokens. Opcional: cycle_id, agent_name.",
}


def cmd_help(d):
    if d and "command" in d:
        cmd = d["command"]
        if cmd in HELP_TEXT:
            out({"command": cmd, "description": HELP_TEXT[cmd],
                 "required_fields": REQUIRED.get(cmd, [])})
        else:
            out({"error": f"Comando desconhecido: '{cmd}'",
                 "available": sorted(COMMANDS.keys())})
    else:
        out({
            "version": "SWARM GENESIS v7.0",
            "total_commands": len(COMMANDS),
            "commands": {
                cmd: HELP_TEXT.get(cmd, "Sem descricao")
                for cmd in sorted(COMMANDS.keys())
            },
            "usage": "python loop_runner.py <comando> ['{\"campo\": \"valor\"}'']",
            "examples": [
                "python loop_runner.py start-cycle",
                "python loop_runner.py status",
                "python loop_runner.py report",
                "python loop_runner.py save-checkpoint '{\"cycle_id\": 1, \"phase\": \"analysis\"}'",
                "python loop_runner.py register-change '{\"file_path\": \"engine.py\", \"change_type\": \"refactor\"}'",
                "python loop_runner.py log-action '{\"action_type\": \"read_file\", \"agent_name\": \"curiosa\", \"tokens_used\": 120}'",
            ],
        })


# ============================================================
# v8 — PLUGIN COMMANDS (CLI bridge)
# ============================================================
def _plugin_conn():
    """Conexão com init de schemas dos plugins."""
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def cmd_check_budget(d):
    from plugins.ekas_efficiency import check_budget, get_today_usage, init_schema, BudgetExceeded
    conn = _plugin_conn()
    init_schema(conn)
    try:
        check_budget(conn, planned_cost_usd=float((d or {}).get("planned_cost", 0)))
        usage = get_today_usage(conn)
        out({"ok": True, **usage})
    except BudgetExceeded as e:
        out({"ok": False, "error": str(e)})
    finally:
        conn.close()


def cmd_ekas_usage(d):
    from plugins.ekas_efficiency import get_today_usage, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    out(get_today_usage(conn))
    conn.close()


def cmd_guard(d):
    from plugins.tiered_autonomy import guard, init_schema, ActionBlocked
    conn = _plugin_conn()
    init_schema(conn)
    try:
        result = guard(conn, d["agent_name"], d["action_type"],
                       target=d.get("target"))
        conn.commit()
        out({"outcome": result})
    except ActionBlocked as e:
        conn.commit()
        out({"outcome": "blocked", "reason": str(e)})
    finally:
        conn.close()


def cmd_verify_audit(d):
    from plugins.tiered_autonomy import verify_audit_chain, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    ok, bad_id = verify_audit_chain(conn)
    out({"ok": ok, "first_bad_id": bad_id})
    conn.close()


def cmd_register_skill(d):
    from plugins.memory_procedural import register_skill, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    meta = register_skill(conn, name=d["name"], description=d["description"],
                          code_body=d.get("code_body", "return {'ok': True}"),
                          tags=d.get("tags"), created_by=d.get("created_by"))
    conn.commit()
    out(meta)
    conn.close()


def cmd_list_skills(d):
    from plugins.memory_procedural import list_skills, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    out(list_skills(conn, status=(d or {}).get("status")))
    conn.close()


def cmd_run_skill(d):
    from plugins.memory_procedural import run_skill, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    result = run_skill(conn, d["name"], d.get("payload", {}))
    conn.commit()
    out(result)
    conn.close()


def cmd_deprecate_stale_skills(d):
    from plugins.memory_procedural import auto_deprecate_stale, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    n = auto_deprecate_stale(conn, days=int((d or {}).get("days", 30)))
    conn.commit()
    out({"deprecated": n})
    conn.close()


def cmd_self_report(d):
    from plugins.self_model import generate_self_report
    conn = _plugin_conn()
    path = generate_self_report(conn, days=int((d or {}).get("days", 7)))
    out({"path": str(path)})
    conn.close()


def cmd_consolidate_day(d):
    from plugins.daily_consolidator import consolidate_day
    conn = _plugin_conn()
    stats = consolidate_day(conn)
    conn.commit()
    out(stats)
    conn.close()


def cmd_emotions(d):
    from plugins.functional_emotions import get_emotions, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    if d and "agent_name" in d:
        out(get_emotions(conn, d["agent_name"]))
    else:
        rows = conn.execute(
            "SELECT agent_name, boredom, curiosity, fear, joy FROM agent_emotions ORDER BY agent_name"
        ).fetchall()
        out([{"agent": r[0], "boredom": r[1], "curiosity": r[2], "fear": r[3], "joy": r[4]} for r in rows])
    conn.close()


def cmd_choose_agent(d):
    from plugins.functional_emotions import choose_agent, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    chosen = choose_agent(conn, d["candidates"])
    out({"chosen": chosen})
    conn.close()


def cmd_dedup_question(d):
    from plugins.question_dedup import dedup_insert
    conn = _plugin_conn()
    status, rid = dedup_insert(conn, d["question"], cycle_id=d.get("cycle_id"))
    conn.commit()
    out({"status": status, "row_id": rid})
    conn.close()


def cmd_what_changed(d):
    from plugins.session_diff import what_changed
    conn = _plugin_conn()
    print(what_changed(conn))
    conn.close()


def cmd_export_knowledge(d):
    from plugins.cross_project_sync import export_knowledge
    conn = _plugin_conn()
    result = export_knowledge(conn, confidence_threshold=float((d or {}).get("threshold", 0.8)))
    conn.commit()
    out(result)
    conn.close()


def cmd_import_knowledge(d):
    from plugins.cross_project_sync import import_knowledge
    conn = _plugin_conn()
    result = import_knowledge(conn, d["path"])
    conn.commit()
    out(result)
    conn.close()


def cmd_calibration_report(d):
    from plugins.confidence_calibrator import generate_calibration_report, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    print(generate_calibration_report(conn))
    conn.close()


def cmd_auto_calibrate(d):
    from plugins.confidence_calibrator import auto_adjust_confidence, init_schema
    conn = _plugin_conn()
    init_schema(conn)
    n = auto_adjust_confidence(conn, min_samples=int((d or {}).get("min_samples", 5)))
    conn.commit()
    out({"adjusted": n})
    conn.close()


def cmd_split_file(d):
    from plugins.skill_split_task import split_file
    out(split_file(d["file_path"], max_tokens=int(d.get("max_tokens", 30000))))


def cmd_split_directory(d):
    from plugins.skill_split_task import split_directory
    out(split_directory(d["dir_path"], max_tokens=int(d.get("max_tokens", 30000))))


def cmd_execution_plan(d):
    from plugins.skill_split_task import generate_execution_plan
    out(generate_execution_plan(d["dir_path"], d.get("task", "Analisar projeto"),
                                max_tokens=int(d.get("max_tokens", 30000))))


# Wire v8 commands
COMMANDS["check-budget"] = cmd_check_budget
COMMANDS["ekas-usage"] = cmd_ekas_usage
COMMANDS["guard"] = cmd_guard
COMMANDS["verify-audit"] = cmd_verify_audit
COMMANDS["register-skill"] = cmd_register_skill
COMMANDS["list-skills"] = cmd_list_skills
COMMANDS["run-skill"] = cmd_run_skill
COMMANDS["deprecate-stale-skills"] = cmd_deprecate_stale_skills
COMMANDS["self-report"] = cmd_self_report
COMMANDS["consolidate-day"] = cmd_consolidate_day
COMMANDS["emotions"] = cmd_emotions
COMMANDS["choose-agent"] = cmd_choose_agent
COMMANDS["dedup-question"] = cmd_dedup_question
COMMANDS["what-changed"] = cmd_what_changed
COMMANDS["export-knowledge"] = cmd_export_knowledge
COMMANDS["import-knowledge"] = cmd_import_knowledge
COMMANDS["calibration-report"] = cmd_calibration_report
COMMANDS["auto-calibrate"] = cmd_auto_calibrate
COMMANDS["split-file"] = cmd_split_file
COMMANDS["split-directory"] = cmd_split_directory
COMMANDS["execution-plan"] = cmd_execution_plan

REQUIRED["guard"] = ["agent_name", "action_type"]
REQUIRED["register-skill"] = ["name", "description"]
REQUIRED["run-skill"] = ["name"]
REQUIRED["dedup-question"] = ["question"]
REQUIRED["import-knowledge"] = ["path"]
REQUIRED["split-file"] = ["file_path"]
REQUIRED["split-directory"] = ["dir_path"]
REQUIRED["execution-plan"] = ["dir_path"]
REQUIRED["choose-agent"] = ["candidates"]

HELP_TEXT["check-budget"] = "[v8] Verifica budget EKAS do dia. Opcional: planned_cost."
HELP_TEXT["ekas-usage"] = "[v8] Resumo de uso EKAS do dia."
HELP_TEXT["guard"] = "[v8] Avalia se acao pode prosseguir (tiered autonomy). Requer: agent_name, action_type."
HELP_TEXT["verify-audit"] = "[v8] Valida cadeia de audit hash. Sem parametros."
HELP_TEXT["register-skill"] = "[v8] Registra skill procedural. Requer: name, description."
HELP_TEXT["list-skills"] = "[v8] Lista skills. Opcional: status (ACTIVE|STABLE|DEPRECATED)."
HELP_TEXT["run-skill"] = "[v8] Executa skill. Requer: name. Opcional: payload."
HELP_TEXT["deprecate-stale-skills"] = "[v8] Deprecia skills sem uso. Opcional: days (default 30)."
HELP_TEXT["self-report"] = "[v8] Gera relatorio semanal. Opcional: days (default 7)."
HELP_TEXT["consolidate-day"] = "[v8] Consolida memoria episodica do dia. Sem parametros."
HELP_TEXT["emotions"] = "[v8] Emocoes dos agentes. Opcional: agent_name."
HELP_TEXT["choose-agent"] = "[v8] Escolhe melhor agente por emocoes. Requer: candidates (lista)."
HELP_TEXT["dedup-question"] = "[v8] Insere pergunta com dedup. Requer: question."
HELP_TEXT["what-changed"] = "[v8] Resumo do que mudou desde ultimo checkpoint."
HELP_TEXT["export-knowledge"] = "[v8] Exporta regras/padroes de alta confianca. Opcional: threshold."
HELP_TEXT["import-knowledge"] = "[v8] Importa conhecimento de outro projeto. Requer: path."
HELP_TEXT["calibration-report"] = "[v8] Relatorio de calibracao de confianca."
HELP_TEXT["auto-calibrate"] = "[v8] Ajusta confidence baseado em resultados reais. Opcional: min_samples."
HELP_TEXT["split-file"] = "[v8] Divide arquivo grande em partes. Requer: file_path."
HELP_TEXT["split-directory"] = "[v8] Agrupa arquivos de diretorio em batches. Requer: dir_path."
HELP_TEXT["execution-plan"] = "[v8] Plano de execucao com agentes. Requer: dir_path."


COMMANDS["help"] = cmd_help


# ============================================================
# MAIN — DISPATCH
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        out({
            "version": "SWARM GENESIS v7.0",
            "commands": sorted(COMMANDS.keys()),
            "total": len(COMMANDS),
            "tip": "Use 'help' para ver descricoes de todos os comandos.",
        })
        sys.exit(0)

    command = sys.argv[1]

    if command not in COMMANDS:
        out({"error": f"Comando desconhecido: '{command}'",
             "available": sorted(COMMANDS.keys())})
        sys.exit(1)

    data = None
    if len(sys.argv) > 2:
        try:
            data = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            out({"error": "JSON invalido", "detail": str(e)})
            sys.exit(1)

    err = validate(command, data)
    if err:
        out({"error": err})
        sys.exit(1)

    try:
        COMMANDS[command](data)
    except Exception as e:
        out({"error": f"{type(e).__name__}: {e}", "command": command})
        sys.exit(1)
