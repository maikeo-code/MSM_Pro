"""
Report Builder para o Daily Intel Report.

Monta o HTML completo do email diario de inteligencia de precos.
Cada anuncio recebe um card com:
  - Thumbnail + SKU + MLB + titulo
  - Metricas atuais (preco, estoque, projecao)
  - Conversao e visitas com variacao vs ontem
  - Comparativo de periodos (ontem / 7d / 15d)
  - Recomendacao colorida (aumentar / diminuir / manter)
  - Health Score (barra de progresso)
  - Sparkline SVG (conversao 7 dias)

100% Python — sem IA, sem acesso a banco.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cores e constantes
# ---------------------------------------------------------------------------

_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
_BG = "#f1f5f9"
_HEADER_BG = "#1e40af"
_GREEN = "#22c55e"
_RED = "#ef4444"
_GRAY = "#94a3b8"
_BLUE = "#3b82f6"
_DARK = "#1e293b"

_ACTION_STYLES = {
    "increase": {
        "bg": "#f0fdf4",
        "border": "#22c55e",
        "label": "AUMENTAR",
        "label_bg": "#dcfce7",
        "label_color": "#15803d",
    },
    "decrease": {
        "bg": "#fef2f2",
        "border": "#ef4444",
        "label": "DIMINUIR",
        "label_bg": "#fee2e2",
        "label_color": "#b91c1c",
    },
    "hold": {
        "bg": "#f8fafc",
        "border": "#94a3b8",
        "label": "MANTER",
        "label_bg": "#f1f5f9",
        "label_color": "#475569",
    },
}

_CONFIDENCE_LABELS = {
    "high": "ALTA",
    "medium": "MEDIA",
    "low": "BAIXA",
}

_RISK_LABELS = {
    "low": "BAIXO",
    "medium": "MEDIO",
    "high": "ALTO",
}

FRONTEND_URL = "https://msmprofrontend-production.up.railway.app"


# ---------------------------------------------------------------------------
# Sparkline SVG
# ---------------------------------------------------------------------------


def _build_sparkline_svg(values: list[float], color: str = "#22c55e") -> str:
    """
    Gera SVG inline de sparkline para 7 dias de dados.

    Retorna string SVG que pode ser embeddada diretamente no HTML.
    Width: 120px, Height: 30px.

    Se menos de 2 valores, retorna string vazia.
    """
    if len(values) < 2:
        return ""

    width = 120
    height = 30
    padding = 2

    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val != min_val else 1.0

    points: list[str] = []
    n = len(values)
    for i, v in enumerate(values):
        x = padding + (i / (n - 1)) * (width - 2 * padding)
        y = padding + (1 - (v - min_val) / val_range) * (height - 2 * padding)
        points.append(f"{x:.1f},{y:.1f}")

    polyline_points = " ".join(points)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:inline-block;vertical-align:middle;">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'points="{polyline_points}"/>'
        f"</svg>"
    )
    return svg


def _sparkline_with_fallback(values: list[float]) -> str:
    """
    Gera sparkline SVG com fallback de texto para email clients que nao suportam SVG.

    Retorna HTML que mostra SVG se suportado, ou texto indicativo.
    """
    if len(values) < 2:
        return '<span style="color:#94a3b8;font-size:11px;">sem dados</span>'

    # Determina tendencia
    first_half = sum(values[: len(values) // 2]) / max(len(values) // 2, 1)
    second_half = sum(values[len(values) // 2 :]) / max(
        len(values) - len(values) // 2, 1
    )

    if second_half > first_half * 1.05:
        color = _GREEN
        trend_text = "subindo"
        arrow = "&#8599;"  # ↗
    elif second_half < first_half * 0.95:
        color = _RED
        trend_text = "caindo"
        arrow = "&#8600;"  # ↘
    else:
        color = _GRAY
        trend_text = "estavel"
        arrow = "&#8594;"  # →

    svg = _build_sparkline_svg(values, color=color)

    # Fallback: se SVG nao renderizar, mostra texto
    return (
        f'<span style="display:inline-block;">'
        f"{svg}"
        f'<span style="font-size:10px;color:{color};margin-left:4px;">'
        f"{arrow} {trend_text}</span>"
        f"</span>"
    )


# ---------------------------------------------------------------------------
# Helpers de formatacao
# ---------------------------------------------------------------------------


def _fmt_currency(value: float) -> str:
    """Formata valor como moeda brasileira."""
    if value >= 1000:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value:.2f}".replace(".", ",")


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _var_arrow(current: float, previous: float) -> str:
    """Gera seta colorida de variacao."""
    if previous == 0:
        return ""
    diff_pct = (current - previous) / previous * 100
    if abs(diff_pct) < 0.5:
        return f'<span style="color:{_GRAY};font-size:11px;">= {abs(diff_pct):.1f}%</span>'
    if diff_pct > 0:
        return (
            f'<span style="color:{_GREEN};font-weight:600;font-size:11px;">'
            f"&#9650; {diff_pct:.1f}%</span>"
        )
    return (
        f'<span style="color:{_RED};font-weight:600;font-size:11px;">'
        f"&#9660; {abs(diff_pct):.1f}%</span>"
    )


def _health_bar(score: int) -> str:
    """Gera barra de progresso colorida para health score."""
    if score >= 70:
        bar_color = _GREEN
    elif score >= 40:
        bar_color = "#f59e0b"  # amber
    else:
        bar_color = _RED

    return (
        f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">'
        f'<span style="font-size:11px;color:#64748b;white-space:nowrap;">Health Score</span>'
        f'<div style="flex:1;background:#e2e8f0;border-radius:4px;height:8px;min-width:80px;">'
        f'<div style="width:{score}%;background:{bar_color};border-radius:4px;height:8px;">'
        f"</div></div>"
        f'<span style="font-size:12px;font-weight:700;color:{bar_color};">{score}</span>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def _build_summary(recommendations: list[dict]) -> dict:
    """
    Calcula metricas de resumo (totais do dia).

    Retorna dict com:
        total_vendas, total_visitas, conversao_media, receita_total,
        vendas_var, visitas_var, conversao_var, receita_var,
        increase_count, decrease_count, hold_count, total_listings
    """
    total_vendas = 0
    total_visitas = 0
    total_receita = 0.0
    vendas_ontem = 0
    visitas_ontem = 0
    receita_ontem = 0.0
    increase_count = 0
    decrease_count = 0
    hold_count = 0

    for rec in recommendations:
        periods = rec.get("periods", {})
        today = periods.get("today", {})
        yesterday = periods.get("yesterday", {})

        total_vendas += today.get("sales", 0)
        total_visitas += today.get("visits", 0)
        total_receita += today.get("revenue", 0.0)

        vendas_ontem += yesterday.get("sales", 0)
        visitas_ontem += yesterday.get("visits", 0)
        receita_ontem += yesterday.get("revenue", 0.0)

        action = rec.get("recommendation", {}).get("action", "hold")
        if action == "increase":
            increase_count += 1
        elif action == "decrease":
            decrease_count += 1
        else:
            hold_count += 1

    conversao_media = (
        round(total_vendas / total_visitas * 100, 2) if total_visitas > 0 else 0.0
    )
    conversao_ontem = (
        round(vendas_ontem / visitas_ontem * 100, 2) if visitas_ontem > 0 else 0.0
    )

    def _calc_var(current, previous):
        if previous > 0:
            return round((current - previous) / previous * 100, 1)
        return None

    return {
        "total_vendas": total_vendas,
        "total_visitas": total_visitas,
        "conversao_media": conversao_media,
        "receita_total": total_receita,
        "vendas_var": _calc_var(total_vendas, vendas_ontem),
        "visitas_var": _calc_var(total_visitas, visitas_ontem),
        "conversao_var": _calc_var(conversao_media, conversao_ontem),
        "receita_var": _calc_var(total_receita, receita_ontem),
        "increase_count": increase_count,
        "decrease_count": decrease_count,
        "hold_count": hold_count,
        "total_listings": len(recommendations),
    }


# ---------------------------------------------------------------------------
# Geracao de HTML dos componentes
# ---------------------------------------------------------------------------


def _kpi_card(label: str, value: str, var_pct: float | None) -> str:
    """Gera um card KPI com variacao."""
    var_html = ""
    if var_pct is not None:
        if var_pct > 0:
            var_html = (
                f'<span style="color:{_GREEN};font-size:12px;font-weight:600;">'
                f"&#9650; {var_pct:.1f}%</span>"
            )
        elif var_pct < 0:
            var_html = (
                f'<span style="color:{_RED};font-size:12px;font-weight:600;">'
                f"&#9660; {abs(var_pct):.1f}%</span>"
            )
        else:
            var_html = (
                f'<span style="color:{_GRAY};font-size:12px;">= 0%</span>'
            )

    return (
        f'<td style="background:white;padding:14px 16px;border-radius:8px;'
        f'border:1px solid #e2e8f0;text-align:center;width:25%;">'
        f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:22px;font-weight:700;color:{_DARK};">{value}</div>'
        f'<div style="margin-top:2px;">{var_html}</div>'
        f"</td>"
    )


def _product_of_the_day_card(rec: dict | None) -> str:
    """Gera card dourado do Produto do Dia."""
    if rec is None:
        return ""

    mlb_id = rec.get("mlb_id", "N/A")
    title = rec.get("title", "")[:60]
    periods = rec.get("periods", {})
    conv_7d = periods.get("last_7d", {}).get("conversion", 0)
    conv_15d = periods.get("last_15d", {}).get("conversion", 0)
    improvement = conv_7d - conv_15d

    thumbnail = rec.get("thumbnail", "")
    thumb_html = ""
    if thumbnail:
        thumb_html = (
            f'<img src="{thumbnail}" alt="" '
            f'style="width:60px;height:60px;border-radius:8px;object-fit:cover;'
            f'border:2px solid #fbbf24;" />'
        )

    return (
        f'<table cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="background:linear-gradient(135deg,#fefce8,#fef9c3);'
        f"border:2px solid #fbbf24;border-radius:10px;margin:16px 0;\">"
        f"<tr><td style=\"padding:16px;\">"
        f'<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
        f'<td style="width:70px;vertical-align:top;">{thumb_html}</td>'
        f'<td style="padding-left:12px;vertical-align:top;">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;'
        f'color:#92400e;font-weight:700;margin-bottom:4px;">'
        f"&#9733; Produto do Dia</div>"
        f'<div style="font-size:14px;font-weight:700;color:{_DARK};margin-bottom:4px;">'
        f"{title}</div>"
        f'<div style="font-size:12px;color:#78716c;">{mlb_id}</div>'
        f'<div style="margin-top:8px;font-size:13px;color:#92400e;">'
        f"Conversao: {_fmt_pct(conv_15d)} &#8594; "
        f'<strong style="color:#15803d;">{_fmt_pct(conv_7d)}</strong> '
        f'<span style="background:#dcfce7;color:#15803d;padding:1px 6px;'
        f'border-radius:10px;font-size:11px;font-weight:700;">'
        f"+{improvement:.2f}pp</span></div>"
        f"</td></tr></table>"
        f"</td></tr></table>"
    )


def _listing_card(rec: dict) -> str:
    """Gera card completo de um anuncio."""
    mlb_id = rec.get("mlb_id", "N/A")
    sku = rec.get("sku") or "sem-sku"
    title = rec.get("title", "")[:65]
    thumbnail = rec.get("thumbnail", "")
    current_price = rec.get("current_price", 0)
    stock = rec.get("stock", 0)
    stock_days = rec.get("stock_days_projection")
    health = rec.get("health_score", 0)
    periods = rec.get("periods", {})
    recommendation = rec.get("recommendation", {})
    sparkline_values = rec.get("sparkline_values", [])
    opportunity_alert = rec.get("opportunity_alert")

    # Thumbnail
    thumb_html = ""
    if thumbnail:
        thumb_html = (
            f'<img src="{thumbnail}" alt="" '
            f'style="width:50px;height:50px;border-radius:6px;object-fit:cover;" />'
        )
    else:
        thumb_html = (
            f'<div style="width:50px;height:50px;border-radius:6px;'
            f'background:#e2e8f0;display:flex;align-items:center;'
            f'justify-content:center;font-size:20px;color:#94a3b8;">?</div>'
        )

    # Metricas de periodo
    p_today = periods.get("today", {})
    p_yesterday = periods.get("yesterday", {})
    p_7d = periods.get("last_7d", {})
    p_15d = periods.get("last_15d", {})

    conv_today = p_today.get("conversion", 0)
    conv_yesterday = p_yesterday.get("conversion", 0)
    visits_today = p_today.get("visits", 0)
    visits_yesterday = p_yesterday.get("visits", 0)

    # Projecao de estoque
    stock_proj_html = ""
    if stock_days is not None:
        proj_color = _GREEN if stock_days > 10 else (_RED if stock_days < 5 else "#f59e0b")
        stock_proj_html = (
            f' | Projecao: <span style="color:{proj_color};font-weight:600;">'
            f"{stock_days:.0f} dias</span>"
        )

    # Conversao com seta
    conv_arrow = _var_arrow(conv_today, conv_yesterday)

    # Visitas com seta
    visits_arrow = _var_arrow(visits_today, visits_yesterday)

    # Comparativo mini-tabela
    comparativo = (
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'style="width:100%;margin-top:8px;font-size:11px;">'
        f"<tr>"
        f'<td style="padding:3px 6px;background:#f8fafc;color:#64748b;font-weight:600;'
        f'border-radius:4px 0 0 4px;">Periodo</td>'
        f'<td style="padding:3px 6px;background:#f8fafc;color:#64748b;text-align:center;">Ontem</td>'
        f'<td style="padding:3px 6px;background:#f8fafc;color:#64748b;text-align:center;">7d</td>'
        f'<td style="padding:3px 6px;background:#f8fafc;color:#64748b;text-align:center;'
        f'border-radius:0 4px 4px 0;">15d</td>'
        f"</tr>"
        f"<tr>"
        f'<td style="padding:3px 6px;color:#374151;">Conversao</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{_fmt_pct(p_yesterday.get("conversion", 0))}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{_fmt_pct(p_7d.get("conversion", 0))}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{_fmt_pct(p_15d.get("conversion", 0))}</td>'
        f"</tr>"
        f"<tr>"
        f'<td style="padding:3px 6px;color:#374151;">Vendas</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_yesterday.get("sales", 0)}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_7d.get("sales", 0)}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_15d.get("sales", 0)}</td>'
        f"</tr>"
        f"<tr>"
        f'<td style="padding:3px 6px;color:#374151;">Visitas</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_yesterday.get("visits", 0)}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_7d.get("visits", 0)}</td>'
        f'<td style="padding:3px 6px;text-align:center;color:#374151;">'
        f'{p_15d.get("visits", 0)}</td>'
        f"</tr>"
        f"</table>"
    )

    # Sparkline
    sparkline_html = ""
    if sparkline_values:
        sparkline_html = (
            f'<div style="margin-top:6px;">'
            f'<span style="font-size:10px;color:#64748b;">Conv. 7d: </span>'
            f"{_sparkline_with_fallback(sparkline_values)}"
            f"</div>"
        )

    # Recomendacao
    action = recommendation.get("action", "hold")
    style = _ACTION_STYLES.get(action, _ACTION_STYLES["hold"])
    suggested_price = recommendation.get("suggested_price", 0)
    price_change_pct = recommendation.get("price_change_pct", 0)
    confidence = recommendation.get("confidence", "low")
    risk = recommendation.get("risk_level", "low")
    reasoning = recommendation.get("reasoning", "")
    estimated_daily_profit = recommendation.get("estimated_daily_profit", 0)

    sign = "+" if price_change_pct >= 0 else ""

    rec_html = (
        f'<div style="background:{style["bg"]};border-left:4px solid {style["border"]};'
        f'padding:10px 12px;border-radius:0 6px 6px 0;margin-top:10px;">'
        # Action label
        f'<span style="background:{style["label_bg"]};color:{style["label_color"]};'
        f'padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">'
        f'{style["label"]}</span>'
        # Sugestao
        f'<span style="font-size:13px;color:{_DARK};margin-left:8px;">'
        f"Sugestao: <strong>{_fmt_currency(suggested_price)}</strong> "
        f"({sign}{price_change_pct:.1f}%)</span><br/>"
        # Lucro estimado
        f'<span style="font-size:12px;color:#64748b;margin-top:4px;display:inline-block;">'
        f"Lucro estimado/dia: <strong>{_fmt_currency(estimated_daily_profit)}</strong>"
        f" &nbsp;|&nbsp; "
        f"Confianca: <strong>{_CONFIDENCE_LABELS.get(confidence, confidence)}</strong>"
        f" &nbsp;|&nbsp; "
        f"Risco: <strong>{_RISK_LABELS.get(risk, risk)}</strong>"
        f"</span>"
    )

    # Reasoning
    if reasoning:
        rec_html += (
            f'<div style="font-size:12px;color:#475569;margin-top:6px;'
            f'line-height:1.5;font-style:italic;">'
            f'"{reasoning}"</div>'
        )

    rec_html += "</div>"

    # Opportunity alert
    opportunity_html = ""
    if opportunity_alert:
        opportunity_html = (
            f'<div style="background:#fffbeb;border:1px solid #fde68a;'
            f'border-radius:6px;padding:8px 12px;margin-top:8px;'
            f'font-size:12px;color:#92400e;">'
            f"&#9888; {opportunity_alert}"
            f"</div>"
        )

    # Health bar
    health_html = _health_bar(health) if health else ""

    # Card completo
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" width="100%" '
        f'style="background:white;border:1px solid #e2e8f0;border-radius:8px;'
        f'margin-bottom:12px;">'
        f"<tr><td style=\"padding:16px;\">"
        # Header row: thumb + info
        f'<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
        f'<td style="width:55px;vertical-align:top;">{thumb_html}</td>'
        f'<td style="padding-left:10px;vertical-align:top;">'
        f'<div style="font-size:11px;color:#64748b;">'
        f'<span style="font-weight:600;">{sku}</span> &middot; '
        f'<span style="font-family:monospace;">{mlb_id}</span></div>'
        f'<div style="font-size:14px;font-weight:600;color:{_DARK};margin-top:2px;">'
        f"{title}</div>"
        f'<div style="font-size:12px;color:#64748b;margin-top:4px;">'
        f"Preco Medio: <strong>{_fmt_currency(current_price)}</strong>"
        f" | Estoque: <strong>{stock} un</strong>"
        f"{stock_proj_html}"
        f"</div>"
        f"</td></tr></table>"
        # Metricas
        f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">'
        f'<div style="font-size:12px;color:#374151;">'
        f"CONVERSAO: <strong>{_fmt_pct(conv_today)}</strong> {conv_arrow}"
        f" &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"VISITAS: <strong>{visits_today}</strong> {visits_arrow}"
        f"</div>"
        f"{comparativo}"
        f"{sparkline_html}"
        f"</div>"
        # Recomendacao
        f"{rec_html}"
        f"{opportunity_html}"
        # Health
        f"{health_html}"
        f"</td></tr></table>"
    )


def _alerts_section(recommendations: list[dict]) -> str:
    """Gera secao de alertas gerais (estoque critico + oportunidades)."""
    critical_stock: list[dict] = []
    opportunities: list[str] = []

    for rec in recommendations:
        stock = rec.get("stock", 0)
        mlb_id = rec.get("mlb_id", "")
        title = rec.get("title", "")[:40]

        if 0 < stock < 5:
            critical_stock.append({
                "mlb_id": mlb_id,
                "title": title,
                "stock": stock,
            })

        alert = rec.get("opportunity_alert")
        if alert:
            opportunities.append(f"<strong>{mlb_id}</strong>: {alert}")

    if not critical_stock and not opportunities:
        return ""

    html = (
        '<table cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="margin-top:16px;"><tr><td>'
        '<div style="font-size:14px;font-weight:700;color:#b91c1c;'
        'margin-bottom:10px;padding-bottom:6px;border-bottom:2px solid #fecaca;">'
        "Alertas Gerais</div>"
    )

    if critical_stock:
        items = "".join(
            f'<div style="padding:4px 0;font-size:12px;color:#991b1b;">'
            f'&#9888; <strong>{s["mlb_id"]}</strong> — {s["title"]} — '
            f'<span style="background:#fef2f2;padding:1px 6px;border-radius:8px;'
            f'font-weight:700;">{s["stock"]} un</span></div>'
            for s in critical_stock
        )
        html += (
            f'<div style="background:#fef2f2;border:1px solid #fecaca;'
            f'border-radius:6px;padding:10px 12px;margin-bottom:8px;">'
            f'<div style="font-size:12px;font-weight:600;color:#b91c1c;'
            f'margin-bottom:4px;">Estoque Critico (&lt; 5 un)</div>'
            f"{items}</div>"
        )

    if opportunities:
        opp_items = "".join(
            f'<div style="padding:3px 0;font-size:12px;color:#92400e;">'
            f"&#9733; {opp}</div>"
            for opp in opportunities[:5]
        )
        html += (
            f'<div style="background:#fffbeb;border:1px solid #fde68a;'
            f'border-radius:6px;padding:10px 12px;">'
            f'<div style="font-size:12px;font-weight:600;color:#92400e;'
            f'margin-bottom:4px;">Oportunidades Detectadas</div>'
            f"{opp_items}</div>"
        )

    html += "</td></tr></table>"
    return html


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------


def build_daily_report_html(
    recommendations: list[dict],
    summary: dict,
    report_date: date,
) -> str:
    """
    Monta HTML completo do relatorio diario de inteligencia de precos.

    Args:
        recommendations: lista de dicts enriquecidos com dados do anuncio,
            metricas de periodo, recomendacao (action, suggested_price etc),
            health_score e sparkline_values.
        summary: dict retornado por _build_summary().
        report_date: data do relatorio.

    Returns:
        String HTML completa, pronta para envio por email.
    """
    date_str = report_date.strftime("%d/%m/%Y")
    total = summary.get("total_listings", 0)
    inc = summary.get("increase_count", 0)
    dec = summary.get("decrease_count", 0)
    hold = summary.get("hold_count", 0)

    # KPI cards
    kpi_html = (
        f'<table cellpadding="0" cellspacing="8" border="0" width="100%"><tr>'
        + _kpi_card(
            "Vendas",
            str(summary.get("total_vendas", 0)),
            summary.get("vendas_var"),
        )
        + _kpi_card(
            "Visitas",
            f'{summary.get("total_visitas", 0):,}'.replace(",", "."),
            summary.get("visitas_var"),
        )
        + _kpi_card(
            "Conversao",
            _fmt_pct(summary.get("conversao_media", 0)),
            summary.get("conversao_var"),
        )
        + _kpi_card(
            "Receita",
            _fmt_currency(summary.get("receita_total", 0)),
            summary.get("receita_var"),
        )
        + "</tr></table>"
    )

    # Resumo de acoes
    actions_html = (
        f'<div style="text-align:center;margin:12px 0;font-size:12px;color:#64748b;">'
        f'<span style="background:#dcfce7;color:#15803d;padding:2px 8px;'
        f'border-radius:10px;font-weight:600;">&#9650; {inc} aumentar</span>'
        f" &nbsp; "
        f'<span style="background:#fee2e2;color:#b91c1c;padding:2px 8px;'
        f'border-radius:10px;font-weight:600;">&#9660; {dec} diminuir</span>'
        f" &nbsp; "
        f'<span style="background:#f1f5f9;color:#475569;padding:2px 8px;'
        f'border-radius:10px;font-weight:600;">= {hold} manter</span>'
        f"</div>"
    )

    # Produto do dia: melhor melhoria de conversao 7d vs 15d
    product_of_day = None
    best_improvement = 0
    for rec in recommendations:
        p = rec.get("periods", {})
        conv_7d = p.get("last_7d", {}).get("conversion", 0)
        conv_15d = p.get("last_15d", {}).get("conversion", 0)
        improvement = conv_7d - conv_15d
        if improvement > best_improvement:
            best_improvement = improvement
            product_of_day = rec

    product_of_day_html = _product_of_the_day_card(product_of_day)

    # Ordenar por SKU (sem SKU vai pro final)
    sorted_recs = sorted(
        recommendations,
        key=lambda r: (r.get("sku") or "zzz_" + (r.get("mlb_id") or "")),
    )

    # Cards de anuncios
    listings_html = "".join(_listing_card(rec) for rec in sorted_recs)

    # Alertas gerais
    alerts_html = _alerts_section(recommendations)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Relatorio Diario de Conversoes - MSM_Pro</title>
</head>
<body style="margin:0;padding:20px;background:{_BG};
             font-family:{_FONT};">
  <div style="max-width:640px;margin:0 auto;">

    <!-- Header -->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr><td style="background:linear-gradient(135deg,{_HEADER_BG},{_BLUE});color:white;
                padding:24px 28px;border-radius:12px 12px 0 0;">
      <div style="font-size:20px;font-weight:700;margin:0;">
        Relatorio Diario de Conversoes
      </div>
      <div style="margin-top:6px;opacity:.85;font-size:13px;">
        {date_str} &nbsp;&middot;&nbsp; {total} anuncios ativos
      </div>
    </td></tr>
    </table>

    <!-- Body -->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr><td style="background:#f8fafc;padding:20px 24px;border:1px solid #e2e8f0;border-top:none;">

      <!-- KPI Cards -->
      {kpi_html}

      <!-- Resumo de acoes -->
      {actions_html}

      <!-- Produto do Dia -->
      {product_of_day_html}

      <!-- Lista de Anuncios -->
      <div style="margin-top:16px;">
        <div style="font-size:14px;font-weight:700;color:{_HEADER_BG};
                    margin-bottom:12px;padding-bottom:6px;
                    border-bottom:2px solid {_HEADER_BG}22;">
          Analise por Anuncio
        </div>
        {listings_html}
      </div>

      <!-- Alertas -->
      {alerts_html}

    </td></tr>
    </table>

    <!-- CTA -->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr><td style="background:{_DARK};color:white;padding:20px 24px;text-align:center;">
      <div style="font-size:13px;color:#e2e8f0;margin-bottom:12px;">
        Analise completa com graficos e detalhes no dashboard
      </div>
      <a href="{FRONTEND_URL}/intel"
         style="background:{_BLUE};color:white;text-decoration:none;
                padding:10px 24px;border-radius:8px;font-weight:600;
                font-size:14px;display:inline-block;">
        Acessar Dashboard Intel &#8594;
      </a>
    </td></tr>
    </table>

    <!-- Footer -->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr><td style="background:#0f172a;color:#475569;padding:14px 24px;
                border-radius:0 0 12px 12px;text-align:center;font-size:11px;">
      <div>MSM_Pro — Dashboard de Inteligencia de Vendas Mercado Livre</div>
      <div style="margin-top:4px;font-size:10px;color:#334155;">
        Gerado por IA (Claude) &middot; Recomendacoes nao sao garantia de resultado
      </div>
    </td></tr>
    </table>

  </div>
</body>
</html>"""
