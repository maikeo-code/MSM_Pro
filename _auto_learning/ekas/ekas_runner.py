"""
============================================================
EKAS v1.0 — External Knowledge Acquisition System Runner
CLI com 40+ comandos para todas as operacoes de inteligencia externa.
============================================================
Uso: python ekas/ekas_runner.py <comando> [json_data]
============================================================
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Carregar .env se existir
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))
from ekas_engine import EkasDB

db = EkasDB()

# ============================================================
# VALIDACAO
# ============================================================
REQUIRED = {
    # Projetos
    "ekas-add-project":             ["project_id", "name"],
    "ekas-update-project":          ["project_id"],
    # Fontes
    "ekas-add-source":              ["source_type", "source_url", "title"],
    "ekas-update-source-status":    ["source_id", "status"],
    "ekas-update-summaries":        ["source_id"],
    # Concorrentes
    "ekas-add-competitor":          ["name"],
    "ekas-update-competitor":       ["competitor_id"],
    "ekas-link-source":             ["competitor_id", "source_id"],
    # Funcionalidades
    "ekas-add-feature":             ["name"],
    "ekas-update-feature-status":   ["feature_id", "status"],
    # Implementacoes
    "ekas-add-implementation":      ["feature_id", "competitor_id"],
    # Tutoriais
    "ekas-add-tutorial":            ["title", "steps"],
    # Oportunidades
    "ekas-add-opportunity":         ["type", "title"],
    "ekas-validate-opportunity":    ["opportunity_id"],
    "ekas-dismiss-opportunity":     ["opportunity_id"],
    "ekas-update-opportunity":      ["opportunity_id", "status"],
    # Watchlist
    "ekas-watch":                   ["watch_type", "target"],
    "ekas-unwatch":                 ["watch_id"],
    "ekas-mark-checked":            ["watch_id"],
    # Coleta
    "ekas-start-run":               ["run_type"],
    "ekas-end-run":                 ["run_id"],
    # Queries compostas
    "ekas-compare":                 ["competitors"],
    "ekas-competitor-profile":      ["name"],
}


def validate(command: str, data: dict | None) -> str | None:
    """Valida campos obrigatorios. Retorna mensagem de erro ou None."""
    required = REQUIRED.get(command, [])
    if not required:
        return None
    if data is None:
        return f"Comando '{command}' requer JSON. Campos: {', '.join(required)}"
    missing = [f for f in required if f not in data]
    if missing:
        return f"Campos ausentes: {', '.join(missing)}"
    return None


def out(obj: object) -> None:
    """Serializa e imprime resultado como JSON."""
    print(json.dumps(obj, ensure_ascii=False, default=str))


def _parse_json_field(value: object) -> object:
    """Converte string JSON em objeto Python se necessario."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


# ============================================================
# PROJETOS
# ============================================================
def cmd_ekas_add_project(d: dict) -> None:
    pid = db.add_project(
        project_id=d["project_id"],
        name=d["name"],
        description=d.get("description", ""),
        base_path=d.get("base_path", ""),
        keywords=_parse_json_field(d.get("keywords", [])),
    )
    out({"ok": True, "project_id": pid})


def cmd_ekas_get_project(d: dict | None) -> None:
    pid = d.get("project_id", "") if d else ""
    project = db.get_project(pid)
    out(project if project else {"error": "Projeto nao encontrado"})


def cmd_ekas_list_projects(_: None) -> None:
    out(db.list_projects())


def cmd_ekas_update_project(d: dict) -> None:
    db.update_project(
        project_id=d["project_id"],
        name=d.get("name"),
        description=d.get("description"),
        base_path=d.get("base_path"),
        keywords=_parse_json_field(d.get("keywords")) if "keywords" in d else None,
        is_active=d.get("is_active"),
    )
    out({"ok": True, "project_id": d["project_id"]})


# ============================================================
# FONTES
# ============================================================
def cmd_ekas_add_source(d: dict) -> None:
    sid = db.add_source(
        source_type=d["source_type"],
        source_url=d["source_url"],
        title=d["title"],
        project_id=d.get("project_id"),
        source_id=d.get("source_id"),
        author=d.get("author", ""),
        author_channel=d.get("author_channel", ""),
        published_at=d.get("published_at"),
        language=d.get("language", "pt-BR"),
        raw_text=d.get("raw_text", ""),
        relevance_score=d.get("relevance_score", 0.0),
        metadata=_parse_json_field(d.get("metadata", {})),
        tags=_parse_json_field(d.get("tags", [])),
    )
    out({"source_id": sid})


def cmd_ekas_get_source(d: dict | None) -> None:
    sid = d.get("source_id") if d else None
    source = db.get_source(sid)
    out(source if source else {"error": "Fonte nao encontrada"})


def cmd_ekas_search_sources(d: dict | None) -> None:
    out(db.search_sources(
        query=d.get("query", "") if d else "",
        source_type=d.get("source_type") if d else None,
        project_id=d.get("project_id") if d else None,
        min_relevance=d.get("min_relevance", 0.0) if d else 0.0,
        limit=d.get("limit", 20) if d else 20,
    ))


def cmd_ekas_update_source_status(d: dict) -> None:
    db.update_source_status(
        source_id=d["source_id"],
        status=d["status"],
        processed_at=d.get("processed_at"),
        error=d.get("error", ""),
    )
    out({"ok": True, "source_id": d["source_id"], "status": d["status"]})


def cmd_ekas_update_summaries(d: dict) -> None:
    db.update_source_summaries(
        source_id=d["source_id"],
        summary_short=d.get("summary_short", ""),
        summary_medium=d.get("summary_medium", ""),
        summary_full=d.get("summary_full", ""),
        relevance_score=d.get("relevance_score"),
        tags=_parse_json_field(d.get("tags")) if "tags" in d else None,
    )
    out({"ok": True, "source_id": d["source_id"]})


def cmd_ekas_sources_by_status(d: dict | None) -> None:
    out(db.get_sources_by_status(
        status=d.get("status", "RAW") if d else "RAW",
        project_id=d.get("project_id") if d else None,
        limit=d.get("limit", 50) if d else 50,
    ))


def cmd_ekas_sources_by_author(d: dict | None) -> None:
    out(db.get_sources_by_author(
        author_channel=d.get("author_channel", "") if d else "",
        limit=d.get("limit", 20) if d else 20,
    ))


# ============================================================
# CONCORRENTES
# ============================================================
def cmd_ekas_add_competitor(d: dict) -> None:
    cid = db.add_competitor(
        name=d["name"],
        project_id=d.get("project_id"),
        category=d.get("category", ""),
        website=d.get("website", ""),
        pricing_info=d.get("pricing_info", ""),
        target_audience=d.get("target_audience", ""),
        integrations=_parse_json_field(d.get("integrations", [])),
        strengths=_parse_json_field(d.get("strengths", [])),
        weaknesses=_parse_json_field(d.get("weaknesses", [])),
        overall_sentiment=d.get("overall_sentiment", 0.0),
    )
    out({"competitor_id": cid})


def cmd_ekas_get_competitor(d: dict | None) -> None:
    name = d.get("name", "") if d else ""
    cid = d.get("competitor_id") if d else None
    competitor = db.get_competitor(name=name, competitor_id=cid)
    out(competitor if competitor else {"error": "Concorrente nao encontrado"})


def cmd_ekas_list_competitors(d: dict | None) -> None:
    out(db.list_competitors(
        project_id=d.get("project_id") if d else None,
        category=d.get("category") if d else None,
    ))


def cmd_ekas_update_competitor(d: dict) -> None:
    db.update_competitor(
        competitor_id=d["competitor_id"],
        category=d.get("category"),
        website=d.get("website"),
        pricing_info=d.get("pricing_info"),
        target_audience=d.get("target_audience"),
        integrations=_parse_json_field(d.get("integrations")) if "integrations" in d else None,
        strengths=_parse_json_field(d.get("strengths")) if "strengths" in d else None,
        weaknesses=_parse_json_field(d.get("weaknesses")) if "weaknesses" in d else None,
        overall_sentiment=d.get("overall_sentiment"),
    )
    out({"ok": True, "competitor_id": d["competitor_id"]})


def cmd_ekas_link_source(d: dict) -> None:
    db.link_competitor_source(
        competitor_id=d["competitor_id"],
        source_id=d["source_id"],
    )
    out({"ok": True, "competitor_id": d["competitor_id"], "source_id": d["source_id"]})


def cmd_ekas_competitor_sources(d: dict | None) -> None:
    cid = d.get("competitor_id") if d else None
    out(db.get_competitor_sources(competitor_id=cid))


def cmd_ekas_competitor_profile(d: dict) -> None:
    """Retorna perfil completo: dados basicos + fontes + features implementadas + tutoriais."""
    name = d["name"]
    profile = db.get_competitor_full_profile(name=name)
    out(profile if profile else {"error": f"Concorrente '{name}' nao encontrado"})


def cmd_ekas_compare(d: dict) -> None:
    """Compara lista de concorrentes em funcionalidades e sentimento."""
    competitors = _parse_json_field(d["competitors"])
    if not isinstance(competitors, list):
        out({"error": "Campo 'competitors' deve ser uma lista de nomes."})
        return
    out(db.compare_competitors(names=competitors, project_id=d.get("project_id")))


# ============================================================
# FUNCIONALIDADES
# ============================================================
def cmd_ekas_add_feature(d: dict) -> None:
    fid = db.add_feature(
        name=d["name"],
        project_id=d.get("project_id"),
        category=d.get("category", ""),
        description=d.get("description", ""),
        importance_score=d.get("importance_score", 0.0),
        implementation_complexity=d.get("implementation_complexity"),
        project_status=d.get("project_status", "NOT_PLANNED"),
    )
    out({"feature_id": fid})


def cmd_ekas_get_feature(d: dict | None) -> None:
    fid = d.get("feature_id") if d else None
    name = d.get("name", "") if d else ""
    feature = db.get_feature(feature_id=fid, name=name)
    out(feature if feature else {"error": "Funcionalidade nao encontrada"})


def cmd_ekas_features_by_category(d: dict | None) -> None:
    out(db.get_features_by_category(
        category=d.get("category", "") if d else "",
        project_id=d.get("project_id") if d else None,
    ))


def cmd_ekas_update_feature_status(d: dict) -> None:
    db.update_feature_status(
        feature_id=d["feature_id"],
        status=d["status"],
        importance_score=d.get("importance_score"),
        implementation_complexity=d.get("implementation_complexity"),
    )
    out({"ok": True, "feature_id": d["feature_id"], "status": d["status"]})


def cmd_ekas_feature_landscape(d: dict | None) -> None:
    """Panorama de todas as funcionalidades: quem implementa o que."""
    out(db.get_feature_landscape(
        project_id=d.get("project_id") if d else None,
        min_importance=d.get("min_importance", 0.0) if d else 0.0,
    ))


# ============================================================
# IMPLEMENTACOES
# ============================================================
def cmd_ekas_add_implementation(d: dict) -> None:
    iid = db.add_feature_implementation(
        feature_id=d["feature_id"],
        competitor_id=d["competitor_id"],
        how_it_works=d.get("how_it_works", ""),
        steps=_parse_json_field(d.get("steps", [])),
        pros=_parse_json_field(d.get("pros", [])),
        cons=_parse_json_field(d.get("cons", [])),
        source_id=d.get("source_id"),
    )
    out({"implementation_id": iid})


def cmd_ekas_feature_implementations(d: dict | None) -> None:
    fid = d.get("feature_id") if d else None
    out(db.get_feature_implementations(feature_id=fid))


def cmd_ekas_competitor_implementations(d: dict | None) -> None:
    cid = d.get("competitor_id") if d else None
    out(db.get_competitor_implementations(competitor_id=cid))


# ============================================================
# TUTORIAIS
# ============================================================
def cmd_ekas_add_tutorial(d: dict) -> None:
    tid = db.add_tutorial(
        title=d["title"],
        steps=_parse_json_field(d["steps"]),
        source_id=d.get("source_id"),
        competitor_id=d.get("competitor_id"),
        feature_id=d.get("feature_id"),
        project_id=d.get("project_id"),
        prerequisites=_parse_json_field(d.get("prerequisites", [])),
        difficulty=d.get("difficulty"),
        estimated_time=d.get("estimated_time", ""),
    )
    out({"tutorial_id": tid})


def cmd_ekas_list_tutorials(d: dict | None) -> None:
    out(db.list_tutorials(
        project_id=d.get("project_id") if d else None,
        feature_id=d.get("feature_id") if d else None,
        competitor_id=d.get("competitor_id") if d else None,
        difficulty=d.get("difficulty") if d else None,
        limit=d.get("limit", 20) if d else 20,
    ))


# ============================================================
# OPORTUNIDADES
# ============================================================
def cmd_ekas_add_opportunity(d: dict) -> None:
    oid = db.add_opportunity(
        type=d["type"],
        title=d["title"],
        project_id=d.get("project_id"),
        description=d.get("description", ""),
        evidence=_parse_json_field(d.get("evidence", [])),
        impact_score=d.get("impact_score", 0.0),
        effort_score=d.get("effort_score", 0.0),
        project_ticket=d.get("project_ticket", ""),
    )
    out({"opportunity_id": oid})


def cmd_ekas_list_opportunities(d: dict | None) -> None:
    out(db.list_opportunities(
        project_id=d.get("project_id") if d else None,
        status=d.get("status") if d else None,
        type=d.get("type") if d else None,
        min_priority=d.get("min_priority", 0.0) if d else 0.0,
        limit=d.get("limit", 30) if d else 30,
    ))


def cmd_ekas_validate_opportunity(d: dict) -> None:
    db.update_opportunity_status(
        opportunity_id=d["opportunity_id"],
        status="VALIDATED",
        project_ticket=d.get("project_ticket"),
    )
    out({"ok": True, "opportunity_id": d["opportunity_id"], "status": "VALIDATED"})


def cmd_ekas_dismiss_opportunity(d: dict) -> None:
    dismiss_reason = d.get("dismiss_reason", "Descartada manualmente")
    db.dismiss_opportunity(
        opportunity_id=d["opportunity_id"],
        reason=dismiss_reason,
    )
    out({"ok": True, "opportunity_id": d["opportunity_id"], "status": "DISMISSED"})


def cmd_ekas_update_opportunity(d: dict) -> None:
    db.update_opportunity_status(
        opportunity_id=d["opportunity_id"],
        status=d["status"],
        ticket=d.get("project_ticket"),
    )
    out({"ok": True, "opportunity_id": d["opportunity_id"], "status": d["status"]})


# ============================================================
# WATCHLIST
# ============================================================
def cmd_ekas_watch(d: dict) -> None:
    wid = db.add_watchlist(
        watch_type=d["watch_type"],
        target=d["target"],
        project_id=d.get("project_id"),
        filters=_parse_json_field(d.get("filters", {})),
        check_interval_hours=d.get("check_interval_hours", 168),
    )
    out({"watch_id": wid})


def cmd_ekas_list_watches(d: dict | None) -> None:
    out(db.list_watchlist(
        project_id=d.get("project_id") if d else None,
        active_only=d.get("active_only", True) if d else True,
    ))


def cmd_ekas_unwatch(d: dict) -> None:
    db.deactivate_watch(watch_id=d["watch_id"])
    out({"ok": True, "watch_id": d["watch_id"], "status": "deactivated"})


def cmd_ekas_mark_checked(d: dict) -> None:
    db.mark_watch_checked(
        watch_id=d["watch_id"],
        new_items_count=d.get("new_items_count", 0),
    )
    out({"ok": True, "watch_id": d["watch_id"]})


def cmd_ekas_due_watches(d: dict | None) -> None:
    """Lista itens da watchlist que estao atrasados para verificacao."""
    out(db.get_due_watches(
        project_id=d.get("project_id") if d else None,
    ))


# ============================================================
# COLETA
# ============================================================
def cmd_ekas_start_run(d: dict) -> None:
    rid = db.start_collection_run(
        run_type=d["run_type"],
        project_id=d.get("project_id"),
        source_type=d.get("source_type", ""),
        query=d.get("query", ""),
    )
    out({"run_id": rid})


def cmd_ekas_end_run(d: dict) -> None:
    db.end_collection_run(
        run_id=d["run_id"],
        status=d.get("status", "COMPLETED"),
        items_found=d.get("items_found", 0),
        items_new=d.get("items_new", 0),
        items_processed=d.get("items_processed", 0),
        tokens_used=d.get("tokens_used", 0),
        duration_ms=d.get("duration_ms"),
        error=d.get("error", ""),
    )
    out({"ok": True, "run_id": d["run_id"], "status": d.get("status", "COMPLETED")})


def cmd_ekas_recent_runs(d: dict | None) -> None:
    out(db.get_recent_runs(
        project_id=d.get("project_id") if d else None,
        limit=d.get("limit", 10) if d else 10,
    ))


# ============================================================
# ANALYTICS
# ============================================================
def cmd_ekas_suggest_roadmap(d: dict | None) -> None:
    """Sugere roadmap priorizando oportunidades por ROI (impacto / esforco)."""
    out(db.suggest_roadmap(
        project_id=d.get("project_id") if d else None,
        limit=d.get("limit", 10) if d else 10,
    ))


def cmd_ekas_stats(_: None) -> None:
    out(db.get_stats())


def cmd_ekas_project_stats(d: dict | None) -> None:
    pid = d.get("project_id", "") if d else ""
    out(db.get_project_stats(project_id=pid))


# ============================================================
# EXPORTACAO
# ============================================================
def cmd_ekas_export(d: dict | None) -> None:
    path = db.export_all()
    out({"exported_to": path})


# ============================================================
# RELATORIO
# ============================================================
def cmd_ekas_report(d: dict | None) -> None:
    """Gera relatorio completo de inteligencia externa em Markdown."""
    project_id = d.get("project_id") if d else None

    stats = db.get_stats()
    competitors = db.list_competitors(project_id=project_id)
    features_data = db.get_feature_landscape(project_id=project_id)
    features = features_data.get("features", []) if isinstance(features_data, dict) else []
    opportunities = db.list_opportunities(
        project_id=project_id, status=None, limit=50
    )
    watches = db.list_watchlist(project_id=project_id, active_only=False)
    recent_runs = db.get_recent_runs(project_id=project_id, limit=10)

    # --- Abertura ---
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        "# EKAS v1.0 — RELATORIO DE INTELIGENCIA EXTERNA",
        f"Gerado em: {now}",
        f"Filtro de projeto: {project_id or 'todos'}",
        "",
    ]

    # --- Resumo geral ---
    lines += [
        "## RESUMO GERAL",
        f"  Fontes coletadas:        {stats.get('total_sources', 0)}",
        f"  Fontes processadas:      {stats.get('sources_processed', 0)}",
        f"  Fontes pendentes:        {stats.get('sources_raw', 0)}",
        f"  Concorrentes mapeados:   {stats.get('total_competitors', 0)}",
        f"  Funcionalidades:         {stats.get('total_features', 0)} ({stats.get('features_implemented', 0)} implementadas)",
        f"  Implementacoes:          {stats.get('total_implementations', 0)}",
        f"  Tutoriais:               {stats.get('total_tutorials', 0)}",
        f"  Oportunidades:           {stats.get('total_opportunities', 0)} ({stats.get('opportunities_detected', 0)} detectadas)",
        f"  Watchlist (ativos):      {stats.get('watches_active', 0)}",
        f"  Runs de coleta:          {stats.get('total_runs', 0)}",
        "",
    ]

    # --- Concorrentes ---
    if competitors:
        lines += [f"## CONCORRENTES ({len(competitors)})", ""]
        for c in competitors:
            sentiment = c.get("overall_sentiment", 0)
            sentiment_label = (
                "positivo" if sentiment > 0.2 else
                "negativo" if sentiment < -0.2 else
                "neutro"
            )
            strengths = _parse_json_field(c.get("strengths") or "[]")
            weaknesses = _parse_json_field(c.get("weaknesses") or "[]")
            s_count = len(strengths) if isinstance(strengths, list) else 0
            w_count = len(weaknesses) if isinstance(weaknesses, list) else 0
            lines.append(
                f"  {c['name']:<30} | "
                f"Cat: {(c.get('category') or '—'):15} | "
                f"Sentimento: {sentiment:+.2f} ({sentiment_label}) | "
                f"Forcas: {s_count} | Fraquezas: {w_count} | "
                f"Fontes: {c.get('source_count', 0)}"
            )
        lines.append("")

    # --- Panorama de funcionalidades ---
    if features:
        lines += [f"## PANORAMA DE FUNCIONALIDADES ({len(features)})", ""]

        # Agrupa por status no projeto
        by_status: dict[str, list] = {}
        for f in features:
            st = f.get("project_status", "NOT_PLANNED")
            by_status.setdefault(st, []).append(f)

        status_order = ["IMPLEMENTED", "IN_PROGRESS", "PLANNED", "NOT_PLANNED", "REJECTED"]
        status_labels = {
            "IMPLEMENTED": "JA IMPLEMENTADAS",
            "IN_PROGRESS": "EM DESENVOLVIMENTO",
            "PLANNED":     "NO BACKLOG",
            "NOT_PLANNED": "NAO PLANEJADAS",
            "REJECTED":    "REJEITADAS",
        }
        for st in status_order:
            items = by_status.get(st, [])
            if not items:
                continue
            lines.append(f"  ### {status_labels.get(st, st)} ({len(items)})")
            for f in sorted(items, key=lambda x: -(x.get("importance", 0) or x.get("importance_score", 0)))[:8]:
                imp = f.get("importance", 0) or f.get("importance_score", 0)
                imp_bar = "#" * int(imp * 10)
                cat = (f.get("category") or "—")[:12]
                fname = f.get("feature") or f.get("name", "?")
                comps = f.get("competitors_with_it", [])
                comp_str = f" | Concorrentes: {', '.join(comps[:3])}" if comps else ""
                lines.append(
                    f"    [{imp_bar:<10}] {imp:.2f} | "
                    f"Cat: {cat:<13} | {fname[:50]}{comp_str}"
                )
        lines.append("")

    # --- Top oportunidades por prioridade ---
    if opportunities:
        active_opps = [
            o for o in opportunities
            if o.get("status") not in ("DISMISSED", "IMPLEMENTED")
        ]
        dismissed_opps = [o for o in opportunities if o.get("status") == "DISMISSED"]
        done_opps = [o for o in opportunities if o.get("status") == "IMPLEMENTED"]

        if active_opps:
            lines += [f"## TOP OPORTUNIDADES ATIVAS ({len(active_opps)})", ""]
            sorted_opps = sorted(
                active_opps,
                key=lambda x: -(x.get("priority_score") or 0)
            )
            type_labels = {
                "gap":            "[LACUNA]",
                "complaint":      "[RECLAMACAO]",
                "trend":          "[TENDENCIA]",
                "differentiator": "[DIFERENCIAL]",
                "unserved_need":  "[NECESSIDADE]",
            }
            for o in sorted_opps[:15]:
                prio = o.get("priority_score") or 0
                impact = o.get("impact_score", 0)
                effort = o.get("effort_score", 0)
                label = type_labels.get(o.get("type", ""), "[?]")
                status = o.get("status", "?")
                lines.append(
                    f"  {label:<14} Prio:{prio:.3f} "
                    f"(Imp:{impact:.2f} | Esf:{effort:.2f}) "
                    f"[{status}] {o['title'][:55]}"
                )
            lines.append("")

        if done_opps:
            lines += [f"## OPORTUNIDADES IMPLEMENTADAS ({len(done_opps)})", ""]
            for o in done_opps[:5]:
                lines.append(f"  [DONE] {o['title'][:70]}")
            lines.append("")

        if dismissed_opps:
            lines += [f"## DESCARTADAS ({len(dismissed_opps)})", ""]
            for o in dismissed_opps[:5]:
                reason = (o.get("dismiss_reason") or "—")[:50]
                lines.append(f"  [SKIP] {o['title'][:50]} — {reason}")
            lines.append("")

    # --- Status da watchlist ---
    if watches:
        active_w = [w for w in watches if w.get("is_active", 1)]
        paused_w = [w for w in watches if not w.get("is_active", 1)]
        lines += [f"## WATCHLIST ({len(watches)} total | {len(active_w)} ativos)", ""]

        if active_w:
            lines.append("  ATIVOS:")
            now_ts = datetime.now()
            for w in active_w:
                last = w.get("last_checked")
                if last:
                    try:
                        delta = now_ts - datetime.fromisoformat(last)
                        hours_ago = int(delta.total_seconds() / 3600)
                        last_label = f"{hours_ago}h atras"
                    except Exception:
                        last_label = last
                else:
                    last_label = "nunca verificado"
                interval = w.get("check_interval_hours", 168)
                new_items = w.get("new_items_count", 0)
                lines.append(
                    f"    [{w['watch_type']:<10}] {w['target'][:40]:<40} | "
                    f"Intervalo: {interval}h | Ultimo: {last_label} | "
                    f"Novos: {new_items}"
                )

        if paused_w:
            lines.append(f"  PAUSADOS: {len(paused_w)} item(s)")
        lines.append("")

    # --- Runs recentes de coleta ---
    if recent_runs:
        lines += [f"## RUNS RECENTES DE COLETA ({len(recent_runs)})", ""]
        for r in recent_runs:
            status = r.get("status", "?")
            rtype = r.get("run_type", "?")
            stype = r.get("source_type") or "—"
            found = r.get("items_found", 0)
            new = r.get("items_new", 0)
            tokens = r.get("tokens_used", 0)
            started = (r.get("started_at") or "?")[:16]
            dur = r.get("duration_ms")
            dur_label = f"{dur}ms" if dur else "—"
            lines.append(
                f"  [{status:9}] [{rtype:9}] src:{stype:<12} | "
                f"Achados:{found:4} Novos:{new:4} Tokens:{tokens:6} | "
                f"Duracao:{dur_label:>8} | {started}"
            )
        lines.append("")

    # --- Tokens e custo acumulado ---
    total_tokens = sum(r.get("tokens_used", 0) for r in recent_runs)
    total_items = sum(r.get("items_processed", 0) for r in recent_runs)
    lines += [
        "## METRICAS DE COLETA (ULTIMOS 10 RUNS)",
        f"  Tokens consumidos:  {total_tokens}",
        f"  Itens processados:  {total_items}",
        "",
    ]

    # --- Rodape ---
    lines += [
        "---",
        "Relatorio gerado pelo EKAS v1.0 — External Knowledge Acquisition System.",
        "Swarm Genesis v6 | MSM Imports",
        "",
    ]

    report = "\n".join(lines)

    report_path = Path(__file__).parent / "reports" / "RELATORIO_EKAS.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n[Salvo em: {report_path}]")


# ============================================================
# DISPATCH
# ============================================================
COMMANDS = {
    # Projetos
    "ekas-add-project":             cmd_ekas_add_project,
    "ekas-get-project":             cmd_ekas_get_project,
    "ekas-list-projects":           cmd_ekas_list_projects,
    "ekas-update-project":          cmd_ekas_update_project,
    # Fontes
    "ekas-add-source":              cmd_ekas_add_source,
    "ekas-get-source":              cmd_ekas_get_source,
    "ekas-search-sources":          cmd_ekas_search_sources,
    "ekas-update-source-status":    cmd_ekas_update_source_status,
    "ekas-update-summaries":        cmd_ekas_update_summaries,
    "ekas-sources-by-status":       cmd_ekas_sources_by_status,
    "ekas-sources-by-author":       cmd_ekas_sources_by_author,
    # Concorrentes
    "ekas-add-competitor":          cmd_ekas_add_competitor,
    "ekas-get-competitor":          cmd_ekas_get_competitor,
    "ekas-list-competitors":        cmd_ekas_list_competitors,
    "ekas-update-competitor":       cmd_ekas_update_competitor,
    "ekas-link-source":             cmd_ekas_link_source,
    "ekas-competitor-sources":      cmd_ekas_competitor_sources,
    "ekas-competitor-profile":      cmd_ekas_competitor_profile,
    "ekas-compare":                 cmd_ekas_compare,
    # Funcionalidades
    "ekas-add-feature":             cmd_ekas_add_feature,
    "ekas-get-feature":             cmd_ekas_get_feature,
    "ekas-features-by-category":    cmd_ekas_features_by_category,
    "ekas-update-feature-status":   cmd_ekas_update_feature_status,
    "ekas-feature-landscape":       cmd_ekas_feature_landscape,
    # Implementacoes
    "ekas-add-implementation":      cmd_ekas_add_implementation,
    "ekas-feature-implementations": cmd_ekas_feature_implementations,
    "ekas-competitor-implementations": cmd_ekas_competitor_implementations,
    # Tutoriais
    "ekas-add-tutorial":            cmd_ekas_add_tutorial,
    "ekas-list-tutorials":          cmd_ekas_list_tutorials,
    # Oportunidades
    "ekas-add-opportunity":         cmd_ekas_add_opportunity,
    "ekas-list-opportunities":      cmd_ekas_list_opportunities,
    "ekas-validate-opportunity":    cmd_ekas_validate_opportunity,
    "ekas-dismiss-opportunity":     cmd_ekas_dismiss_opportunity,
    "ekas-update-opportunity":      cmd_ekas_update_opportunity,
    # Watchlist
    "ekas-watch":                   cmd_ekas_watch,
    "ekas-list-watches":            cmd_ekas_list_watches,
    "ekas-unwatch":                 cmd_ekas_unwatch,
    "ekas-mark-checked":            cmd_ekas_mark_checked,
    "ekas-due-watches":             cmd_ekas_due_watches,
    # Coleta
    "ekas-start-run":               cmd_ekas_start_run,
    "ekas-end-run":                 cmd_ekas_end_run,
    "ekas-recent-runs":             cmd_ekas_recent_runs,
    # Analytics
    "ekas-suggest-roadmap":         cmd_ekas_suggest_roadmap,
    "ekas-stats":                   cmd_ekas_stats,
    "ekas-project-stats":           cmd_ekas_project_stats,
    # Exportacao
    "ekas-export":                  cmd_ekas_export,
    # Relatorio
    "ekas-report":                  cmd_ekas_report,
}

# ============================================================
# HELP
# ============================================================
HELP_TEXT = {
    # Projetos
    "ekas-add-project":
        "Cadastra um projeto no EKAS. Requer: project_id (slug), name. "
        "Opcional: description, base_path, keywords (JSON list).",
    "ekas-get-project":
        "Busca projeto pelo slug. Requer: project_id.",
    "ekas-list-projects":
        "Lista todos os projetos cadastrados. Sem parametros.",
    "ekas-update-project":
        "Atualiza projeto existente. Requer: project_id. "
        "Opcional: name, description, base_path, keywords, is_active.",
    # Fontes
    "ekas-add-source":
        "Registra nova fonte externa. Requer: source_type, source_url, title. "
        "Opcional: project_id, author, author_channel, published_at, language, "
        "raw_text, relevance_score, metadata (JSON), tags (JSON list).",
    "ekas-get-source":
        "Busca fonte pelo ID. Requer: source_id.",
    "ekas-search-sources":
        "Pesquisa fontes por texto. Opcional: query, source_type, project_id, "
        "min_relevance, limit.",
    "ekas-update-source-status":
        "Atualiza status de processamento de uma fonte. "
        "Requer: source_id, status (RAW|PROCESSING|PROCESSED|FAILED|ARCHIVED). "
        "Opcional: processed_at, error.",
    "ekas-update-summaries":
        "Salva resumos gerados por IA em uma fonte. Requer: source_id. "
        "Opcional: summary_short, summary_medium, summary_full, relevance_score, tags.",
    "ekas-sources-by-status":
        "Lista fontes por status. Opcional: status (padrao RAW), project_id, limit.",
    "ekas-sources-by-author":
        "Lista fontes de um canal/autor. Opcional: author_channel, limit.",
    # Concorrentes
    "ekas-add-competitor":
        "Cadastra concorrente. Requer: name. "
        "Opcional: project_id, category, website, pricing_info, target_audience, "
        "integrations (JSON), strengths (JSON), weaknesses (JSON), overall_sentiment.",
    "ekas-get-competitor":
        "Busca concorrente. Opcional: name, competitor_id.",
    "ekas-list-competitors":
        "Lista concorrentes. Opcional: project_id, category.",
    "ekas-update-competitor":
        "Atualiza dados de concorrente. Requer: competitor_id. "
        "Opcional: category, website, pricing_info, target_audience, "
        "integrations, strengths, weaknesses, overall_sentiment.",
    "ekas-link-source":
        "Vincula fonte a concorrente (N:N). Requer: competitor_id, source_id.",
    "ekas-competitor-sources":
        "Lista fontes vinculadas a um concorrente. Requer: competitor_id.",
    "ekas-competitor-profile":
        "Perfil completo do concorrente: dados + fontes + features + tutoriais. "
        "Requer: name.",
    "ekas-compare":
        "Compara lista de concorrentes. Requer: competitors (JSON list de nomes).",
    # Funcionalidades
    "ekas-add-feature":
        "Cadastra funcionalidade de mercado. Requer: name. "
        "Opcional: project_id, category, description, importance_score, "
        "implementation_complexity (low|medium|high|very_high), "
        "project_status (NOT_PLANNED|PLANNED|IN_PROGRESS|IMPLEMENTED|REJECTED).",
    "ekas-get-feature":
        "Busca funcionalidade. Opcional: feature_id, name.",
    "ekas-features-by-category":
        "Lista funcionalidades por categoria. Opcional: category, project_id.",
    "ekas-update-feature-status":
        "Atualiza status de uma funcionalidade. "
        "Requer: feature_id, status. Opcional: importance_score, implementation_complexity.",
    "ekas-feature-landscape":
        "Panorama geral de funcionalidades x concorrentes. "
        "Opcional: project_id, min_importance.",
    # Implementacoes
    "ekas-add-implementation":
        "Registra como um concorrente implementa uma feature. "
        "Requer: feature_id, competitor_id. "
        "Opcional: how_it_works, steps (JSON), pros (JSON), cons (JSON), source_id.",
    "ekas-feature-implementations":
        "Lista implementacoes de uma feature por todos os concorrentes. "
        "Requer: feature_id.",
    "ekas-competitor-implementations":
        "Lista todas as features implementadas por um concorrente. "
        "Requer: competitor_id.",
    # Tutoriais
    "ekas-add-tutorial":
        "Registra tutorial extraido de fonte. "
        "Requer: title, steps (JSON list de {step, action, detail}). "
        "Opcional: source_id, competitor_id, feature_id, project_id, "
        "prerequisites (JSON), difficulty (beginner|intermediate|advanced), estimated_time.",
    "ekas-list-tutorials":
        "Lista tutoriais. Opcional: project_id, feature_id, competitor_id, difficulty, limit.",
    # Oportunidades
    "ekas-add-opportunity":
        "Registra oportunidade detectada. "
        "Requer: type (gap|complaint|trend|differentiator|unserved_need), title. "
        "Opcional: project_id, description, evidence (JSON), "
        "impact_score (0-1), effort_score (0-1), project_ticket.",
    "ekas-list-opportunities":
        "Lista oportunidades. Opcional: project_id, status, type, min_priority, limit.",
    "ekas-validate-opportunity":
        "Valida oportunidade detectada. Requer: opportunity_id. Opcional: project_ticket.",
    "ekas-dismiss-opportunity":
        "Descarta oportunidade. Requer: opportunity_id. Opcional: dismiss_reason.",
    "ekas-update-opportunity":
        "Atualiza status de oportunidade. Requer: opportunity_id, status. "
        "Opcional: project_ticket, dismiss_reason.",
    # Watchlist
    "ekas-watch":
        "Adiciona item ao monitoramento continuo. "
        "Requer: watch_type (channel|keyword|competitor|feature|author), target. "
        "Opcional: project_id, filters (JSON), check_interval_hours (padrao 168).",
    "ekas-list-watches":
        "Lista watchlist. Opcional: project_id, active_only (padrao true).",
    "ekas-unwatch":
        "Desativa monitoramento. Requer: watch_id.",
    "ekas-mark-checked":
        "Registra verificacao concluida. Requer: watch_id. Opcional: new_items_count.",
    "ekas-due-watches":
        "Lista itens da watchlist atrasados para verificacao. Opcional: project_id.",
    # Coleta
    "ekas-start-run":
        "Inicia run de coleta. Requer: run_type (manual|scheduled|watchlist|batch). "
        "Opcional: project_id, source_type, query.",
    "ekas-end-run":
        "Finaliza run de coleta. Requer: run_id. "
        "Opcional: status (COMPLETED|FAILED|PARTIAL), items_found, items_new, "
        "items_processed, tokens_used, duration_ms, error.",
    "ekas-recent-runs":
        "Lista runs recentes de coleta. Opcional: project_id, limit.",
    # Analytics
    "ekas-suggest-roadmap":
        "Sugere roadmap priorizando oportunidades por ROI. "
        "Opcional: project_id, limit.",
    "ekas-stats":
        "Estatisticas globais do EKAS (contagens por entidade).",
    "ekas-project-stats":
        "Estatisticas detalhadas por projeto. Opcional: project_id.",
    # Exportacao
    "ekas-export":
        "Exporta todos os dados para JSON. Opcional: project_id.",
    # Relatorio
    "ekas-report":
        "Gera relatorio completo de inteligencia externa em Markdown. "
        "Salvo em ekas/reports/RELATORIO_EKAS.md. Opcional: project_id.",
}


def cmd_ekas_help(d: dict | None) -> None:
    if d and "command" in d:
        cmd = d["command"]
        if cmd in HELP_TEXT:
            out({
                "command": cmd,
                "description": HELP_TEXT[cmd],
                "required_fields": REQUIRED.get(cmd, []),
            })
        else:
            out({
                "error": f"Comando desconhecido: '{cmd}'",
                "available": sorted(COMMANDS.keys()),
            })
    else:
        out({
            "version": "EKAS v1.0 — External Knowledge Acquisition System",
            "total_commands": len(COMMANDS),
            "commands": {
                cmd: HELP_TEXT.get(cmd, "Sem descricao")
                for cmd in sorted(COMMANDS.keys())
            },
            "usage": "python ekas/ekas_runner.py <comando> ['{\"campo\": \"valor\"}'']",
            "groups": {
                "Projetos":        ["ekas-add-project", "ekas-get-project", "ekas-list-projects", "ekas-update-project"],
                "Fontes":          ["ekas-add-source", "ekas-get-source", "ekas-search-sources",
                                    "ekas-update-source-status", "ekas-update-summaries",
                                    "ekas-sources-by-status", "ekas-sources-by-author"],
                "Concorrentes":    ["ekas-add-competitor", "ekas-get-competitor", "ekas-list-competitors",
                                    "ekas-update-competitor", "ekas-link-source",
                                    "ekas-competitor-sources", "ekas-competitor-profile", "ekas-compare"],
                "Funcionalidades": ["ekas-add-feature", "ekas-get-feature", "ekas-features-by-category",
                                    "ekas-update-feature-status", "ekas-feature-landscape"],
                "Implementacoes":  ["ekas-add-implementation", "ekas-feature-implementations",
                                    "ekas-competitor-implementations"],
                "Tutoriais":       ["ekas-add-tutorial", "ekas-list-tutorials"],
                "Oportunidades":   ["ekas-add-opportunity", "ekas-list-opportunities",
                                    "ekas-validate-opportunity", "ekas-dismiss-opportunity",
                                    "ekas-update-opportunity"],
                "Watchlist":       ["ekas-watch", "ekas-list-watches", "ekas-unwatch",
                                    "ekas-mark-checked", "ekas-due-watches"],
                "Coleta":          ["ekas-start-run", "ekas-end-run", "ekas-recent-runs"],
                "Analytics":       ["ekas-suggest-roadmap", "ekas-stats", "ekas-project-stats"],
                "Exportacao":      ["ekas-export"],
                "Relatorio":       ["ekas-report"],
                "Ajuda":           ["ekas-help"],
            },
            "examples": [
                "python ekas/ekas_runner.py ekas-stats",
                "python ekas/ekas_runner.py ekas-report",
                "python ekas/ekas_runner.py ekas-add-project '{\"project_id\": \"msm_pro\", \"name\": \"MSM Pro\"}'",
                "python ekas/ekas_runner.py ekas-add-competitor '{\"name\": \"Bling\", \"category\": \"ERP\"}'",
                "python ekas/ekas_runner.py ekas-add-source '{\"source_type\": \"youtube\", \"source_url\": \"https://youtu.be/xyz\", \"title\": \"Tutorial Bling\"}'",
                "python ekas/ekas_runner.py ekas-add-opportunity '{\"type\": \"gap\", \"title\": \"Importacao automatica de NF-e\"}'",
                "python ekas/ekas_runner.py ekas-watch '{\"watch_type\": \"channel\", \"target\": \"https://youtube.com/@bling\", \"check_interval_hours\": 72}'",
                "python ekas/ekas_runner.py ekas-compare '{\"competitors\": [\"Bling\", \"Tiny\", \"Omie\"]}'",
                "python ekas/ekas_runner.py ekas-suggest-roadmap '{\"project_id\": \"msm_pro\", \"limit\": 5}'",
                "python ekas/ekas_runner.py ekas-help '{\"command\": \"ekas-add-opportunity\"}'",
            ],
        })


COMMANDS["ekas-help"] = cmd_ekas_help


# ============================================================
# MAIN — DISPATCH
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        out({
            "version": "EKAS v1.0 — External Knowledge Acquisition System",
            "commands": sorted(COMMANDS.keys()),
            "total": len(COMMANDS),
            "tip": "Use 'ekas-help' para ver descricoes de todos os comandos.",
        })
        sys.exit(0)

    command = sys.argv[1]

    if command not in COMMANDS:
        out({
            "error": f"Comando desconhecido: '{command}'",
            "available": sorted(COMMANDS.keys()),
        })
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
