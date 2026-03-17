"""
Health score e quality score de anúncios.
"""


def _calculate_health_score(
    listing,
    snapshots: list[dict],
    product=None,
    competitor_price: float | None = None,
) -> dict:
    """
    Calcula score de qualidade do anúncio (0-100) baseado na Missão 3 do ML.

    Critérios (total = 100 pts):
    - Título: comprimento >60 chars = +10pts
    - Imagens: tem thumbnail = +15pts (proxy para >5 fotos)
    - Preço competitivo (vs concorrente se disponível) = +10pts
    - Frete grátis (premium ou full) = +10pts
    - Fulfillment (Full) = +10pts
    - Conversão >3% = +10pts
    - Estoque >10 = +10pts
    - Vendas recentes (últimos 3 dias >0) = +10pts
    - Anúncio ativo = +5pts
    - Custo do SKU cadastrado = +10pts
    """
    score = 0
    checks = []

    # 1. Título: comprimento >60 chars = +10pts
    title = getattr(listing, 'title', '') or ''
    title_len = len(title)
    if title_len > 60:
        score += 10
        checks.append({"item": "Título otimizado", "ok": True, "points": 10, "max": 10, "detail": f"{title_len} caracteres"})
    else:
        checks.append({"item": "Título otimizado", "ok": False, "points": 0, "max": 10, "action": f"Título com {title_len} chars. Ideal: >60 chars com palavras-chave", "detail": f"{title_len} caracteres"})

    # 2. Imagens: tem thumbnail = +15pts
    has_thumb = bool(getattr(listing, 'thumbnail', None))
    if has_thumb:
        score += 15
        checks.append({"item": "Imagens do anúncio", "ok": True, "points": 15, "max": 15})
    else:
        checks.append({"item": "Imagens do anúncio", "ok": False, "points": 0, "max": 15, "action": "Adicione fotos de qualidade ao anúncio (ideal: >5 fotos)"})

    # 3. Preço competitivo (vs concorrente) = +10pts
    current_price = float(getattr(listing, 'sale_price', None) or getattr(listing, 'price', 0) or 0)
    if competitor_price and current_price > 0:
        if current_price <= competitor_price * 1.05:
            score += 10
            checks.append({"item": "Preço competitivo", "ok": True, "points": 10, "max": 10, "detail": f"R$ {current_price:.0f} vs concorrente R$ {competitor_price:.0f}"})
        else:
            diff_pct = ((current_price - competitor_price) / competitor_price) * 100
            checks.append({"item": "Preço competitivo", "ok": False, "points": 0, "max": 10, "action": f"Preço {diff_pct:.0f}% acima do concorrente", "detail": f"R$ {current_price:.0f} vs R$ {competitor_price:.0f}"})
    elif current_price > 0:
        score += 5
        checks.append({"item": "Preço competitivo", "ok": True, "points": 5, "max": 10, "detail": "Sem concorrente vinculado para comparar"})
    else:
        checks.append({"item": "Preço competitivo", "ok": False, "points": 0, "max": 10, "action": "Vincule um concorrente para comparar preços"})

    # 4. Frete grátis (premium ou full) = +10pts
    listing_type = getattr(listing, 'listing_type', 'classico') or 'classico'
    if listing_type in ('premium', 'full'):
        score += 10
        checks.append({"item": "Frete grátis", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Frete grátis", "ok": False, "points": 0, "max": 10, "action": "Migre para Premium ou Full para oferecer frete grátis"})

    # 5. Fulfillment (Full) = +10pts
    if listing_type == 'full':
        score += 10
        checks.append({"item": "Fulfillment (Full)", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Fulfillment (Full)", "ok": False, "points": 0, "max": 10, "action": "Envie estoque ao Full para entregas mais rápidas"})

    # 6. Conversão >3% nos últimos 7 dias = +10pts
    if snapshots and len(snapshots) >= 3:
        recent = snapshots[-7:] if len(snapshots) >= 7 else snapshots
        total_visits = sum(s.get("visits", 0) for s in recent)
        total_sales = sum(s.get("sales_today", 0) for s in recent)
        conversion = (total_sales / max(1, total_visits)) * 100
        if conversion >= 3:
            score += 10
            checks.append({"item": "Conversão (>3%)", "ok": True, "points": 10, "max": 10, "detail": f"{conversion:.1f}%"})
        elif conversion >= 1:
            score += 5
            checks.append({"item": "Conversão (>3%)", "ok": True, "points": 5, "max": 10, "detail": f"{conversion:.1f}% (ideal: 3%+)"})
        else:
            checks.append({"item": "Conversão (>3%)", "ok": False, "points": 0, "max": 10, "action": f"Conversão de {conversion:.1f}%. Revise título, fotos e preço.", "detail": f"{conversion:.1f}%"})
    else:
        checks.append({"item": "Conversão (>3%)", "ok": False, "points": 0, "max": 10, "action": "Sem dados suficientes de vendas"})

    # 7. Estoque >10 unidades = +10pts
    if snapshots:
        last_snap = snapshots[-1]
        stock = last_snap.get("stock", 0)
        if stock > 10:
            score += 10
            checks.append({"item": "Estoque (>10 un.)", "ok": True, "points": 10, "max": 10, "detail": f"{stock} unidades"})
        else:
            checks.append({"item": "Estoque (>10 un.)", "ok": False, "points": 0, "max": 10, "action": f"Apenas {stock} unidades. Reabasteça!", "detail": f"{stock} unidades"})
    else:
        checks.append({"item": "Estoque (>10 un.)", "ok": False, "points": 0, "max": 10, "action": "Sem dados de estoque ainda"})

    # 8. Vendas recentes (últimos 3 dias >0) = +10pts
    if snapshots and len(snapshots) >= 3:
        last_3 = snapshots[-3:]
        total_recent = sum(s.get("sales_today", 0) for s in last_3)
        if total_recent > 0:
            score += 10
            checks.append({"item": "Vendas recentes", "ok": True, "points": 10, "max": 10, "detail": f"{total_recent} vendas nos últimos 3 dias"})
        else:
            checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 10, "action": "0 vendas nos últimos 3 dias. Verifique preço e visibilidade."})
    else:
        checks.append({"item": "Vendas recentes", "ok": False, "points": 0, "max": 10, "action": "Sem dados de vendas ainda"})

    # 9. Anúncio ativo = +5pts
    is_active = getattr(listing, 'status', 'active') == 'active'
    if is_active:
        score += 5
        checks.append({"item": "Status ativo", "ok": True, "points": 5, "max": 5})
    else:
        checks.append({"item": "Status ativo", "ok": False, "points": 0, "max": 5, "action": "Anúncio pausado ou inativo"})

    # 10. Custo do SKU cadastrado = +10pts
    has_cost = product is not None and product.cost and float(product.cost) > 0
    if has_cost:
        score += 10
        checks.append({"item": "Custo do SKU", "ok": True, "points": 10, "max": 10})
    else:
        checks.append({"item": "Custo do SKU", "ok": False, "points": 0, "max": 10, "action": "Cadastre o custo para calcular margens reais"})

    # Classifica o score
    if score >= 80:
        health_status = "excellent"
        label = "Excelente"
        color = "green"
    elif score >= 60:
        health_status = "good"
        label = "Bom"
        color = "yellow"
    elif score >= 40:
        health_status = "warning"
        label = "Atenção"
        color = "orange"
    else:
        health_status = "critical"
        label = "Crítico"
        color = "red"

    return {
        "score": score,
        "max_score": 100,
        "status": health_status,
        "label": label,
        "color": color,
        "checks": checks,
    }


def calculate_quality_score_quick(listing) -> int:
    """
    Calcula quality_score rápido sem snapshots (para usar durante sync).
    Baseado apenas nos atributos do listing.
    """
    score = 0
    title = getattr(listing, 'title', '') or ''
    if len(title) > 60:
        score += 10
    if getattr(listing, 'thumbnail', None):
        score += 15
    listing_type = getattr(listing, 'listing_type', 'classico') or 'classico'
    if listing_type in ('premium', 'full'):
        score += 10  # frete grátis
    if listing_type == 'full':
        score += 10  # fulfillment
    if getattr(listing, 'status', 'active') == 'active':
        score += 5
    if float(getattr(listing, 'price', 0) or 0) > 0:
        score += 5  # preço parcial (sem concorrente)
    return min(100, score)
