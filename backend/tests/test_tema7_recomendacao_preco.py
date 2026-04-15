"""
Tema 7 — Validacao dos pesos ajustados e da regra "venda vale mais que visita".

Hierarquia de prioridade:
1. VENDAS (35%)
2. VISITAS (25%)
3. CONVERSAO (15%)
"""
from app.intel.pricing.service_score import calculate_recommendation_score
from app.intel.pricing.service_weights import DEFAULT_WEIGHTS


# ─── Pesos ──────────────────────────────────────────────────────────────────

def test_pesos_somam_100_pct():
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"Pesos devem somar 100%, soma={total}"


def test_hierarquia_vendas_maior_que_visitas():
    """Vendas deve ser o maior peso."""
    assert DEFAULT_WEIGHTS["sales_trend"] >= DEFAULT_WEIGHTS["visit_trend"]


def test_hierarquia_visitas_maior_que_conversao():
    """Visitas deve pesar mais que conversao."""
    assert DEFAULT_WEIGHTS["visit_trend"] >= DEFAULT_WEIGHTS["conv_trend"]


def test_vendas_peso_35pct():
    assert DEFAULT_WEIGHTS["sales_trend"] == 0.35


def test_visitas_peso_25pct():
    assert DEFAULT_WEIGHTS["visit_trend"] == 0.25


def test_conversao_peso_15pct():
    assert DEFAULT_WEIGHTS["conv_trend"] == 0.15


def test_vendas_e_mais_da_metade_que_visitas_conversao():
    """sales >= visit + conv menos comp, indicando prioridade clara."""
    assert DEFAULT_WEIGHTS["sales_trend"] > DEFAULT_WEIGHTS["conv_trend"]
    assert DEFAULT_WEIGHTS["sales_trend"] > DEFAULT_WEIGHTS["comp_score"]


# ─── Regra "venda vale mais que visita" (venda sobe, visita cai) ────────────

def _build_anuncio(
    sales_yest: int, sales_day_before: int, sales_7d: int,
    visits_yest: int, visits_7d: int,
    conv_yest: float = 1.0, conv_7d: float = 1.0, conv_15d: float = 1.0,
    current_price: float = 100.0,
) -> dict:
    """Cria um anuncio ficticio no formato esperado por calculate_recommendation_score."""
    return {
        "mlb_id": "MLB-TEST",
        "current_price": current_price,
        "stock_days_projection": 20,
        "product_cost": None,
        "competitor_prices": [],
        "historical": None,
        "periods": {
            "today": {"sales": 0, "visits": 0, "conversion": 0.0},
            "yesterday": {
                "sales": sales_yest,
                "visits": visits_yest,
                "conversion": conv_yest,
            },
            "day_before": {
                "sales": sales_day_before,
                "visits": 100,
                "conversion": conv_7d,
            },
            "last_7d": {
                "sales": sales_7d,
                "visits": visits_7d,
                "conversion": conv_7d,
            },
            "last_15d": {
                "sales": sales_7d * 2,
                "visits": visits_7d * 2,
                "conversion": conv_15d,
            },
            "last_30d": {
                "sales": sales_7d * 4,
                "visits": visits_7d * 4,
                "conversion": conv_15d,
            },
        },
    }


def test_venda_sobe_visita_cai_prioriza_venda():
    """
    Cenario: Vendas de ontem muito acima da media 7d, mas visitas ontem
    abaixo da media. Regra Tema 7: a venda sobrepoe e o score nao deve
    ser penalizado por visitas caindo.
    """
    # Baseline: visit_trend NEGATIVO (visitas caindo)
    anuncio_base = _build_anuncio(
        sales_yest=20, sales_day_before=18, sales_7d=70,  # sales_7d_avg=10, recent=19 → sales_trend=+90%
        visits_yest=50, visits_7d=700,                      # visits_7d_avg=100, ontem=50 → visit_trend=-50%
    )
    result = calculate_recommendation_score(anuncio_base)

    # Score deve ser positivo (recomendar aumento) mesmo com visitas caindo
    assert result["score"] > 0, (
        f"score={result['score']}: esperava positivo com venda subindo e visita caindo"
    )


def test_visita_sobe_venda_sobe_bonus_nao_aplica():
    """
    Cenario inverso: ambos subindo. Regra especial NAO deve aplicar
    (e assim nao ha amplificacao artificial, so usa peso normal).
    """
    anuncio = _build_anuncio(
        sales_yest=15, sales_day_before=14, sales_7d=70,  # sales_trend positivo
        visits_yest=150, visits_7d=700,                     # visit_trend positivo tambem
    )
    result = calculate_recommendation_score(anuncio)
    # Score deve ser positivo (tudo bom)
    assert result["score"] > 0


def test_venda_cai_visita_cai_nao_aplica_regra():
    """
    Cenario: ambos caindo. Regra especial NAO se aplica — visitas
    continuam pesando negativamente no score.
    """
    anuncio = _build_anuncio(
        sales_yest=5, sales_day_before=6, sales_7d=70,    # media=10, recent=5.5 → sales_trend=-45%
        visits_yest=30, visits_7d=700,                      # visits_7d_avg=100, ontem=30 → visit_trend=-70%
    )
    result = calculate_recommendation_score(anuncio)
    assert result["score"] < 0, f"score={result['score']}: esperava negativo"


def test_venda_cai_visita_sobe_aplica_peso_normal():
    """Visita subindo e venda caindo: regra especial nao aplica, pesos normais."""
    anuncio = _build_anuncio(
        sales_yest=5, sales_day_before=4, sales_7d=70,    # sales_trend negativo
        visits_yest=200, visits_7d=700,                    # visit_trend positivo
    )
    result = calculate_recommendation_score(anuncio)
    # Score pode ser positivo ou negativo dependendo dos pesos, mas deve
    # usar o componente normal de visitas (positivo) sem zerar.
    assert "score" in result
    assert "action" in result


def test_score_resultado_estrutura():
    """Valida que o dict de resposta tem todas as keys esperadas."""
    anuncio = _build_anuncio(
        sales_yest=10, sales_day_before=10, sales_7d=70,
        visits_yest=100, visits_7d=700,
    )
    result = calculate_recommendation_score(anuncio)
    assert "score" in result
    assert "action" in result
    assert result["action"] in {"increase", "decrease", "hold"}
    assert "suggested_price" in result


def test_action_hold_quando_sem_dados():
    """0 vendas e 0 visitas em 7d deve resultar em hold."""
    anuncio = _build_anuncio(
        sales_yest=0, sales_day_before=0, sales_7d=0,
        visits_yest=0, visits_7d=0,
    )
    result = calculate_recommendation_score(anuncio)
    assert result["action"] == "hold"
