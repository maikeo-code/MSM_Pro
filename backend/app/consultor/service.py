from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.concorrencia.models import Competitor, CompetitorSnapshot
from app.vendas.models import ListingSnapshot
from app.vendas.service import get_kpi_by_period, list_listings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
MAX_LISTINGS = 20

SYSTEM_PROMPT = """Voce e um especialista em vendas no Mercado Livre com mais de 10 anos de experiencia ajudando vendedores brasileiros a maximizar seus resultados.

Seu papel e analisar os dados dos anuncios fornecidos e gerar insights acionaveis e recomendacoes praticas.

Voce recebe dados ricos incluindo historico de 7 dias, concorrentes vinculados, projecao de estoque e taxas reais. Use TODOS esses dados na sua analise.

Foque em:
1. **Performance individual**: identifique anuncios com alta e baixa performance
2. **Tendencias**: analise o historico de 7 dias para identificar tendencias de vendas, visitas e receita (crescendo, caindo, estavel). Destaque mudancas significativas.
3. **Precificacao vs Concorrencia**: quando houver dados de concorrentes, compare precos e sugira ajustes. Indique se o vendedor esta mais caro ou mais barato e o impacto nas vendas.
4. **Margem e Rentabilidade**: use as taxas ML reais e frete quando disponiveis para calcular a margem real. ALERTE sobre produtos com margem negativa ou muito baixa (< 10%).
5. **Estoque**: analise a velocidade de vendas dos ultimos 7 dias e alerte sobre riscos de ruptura. Indique quando o vendedor precisa repor.
6. **Oportunidades**: destaque anuncios com potencial nao explorado (visitas altas, conversao baixa ou preco acima dos concorrentes)
7. **Score de qualidade**: considere o quality_score (0-100) nas recomendacoes. Anuncios com score baixo (<50) precisam de atencao na qualidade do anuncio (fotos, titulo, descricao).
8. **Acoes imediatas**: liste as 3 acoes mais impactantes que o vendedor deve fazer HOJE, com justificativa baseada nos dados.

Seja direto, use numeros e porcentagens reais dos dados, evite jargoes desnecessarios.
Responda sempre em portugues brasileiro."""


async def _buscar_snapshots_7d(
    db: AsyncSession, listing_ids: list[UUID]
) -> dict[UUID, list[dict]]:
    """Busca os snapshots dos ultimos 7 dias para cada listing, agrupados por listing_id."""
    if not listing_ids:
        return {}

    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(ListingSnapshot)
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            ListingSnapshot.captured_at >= cutoff_7d,
        )
        .order_by(ListingSnapshot.listing_id, ListingSnapshot.captured_at.asc())
    )

    snapshots_by_listing: dict[UUID, list[dict]] = {}
    for snap in result.scalars().all():
        lid = snap.listing_id
        if lid not in snapshots_by_listing:
            snapshots_by_listing[lid] = []
        snapshots_by_listing[lid].append({
            "date": snap.captured_at.strftime("%d/%m"),
            "sales": snap.sales_today or 0,
            "visits": snap.visits or 0,
            "revenue": float(snap.revenue) if snap.revenue else 0.0,
            "price": float(snap.price),
            "stock": snap.stock or 0,
            "conversion": float(snap.conversion_rate) if snap.conversion_rate else 0.0,
            "orders": snap.orders_count or 0,
            "cancelled": snap.cancelled_orders or 0,
            "returns": snap.returns_count or 0,
        })

    return snapshots_by_listing


async def _buscar_concorrentes(
    db: AsyncSession, listing_ids: list[UUID]
) -> dict[UUID, list[dict]]:
    """Busca concorrentes vinculados a cada listing com seu ultimo snapshot."""
    if not listing_ids:
        return {}

    # Busca concorrentes ativos
    result = await db.execute(
        select(Competitor)
        .where(
            Competitor.listing_id.in_(listing_ids),
            Competitor.is_active.is_(True),
        )
    )
    competitors = result.scalars().all()

    if not competitors:
        return {}

    competitor_ids = [c.id for c in competitors]

    # Subquery: ultimo snapshot de cada concorrente
    latest_snap_subq = (
        select(
            CompetitorSnapshot.competitor_id,
            func.max(CompetitorSnapshot.captured_at).label("max_captured_at"),
        )
        .where(CompetitorSnapshot.competitor_id.in_(competitor_ids))
        .group_by(CompetitorSnapshot.competitor_id)
        .subquery()
    )

    snaps_result = await db.execute(
        select(CompetitorSnapshot)
        .join(
            latest_snap_subq,
            (CompetitorSnapshot.competitor_id == latest_snap_subq.c.competitor_id)
            & (CompetitorSnapshot.captured_at == latest_snap_subq.c.max_captured_at),
        )
    )
    snap_by_competitor = {
        s.competitor_id: s for s in snaps_result.scalars().all()
    }

    # Agrupa por listing_id
    concorrentes_by_listing: dict[UUID, list[dict]] = {}
    for comp in competitors:
        lid = comp.listing_id
        if lid not in concorrentes_by_listing:
            concorrentes_by_listing[lid] = []

        snap = snap_by_competitor.get(comp.id)
        concorrentes_by_listing[lid].append({
            "mlb_id": comp.mlb_id,
            "title": comp.title or "Sem titulo",
            "price": float(snap.price) if snap else None,
            "sales_delta": snap.sales_delta if snap else None,
            "visits": snap.visits if snap else None,
        })

    return concorrentes_by_listing


def _formatar_historico_7d(snapshots: list[dict]) -> str:
    """Formata historico de 7 dias como texto conciso."""
    if not snapshots:
        return "  Historico 7d: sem dados"

    # Linha de resumo diario
    dias = []
    for s in snapshots[-7:]:  # ultimos 7
        dias.append(
            f"{s['date']}: {s['sales']}v {s['visits']}vis R${s['revenue']:.0f}"
        )
    resumo = " | ".join(dias)

    # Calcula tendencia comparando primeira e segunda metade
    n = len(snapshots)
    if n >= 2:
        mid = n // 2
        first_half = snapshots[:mid]
        second_half = snapshots[mid:]

        avg_sales_1 = sum(s["sales"] for s in first_half) / len(first_half)
        avg_sales_2 = sum(s["sales"] for s in second_half) / len(second_half)
        avg_visits_1 = sum(s["visits"] for s in first_half) / len(first_half)
        avg_visits_2 = sum(s["visits"] for s in second_half) / len(second_half)
        avg_rev_1 = sum(s["revenue"] for s in first_half) / len(first_half)
        avg_rev_2 = sum(s["revenue"] for s in second_half) / len(second_half)

        def trend_symbol(old: float, new: float) -> str:
            if old == 0:
                return "=" if new == 0 else "subindo"
            pct = ((new - old) / old) * 100
            if pct > 10:
                return f"subindo (+{pct:.0f}%)"
            elif pct < -10:
                return f"caindo ({pct:.0f}%)"
            else:
                return "estavel"

        trend_vendas = trend_symbol(avg_sales_1, avg_sales_2)
        trend_visitas = trend_symbol(avg_visits_1, avg_visits_2)
        trend_receita = trend_symbol(avg_rev_1, avg_rev_2)

        tendencia = f"  Tendencia 7d: vendas {trend_vendas}, visitas {trend_visitas}, receita {trend_receita}"
    else:
        tendencia = "  Tendencia 7d: dados insuficientes"

    # Totais 7 dias
    total_vendas = sum(s["sales"] for s in snapshots)
    total_receita = sum(s["revenue"] for s in snapshots)
    total_visitas = sum(s["visits"] for s in snapshots)
    total_cancelados = sum(s["cancelled"] for s in snapshots)
    total_devolucoes = sum(s["returns"] for s in snapshots)

    totais = (
        f"  Totais 7d: {total_vendas} vendas, {total_visitas} visitas, "
        f"R$ {total_receita:.2f} receita"
    )
    if total_cancelados > 0 or total_devolucoes > 0:
        totais += f", {total_cancelados} cancelamentos, {total_devolucoes} devolucoes"

    lines = [
        f"  Historico 7d: {resumo}",
        tendencia,
        totais,
    ]
    return "\n".join(lines)


def _formatar_concorrentes(concorrentes: list[dict], meu_preco: float) -> str:
    """Formata concorrentes vinculados como texto."""
    if not concorrentes:
        return ""

    lines = ["  Concorrentes vinculados:"]
    for c in concorrentes:
        preco_conc = c.get("price")
        if preco_conc is not None:
            diff_pct = ((meu_preco - preco_conc) / preco_conc * 100) if preco_conc > 0 else 0
            sinal = "+" if diff_pct > 0 else ""
            vendas_info = ""
            if c.get("sales_delta") is not None:
                vendas_info = f", {c['sales_delta']} vendas/dia"
            lines.append(
                f"    - [{c['mlb_id']}] {c['title'][:50]}: "
                f"R$ {preco_conc:.2f} (seu preco {sinal}{diff_pct:.1f}% vs concorrente{vendas_info})"
            )
        else:
            lines.append(f"    - [{c['mlb_id']}] {c['title'][:50]}: sem dados de preco")

    return "\n".join(lines)


def _formatar_listing(
    listing: dict,
    historico_7d: list[dict] | None = None,
    concorrentes: list[dict] | None = None,
) -> str:
    """Formata um listing para texto estruturado enviado ao LLM, com contexto enriquecido."""
    snap = listing.get("last_snapshot")

    title = listing.get("title", "Sem titulo")[:60]
    mlb_id = listing.get("mlb_id", "N/A")
    price = listing.get("price")
    listing_type = listing.get("listing_type", "desconhecido")
    voce_recebe = listing.get("voce_recebe")
    sku = listing.get("seller_sku") or listing.get("sku_code") or "N/A"
    quality_score = listing.get("quality_score")

    lines = [f"- [{mlb_id}] {title}"]
    lines.append(f"  Tipo: {listing_type} | SKU: {sku}")

    if price is not None:
        price_float = float(price)
        lines.append(f"  Preco: R$ {price_float:.2f}")

        # Preco original / desconto
        original_price = listing.get("original_price")
        if original_price and float(original_price) > price_float:
            desconto_pct = ((float(original_price) - price_float) / float(original_price)) * 100
            lines.append(f"  Preco original: R$ {float(original_price):.2f} (desconto de {desconto_pct:.0f}%)")

    if voce_recebe is not None:
        lines.append(f"  Voce recebe (liquido): R$ {float(voce_recebe):.2f}")
        if price is not None and float(price) > 0:
            pct_recebe = (float(voce_recebe) / float(price)) * 100
            lines.append(f"  Retencao liquida: {pct_recebe:.1f}% do preco")

    # Quality score
    if quality_score is not None:
        nivel = "Excelente" if quality_score >= 80 else "Bom" if quality_score >= 60 else "Regular" if quality_score >= 40 else "Ruim"
        lines.append(f"  Score de qualidade: {quality_score}/100 ({nivel})")

    if snap:
        stock = snap.get("stock") if isinstance(snap, dict) else getattr(snap, "stock", None)
        visits = snap.get("visits") if isinstance(snap, dict) else getattr(snap, "visits", None)
        sales = snap.get("sales_today") if isinstance(snap, dict) else getattr(snap, "sales_today", None)
        conversion = snap.get("conversion_rate") if isinstance(snap, dict) else getattr(snap, "conversion_rate", None)
        revenue = snap.get("revenue") if isinstance(snap, dict) else getattr(snap, "revenue", None)
        orders = snap.get("orders_count") if isinstance(snap, dict) else getattr(snap, "orders_count", None)
        cancelled = snap.get("cancelled_orders") if isinstance(snap, dict) else getattr(snap, "cancelled_orders", None)
        returns_count = snap.get("returns_count") if isinstance(snap, dict) else getattr(snap, "returns_count", None)
        dias_para_zerar = listing.get("dias_para_zerar")
        participation = listing.get("participacao_pct")
        vendas_var = listing.get("vendas_variacao")
        receita_var = listing.get("receita_variacao")
        rpv = listing.get("rpv")
        taxa_cancel = listing.get("taxa_cancelamento")

        if stock is not None:
            lines.append(f"  Estoque: {stock} unidades")

        # Projecao de estoque enriquecida
        if dias_para_zerar is not None and historico_7d:
            avg_sales_7d = sum(s["sales"] for s in historico_7d) / max(len(historico_7d), 1)
            lines.append(
                f"  Projecao estoque: {stock} un, velocidade 7d: {avg_sales_7d:.1f}/dia, "
                f"zera em ~{dias_para_zerar} dias"
            )
            if dias_para_zerar <= 7:
                lines.append(f"  ALERTA: Estoque critico! Repor URGENTE.")
            elif dias_para_zerar <= 15:
                lines.append(f"  ATENCAO: Estoque baixo. Repor em breve.")
        elif dias_para_zerar is not None:
            lines.append(f"  Dias para zerar estoque: {dias_para_zerar}")

        if visits is not None:
            lines.append(f"  Visitas hoje: {visits}")
        if sales is not None:
            lines.append(f"  Vendas hoje: {sales} unidades")
        if orders is not None and orders > 0:
            lines.append(f"  Pedidos hoje: {orders}")
        if conversion is not None:
            lines.append(f"  Conversao: {float(conversion):.2f}%")
        if revenue is not None:
            lines.append(f"  Receita hoje: R$ {float(revenue):.2f}")
        if rpv is not None:
            lines.append(f"  Receita por visita: R$ {float(rpv):.4f}")
        if participation is not None:
            lines.append(f"  Participacao na receita total: {float(participation):.1f}%")

        # Variacao vs ontem
        if vendas_var is not None or receita_var is not None:
            parts = []
            if vendas_var is not None:
                sinal = "+" if vendas_var > 0 else ""
                parts.append(f"vendas {sinal}{vendas_var:.0f}%")
            if receita_var is not None:
                sinal = "+" if receita_var > 0 else ""
                parts.append(f"receita {sinal}{receita_var:.0f}%")
            lines.append(f"  Variacao vs ontem: {', '.join(parts)}")

        # Cancelamentos e devolucoes
        if cancelled and cancelled > 0:
            lines.append(f"  Cancelamentos hoje: {cancelled}")
        if returns_count and returns_count > 0:
            lines.append(f"  Devolucoes hoje: {returns_count}")
        if taxa_cancel is not None and taxa_cancel > 0:
            lines.append(f"  Taxa cancelamento: {taxa_cancel:.1f}%")
    else:
        lines.append("  Sem dados de snapshot disponiveis")

    # Historico 7 dias
    if historico_7d:
        lines.append(_formatar_historico_7d(historico_7d))

    # Concorrentes
    if concorrentes and price is not None:
        lines.append(_formatar_concorrentes(concorrentes, float(price)))

    return "\n".join(lines)


def _formatar_kpi(kpi: dict) -> str:
    """Formata KPIs para texto estruturado."""
    linhas = ["=== KPIs CONSOLIDADOS ==="]

    periodos = [
        ("hoje", "Hoje"),
        ("ontem", "Ontem"),
        ("anteontem", "Anteontem"),
        ("7dias", "Ultimos 7 dias"),
        ("30dias", "Ultimos 30 dias"),
    ]

    for key, label in periodos:
        periodo = kpi.get(key, {})
        if not periodo:
            continue

        vendas = periodo.get("vendas", 0)
        receita = periodo.get("receita_total", 0)
        visitas = periodo.get("visitas", 0)
        pedidos = periodo.get("pedidos", 0)
        conversao = periodo.get("conversao", 0)
        anuncios = periodo.get("anuncios", 0)

        linhas.append(
            f"{label}: {vendas} vendas | {pedidos} pedidos | R$ {float(receita):.2f} receita | "
            f"{visitas} visitas | {float(conversao):.2f}% conversao | {anuncios} anuncios ativos"
        )

    return "\n".join(linhas)


async def analisar_listings(
    db: AsyncSession,
    user_id: UUID,
    mlb_id: Optional[str] = None,
) -> tuple[str, int]:
    """
    Busca os listings e KPIs do usuario, enriquece com historico 7d e concorrentes,
    formata o contexto e chama a API Claude.
    Retorna (texto_da_analise, quantidade_de_anuncios_analisados).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Consultor IA nao configurado: ANTHROPIC_API_KEY ausente. "
                   "Configure a variavel de ambiente no servidor.",
        )

    # Busca dados base
    listings = await list_listings(db, user_id)
    kpis = await get_kpi_by_period(db, user_id)

    # Filtra por mlb_id se informado
    if mlb_id:
        listings = [l for l in listings if l.get("mlb_id") == mlb_id]
        if not listings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anuncio {mlb_id} nao encontrado.",
            )

    # Limita a 20 anuncios para nao estourar o contexto
    listings_limitados = listings[:MAX_LISTINGS]
    total_analisados = len(listings_limitados)

    # Coleta listing_ids para queries adicionais
    listing_ids = [l["id"] for l in listings_limitados]

    # Busca dados enriquecidos em paralelo (historico 7d + concorrentes)
    historico_7d = await _buscar_snapshots_7d(db, listing_ids)
    concorrentes = await _buscar_concorrentes(db, listing_ids)

    # Monta o prompt do usuario com contexto enriquecido
    kpi_texto = _formatar_kpi(kpis)
    listings_texto = "\n\n".join(
        _formatar_listing(
            l,
            historico_7d=historico_7d.get(l["id"]),
            concorrentes=concorrentes.get(l["id"]),
        )
        for l in listings_limitados
    )

    # Contagem de concorrentes total para informar no prompt
    total_concorrentes = sum(len(v) for v in concorrentes.values())

    prompt_usuario = f"""Analise os seguintes dados do meu negocio no Mercado Livre e gere insights e recomendacoes praticas:

{kpi_texto}

=== ANUNCIOS ({total_analisados} anuncios, {total_concorrentes} concorrentes monitorados) ===

{listings_texto}

Por favor, analise esses dados e me de:
1. Um diagnostico geral da performance (incluindo tendencia dos ultimos 7 dias)
2. Os 3 anuncios com melhor e pior performance (com justificativa baseada em dados e tendencia)
3. Recomendacoes especificas de precificacao (considere os concorrentes quando disponiveis)
4. Alertas de estoque (destaque produtos com ruptura proxima e sugira data de reposicao)
5. Analise de margem (identifique produtos com margem critica baseado no voce_recebe)
6. Analise de qualidade (destaque anuncios com score baixo que precisam de otimizacao)
7. As 3 acoes imediatas mais importantes que devo fazer AGORA, com justificativa numerica"""

    # Chama a API Claude via httpx
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 3000,
        "temperature": 0.3,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": prompt_usuario}
        ],
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Chave da API Claude invalida. Verifique ANTHROPIC_API_KEY.",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro ao chamar API Claude: {e.response.status_code} — {e.response.text[:200]}",
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Timeout ao chamar API Claude. Tente novamente em alguns segundos.",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro de conexao com API Claude: {str(e)}",
            )

    data = response.json()
    try:
        analise = data["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        analise = data.get("error", {}).get("message", "Resposta inesperada da API Claude.")

    return analise, total_analisados
