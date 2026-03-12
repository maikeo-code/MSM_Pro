from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.vendas.service import get_kpi_by_period, list_listings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
MAX_LISTINGS = 20

SYSTEM_PROMPT = """Você é um especialista em vendas no Mercado Livre com mais de 10 anos de experiência ajudando vendedores brasileiros a maximizar seus resultados.

Seu papel é analisar os dados dos anúncios fornecidos e gerar insights acionáveis e recomendações práticas.

Foque em:
1. **Performance individual**: identifique anúncios com alta e baixa performance
2. **Precificação**: sugira ajustes de preço baseados em conversão, visitas e vendas
3. **Estoque**: alerte sobre riscos de ruptura (anúncios com estoque crítico)
4. **Oportunidades**: destaque anúncios com potencial não explorado (visitas altas, conversão baixa)
5. **Comparação**: compare os anúncios entre si para identificar padrões de sucesso
6. **Ações imediatas**: liste as 3 ações mais impactantes que o vendedor deve fazer hoje

Seja direto, use números e porcentagens reais dos dados, evite jargões desnecessários.
Responda sempre em português brasileiro."""


def _formatar_listing(listing: dict) -> str:
    """Formata um listing para texto estruturado enviado ao LLM."""
    snap = listing.get("last_snapshot")

    title = listing.get("title", "Sem título")[:60]
    mlb_id = listing.get("mlb_id", "N/A")
    price = listing.get("price")
    listing_type = listing.get("listing_type", "desconhecido")
    voce_recebe = listing.get("voce_recebe")
    sku = listing.get("seller_sku") or listing.get("sku_code") or "N/A"

    lines = [f"- [{mlb_id}] {title}"]
    lines.append(f"  Tipo: {listing_type} | SKU: {sku}")

    if price is not None:
        lines.append(f"  Preço: R$ {float(price):.2f}")
    if voce_recebe is not None:
        lines.append(f"  Você recebe (líquido): R$ {float(voce_recebe):.2f}")

    if snap:
        stock = snap.get("stock") if isinstance(snap, dict) else getattr(snap, "stock", None)
        visits = snap.get("visits") if isinstance(snap, dict) else getattr(snap, "visits", None)
        sales = snap.get("sales_today") if isinstance(snap, dict) else getattr(snap, "sales_today", None)
        conversion = snap.get("conversion_rate") if isinstance(snap, dict) else getattr(snap, "conversion_rate", None)
        revenue = snap.get("revenue") if isinstance(snap, dict) else getattr(snap, "revenue", None)
        days_to_zero = listing.get("dias_para_zerar")
        participation = listing.get("participacao_pct")

        if stock is not None:
            lines.append(f"  Estoque: {stock} unidades")
            if days_to_zero is not None:
                lines.append(f"  Dias para zerar: {days_to_zero}")
        if visits is not None:
            lines.append(f"  Visitas hoje: {visits}")
        if sales is not None:
            lines.append(f"  Vendas hoje: {sales} unidades")
        if conversion is not None:
            lines.append(f"  Conversão: {float(conversion):.2f}%")
        if revenue is not None:
            lines.append(f"  Receita hoje: R$ {float(revenue):.2f}")
        if participation is not None:
            lines.append(f"  Participação na receita: {float(participation):.1f}%")
    else:
        lines.append("  Sem dados de snapshot disponíveis")

    return "\n".join(lines)


def _formatar_kpi(kpi: dict) -> str:
    """Formata KPIs para texto estruturado."""
    linhas = ["=== KPIs CONSOLIDADOS ==="]

    periodos = [
        ("hoje", "Hoje"),
        ("ontem", "Ontem"),
        ("anteontem", "Anteontem"),
        ("7dias", "Últimos 7 dias"),
        ("30dias", "Últimos 30 dias"),
    ]

    for key, label in periodos:
        periodo = kpi.get(key, {})
        if not periodo:
            continue

        vendas = periodo.get("total_sales", 0)
        receita = periodo.get("total_revenue", 0)
        visitas = periodo.get("total_visits", 0)
        anuncios = periodo.get("listings_with_sales", 0)

        linhas.append(
            f"{label}: {vendas} vendas | R$ {float(receita):.2f} receita | "
            f"{visitas} visitas | {anuncios} anúncios com venda"
        )

    return "\n".join(linhas)


async def analisar_listings(
    db: AsyncSession,
    user_id: UUID,
    mlb_id: Optional[str] = None,
) -> tuple[str, int]:
    """
    Busca os listings e KPIs do usuário, formata o contexto e chama a API Claude.
    Retorna (texto_da_analise, quantidade_de_anuncios_analisados).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Consultor IA não configurado: ANTHROPIC_API_KEY ausente. "
                   "Configure a variável de ambiente no servidor.",
        )

    # Busca dados
    listings = await list_listings(db, user_id)
    kpis = await get_kpi_by_period(db, user_id)

    # Filtra por mlb_id se informado
    if mlb_id:
        listings = [l for l in listings if l.get("mlb_id") == mlb_id]
        if not listings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anúncio {mlb_id} não encontrado.",
            )

    # Limita a 20 anúncios para não estourar o contexto
    listings_limitados = listings[:MAX_LISTINGS]
    total_analisados = len(listings_limitados)

    # Monta o prompt do usuário
    kpi_texto = _formatar_kpi(kpis)
    listings_texto = "\n\n".join(_formatar_listing(l) for l in listings_limitados)

    prompt_usuario = f"""Analise os seguintes dados do meu negócio no Mercado Livre e gere insights e recomendações práticas:

{kpi_texto}

=== ANÚNCIOS ({total_analisados} anúncios) ===

{listings_texto}

Por favor, analise esses dados e me dê:
1. Um diagnóstico geral da performance
2. Os 3 anúncios com melhor e pior performance (com justificativa)
3. Recomendações específicas de precificação
4. Alertas de estoque
5. As 3 ações imediatas mais importantes que devo fazer agora"""

    # Chama a API Claude via httpx
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "temperature": 0.3,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": prompt_usuario}
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Chave da API Claude inválida. Verifique ANTHROPIC_API_KEY.",
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
                detail=f"Erro de conexão com API Claude: {str(e)}",
            )

    data = response.json()
    analise = data["content"][0]["text"]

    return analise, total_analisados
