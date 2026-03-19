"""
Score Calculator para o Daily Intel Report.

Calcula score de recomendacao de preco e health score para cada anuncio.
Funcoes puras — nao acessam banco de dados.

100% Python — sem IA.
"""
import logging

from app.intel.pricing.service_weights import DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: calculo de margem percentual
# ---------------------------------------------------------------------------


def _calcular_margem_pct(anuncio: dict) -> float | None:
    """
    Calcula margem percentual usando a formula do financeiro.
    Retorna None se o custo nao esta definido.
    """
    cost = anuncio.get("cost", 0)
    if not cost or cost <= 0:
        return None
    price = anuncio["current_price"]
    if price <= 0:
        return None

    from decimal import Decimal
    from app.financeiro.service import calcular_margem

    fee = anuncio.get("sale_fee_pct")
    result = calcular_margem(
        preco=Decimal(str(price)),
        custo=Decimal(str(cost)),
        listing_type=anuncio.get("listing_type", "classico"),
        frete=Decimal(str(anuncio.get("avg_shipping_cost") or 0)),
        sale_fee_pct=Decimal(str(fee)) if fee else None,
    )
    return float(result["margem_pct"])


# ---------------------------------------------------------------------------
# Score de Recomendacao
# ---------------------------------------------------------------------------


def calculate_recommendation_score(
    anuncio: dict, weights: dict | None = None
) -> dict:
    """
    Score composto ponderado para decidir se deve aumentar, diminuir ou manter preco.

    Args:
        anuncio: dict com dados enriquecidos do anuncio (do collector).
        weights: pesos adaptativos (opcionais). Se None, usa DEFAULT_WEIGHTS.

    Pesos default:
        - Tendencia de conversao: 30%
        - Tendencia de visitas: 20%
        - Posicao competitiva: 20%
        - Pressao de estoque: 10%
        - Margem atual: 5%
        - Historico: 15%

    Thresholds:
        Score > 0.15  -> AUMENTAR
        Score < -0.15 -> DIMINUIR
        Score [-0.15, 0.15] -> MANTER

    Retorna dict com action, suggested_price, breakdown, confidence, risk, urgency etc.
    """
    w = weights or DEFAULT_WEIGHTS
    # 1. Conversion Index — PRINCIPAL INDICE DE DECISAO
    # REGRA: "hoje nunca para comparacao" — baseline e ONTEM
    conv_yesterday = anuncio["periods"]["yesterday"]["conversion"]
    conv_day_before = anuncio["periods"].get("day_before", {}).get("conversion", 0.0)
    conv_7d = anuncio["periods"]["last_7d"]["conversion"]
    conv_15d = anuncio["periods"]["last_15d"]["conversion"]
    conv_30d = anuncio["periods"].get("last_30d", {}).get("conversion", 0.0)

    # Tendencia curta (ontem vs anteontem)
    short_trend = (conv_yesterday - conv_day_before) / conv_day_before if conv_day_before > 0 else 0.0
    # Tendencia media (ontem vs 7d)
    medium_trend = (conv_yesterday - conv_7d) / conv_7d if conv_7d > 0 else 0.0
    # Tendencia longa (7d vs 30d)
    long_trend = (conv_7d - conv_30d) / conv_30d if conv_30d > 0 else 0.0

    # Index combinado: short 40% + medium 40% + long 20%
    conv_trend = short_trend * 0.4 + medium_trend * 0.4 + long_trend * 0.2

    # 2. Tendencia de visitas (25%) — baseline ONTEM vs 7d media
    visits_yesterday = anuncio["periods"]["yesterday"]["visits"]
    visits_7d_total = anuncio["periods"]["last_7d"]["visits"]
    visits_7d_avg = visits_7d_total / 7 if visits_7d_total else 0
    visit_trend = 0.0
    if visits_7d_avg > 0:
        visit_trend = (visits_yesterday - visits_7d_avg) / visits_7d_avg

    # 3. Posicao competitiva (20%)
    my_price = anuncio["current_price"]
    comp_prices = anuncio.get("competitor_prices", [])
    comp_score = 0.0
    if comp_prices and my_price > 0:
        avg_comp = sum(comp_prices) / len(comp_prices)
        comp_score = (avg_comp - my_price) / my_price

    # 4. Pressao de estoque (ideal = 30 dias)
    stock_days = anuncio.get("stock_days_projection")
    stock_score = 0.0
    if stock_days is not None:
        if stock_days < 5:
            stock_score = 0.3  # acabando = pode subir preco
        elif stock_days > 45:
            stock_score = -0.3  # muito encalhado = deve descer preco
        elif stock_days > 30:
            stock_score = -0.15  # zona de alerta — acima do ideal de 30d

    # 5. Margem atual (5%)
    margem_pct = _calcular_margem_pct(anuncio)
    margem_score = 0.0
    if margem_pct is not None:
        if margem_pct < 10:
            margem_score = 0.2  # margem apertada = subir
        elif margem_pct > 40:
            margem_score = -0.1  # margem folgada = pode descer

    # 6. Historical trend modifier (novo)
    historical = anuncio.get("historical")
    hist_score = 0.0
    if historical:
        trend = historical.get("trend_180d", "stable")
        current_vs_peak = historical.get("current_vs_peak_pct", 0)

        # Tendencia de 180 dias influencia o score
        if trend == "declining":
            hist_score = -0.15  # penaliza — produto em queda estrutural
        elif trend == "increasing":
            hist_score = 0.1  # bonus — produto em ascensao

        # Se media atual < 50% do pico, penaliza fortemente
        if current_vs_peak < -50:
            hist_score = min(hist_score, -0.2)

    # Score final ponderado (pesos adaptativos ou default)
    w_conv = w.get("conv_trend", 0.30)
    w_visit = w.get("visit_trend", 0.20)
    w_comp = w.get("comp_score", 0.20)
    w_stock = w.get("stock_score", 0.10)
    w_margem = w.get("margem_score", 0.05)
    w_hist = w.get("hist_score", 0.15)

    score = (
        conv_trend * w_conv
        + visit_trend * w_visit
        + comp_score * w_comp
        + stock_score * w_stock
        + margem_score * w_margem
        + hist_score * w_hist
    )

    # Acao e magnitude (max 5% por dia)
    if score > 0.15:
        action = "increase"
        pct = min(score * 10, 5.0)
    elif score < -0.15:
        action = "decrease"
        pct = max(score * 10, -5.0)
    else:
        action = "hold"
        pct = 0.0

    # REGRA: Se media atual < 50% do pico historico, NAO recomendar aumento
    if historical:
        current_vs_peak = historical.get("current_vs_peak_pct", 0)
        if current_vs_peak < -50 and action == "increase":
            action = "hold"
            pct = 0.0
            logger.debug(
                "%s: aumento bloqueado — media atual %.0f%% abaixo do pico historico",
                anuncio.get("mlb_id"),
                abs(current_vs_peak),
            )

        # REGRA: Se preco sugerido esta fora do range historico praticado, alertar
        price_range = historical.get("price_range_180d", {})
        hist_max = price_range.get("max", 0)
        if hist_max > 0 and action == "increase":
            tentative_price = my_price * (1 + pct / 100) if my_price > 0 else 0
            if tentative_price > hist_max * 1.05:
                # Preco ficaria > 5% acima do maximo ja praticado — limitar
                pct = max(((hist_max - my_price) / my_price * 100) if my_price > 0 else 0, 0)
                if pct < 0.5:
                    action = "hold"
                    pct = 0.0

    suggested_price = round(my_price * (1 + pct / 100), 2) if my_price > 0 else 0.0

    # Confidence baseada na quantidade de dados
    sales_7d = anuncio["periods"]["last_7d"]["sales"]
    visits_7d = anuncio["periods"]["last_7d"]["visits"]
    if sales_7d >= 10 and visits_7d >= 100:
        confidence = "high"
    elif sales_7d >= 3 and visits_7d >= 30:
        confidence = "medium"
    else:
        confidence = "low"

    # REGRA: Se tendencia historica e declining, rebaixar confianca
    if historical and historical.get("trend_180d") == "declining":
        if confidence == "high":
            confidence = "medium"

    # Risk level
    risk = "low"
    if abs(pct) > 3:
        risk = "medium"
    if abs(pct) > 4.5 or (
        comp_prices and suggested_price > max(comp_prices) * 1.1
    ):
        risk = "high"

    # Urgency
    urgency = "monitor"
    if action != "hold":
        # REGRA: Para quedas recentes — usa ontem e anteontem (nunca hoje para comparacao)
        sales_yesterday = anuncio["periods"]["yesterday"]["sales"]
        sales_day_before = anuncio["periods"].get("day_before", {}).get("sales", 0)
        avg_sales_7d = sales_7d / 7 if sales_7d else 0
        # Se ontem e anteontem estao ruins mas a media de 7d e OK, e queda recente
        short_term_dip = (
            avg_sales_7d > 0
            and (sales_yesterday + sales_day_before) < avg_sales_7d * 0.5
            and sales_7d >= 3
        )
        if short_term_dip:
            urgency = "monitor"
        elif confidence == "high" and abs(pct) >= 2:
            urgency = "immediate"
        elif confidence in ("high", "medium"):
            urgency = "next_48h"

    # Estimated daily sales e profit
    avg_sales_7d = sales_7d / 7 if sales_7d else 0
    estimated_daily_sales = avg_sales_7d

    # Calcular margem estimada com preco sugerido
    estimated_daily_profit = 0.0
    try:
        from decimal import Decimal
        from app.financeiro.service import calcular_margem

        fee = anuncio.get("sale_fee_pct")
        margem_result = calcular_margem(
            preco=Decimal(str(suggested_price)),
            custo=Decimal(str(anuncio.get("cost", 0))),
            listing_type=anuncio.get("listing_type", "classico"),
            frete=Decimal(str(anuncio.get("avg_shipping_cost") or 0)),
            sale_fee_pct=Decimal(str(fee)) if fee else None,
        )
        estimated_daily_profit = round(
            float(margem_result["margem_bruta"]) * estimated_daily_sales, 2
        )
    except Exception as exc:
        logger.debug("Erro ao calcular margem para %s: %s", anuncio.get("mlb_id"), exc)

    return {
        "action": action,
        "suggested_price": suggested_price,
        "price_change_pct": round(pct, 2),
        "score": round(score, 4),
        "confidence": confidence,
        "risk_level": risk,
        "urgency": urgency,
        "estimated_daily_sales": round(estimated_daily_sales, 2),
        "estimated_daily_profit": estimated_daily_profit,
        "breakdown": {
            "conv_trend": round(conv_trend * w_conv, 4),
            "visit_trend": round(visit_trend * w_visit, 4),
            "comp_score": round(comp_score * w_comp, 4),
            "stock_score": round(stock_score * w_stock, 4),
            "margem_score": round(margem_score * w_margem, 4),
            "hist_score": round(hist_score * w_hist, 4),
        },
        "conversion_index": {
            "value": round(conv_trend, 4),
            "short_trend": round(short_trend, 4),
            "medium_trend": round(medium_trend, 4),
            "long_trend": round(long_trend, 4),
        },
    }


# ---------------------------------------------------------------------------
# Health Score (0-100)
# ---------------------------------------------------------------------------


def calculate_health_score(anuncio: dict) -> int:
    """
    Score de saude do anuncio (0-100).

    Combina:
        - Conversao (30 pts)
        - Tendencia de visitas (25 pts)
        - Estoque (25 pts)
        - Margem (20 pts)
    """
    score = 0

    # --- Conversao: 0-30 pts ---
    conv_7d = anuncio["periods"]["last_7d"]["conversion"]
    if conv_7d >= 5:
        score += 30
    elif conv_7d >= 3:
        score += 20
    elif conv_7d >= 1:
        score += 10
    # conv_7d < 1 => 0 pts

    # --- Tendencia de visitas: 0-25 pts ---
    visits_7d_total = anuncio["periods"]["last_7d"]["visits"]
    visits_15d_total = anuncio["periods"]["last_15d"]["visits"]
    visits_7d_avg = visits_7d_total / 7 if visits_7d_total else 0
    visits_15d_avg = visits_15d_total / 15 if visits_15d_total else 0

    if visits_15d_avg > 0:
        trend = (visits_7d_avg - visits_15d_avg) / visits_15d_avg
        if trend > 0.1:
            score += 25
        elif trend > -0.1:
            score += 15
        else:
            score += 5
    else:
        # Sem dados de 15d — se tem visitas recentes, da pontuacao parcial
        if visits_7d_avg > 0:
            score += 10

    # --- Estoque: 0-25 pts ---
    stock_days = anuncio.get("stock_days_projection")
    if stock_days is not None:
        if 10 <= stock_days <= 30:
            score += 25  # faixa ideal
        elif 5 <= stock_days <= 45:
            score += 15  # aceitavel
        elif stock_days > 0:
            score += 5  # critico ou excesso
        # stock_days == 0 => 0 pts (sem estoque)
    else:
        # Sem projecao (sem vendas recentes) — verifica estoque absoluto
        stock = anuncio.get("stock", 0)
        if stock > 0:
            score += 10  # tem estoque mas sem velocidade de venda

    # --- Margem: 0-20 pts ---
    margem = _calcular_margem_pct(anuncio)
    if margem is not None:
        if margem >= 25:
            score += 20
        elif margem >= 15:
            score += 15
        elif margem >= 5:
            score += 10
        elif margem > 0:
            score += 5
        # margem <= 0 => 0 pts

    return min(100, max(0, score))
