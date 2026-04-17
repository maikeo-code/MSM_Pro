"""
EKAS Query Engine v1.0
Motor de consultas em linguagem natural sobre dados de inteligencia.
Integra com Claude para interpretar perguntas e buscar respostas no ekas.db.
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from ekas_engine import EkasDB

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class QueryEngine:
    """Responde perguntas em linguagem natural sobre dados EKAS."""

    def __init__(self, db: EkasDB = None, api_key: str = None,
                 model: str = "claude-haiku-4-5-20251001"):
        self.db = db or EkasDB()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic nao instalado")
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def ask(self, question: str, project_id: str = None) -> Dict[str, Any]:
        """Responde uma pergunta sobre os dados EKAS."""
        # Coletar contexto
        stats = self.db.get_stats()
        competitors = self.db.get_all_competitors(project_id)
        features = self.db.get_features_by_category(project_id=project_id)
        opportunities = self.db.get_opportunities(project_id=project_id, limit=20)

        comp_summary = [
            {"name": c["name"], "category": c.get("category"),
             "strengths": c.get("strengths", [])[:3],
             "weaknesses": c.get("weaknesses", [])[:3],
             "source_count": c.get("source_count", 0)}
            for c in competitors[:20]
        ]

        feat_summary = [
            {"name": f["name"], "category": f.get("category"),
             "importance": f.get("importance_score", 0),
             "project_status": f.get("project_status")}
            for f in features[:30]
        ]

        opp_summary = [
            {"type": o.get("type"), "title": o["title"],
             "priority": o.get("priority_score", 0),
             "status": o.get("status")}
            for o in opportunities[:15]
        ]

        context = json.dumps({
            "stats": stats,
            "competitors": comp_summary,
            "features": feat_summary,
            "opportunities": opp_summary,
        }, ensure_ascii=False, indent=2)

        prompt = f"""Com base nos seguintes dados de inteligencia competitiva, responda a pergunta.

DADOS EKAS:
{context}

PERGUNTA: {question}

Responda de forma direta e util. Se a pergunta pedir comparacao, monte tabela.
Se pedir sugestao, justifique com dados. Responda em portugues."""

        try:
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system="Voce e um analista de inteligencia competitiva respondendo perguntas sobre dados coletados.",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = msg.content[0].text if msg.content else ""
            tokens = (msg.usage.input_tokens or 0) + (msg.usage.output_tokens or 0)
            return {
                "question": question,
                "answer": answer,
                "tokens_used": tokens,
                "data_context": {
                    "competitors_count": len(comp_summary),
                    "features_count": len(feat_summary),
                    "opportunities_count": len(opp_summary),
                }
            }
        except Exception as e:
            return {"question": question, "answer": f"Erro: {e}", "tokens_used": 0}

    def compare(self, names: List[str], project_id: str = None) -> Dict[str, Any]:
        """Comparacao direta entre concorrentes usando dados do DB."""
        return self.db.compare_competitors(names, project_id)

    def landscape(self, project_id: str = None) -> Dict[str, Any]:
        """Panorama completo de funcionalidades do mercado."""
        return self.db.get_feature_landscape(project_id)

    def roadmap(self, project_id: str = None, limit: int = 10) -> List[Dict]:
        """Sugestao de roadmap baseada em dados."""
        return self.db.suggest_roadmap(project_id, limit)
