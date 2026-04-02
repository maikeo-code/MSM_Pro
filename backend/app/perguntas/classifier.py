"""Classificador de perguntas Q&A por tipo usando regex + fallback Claude Haiku."""
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 7 tipos de pergunta
QUESTION_TYPES = [
    "compatibilidade",  # "serve no", "compatível com", "funciona no"
    "material",         # "feito de", "material", "composição"
    "envio",           # "prazo", "entrega", "frete", "envio", "chega"
    "preco",           # "desconto", "menor preço", "parcelar", "negociar"
    "instalacao",      # "instalar", "montagem", "manual", "instrução"
    "estoque",         # "disponível", "tem em estoque", "pronta entrega"
    "garantia",        # "garantia", "troca", "defeito", "devolver"
]

# Patterns regex por tipo (case insensitive)
_PATTERNS: dict[str, list[str]] = {
    "compatibilidade": [
        r"\bserve\b.*\b(no|na|para)\b",
        r"\bcompat[ií]vel\b",
        r"\bfunciona\b.*\b(no|na|com|para)\b",
        r"\bencaixa\b",
        r"\bmodelo\b.*\b(do|da|meu|minha)\b",
        r"\bveiculo\b|\bcarro\b|\bmoto\b",
        r"\bano\b.*\d{4}",
    ],
    "material": [
        r"\bmaterial\b",
        r"\bfeito\s+de\b",
        r"\bcomposi[çc][ãa]o\b",
        r"\bmetal\b|\bpl[áa]stico\b|\bmadeira\b|\btecido\b|\bcouro\b",
        r"\boriginal\b.*\b(ou|é)\b",
    ],
    "envio": [
        r"\bprazo\b",
        r"\bentrega\b",
        r"\bfrete\b",
        r"\benvio\b",
        r"\bchega\b.*\b(quando|dias|quanto)\b",
        r"\bdemora\b",
        r"\bretirar\b|\bretirada\b",
    ],
    "preco": [
        r"\bdesconto\b",
        r"\bmenor\s+pre[çc]o\b",
        r"\bparcel[ao]\b",
        r"\bnegocia\b|\bnegociar\b",
        r"\bpaga\b.*\b(menos|quanto)\b",
        r"\bvalor\b.*\b(final|total)\b",
    ],
    "instalacao": [
        r"\binstala[çc][ãa]o\b|\binstalar\b",
        r"\bmontagem\b|\bmontar\b",
        r"\bmanual\b",
        r"\binstru[çc][ãa]o\b|\binstru[çc][õo]es\b",
    ],
    "estoque": [
        r"\bdispon[ií]vel\b",
        r"\bestoque\b",
        r"\bpronta\s+entrega\b",
        r"\btem\b.*\b(para|pra)\b.*\b(vend|envi)\b",
        r"\bunidade\b",
    ],
    "garantia": [
        r"\bgarantia\b",
        r"\btroca\b|\btrocar\b",
        r"\bdefeito\b|\bdefeituo\b",
        r"\bdevolver\b|\bdevolu[çc][ãa]o\b",
    ],
}


def classify_question(text: str) -> str:
    """
    Classifica uma pergunta por tipo usando regex.
    Retorna o tipo com maior número de matches, ou "outros" se nenhum.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for qtype, patterns in _PATTERNS.items():
        score = 0
        for pattern in patterns:
            try:
                if re.search(pattern, text_lower):
                    score += 1
            except Exception:
                pass
        if score > 0:
            scores[qtype] = score

    if not scores:
        return "outros"

    # Retorna o tipo com maior score
    return max(scores, key=scores.get)


async def classify_with_ai_fallback(text: str) -> str:
    """
    Tenta classificar com regex. Se retornar 'outros', usa Claude Haiku como fallback.
    Retorna sempre uma string válida (um dos tipos ou "outros").
    """
    result = classify_question(text)
    if result != "outros":
        return result

    # Fallback: Claude Haiku
    if not settings.anthropic_api_key:
        return "outros"

    try:
        payload = {
            "model": "claude-haiku-4-20250514",
            "max_tokens": 20,
            "temperature": 0.0,
            "system": "Classifique a pergunta de comprador em UMA das categorias: compatibilidade, material, envio, preco, instalacao, estoque, garantia, outros. Responda APENAS com o nome da categoria sem pontuação.",
            "messages": [{"role": "user", "content": text[:500]}],
        }
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            answer = resp.json()["content"][0]["text"].strip().lower()

            # Validar que é um tipo conhecido
            valid_types = QUESTION_TYPES + ["outros"]
            if answer in valid_types:
                return answer

            # Fuzzy match: se a resposta contiver o nome de um tipo
            for t in valid_types:
                if t in answer:
                    return t

            return "outros"
    except Exception as exc:
        logger.warning("Falha na classificação IA: %s", exc)
        return "outros"
