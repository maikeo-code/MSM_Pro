"""
Testes para intel/pricing/service_report.py — funções puras de HTML

Ciclo 13 do auto-learning — cobertura alvo:
- service_report.py: 52.72% → 85%+
  (funções não cobertas: _product_of_the_day_card, _listing_card,
   _alerts_section, build_daily_report_html)

Estratégia: todas são funções puras — chamadas diretas sem DB/HTTP.
"""
import os
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ─── Helper: dicts de entrada ────────────────────────────────────────────────


def _periods(
    conv_today=2.5, conv_yest=2.0, conv_7d=3.0, conv_15d=2.8,
    visits_today=100, visits_yest=90,
    sales_today=5, sales_yest=4, sales_7d=30, sales_15d=55
):
    return {
        "today":     {"conversion": conv_today, "visits": visits_today, "sales_today": sales_today},
        "yesterday": {"conversion": conv_yest,  "visits": visits_yest,  "sales_today": sales_yest},
        "last_7d":   {"conversion": conv_7d,    "visits": visits_today * 7, "sales_today": sales_7d},
        "last_15d":  {"conversion": conv_15d,   "visits": visits_today * 15, "sales_today": sales_15d},
    }


def _rec(
    mlb_id="MLB123456789",
    sku="SKU-001",
    title="Produto de Teste para Relatorio",
    thumbnail="",
    current_price=99.90,
    stock=20,
    stock_days=15.0,
    health_score=75,
    action="hold",
    suggested_price=99.90,
    confidence="high",
    reasoning="Manter preço atual.",
    sparkline_values=None,
    opportunity_alert=None,
    periods=None,
):
    return {
        "mlb_id": mlb_id,
        "sku": sku,
        "title": title,
        "thumbnail": thumbnail,
        "current_price": current_price,
        "stock": stock,
        "stock_days_projection": stock_days,
        "health_score": health_score,
        "periods": periods or _periods(),
        "recommendation": {
            "action": action,
            "suggested_price": suggested_price,
            "confidence": confidence,
            "reasoning": reasoning,
            "confidence_score": 0.85,
        },
        "sparkline_values": sparkline_values or [1.0, 2.0, 3.0, 2.5, 2.8, 3.1, 3.0],
        "opportunity_alert": opportunity_alert,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: _product_of_the_day_card
# ═══════════════════════════════════════════════════════════════════════════════


class TestProductOfTheDayCard:

    def test_rec_none_retorna_vazio(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        result = _product_of_the_day_card(None)
        assert result == ""

    def test_rec_valido_retorna_html(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        rec = _rec(mlb_id="MLB111", title="Produto Destaque")
        result = _product_of_the_day_card(rec)
        assert isinstance(result, str)
        assert len(result) > 50
        assert "MLB111" in result

    def test_titulo_truncado_em_60_chars(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        longo = "A" * 80
        rec = _rec(title=longo)
        result = _product_of_the_day_card(rec)
        assert "A" * 61 not in result  # truncado em 60

    def test_sem_thumbnail_sem_img_tag(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        rec = _rec(thumbnail="")
        result = _product_of_the_day_card(rec)
        assert "<img" not in result

    def test_com_thumbnail_tem_img_tag(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        rec = _rec(thumbnail="https://example.com/img.jpg")
        result = _product_of_the_day_card(rec)
        assert "<img" in result
        assert "https://example.com/img.jpg" in result

    def test_produto_do_dia_label_presente(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        rec = _rec()
        result = _product_of_the_day_card(rec)
        assert "Produto do Dia" in result

    def test_melhoria_de_conversao_exibida(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        periods = _periods(conv_7d=5.0, conv_15d=3.0)
        rec = _rec(periods=periods)
        result = _product_of_the_day_card(rec)
        # Conversão melhorou 2pp → deve aparecer +2.00pp
        assert "+2.00pp" in result

    def test_mlb_id_na_saida(self):
        from app.intel.pricing.service_report import _product_of_the_day_card
        rec = _rec(mlb_id="MLB999888777")
        result = _product_of_the_day_card(rec)
        assert "MLB999888777" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: _listing_card
# ═══════════════════════════════════════════════════════════════════════════════


class TestListingCard:

    def test_retorna_string_html(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec())
        assert isinstance(result, str)
        assert len(result) > 100

    def test_mlb_id_presente(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(mlb_id="MLB000111222"))
        assert "MLB000111222" in result

    def test_sku_presente(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(sku="SKU-TESTE-99"))
        assert "SKU-TESTE-99" in result

    def test_titulo_truncado_em_65(self):
        from app.intel.pricing.service_report import _listing_card
        titulo_longo = "X" * 80
        result = _listing_card(_rec(title=titulo_longo))
        assert "X" * 66 not in result

    def test_sem_thumbnail_placeholder(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(thumbnail=""))
        # placeholder com "?"
        assert "?" in result

    def test_com_thumbnail_img_tag(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(thumbnail="https://example.com/t.jpg"))
        assert "<img" in result

    def test_acao_hold(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(action="hold"))
        assert "MANTER" in result

    def test_acao_increase(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(action="increase"))
        assert "AUMENTAR" in result

    def test_acao_decrease(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(action="decrease"))
        assert "DIMINUIR" in result

    def test_stock_days_alto(self):
        from app.intel.pricing.service_report import _listing_card
        # stock_days > 10 → verde
        result = _listing_card(_rec(stock_days=30.0))
        assert "30" in result

    def test_stock_days_critico(self):
        from app.intel.pricing.service_report import _listing_card
        # stock_days < 5 → vermelho
        result = _listing_card(_rec(stock_days=3.0))
        assert "3" in result

    def test_stock_days_none_sem_projecao(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(stock_days=None))
        assert "Projecao" not in result

    def test_opportunity_alert_presente(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(opportunity_alert="Alta demanda detectada!"))
        assert "Alta demanda detectada!" in result

    def test_opportunity_alert_ausente(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(opportunity_alert=None))
        # Sem alerta, não deve quebrar
        assert isinstance(result, str)

    def test_sparkline_com_valores(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(sparkline_values=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]))
        assert isinstance(result, str)

    def test_sparkline_sem_valores(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(sparkline_values=[]))
        assert isinstance(result, str)

    def test_confianca_alta(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(confidence="high"))
        assert "ALTA" in result

    def test_confianca_media(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(confidence="medium"))
        assert "MEDIA" in result

    def test_confianca_baixa(self):
        from app.intel.pricing.service_report import _listing_card
        result = _listing_card(_rec(confidence="low"))
        assert "BAIXA" in result

    def test_sem_sku_usa_sem_sku(self):
        from app.intel.pricing.service_report import _listing_card
        rec = _rec()
        rec["sku"] = None
        result = _listing_card(rec)
        assert "sem-sku" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3: _alerts_section
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertsSection:

    def test_sem_alertas_retorna_vazio(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [_rec(stock=20, opportunity_alert=None)]
        result = _alerts_section(recs)
        assert result == ""

    def test_estoque_critico_abaixo_5(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [_rec(mlb_id="MLB_CRIT", stock=3, opportunity_alert=None)]
        result = _alerts_section(recs)
        assert "Estoque Critico" in result
        assert "MLB_CRIT" in result

    def test_estoque_zero_nao_aparece_em_critico(self):
        from app.intel.pricing.service_report import _alerts_section
        # stock=0 não entra na lista (condição é 0 < stock < 5)
        recs = [_rec(stock=0, opportunity_alert=None)]
        result = _alerts_section(recs)
        assert result == ""

    def test_estoque_exatamente_5_nao_critico(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [_rec(stock=5, opportunity_alert=None)]
        result = _alerts_section(recs)
        assert result == ""

    def test_oportunidade_detectada(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [_rec(mlb_id="MLB_OPP", stock=20, opportunity_alert="Alta demanda vs baixa conversão")]
        result = _alerts_section(recs)
        assert "Oportunidades Detectadas" in result
        assert "MLB_OPP" in result

    def test_oportunidades_limitadas_a_5(self):
        from app.intel.pricing.service_report import _alerts_section
        # 8 oportunidades → somente 5 devem aparecer
        recs = [
            _rec(mlb_id=f"MLB{i:03d}", stock=20, opportunity_alert=f"Oportunidade {i}")
            for i in range(8)
        ]
        result = _alerts_section(recs)
        assert "Oportunidades Detectadas" in result
        # Primeiros 5 aparecem
        assert "Oportunidade 0" in result
        assert "Oportunidade 4" in result
        # Depois do 5 não aparece (limite)
        assert "Oportunidade 7" not in result

    def test_ambos_estoque_e_oportunidade(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [
            _rec(mlb_id="MLB_CRIT", stock=2, opportunity_alert="Oportunidade aqui"),
        ]
        result = _alerts_section(recs)
        assert "Estoque Critico" in result
        assert "Oportunidades Detectadas" in result

    def test_multiplos_estoques_criticos(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [
            _rec(mlb_id="MLB001", stock=1),
            _rec(mlb_id="MLB002", stock=3),
            _rec(mlb_id="MLB003", stock=20),  # não é crítico
        ]
        result = _alerts_section(recs)
        assert "MLB001" in result
        assert "MLB002" in result
        assert "MLB003" not in result

    def test_alertas_gerais_label(self):
        from app.intel.pricing.service_report import _alerts_section
        recs = [_rec(stock=1)]
        result = _alerts_section(recs)
        assert "Alertas Gerais" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4: build_daily_report_html
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildDailyReportHtml:

    def _make_summary(self, total=5, inc=2, dec=1, hold=2):
        return {
            "total_listings": total,
            "increase_count": inc,
            "decrease_count": dec,
            "hold_count": hold,
            "total_vendas": 50,
            "total_visitas": 1200,
            "conversao_media": 3.5,
            "receita_total": 5000.0,
            "vendas_var": 10.0,
            "visitas_var": -5.0,
            "conversao_var": 2.0,
            "receita_var": 15.0,
        }

    def test_retorna_html_valido(self):
        from app.intel.pricing.service_report import build_daily_report_html
        recs = [_rec()]
        summary = self._make_summary()
        result = build_daily_report_html(recs, summary, date(2026, 4, 15))
        assert "<!DOCTYPE html>" in result
        assert "</html>" in result

    def test_data_formatada(self):
        from app.intel.pricing.service_report import build_daily_report_html
        recs = [_rec()]
        summary = self._make_summary()
        result = build_daily_report_html(recs, summary, date(2026, 4, 15))
        assert "15/04/2026" in result

    def test_kpi_cards_presentes(self):
        from app.intel.pricing.service_report import build_daily_report_html
        recs = [_rec()]
        summary = self._make_summary()
        result = build_daily_report_html(recs, summary, date(2026, 4, 15))
        assert "Vendas" in result
        assert "Visitas" in result
        assert "Conversao" in result
        assert "Receita" in result

    def test_acoes_resumidas(self):
        from app.intel.pricing.service_report import build_daily_report_html
        recs = [_rec()]
        summary = self._make_summary(inc=3, dec=2, hold=1)
        result = build_daily_report_html(recs, summary, date(2026, 4, 15))
        assert "aumentar" in result
        assert "diminuir" in result
        assert "manter" in result

    def test_produto_do_dia_presente_quando_melhoria(self):
        from app.intel.pricing.service_report import build_daily_report_html
        # rec com melhoria de conversão 7d vs 15d
        periods = _periods(conv_7d=5.0, conv_15d=2.0)
        rec = _rec(periods=periods)
        summary = self._make_summary()
        result = build_daily_report_html([rec], summary, date(2026, 4, 15))
        assert "Produto do Dia" in result

    def test_lista_vazia_de_recs(self):
        from app.intel.pricing.service_report import build_daily_report_html
        summary = self._make_summary(total=0, inc=0, dec=0, hold=0)
        result = build_daily_report_html([], summary, date(2026, 4, 15))
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result

    def test_ordenacao_por_sku(self):
        from app.intel.pricing.service_report import build_daily_report_html
        rec_b = _rec(mlb_id="MLB001", sku="B-SKU")
        rec_a = _rec(mlb_id="MLB002", sku="A-SKU")
        summary = self._make_summary()
        result = build_daily_report_html([rec_b, rec_a], summary, date(2026, 4, 15))
        # A-SKU deve aparecer antes de B-SKU no HTML
        pos_a = result.index("A-SKU")
        pos_b = result.index("B-SKU")
        assert pos_a < pos_b

    def test_html_contem_anuncio(self):
        from app.intel.pricing.service_report import build_daily_report_html
        rec = _rec(mlb_id="MLB_UNICO")
        summary = self._make_summary()
        result = build_daily_report_html([rec], summary, date(2026, 4, 15))
        assert "MLB_UNICO" in result

    def test_multiplos_anuncios(self):
        from app.intel.pricing.service_report import build_daily_report_html
        recs = [
            _rec(mlb_id="MLB001", sku="SKU-A"),
            _rec(mlb_id="MLB002", sku="SKU-B"),
            _rec(mlb_id="MLB003", sku="SKU-C"),
        ]
        summary = self._make_summary(total=3)
        result = build_daily_report_html(recs, summary, date(2026, 4, 15))
        assert "MLB001" in result
        assert "MLB002" in result
        assert "MLB003" in result

    def test_sem_alertas_sem_secao_alertas(self):
        from app.intel.pricing.service_report import build_daily_report_html
        rec = _rec(stock=50, opportunity_alert=None)
        summary = self._make_summary()
        result = build_daily_report_html([rec], summary, date(2026, 4, 15))
        assert "Alertas Gerais" not in result

    def test_com_estoque_critico_secao_alertas(self):
        from app.intel.pricing.service_report import build_daily_report_html
        rec = _rec(stock=2, opportunity_alert=None)
        summary = self._make_summary()
        result = build_daily_report_html([rec], summary, date(2026, 4, 15))
        assert "Alertas Gerais" in result
