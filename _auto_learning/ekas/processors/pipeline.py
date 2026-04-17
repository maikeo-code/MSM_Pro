"""
EKAS Processing Pipeline v1.0
Orquestra analise de conteudo bruto via Claude AI em multiplos estagios:
1. Resumir conteudo (3 niveis)
2. Extrair funcionalidades mencionadas
3. Extrair tutoriais passo-a-passo
4. Perfilar concorrentes mencionados
5. Pontuar relevancia para o projeto
6. Detectar oportunidades/gaps
"""
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

# Carregar .env do EKAS se existir
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


DEFAULT_FAST_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_SMART_MODEL = "claude-haiku-4-5-20251001"  # Usar Haiku para tudo ate Sonnet estar disponivel


@dataclass
class ProcessedContent:
    """Resultado do processamento de uma fonte pelo pipeline."""
    source_id: int = 0
    summary_short: str = ""
    summary_medium: str = ""
    summary_full: str = ""
    features_detected: List[Dict] = field(default_factory=list)
    tutorials_extracted: List[Dict] = field(default_factory=list)
    competitors_mentioned: List[Dict] = field(default_factory=list)
    relevance_score: float = 0.0
    relevance_reason: str = ""
    opportunities: List[Dict] = field(default_factory=list)
    tags_generated: List[str] = field(default_factory=list)
    tokens_used: int = 0
    processing_time_ms: int = 0
    errors: List[str] = field(default_factory=list)


class ProcessingPipeline:
    """Pipeline principal de processamento com IA para conteudo EKAS."""

    def __init__(self, api_key: str = None,
                 fast_model: str = DEFAULT_FAST_MODEL,
                 smart_model: str = DEFAULT_SMART_MODEL,
                 project_context: str = ""):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.fast_model = fast_model
        self.smart_model = smart_model
        self.project_context = project_context
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic nao instalado. Rode: pip install anthropic")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY nao definida")
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _call_ai(self, prompt: str, model: str = None, max_tokens: int = 2000,
                 system: str = "") -> tuple:
        """Chama Claude API. Retorna (texto_resposta, tokens_usados)."""
        model = model or self.fast_model
        try:
            msg = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system or "Voce e um analista de inteligencia competitiva. Responda SEMPRE em JSON valido.",
                messages=[{"role": "user", "content": prompt}]
            )
            text = msg.content[0].text if msg.content else ""
            tokens = (msg.usage.input_tokens or 0) + (msg.usage.output_tokens or 0)
            return text, tokens
        except Exception as e:
            return json.dumps({"error": str(e)}), 0

    def _parse_json(self, text: str) -> Any:
        """Extrai JSON da resposta da IA (suporta code blocks markdown)."""
        text = text.strip()
        # Remove code fences
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                if line.strip() == "```" and in_block:
                    break
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Tentar encontrar JSON no texto
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"raw": text}

    def process(self, title: str, raw_text: str, source_type: str = "unknown",
                metadata: dict = None, source_id: int = 0) -> ProcessedContent:
        """Processa conteudo pelo pipeline completo (6 estagios)."""
        result = ProcessedContent(source_id=source_id)
        total_tokens = 0
        start = time.time()
        metadata = metadata or {}

        max_chars = 50000
        text = raw_text[:max_chars] if len(raw_text) > max_chars else raw_text
        text_preview = text[:5000]

        # === ESTAGIO 1: Resumir ===
        try:
            prompt = f"""Analise este conteudo e gere 3 niveis de resumo.

TITULO: {title}
TIPO: {source_type}
CONTEUDO:
{text[:10000]}

Responda em JSON:
{{
  "summary_short": "resumo em 1 frase (max 100 chars)",
  "summary_medium": "resumo em 1 paragrafo (max 300 chars)",
  "summary_full": "resumo completo (max 800 chars)",
  "tags": ["tag1", "tag2", "tag3"]
}}"""
            resp, tokens = self._call_ai(prompt, model=self.fast_model, max_tokens=1000)
            total_tokens += tokens
            data = self._parse_json(resp)
            result.summary_short = data.get("summary_short", "")
            result.summary_medium = data.get("summary_medium", "")
            result.summary_full = data.get("summary_full", "")
            result.tags_generated = data.get("tags", [])
        except Exception as e:
            result.errors.append(f"summarize: {e}")

        # === ESTAGIO 2: Extrair Features ===
        try:
            prompt = f"""Identifique TODAS as funcionalidades de software mencionadas neste conteudo.

TITULO: {title}
CONTEUDO:
{text[:15000]}

Para cada funcionalidade, extraia:
- name: nome da funcionalidade
- category: categoria (fiscal, estoque, vendas, logistica, IA, financeiro, atendimento, marketing, integracoes, outro)
- description: breve descricao
- how_it_works: como funciona (se mencionado)

Responda em JSON:
{{"features": [
  {{"name": "...", "category": "...", "description": "...", "how_it_works": "..."}}
]}}

Se nenhuma funcionalidade for mencionada, retorne {{"features": []}}"""
            resp, tokens = self._call_ai(prompt, model=self.fast_model, max_tokens=2000)
            total_tokens += tokens
            data = self._parse_json(resp)
            result.features_detected = data.get("features", [])
        except Exception as e:
            result.errors.append(f"features: {e}")

        # === ESTAGIO 3: Extrair Tutoriais ===
        try:
            prompt = f"""Este conteudo contem tutorial ou passo-a-passo?
Se sim, extraia todos os tutoriais encontrados.

TITULO: {title}
TIPO: {source_type}
CONTEUDO:
{text[:15000]}

Responda em JSON:
{{"tutorials": [
  {{
    "title": "titulo do tutorial",
    "steps": [
      {{"step": 1, "action": "o que fazer", "detail": "como fazer em detalhe"}},
      {{"step": 2, "action": "...", "detail": "..."}}
    ],
    "prerequisites": ["pre-requisito 1"],
    "difficulty": "beginner|intermediate|advanced",
    "estimated_time": "ex: 10 minutos"
  }}
]}}

Se nao houver tutorial, retorne {{"tutorials": []}}"""
            resp, tokens = self._call_ai(prompt, model=self.smart_model, max_tokens=3000)
            total_tokens += tokens
            data = self._parse_json(resp)
            result.tutorials_extracted = data.get("tutorials", [])
        except Exception as e:
            result.errors.append(f"tutorials: {e}")

        # === ESTAGIO 4: Perfilar Concorrentes ===
        try:
            prompt = f"""Identifique ferramentas/produtos/concorrentes mencionados neste conteudo.
Podem ser ERPs, sistemas de gestao, marketplaces, ferramentas de logistica, etc.

TITULO: {title}
CONTEUDO:
{text_preview}

Responda em JSON:
{{"competitors": [
  {{
    "name": "Nome do Produto/Ferramenta",
    "category": "ERP|marketplace|logistica|fiscal|IA|atendimento|outro",
    "strengths": ["ponto forte 1"],
    "weaknesses": ["ponto fraco 1"],
    "pricing_mentioned": "preco se mencionado ou null",
    "sentiment": "positivo|negativo|neutro"
  }}
]}}

Se nenhum concorrente for mencionado, retorne {{"competitors": []}}"""
            resp, tokens = self._call_ai(prompt, model=self.fast_model, max_tokens=1500)
            total_tokens += tokens
            data = self._parse_json(resp)
            result.competitors_mentioned = data.get("competitors", [])
        except Exception as e:
            result.errors.append(f"competitors: {e}")

        # === ESTAGIO 5: Pontuar Relevancia ===
        if self.project_context:
            try:
                feat_names = [f.get("name", "") for f in result.features_detected]
                comp_names = [c.get("name", "") for c in result.competitors_mentioned]
                prompt = f"""Avalie a relevancia deste conteudo para o seguinte projeto:

PROJETO: {self.project_context}

CONTEUDO ANALISADO:
Titulo: {title}
Resumo: {result.summary_medium}
Features: {json.dumps(feat_names, ensure_ascii=False)}
Concorrentes: {json.dumps(comp_names, ensure_ascii=False)}

Responda em JSON:
{{
  "relevance_score": 0.0-1.0,
  "reason": "por que e ou nao relevante para o projeto"
}}"""
                resp, tokens = self._call_ai(prompt, model=self.fast_model, max_tokens=500)
                total_tokens += tokens
                data = self._parse_json(resp)
                result.relevance_score = float(data.get("relevance_score", 0))
                result.relevance_reason = data.get("reason", "")
            except Exception as e:
                result.errors.append(f"relevance: {e}")

        # === ESTAGIO 6: Detectar Oportunidades ===
        try:
            ctx = f"PROJETO: {self.project_context}\n" if self.project_context else ""
            prompt = f"""Com base na analise deste conteudo, identifique oportunidades de negocio.
{ctx}
CONTEUDO ANALISADO:
Titulo: {title}
Resumo: {result.summary_full}
Features: {json.dumps(result.features_detected, ensure_ascii=False)}
Concorrentes: {json.dumps(result.competitors_mentioned, ensure_ascii=False)}

Tipos de oportunidade:
- gap: funcionalidade que ninguem oferece bem
- complaint: reclamacao recorrente de usuarios
- trend: tendencia emergente no mercado
- differentiator: algo que pode ser um diferencial competitivo
- unserved_need: necessidade nao atendida pelos concorrentes

Responda em JSON:
{{"opportunities": [
  {{
    "type": "gap|complaint|trend|differentiator|unserved_need",
    "title": "titulo curto",
    "description": "descricao da oportunidade",
    "impact_score": 0.0-1.0,
    "effort_score": 0.0-1.0
  }}
]}}

Se nenhuma oportunidade for detectada, retorne {{"opportunities": []}}"""
            resp, tokens = self._call_ai(prompt, model=self.smart_model, max_tokens=2000)
            total_tokens += tokens
            data = self._parse_json(resp)
            result.opportunities = data.get("opportunities", [])
        except Exception as e:
            result.errors.append(f"opportunities: {e}")

        result.tokens_used = total_tokens
        result.processing_time_ms = int((time.time() - start) * 1000)
        return result

    def process_light(self, title: str, raw_text: str, source_type: str = "unknown",
                      source_id: int = 0) -> ProcessedContent:
        """Processamento leve — apenas resumo e tags. Bom para bulk."""
        result = ProcessedContent(source_id=source_id)
        start = time.time()

        text = raw_text[:10000]
        try:
            prompt = f"""Analise este conteudo rapidamente.

TITULO: {title}
TIPO: {source_type}
CONTEUDO:
{text}

Responda em JSON:
{{
  "summary_short": "1 frase (max 100 chars)",
  "summary_medium": "1 paragrafo (max 300 chars)",
  "summary_full": "resumo completo (max 600 chars)",
  "tags": ["tag1", "tag2"],
  "relevance_hint": 0.0-1.0,
  "competitors_mentioned": ["nome1", "nome2"],
  "has_tutorial": true
}}"""
            resp, tokens = self._call_ai(prompt, model=self.fast_model, max_tokens=800)
            data = self._parse_json(resp)
            result.summary_short = data.get("summary_short", "")
            result.summary_medium = data.get("summary_medium", "")
            result.summary_full = data.get("summary_full", "")
            result.tags_generated = data.get("tags", [])
            result.relevance_score = float(data.get("relevance_hint", 0))
            result.tokens_used = tokens
        except Exception as e:
            result.errors.append(str(e))

        result.processing_time_ms = int((time.time() - start) * 1000)
        return result
