"""
Adaptive Weights Calculator — calibra pesos da formula de score
baseado na performance historica das recomendacoes.

Logica:
1. Busca recomendacoes "applied" dos ultimos 60 dias
2. Para cada, compara estimated_daily_sales vs vendas reais 7 dias apos aplicacao
3. Agrupa por fator dominante (qual breakdown teve maior peso)
4. Calcula acuracia por fator
5. Ajusta pesos proporcionalmente a acuracia

Se nao houver dados suficientes (< 10 recomendacoes aplicadas),
retorna pesos default.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, cast
from sqlalchemy import Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "conv_trend": 0.30,
    "visit_trend": 0.20,
    "comp_score": 0.20,
    "stock_score": 0.10,
    "margem_score": 0.05,
    "hist_score": 0.15,
}

MIN_APPLIED_FOR_CALIBRATION = 10  # minimo de recomendacoes aplicadas para calibrar


async def get_adaptive_weights(db: AsyncSession, user_id: UUID) -> dict:
    """
    Retorna pesos calibrados baseados na performance historica.
    Se nao houver dados suficientes, retorna DEFAULT_WEIGHTS.
    """
    from app.intel.models import PriceRecommendation
    from app.vendas.models import ListingSnapshot

    cutoff = datetime.now(timezone.utc) - timedelta(days=60)

    # Buscar recomendacoes aplicadas nos ultimos 60 dias
    result = await db.execute(
        select(PriceRecommendation).where(
            PriceRecommendation.user_id == user_id,
            PriceRecommendation.status == "applied",
            PriceRecommendation.applied_at.isnot(None),
            PriceRecommendation.applied_at >= cutoff,
        )
    )
    applied_recs = result.scalars().all()

    if len(applied_recs) < MIN_APPLIED_FOR_CALIBRATION:
        return DEFAULT_WEIGHTS.copy()

    # Para cada recomendacao aplicada, verificar se o resultado foi positivo
    # Resultado positivo = vendas melhoraram nos 7 dias seguintes vs 7 dias anteriores
    factor_hits: dict[str, dict[str, int]] = {
        k: {"correct": 0, "total": 0} for k in DEFAULT_WEIGHTS
    }

    for rec in applied_recs:
        if not rec.applied_at or not rec.score_breakdown:
            continue

        # Buscar vendas 7d antes e 7d depois da aplicacao
        applied_date = (
            rec.applied_at.date()
            if hasattr(rec.applied_at, "date")
            else rec.applied_at
        )
        before_start = applied_date - timedelta(days=7)
        after_end = applied_date + timedelta(days=7)

        # Se ainda nao passou 7 dias apos aplicacao, pular
        if after_end > datetime.now(timezone.utc).date():
            continue

        before_result = await db.execute(
            select(func.sum(ListingSnapshot.sales_today)).where(
                ListingSnapshot.listing_id == rec.listing_id,
                cast(ListingSnapshot.captured_at, SADate) >= before_start,
                cast(ListingSnapshot.captured_at, SADate) < applied_date,
            )
        )
        after_result = await db.execute(
            select(func.sum(ListingSnapshot.sales_today)).where(
                ListingSnapshot.listing_id == rec.listing_id,
                cast(ListingSnapshot.captured_at, SADate) >= applied_date,
                cast(ListingSnapshot.captured_at, SADate) <= after_end,
            )
        )

        sales_before = before_result.scalar() or 0
        sales_after = after_result.scalar() or 0

        # Determinar se a recomendacao acertou
        if rec.action == "increase":
            # Acertou se vendas nao cairam significativamente (> -20%)
            correct = (
                sales_after >= sales_before * 0.8
                if sales_before > 0
                else sales_after > 0
            )
        elif rec.action == "decrease":
            # Acertou se vendas aumentaram
            correct = sales_after > sales_before if sales_before > 0 else True
        else:
            continue  # "hold" nao conta

        # Encontrar o fator dominante (maior valor absoluto no breakdown)
        breakdown = rec.score_breakdown
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except (json.JSONDecodeError, TypeError):
                continue

        if not breakdown or not isinstance(breakdown, dict):
            continue

        # Filtrar apenas fatores que existem nos pesos default
        valid_factors = [
            (k, abs(v))
            for k, v in breakdown.items()
            if k in DEFAULT_WEIGHTS and isinstance(v, (int, float))
        ]
        if not valid_factors:
            continue

        # Registrar hit/miss para o fator dominante
        dominant_factor = max(valid_factors, key=lambda x: x[1])[0]

        factor_hits[dominant_factor]["total"] += 1
        if correct:
            factor_hits[dominant_factor]["correct"] += 1

    # Calcular acuracia por fator e ajustar pesos
    weights = DEFAULT_WEIGHTS.copy()
    total_accuracy = 0.0
    factor_accuracy: dict[str, float] = {}

    for factor, hits in factor_hits.items():
        if hits["total"] >= 3:  # minimo 3 observacoes para calibrar
            accuracy = hits["correct"] / hits["total"]
            factor_accuracy[factor] = accuracy
            total_accuracy += accuracy
        else:
            factor_accuracy[factor] = 0.5  # default sem dados
            total_accuracy += 0.5

    # Normalizar pesos baseado na acuracia relativa
    if total_accuracy > 0:
        for factor in weights:
            acc = factor_accuracy.get(factor, 0.5)
            # Ajusta peso proporcional a acuracia, mas limita entre 50% e 150% do original
            multiplier = max(
                0.5, min(1.5, acc / (total_accuracy / len(weights)))
            )
            weights[factor] = round(DEFAULT_WEIGHTS[factor] * multiplier, 4)

        # Normalizar para somar 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

    logger.info(
        "Adaptive weights for user %s: %s (based on %d applied recs)",
        user_id,
        weights,
        len(applied_recs),
    )
    return weights
