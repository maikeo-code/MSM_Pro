"""
AI Analyzer — refina recomendacoes de preco usando Claude.

Pipeline:
1. Recebe lista de anuncios com scores pre-calculados (do service_score.py)
2. Envia batch para Claude Opus 4.6 com prompt otimizado
3. Claude valida os scores, ajusta contexto e gera justificativas
4. Retorna lista de recomendacoes refinadas

Modelo: claude-opus-4-6 (melhor qualidade para analise de pricing)
Custo estimado: ~$0.10/dia para 16 anuncios
"""
import json
import logging
from typing import Any

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

# Prompt otimizado para o Analyzer
ANALYZER_SYSTEM_PROMPT = """Voce e um analista senior de pricing especializado no Mercado Livre Brasil.
Sua funcao e REFINAR recomendacoes de preco pre-calculadas por um algoritmo.

REGRAS:
1. Voce NAO recalcula os scores — eles ja foram calculados por formula.
2. Voce VALIDA se a recomendacao faz sentido no contexto do Mercado Livre.
3. Voce AJUSTA a recomendacao se detectar situacoes que a formula nao captura:
   - Sazonalidade (ex: produto de inverno em marco)
   - Categoria sensivel a preco (eletronicos vs acessorios)
   - Promocoes do ML que podem estar afetando conversao
   - Concorrente com preco agressivo que pode ser temporario
4. Voce GERA uma justificativa clara e acionavel para cada anuncio.

5. HISTORICO DE VENDAS (6 meses):
   - Se o campo "historical" estiver presente, USE para contextualizar a recomendacao.
   - Se media atual (avg_daily_sales_30d) < 50% do pico historico (peak_daily_sales):
     produto em queda estrutural — NAO recomendar aumento de preco.
     Exemplo: "Pico de 5 vendas/dia em dez/2025, media atual 1.8/dia — queda estrutural, aumentar preco nao recupera volume."
   - Se preco atual esta FORA do range historico (price_range_180d), ALERTAR:
     "Preco atual R$X esta acima/abaixo do range historico R$Y-R$Z."
   - Se trend_180d == "declining": mencionar a tendencia no reasoning.
   - Se trend_180d == "increasing": isso valida recomendacoes de aumento.
   - Se preco baixo NAO aumentou vendas (preco atual proximo do min historico mas vendas abaixo da media):
     produto pode ter teto natural de demanda — nao insistir em reducao.
   - Mencione o pico historico e a tendencia no reasoning quando relevante.

6. CONCORRENTES NAO VINCULADOS:
   - Se competitor_prices esta VAZIO (lista vazia ou ausente), MENCIONAR no reasoning:
     "Sem concorrentes vinculados — vincule para analise competitiva mais precisa (score competitivo zerado)."
   - Isso e importante pois o score competitivo fica zerado sem concorrentes,
     o que pode distorcer a recomendacao.

7. ESTOQUE IDEAL = 30 DIAS:
   - stock_days > 30: zona de alerta (excesso)
   - stock_days > 45: critico (muito encalhado)
   - stock_days < 5: urgente (risco de ruptura)

8. URGENCIA PARA QUEDAS RECENTES:
   - Se a queda de vendas tem menos de 7 dias, urgencia deve ser "monitor", nao "immediate".
   - Flutuacoes de curto prazo sao normais no ML.

SENSIBILIDADE DO ML A PRECOS:
- Reducao > 10% pode acionar review automatico do ML
- Aumento > 5% pode derrubar ranking temporariamente
- Ajustes graduais (2-3% por vez) sao mais seguros
- Intervalo minimo entre ajustes: 24h (ML precisa indexar)

FORMATO DE RESPOSTA:
Responda em JSON valido com array de objetos, um por anuncio:
[
  {
    "mlb_id": "MLB...",
    "action": "increase" | "decrease" | "hold",
    "suggested_price": 154.90,
    "price_change_pct": 3.3,
    "confidence": "high" | "medium" | "low",
    "risk_level": "low" | "medium" | "high",
    "urgency": "immediate" | "next_48h" | "monitor",
    "reasoning": "Texto explicativo de 2-3 frases...",
    "opportunity_alert": null | "Visitas subiram 30% mas conversao nao acompanhou — revisar titulo e fotos"
  }
]

IMPORTANTE:
- O campo "reasoning" deve ser em portugues, claro e acionavel.
- Se detectar uma oportunidade (ex: visitas altas mas conversao baixa), preencher "opportunity_alert".
- Nunca sugira ajustes maiores que 5% de uma vez.
- Se discordar do score pre-calculado, mude action/price mas EXPLIQUE no reasoning.
"""


async def analyze_with_ai(
    anuncios_with_scores: list[dict],
) -> list[dict]:
    """
    Envia anuncios com scores pre-calculados para Claude e retorna recomendacoes refinadas.

    Args:
        anuncios_with_scores: lista de dicts com dados do anuncio + score pre-calculado

    Returns:
        Lista de dicts com recomendacoes refinadas pela IA
    """
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY nao configurada — retornando scores sem refinamento IA")
        return _fallback_without_ai(anuncios_with_scores)

    # Preparar dados para enviar (reduzir tokens — so o necessario)
    simplified = _simplify_for_ai(anuncios_with_scores)

    user_prompt = (
        f"Analise os seguintes {len(simplified)} anuncios do Mercado Livre "
        "e refine as recomendacoes de preco.\n"
        "Cada anuncio ja tem um score pre-calculado e uma acao sugerida. "
        "Valide, ajuste se necessario e gere justificativas.\n\n"
        f"Dados:\n{json.dumps(simplified, ensure_ascii=False, indent=2)}\n\n"
        "Responda APENAS com o JSON array, sem texto adicional."
    )

    response_text = ""
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        message = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=ANALYZER_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        # Extrair JSON da resposta
        response_text = message.content[0].text.strip()

        # Tentar parsear JSON (pode ter markdown code block)
        if response_text.startswith("```"):
            # Remove code block markers
            lines = response_text.split("\n")
            response_text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        ai_recommendations = json.loads(response_text)

        # Mesclar recomendacoes da IA com os dados originais
        return _merge_ai_recommendations(anuncios_with_scores, ai_recommendations)

    except anthropic.APIError as e:
        logger.error("Erro na API Anthropic: %s", e)
        return _fallback_without_ai(anuncios_with_scores)
    except json.JSONDecodeError as e:
        logger.error(
            "Erro ao parsear resposta da IA: %s — response: %s",
            e,
            response_text[:500],
        )
        return _fallback_without_ai(anuncios_with_scores)
    except Exception as e:
        logger.error("Erro inesperado no analyzer: %s", e)
        return _fallback_without_ai(anuncios_with_scores)


def _simplify_for_ai(anuncios: list[dict]) -> list[dict]:
    """Reduz dados para enviar menos tokens."""
    result = []
    for a in anuncios:
        entry: dict[str, Any] = {
            "mlb_id": a.get("mlb_id"),
            "title": a.get("title", "")[:60],
            "current_price": a.get("current_price"),
            "stock": a.get("stock"),
            "stock_days": a.get("stock_days_projection"),
            "cost": a.get("cost"),
            "listing_type": a.get("listing_type"),
            "periods": a.get("periods"),
            "competitor_prices": a.get("competitor_prices", []),
            "pre_calc": {
                "action": a.get("recommendation", {}).get("action"),
                "suggested_price": a.get("recommendation", {}).get("suggested_price"),
                "price_change_pct": a.get("recommendation", {}).get("price_change_pct"),
                "score": a.get("recommendation", {}).get("score"),
                "confidence": a.get("recommendation", {}).get("confidence"),
                "breakdown": a.get("recommendation", {}).get("breakdown"),
            },
        }
        # Incluir dados historicos se disponiveis (contexto crucial para IA)
        historical = a.get("historical")
        if historical:
            entry["historical"] = historical
        result.append(entry)
    return result


def _merge_ai_recommendations(
    originals: list[dict],
    ai_recs: list[dict],
) -> list[dict]:
    """Mescla recomendacoes da IA com dados originais."""
    ai_by_mlb = {r["mlb_id"]: r for r in ai_recs}

    merged = []
    for orig in originals:
        mlb_id = orig.get("mlb_id")
        ai_rec = ai_by_mlb.get(mlb_id, {})
        score_result = orig.get("recommendation", {})

        # Build recommendation dict (nested, compatible with downstream consumers)
        recommendation = {
            "action": ai_rec.get("action", score_result.get("action", "hold")),
            "suggested_price": ai_rec.get(
                "suggested_price",
                score_result.get("suggested_price", orig.get("current_price")),
            ),
            "price_change_pct": ai_rec.get(
                "price_change_pct",
                score_result.get("price_change_pct", 0),
            ),
            "confidence": ai_rec.get(
                "confidence", score_result.get("confidence", "low")
            ),
            "risk_level": ai_rec.get(
                "risk_level", score_result.get("risk_level", "low")
            ),
            "urgency": ai_rec.get(
                "urgency", score_result.get("urgency", "monitor")
            ),
            "reasoning": ai_rec.get(
                "reasoning",
                _generate_fallback_reasoning(orig, score_result),
            ),
            "score": score_result.get("score"),
            "breakdown": score_result.get("breakdown"),
            "estimated_daily_sales": score_result.get("estimated_daily_sales"),
            "estimated_daily_profit": score_result.get("estimated_daily_profit"),
        }

        # Copy original anuncio and update with AI-refined recommendation
        entry = dict(orig)
        entry["recommendation"] = recommendation
        entry["opportunity_alert"] = ai_rec.get("opportunity_alert")
        entry["ai_model"] = "claude-opus-4-6"

        merged.append(entry)

    return merged


def _fallback_without_ai(anuncios: list[dict]) -> list[dict]:
    """Gera recomendacoes sem IA quando API nao esta disponivel."""
    result = []
    for orig in anuncios:
        score_result = orig.get("recommendation", {})

        # Build recommendation dict with reasoning added
        recommendation = dict(score_result)
        recommendation["reasoning"] = _generate_fallback_reasoning(orig, score_result)

        # Copy original anuncio and update
        entry = dict(orig)
        entry["recommendation"] = recommendation
        entry["opportunity_alert"] = _detect_opportunity(orig)
        entry["ai_model"] = "fallback-python"

        result.append(entry)
    return result


def _generate_fallback_reasoning(anuncio: dict, score_result: dict) -> str:
    """Gera texto explicativo sem IA baseado nos scores e contexto historico."""
    action = score_result.get("action", "hold")
    pct = score_result.get("price_change_pct", 0)
    breakdown = score_result.get("breakdown", {})

    parts = []

    if action == "increase":
        parts.append(f"Recomendacao de aumento de {abs(pct):.1f}%.")
    elif action == "decrease":
        parts.append(f"Recomendacao de reducao de {abs(pct):.1f}%.")
    else:
        parts.append("Manter preco atual.")

    # Explicar o principal driver
    # (encontrar o fator com maior peso absoluto no breakdown)
    if breakdown:
        drivers = sorted(breakdown.items(), key=lambda x: abs(x[1]), reverse=True)
        top_driver, top_value = drivers[0]
        driver_labels = {
            "conv_trend": "tendencia de conversao",
            "visit_trend": "tendencia de visitas",
            "comp_score": "posicao competitiva",
            "stock_score": "pressao de estoque",
            "margem_score": "margem atual",
            "hist_score": "tendencia historica (6 meses)",
        }
        label = driver_labels.get(top_driver, top_driver)
        direction = "positiva" if top_value > 0 else "negativa"
        parts.append(f"Principal fator: {label} ({direction}).")

    # Contexto historico (6 meses)
    historical = anuncio.get("historical")
    if historical:
        trend = historical.get("trend_180d")
        peak = historical.get("peak_daily_sales", 0)
        current_vs_peak = historical.get("current_vs_peak_pct", 0)
        avg_30d = historical.get("avg_daily_sales_30d", 0)
        peak_period = historical.get("peak_period")

        if trend == "declining":
            parts.append("Historico de 6 meses mostra tendencia de queda.")
        elif trend == "increasing":
            parts.append("Historico de 6 meses mostra tendencia de crescimento.")

        if peak and peak > 0:
            peak_label = f" ({peak_period})" if peak_period else ""
            parts.append(f"Pico historico: {peak:.1f} vendas/dia{peak_label}.")

        if current_vs_peak < -50 and avg_30d > 0:
            parts.append(
                f"Media atual ({avg_30d:.1f}/dia) esta {abs(current_vs_peak):.0f}% "
                f"abaixo do pico — queda estrutural."
            )

        # Alertar se preco esta fora do range historico
        price_range = historical.get("price_range_180d", {})
        current_price = anuncio.get("current_price", 0)
        hist_min = price_range.get("min", 0)
        hist_max = price_range.get("max", 0)
        if hist_max > 0 and current_price > 0:
            if current_price > hist_max * 1.05:
                parts.append(
                    f"Preco atual R${current_price:.2f} esta acima do "
                    f"maximo historico R${hist_max:.2f}."
                )
            elif current_price < hist_min * 0.95 and hist_min > 0:
                parts.append(
                    f"Preco atual R${current_price:.2f} esta abaixo do "
                    f"minimo historico R${hist_min:.2f}."
                )

    # Alertas de estoque
    stock = anuncio.get("stock", 0)
    stock_days = anuncio.get("stock_days_projection")
    if stock_days is not None and stock_days < 5:
        parts.append(
            f"Atencao: estoque baixo ({stock} un, ~{stock_days:.0f} dias)."
        )

    # Alerta de concorrentes nao vinculados
    comp_prices = anuncio.get("competitor_prices", [])
    if not comp_prices:
        parts.append(
            "Sem concorrentes vinculados — vincule para analise competitiva mais precisa."
        )

    return " ".join(parts)


def _detect_opportunity(anuncio: dict) -> str | None:
    """Detecta oportunidade (melhoria 5.1 — Alerta de Oportunidade)."""
    periods = anuncio.get("periods", {})
    p7 = periods.get("last_7d", {})
    p15 = periods.get("last_15d", {})

    visits_7d_avg = p7.get("visits", 0) / 7 if p7.get("visits") else 0
    visits_15d_avg = p15.get("visits", 0) / 15 if p15.get("visits") else 0
    conv_7d = p7.get("conversion", 0)
    conv_15d = p15.get("conversion", 0)

    # Visitas subiram mas conversao caiu
    if visits_15d_avg > 0 and visits_7d_avg > visits_15d_avg * 1.2:
        if conv_15d > 0 and conv_7d < conv_15d * 0.85:
            return (
                f"Visitas subiram {((visits_7d_avg / visits_15d_avg - 1) * 100):.0f}% "
                f"mas conversao caiu {((1 - conv_7d / conv_15d) * 100):.0f}%. "
                "Revisar preco, titulo e fotos do anuncio."
            )

    # Conversao alta mas poucas visitas
    if conv_7d > 5 and p7.get("visits", 0) < 50:
        return (
            f"Conversao excelente ({conv_7d:.1f}%) mas poucas visitas "
            f"({p7.get('visits', 0)}). "
            "Considerar investir em Product Ads para aumentar trafego."
        )

    return None
