"""
EKAS Report Generator v1.0
Gera relatorios de inteligencia competitiva em Markdown.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from ekas_engine import EkasDB


class ReportGenerator:
    """Gera relatorios de inteligencia a partir dos dados EKAS."""

    def __init__(self, db: EkasDB = None):
        self.db = db or EkasDB()

    def generate_full_report(self, project_id: str = None) -> str:
        """Gera relatorio completo de inteligencia externa."""
        stats = self.db.get_stats()
        competitors = self.db.get_all_competitors(project_id)
        features = self.db.get_features_by_category(project_id=project_id)
        opportunities = self.db.get_opportunities(project_id=project_id)
        watches = self.db.get_active_watches(project_id)
        runs = self.db.get_recent_runs(10, project_id)

        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        lines = [
            "# EKAS v1.0 — RELATORIO DE INTELIGENCIA EXTERNA",
            f"Gerado em: {now}",
        ]

        if project_id:
            lines.append(f"Projeto: {project_id}")
        lines.append("")

        # Visao geral
        lines += [
            "## VISAO GERAL",
            f"  Projetos ativos: {stats['projects']}",
            f"  Fontes coletadas: {stats['sources_total']} "
            f"(RAW: {stats['sources_raw']} | Processadas: {stats['sources_processed']} "
            f"| Falhas: {stats['sources_failed']})",
            f"  Concorrentes mapeados: {stats['competitors']}",
            f"  Funcionalidades detectadas: {stats['features']} "
            f"(Implementadas: {stats['features_implemented']} "
            f"| Planejadas: {stats['features_planned']})",
            f"  Tutoriais extraidos: {stats['tutorials']}",
            f"  Oportunidades: {stats['opportunities_total']} "
            f"(Detectadas: {stats['opportunities_detected']} "
            f"| Validadas: {stats['opportunities_validated']})",
            f"  Monitoramento ativo: {stats['watchlist_active']} itens",
            f"  Coletas realizadas: {stats['collection_runs']}",
            "",
        ]

        # Concorrentes
        if competitors:
            lines += ["## CONCORRENTES MAPEADOS", ""]
            for c in competitors[:15]:
                s = c.get("overall_sentiment", 0)
                icon = "+" if s > 0 else ("-" if s < 0 else "~")
                lines.append(
                    f"  [{icon}] {c['name']} ({c.get('category', '?')}) "
                    f"— {c.get('source_count', 0)} fontes"
                )
                if c.get("strengths"):
                    lines.append(f"      Forcas: {', '.join(str(s) for s in c['strengths'][:3])}")
                if c.get("weaknesses"):
                    lines.append(f"      Fraquezas: {', '.join(str(w) for w in c['weaknesses'][:3])}")
            lines.append("")

        # Features por categoria
        if features:
            lines += ["## FUNCIONALIDADES DO MERCADO", ""]
            by_cat = {}
            for f in features:
                cat = f.get("category", "outro")
                by_cat.setdefault(cat, []).append(f)
            for cat, feats in sorted(by_cat.items()):
                lines.append(f"  [{cat.upper()}]")
                for f in sorted(feats, key=lambda x: -x.get("importance_score", 0))[:5]:
                    status_map = {
                        "IMPLEMENTED": "[OK]", "IN_PROGRESS": "[>>]",
                        "PLANNED": "[..] ", "NOT_PLANNED": "[  ]", "REJECTED": "[XX]"
                    }
                    si = status_map.get(f.get("project_status", ""), "[  ]")
                    imp = f.get("importance_score") or 0
                    bar = "#" * int(float(imp) * 10)
                    lines.append(f"    {si} {bar:10} {float(imp):.1f} | {f.get('name', '?')}")
            lines.append("")

        # Top oportunidades
        if opportunities:
            lines += ["## TOP OPORTUNIDADES (por prioridade)", ""]
            type_labels = {
                "gap": "[GAP]", "complaint": "[RECLAMACAO]",
                "trend": "[TENDENCIA]", "differentiator": "[DIFERENCIAL]",
                "unserved_need": "[NECESSIDADE]"
            }
            for o in sorted(opportunities, key=lambda x: -x.get("priority_score", 0))[:10]:
                label = type_labels.get(o.get("type", ""), "[?]")
                ps = o.get("priority_score", 0)
                lines.append(
                    f"  {label} [{o.get('status', '?')}] "
                    f"Prioridade={ps:.2f} | {o.get('title', '?')}"
                )
                if o.get("description"):
                    lines.append(f"    {o['description'][:100]}")
            lines.append("")

        # Watchlist
        if watches:
            lines += ["## MONITORAMENTO ATIVO", ""]
            for w in watches:
                last = w.get("last_checked", "nunca")
                lines.append(
                    f"  [{w['watch_type'].upper()}] {w['target']} "
                    f"— a cada {w.get('check_interval_hours', '?')}h "
                    f"— ultimo: {last}"
                )
            lines.append("")

        # Coletas recentes
        if runs:
            lines += ["## COLETAS RECENTES", ""]
            for r in runs[:5]:
                q = (r.get("query") or "?")[:30]
                lines.append(
                    f"  [{r.get('status', '?')}] {r.get('source_type', '?')} "
                    f"— q=\"{q}\" — "
                    f"encontrados: {r.get('items_found', 0)} | "
                    f"novos: {r.get('items_new', 0)} | "
                    f"tokens: {r.get('tokens_used', 0)}"
                )
            lines.append("")

        # Roadmap sugerido
        try:
            suggestions = self.db.suggest_roadmap(project_id=project_id, limit=5)
            if suggestions:
                lines += ["## ROADMAP SUGERIDO (baseado em dados)", ""]
                for i, s in enumerate(suggestions, 1):
                    lines.append(
                        f"  {i}. {s['feature']} [{s.get('category', '?')}] "
                        f"— Score: {s['score']:.2f} | "
                        f"Complexidade: {s.get('complexity', '?')} | "
                        f"{s.get('competitors_with_it', 0)} concorrentes tem"
                    )
                    lines.append(f"     Razao: {s.get('reason', '')}")
                lines.append("")
        except Exception:
            pass

        report = "\n".join(lines)

        # Salvar
        report_dir = Path(__file__).parent.parent / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "EKAS_RELATORIO_ATUAL.md"
        report_path.write_text(report, encoding="utf-8")

        return report
