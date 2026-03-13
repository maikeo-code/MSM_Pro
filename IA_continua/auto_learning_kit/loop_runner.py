"""
============================================================
LOOP RUNNER - Executa o ciclo infinito de auto-aprendizado
============================================================
Este script é chamado pelo Claude Code para executar operações
no banco de dados durante o loop de aprendizado.

Uso pelo Claude Code:
    python loop_runner.py start-cycle
    python loop_runner.py register-feedback '{"source":"user","topic":"API","question":"...","answer":"...","sentiment":"positivo"}'
    python loop_runner.py register-success '{"feedback_id":1,"topic":"API","insight":"..."}'
    python loop_runner.py register-failure '{"feedback_id":1,"topic":"API","what_failed":"..."}'
    python loop_runner.py save-question '{"question":"...","category":"exploratoria","cycle_id":1}'
    python loop_runner.py answer-question '{"question_id":1,"answer":"...","was_relevant":true}'
    python loop_runner.py register-consensus '{"topic":"...","agents":["curiosa","confrontadora"],"positions":{},"verdict":"...","agreement":0.8,"reasoning":"..."}'
    python loop_runner.py create-rule '{"rule_text":"...","source":"consenso"}'
    python loop_runner.py get-context
    python loop_runner.py status
    python loop_runner.py export
    python loop_runner.py end-cycle '{"cycle_id":1,"summary":"..."}'
============================================================
"""

import sys
import json
from engine import LearningDB

db = LearningDB()


def cmd_start_cycle():
    cycle_id = db.start_cycle()
    print(json.dumps({"cycle_id": cycle_id}))


def cmd_end_cycle(data):
    db.end_cycle(data["cycle_id"], data.get("summary", ""))
    print(json.dumps({"ok": True}))


def cmd_register_feedback(data):
    fid = db.register_feedback(
        source=data["source"],
        topic=data["topic"],
        question=data["question"],
        answer=data["answer"],
        feedback_text=data.get("feedback_text", ""),
        sentiment=data.get("sentiment", "neutro"),
        confidence=data.get("confidence", 0.5),
        cycle_id=data.get("cycle_id"),
        parent_id=data.get("parent_id"),
        tags=data.get("tags", []),
    )
    print(json.dumps({"feedback_id": fid}))


def cmd_register_success(data):
    sid = db.register_success(
        feedback_id=data["feedback_id"],
        topic=data["topic"],
        insight=data["insight"],
        evidence=data.get("evidence", ""),
        relevance_score=data.get("relevance_score", 0.5),
        tags=data.get("tags", []),
    )
    print(json.dumps({"success_id": sid}))


def cmd_register_failure(data):
    fid = db.register_failure(
        feedback_id=data["feedback_id"],
        topic=data["topic"],
        what_failed=data["what_failed"],
        why_failed=data.get("why_failed", ""),
        tags=data.get("tags", []),
    )
    print(json.dumps({"failure_id": fid}))


def cmd_save_question(data):
    qid = db.save_question(
        question=data["question"],
        context=data.get("context", ""),
        category=data.get("category", "exploratoria"),
        cycle_id=data.get("cycle_id"),
    )
    print(json.dumps({"question_id": qid}))


def cmd_answer_question(data):
    db.answer_question(
        question_id=data["question_id"],
        answer=data["answer"],
        was_relevant=data.get("was_relevant"),
        relevance_reason=data.get("relevance_reason", ""),
    )
    print(json.dumps({"ok": True}))


def cmd_register_consensus(data):
    cid = db.register_consensus(
        topic=data["topic"],
        agents=data["agents"],
        positions=data["positions"],
        verdict=data["verdict"],
        agreement=data["agreement"],
        reasoning=data["reasoning"],
    )
    print(json.dumps({"consensus_id": cid}))


def cmd_create_rule(data):
    rid = db.create_rule(
        rule_text=data["rule_text"],
        source=data.get("source", "consenso"),
        confidence=data.get("confidence", 0.5),
        tags=data.get("tags", []),
    )
    print(json.dumps({"rule_id": rid}))


def cmd_get_context():
    """Retorna contexto completo para as IAs decidirem próximas perguntas."""
    context = {
        "stats": db.get_stats(),
        "top_successes": db.get_top_successes(10),
        "unresolved_failures": db.get_unresolved_failures(10),
        "unanswered_questions": db.get_unanswered_questions(10),
        "active_rules": db.get_active_rules(),
    }
    print(json.dumps(context, ensure_ascii=False, default=str))


def cmd_status():
    stats = db.get_stats()
    print(json.dumps(stats))


def cmd_export():
    path = db.export_all()
    print(json.dumps({"exported_to": path}))


COMMANDS = {
    "start-cycle": lambda _: cmd_start_cycle(),
    "end-cycle": cmd_end_cycle,
    "register-feedback": cmd_register_feedback,
    "register-success": cmd_register_success,
    "register-failure": cmd_register_failure,
    "save-question": cmd_save_question,
    "answer-question": cmd_answer_question,
    "register-consensus": cmd_register_consensus,
    "create-rule": cmd_create_rule,
    "get-context": lambda _: cmd_get_context(),
    "status": lambda _: cmd_status(),
    "export": lambda _: cmd_export(),
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python loop_runner.py <comando> [json_data]")
        print(f"Comandos: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Comando desconhecido: {command}")
        sys.exit(1)

    data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    COMMANDS[command](data)
