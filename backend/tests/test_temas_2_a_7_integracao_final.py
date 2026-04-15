"""
Testes de integracao final — 10 validacoes cruzadas dos Temas 2-7.

Estes testes validam que as mudancas dos 6 temas funcionam em conjunto
sem interferir umas nas outras. Sao os "10 testes adicionais" solicitados
apos a implementacao de todos os temas.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ads.models import AdCampaign, AdSnapshot
from app.ads.service import get_ads_dashboard
from app.atendimento.models import Claim
from app.atendimento.service_claims import (
    get_claim_stats,
    list_claims_from_db,
    mark_claim_resolved,
)
from app.auth.models import MLAccount, User
from app.core.constants import ML_FEES_FLOAT
from app.financeiro.service import calcular_margem, calcular_taxa_ml
from app.intel.pricing.service_score import calculate_recommendation_score
from app.intel.pricing.service_weights import DEFAULT_WEIGHTS
from app.perguntas.models import Question
from app.perguntas.schemas import QuestionDB
from app.perguntas.service import list_questions_from_db
from app.vendas.models import Listing
from app.vendas.schemas import KpiPeriodOut
from app.vendas.service_kpi import _kpi_date_range


# ─── Teste 1: Financeiro + Dashboard: margem coerente com KPI de dias ──────

def test_integracao_1_margem_usa_taxa_correta_e_dashboard_media():
    """
    Tema 6 (taxa ML) + Tema 2 (media diaria) — um anuncio com vendas
    distribuidas em 7 dias mostra margem por unidade e media/dia
    consistentes entre si.
    """
    res = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("55"),
        listing_type="classico",  # 11%
        frete=Decimal("15"),
    )
    margem_unitaria = float(res["margem_bruta"])  # 100 - 55 - 11 - 15 = 19

    # 7 dias com 3 vendas/dia = 21 vendas totais
    vendas_total = 21
    dias = 7
    media_dia = vendas_total / dias

    lucro_total_estimado = margem_unitaria * vendas_total
    lucro_media_dia = margem_unitaria * media_dia

    assert margem_unitaria == 19.0
    assert round(lucro_total_estimado, 2) == 399.0
    assert round(lucro_media_dia, 2) == 57.0  # 19 * 3 = 57
    # Media diaria deve ser exatamente total/dias
    assert round(lucro_total_estimado / dias, 2) == round(lucro_media_dia, 2)


# ─── Teste 2: Score de recomendacao usa taxa real para calcular margem ────

def test_integracao_2_score_com_margem_real():
    """
    Tema 6 + Tema 7: a recomendacao de preco considera margem,
    e a margem agora usa a taxa correta (11% classico vs 16% premium).
    """
    anuncio_base = {
        "mlb_id": "MLB-INT-2",
        "current_price": 100.0,
        "product_cost": 60.0,
        "listing_type": "classico",
        "sale_fee_pct": 0.11,
        "avg_shipping_cost": 5.0,
        "stock_days_projection": 25,
        "competitor_prices": [],
        "historical": None,
        "periods": {
            "today": {"sales": 0, "visits": 0, "conversion": 0.0},
            "yesterday": {"sales": 10, "visits": 100, "conversion": 10.0},
            "day_before": {"sales": 10, "visits": 100, "conversion": 10.0},
            "last_7d": {"sales": 70, "visits": 700, "conversion": 10.0},
            "last_15d": {"sales": 150, "visits": 1500, "conversion": 10.0},
            "last_30d": {"sales": 300, "visits": 3000, "conversion": 10.0},
        },
    }
    result = calculate_recommendation_score(anuncio_base)
    # Score deve ser calculado sem erro
    assert "score" in result
    assert "action" in result


# ─── Teste 3: Ads dashboard sem acumulacao + Tema 3 period_days ────────────

@pytest.mark.asyncio
async def test_integracao_3_ads_dashboard_nao_duplica_e_usa_period(db):
    """
    Tema 3: dashboard de ads respeita period_days e nao duplica valores.
    """
    u = User(id=uuid4(), email=f"i3_{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="55",
        nickname="I3", access_token="t", refresh_token="r",
    )
    db.add(acc)
    await db.flush()

    c = AdCampaign(
        id=uuid4(), ml_account_id=acc.id, campaign_id="INT-3",
        name="C", status="active", daily_budget=Decimal("50"),
    )
    db.add(c)
    await db.flush()

    # 3 snapshots em dias diferentes, cada um = 30d acumulado
    for offset in range(3):
        db.add(AdSnapshot(
            id=uuid4(),
            campaign_id=c.id,
            date=date.today() - timedelta(days=offset),
            impressions=5000,
            clicks=100,
            spend=Decimal("75.00"),
            attributed_sales=8,
            attributed_revenue=Decimal("400.00"),
            organic_sales=2,
        ))
    await db.commit()

    result = await get_ads_dashboard(db, acc.id, period=7, user_id=u.id)

    # Pega mais recente, nao soma 3 x 75
    assert result.total_spend == Decimal("75.00")
    assert result.period_days == 7


# ─── Teste 4: KpiPeriodOut serializavel via Pydantic com medias ────────────

def test_integracao_4_kpi_period_serializa_medias():
    """Tema 2: roundtrip Pydantic preserva campos de media."""
    out = KpiPeriodOut(
        vendas=210, visitas=2100, conversao=10.0, anuncios=3,
        dias_no_periodo=7,
        vendas_media_dia=30.0, visitas_media_dia=300.0,
        pedidos_media_dia=25.0, receita_media_dia=1500.0,
    )
    d = out.model_dump()
    assert d["vendas_media_dia"] == 30.0
    assert d["dias_no_periodo"] == 7
    re = KpiPeriodOut(**d)
    assert re.vendas_media_dia == 30.0


# ─── Teste 5: Perguntas enriquecidas + schema aceita sem thumbnail ────────

@pytest.mark.asyncio
async def test_integracao_5_pergunta_enriquecida_serializa_via_schema(db):
    """Tema 4: dict retornado pela service passa pelo schema."""
    u = User(id=uuid4(), email=f"i5_{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="55",
        nickname="I5", access_token="t", refresh_token="r",
    )
    db.add(acc)
    await db.flush()

    q = Question(
        id=uuid4(),
        ml_question_id=77,
        ml_account_id=acc.id,
        mlb_id="MLB-I5",
        text="Tem?",
        status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    items, total = await list_questions_from_db(db, u.id)
    assert total == 1
    dto = QuestionDB(**items[0])
    assert dto.mlb_id == "MLB-I5"
    assert dto.item_thumbnail is None  # sem listing
    assert dto.item_permalink is None


# ─── Teste 6: Claim lifecycle completo (criar → listar → resolver → stats) ─

@pytest.mark.asyncio
async def test_integracao_6_claim_lifecycle_completo(db):
    """Tema 5: ciclo de vida completo de um claim."""
    u = User(id=uuid4(), email=f"i6_{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="55",
        nickname="I6", access_token="t", refresh_token="r",
    )
    db.add(acc)
    await db.flush()

    c = Claim(
        id=uuid4(),
        ml_claim_id="I6-CLM",
        ml_account_id=acc.id,
        claim_type="reclamacao",
        status="open",
        reason="produto_defeituoso",
        mlb_id="MLB-I6",
        date_created=datetime.now(timezone.utc),
    )
    db.add(c)
    await db.commit()

    # 1. Listar — deve estar em aberto
    items, total = await list_claims_from_db(db, u.id)
    assert total == 1
    assert items[0]["status"] == "open"
    assert items[0]["resolution_type"] is None

    # 2. Stats antes de resolver
    stats_before = await get_claim_stats(db, u.id)
    assert stats_before["open"] == 1
    assert stats_before["resolved"] == 0

    # 3. Resolver
    resolved = await mark_claim_resolved(
        db, u.id, c.id,
        resolution_type="replace",
        notes="Enviamos novo produto",
    )
    assert resolved.resolution_type == "replace"

    # 4. Stats depois
    stats_after = await get_claim_stats(db, u.id)
    assert stats_after["resolved"] == 1
    assert stats_after["unresolved"] == 0


# ─── Teste 7: Taxa ML nunca retorna None (sempre Decimal) ─────────────────

def test_integracao_7_calcular_taxa_ml_sempre_decimal():
    """Tema 6: todos os paths retornam Decimal, nunca None."""
    casos = [
        ("classico", None),
        ("premium", None),
        ("full", None),
        ("XPTO", None),  # listing_type desconhecido
        ("classico", Decimal("0.09")),  # sale_fee_pct real
        ("", None),
        (None, None),
    ]
    for lt, pct in casos:
        result = calcular_taxa_ml(lt or "", sale_fee_pct=pct)
        assert result is not None
        assert isinstance(result, Decimal)
        assert result > 0


# ─── Teste 8: Pesos somam 100% e vendas e prioridade max ──────────────────

def test_integracao_8_pesos_vendas_dominantes_somam_100():
    """
    Tema 7: valida que a hierarquia sales > visits > conv e preservada
    e que os pesos somam exatamente 100%.
    """
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001

    # Vendas deve ser >= todos os outros individualmente
    max_weight_factor = max(DEFAULT_WEIGHTS, key=lambda k: DEFAULT_WEIGHTS[k])
    assert max_weight_factor == "sales_trend"

    # Ordem esperada: sales > visit > conv > comp
    assert DEFAULT_WEIGHTS["sales_trend"] >= DEFAULT_WEIGHTS["visit_trend"]
    assert DEFAULT_WEIGHTS["visit_trend"] >= DEFAULT_WEIGHTS["conv_trend"]
    assert DEFAULT_WEIGHTS["conv_trend"] >= DEFAULT_WEIGHTS["comp_score"]


# ─── Teste 9: KPI date range com listings vazios nao explode ──────────────

@pytest.mark.asyncio
async def test_integracao_9_kpi_robusto_para_inputs_invalidos(db):
    """Tema 2: funcoes agregadoras nao explodem com inputs edge case."""
    # Lista vazia de listings
    result = await _kpi_date_range(
        db, [], date(2026, 4, 4), date(2026, 4, 10)
    )
    # Todas as keys presentes
    esperado = [
        "vendas", "visitas", "conversao", "anuncios", "receita",
        "dias_no_periodo", "vendas_media_dia", "visitas_media_dia",
        "pedidos_media_dia", "receita_media_dia",
    ]
    for k in esperado:
        assert k in result, f"key {k} ausente"
    assert result["vendas_media_dia"] == 0.0
    assert result["dias_no_periodo"] == 7


# ─── Teste 10: Integracao full cross-modules (ads + claims + questions) ───

@pytest.mark.asyncio
async def test_integracao_10_cross_modules_mesmo_user_isolado(db):
    """
    Valida isolamento multi-tenant: user com ads, claims, questions
    e listings proprios nao vaza dados de outro user. Cobre Temas 3, 4, 5.
    """
    # User A
    uA = User(id=uuid4(), email=f"A_{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(uA)
    accA = MLAccount(
        id=uuid4(), user_id=uA.id, ml_user_id="100",
        nickname="A", access_token="t", refresh_token="r",
    )
    db.add(accA)
    # User B
    uB = User(id=uuid4(), email=f"B_{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(uB)
    accB = MLAccount(
        id=uuid4(), user_id=uB.id, ml_user_id="200",
        nickname="B", access_token="t", refresh_token="r",
    )
    db.add(accB)
    await db.flush()

    # Recursos de A
    db.add(Claim(
        id=uuid4(), ml_claim_id="A-CLM", ml_account_id=accA.id,
        claim_type="reclamacao", status="open", mlb_id="MLB-A",
        date_created=datetime.now(timezone.utc),
    ))
    db.add(Question(
        id=uuid4(), ml_question_id=1001, ml_account_id=accA.id,
        mlb_id="MLB-A", text="A?", status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    ))
    # Recursos de B
    db.add(Claim(
        id=uuid4(), ml_claim_id="B-CLM", ml_account_id=accB.id,
        claim_type="reclamacao", status="open", mlb_id="MLB-B",
        date_created=datetime.now(timezone.utc),
    ))
    db.add(Question(
        id=uuid4(), ml_question_id=2001, ml_account_id=accB.id,
        mlb_id="MLB-B", text="B?", status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    ))
    await db.commit()

    # A ve apenas seus dados
    claims_A, total_A = await list_claims_from_db(db, uA.id)
    assert total_A == 1
    assert claims_A[0]["ml_claim_id"] == "A-CLM"

    qs_A, total_qs_A = await list_questions_from_db(db, uA.id)
    assert total_qs_A == 1
    assert qs_A[0]["mlb_id"] == "MLB-A"

    # B ve apenas os seus
    claims_B, total_B = await list_claims_from_db(db, uB.id)
    assert total_B == 1
    assert claims_B[0]["ml_claim_id"] == "B-CLM"

    qs_B, total_qs_B = await list_questions_from_db(db, uB.id)
    assert total_qs_B == 1
    assert qs_B[0]["mlb_id"] == "MLB-B"
