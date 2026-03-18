"""
Health score, quality score e analise de titulo de anuncios.
"""
import re


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


# ─── Palavras genericas indesejadas em titulos de anuncios ────────────────────
_GENERIC_WORDS = frozenset([
    "otimo", "ótimo", "melhor", "promocao", "promoção", "oferta",
    "imperdivel", "imperdível", "imperdivel", "super", "mega",
    "incrivel", "incrível", "barato", "barata", "economize",
    "novidade", "exclusivo", "exclusiva", "original", "lancamento",
    "lançamento", "top", "excelente", "perfeito", "perfeita",
    "qualidade", "especial", "imperdivel", "produto", "item",
])

# Palavras descritivas relevantes (cor, tamanho, materiais, etc.)
_DESCRIPTIVE_PATTERNS = [
    r'\b(preto|branco|azul|vermelho|verde|amarelo|rosa|cinza|prata|dourado|bege|laranja|roxo|marrom)\b',
    r'\b(pequeno|medio|grande|xl|xxl|xs|xg|p\b|m\b|g\b)\b',
    r'\b(\d+\s*(cm|mm|m\b|kg|g\b|l\b|ml|w\b|v\b|hz|gb|tb|mb))\b',
    r'\b(inox|aluminio|alumínio|plastico|plástico|madeira|couro|tecido|borracha)\b',
    r'\b(sem fio|wireless|bluetooth|usb|hdmi|wifi|wi-fi)\b',
]


def analyze_title_quality(title: str) -> dict:
    """
    Analisa a qualidade do titulo de um anuncio e retorna score 0-100 com checklist.

    Criterios:
    - Comprimento: ideal 60-120 chars (25 pts)
    - Marca/modelo aparece nos primeiros 2 termos (25 pts)
    - Contem palavras descritivas (cor, tamanho, modelo) (25 pts)
    - Nao contem termos genericos inuteis (25 pts)

    Retorna dict com: title, score, length, checks, suggested_title (sempre null por ora).
    """
    title = (title or "").strip()
    length = len(title)
    checks = []
    score = 0

    # 1. Comprimento ideal: 60-120 chars (25 pts, parcial 60-120 vs extremos)
    if 60 <= length <= 120:
        score += 25
        checks.append({
            "item": "Comprimento",
            "ok": True,
            "detail": f"{length} chars (ideal: 60-120)",
        })
    elif length > 120:
        score += 10
        checks.append({
            "item": "Comprimento",
            "ok": False,
            "detail": f"{length} chars (ideal: 60-120)",
            "action": "Titulo muito longo — o ML corta apos ~120 chars na busca",
        })
    elif length >= 40:
        score += 10
        checks.append({
            "item": "Comprimento",
            "ok": False,
            "detail": f"{length} chars (ideal: 60-120)",
            "action": "Adicione mais palavras-chave relevantes ao titulo",
        })
    else:
        checks.append({
            "item": "Comprimento",
            "ok": False,
            "detail": f"{length} chars (ideal: 60-120)",
            "action": "Titulo muito curto — adicione marca, modelo, cor e tamanho",
        })

    # 2. Marca/modelo nos primeiros 2 termos (25 pts)
    # Heuristica: primeiro ou segundo token com mais de 2 chars e sem numeros puros
    tokens = [t for t in re.split(r'[\s\-_,]+', title) if len(t) > 2]
    first_tokens = tokens[:2]
    has_brand_position = bool(first_tokens) and any(
        not t.isdigit() and re.search(r'[a-zA-ZÀ-ú]', t) for t in first_tokens
    )
    if has_brand_position:
        score += 25
        brand_sample = first_tokens[0] if first_tokens else ""
        checks.append({
            "item": "Marca/modelo em posicao destaque",
            "ok": True,
            "detail": f"Iniciado com: {brand_sample}",
        })
    else:
        checks.append({
            "item": "Marca/modelo em posicao destaque",
            "ok": False,
            "action": "Coloque a marca ou modelo no inicio do titulo para melhor indexacao",
        })

    # 3. Palavras descritivas (cor, tamanho, material, etc.) (25 pts)
    title_lower = title.lower()
    found_descriptive: list[str] = []
    for pattern in _DESCRIPTIVE_PATTERNS:
        matches = re.findall(pattern, title_lower)
        found_descriptive.extend([m if isinstance(m, str) else m[0] for m in matches])

    found_descriptive = list(dict.fromkeys(found_descriptive))  # dedup mantendo ordem

    if found_descriptive:
        score += 25
        sample = ", ".join(found_descriptive[:3])
        checks.append({
            "item": "Palavras descritivas",
            "ok": True,
            "detail": f"Contem: {sample}",
        })
    else:
        checks.append({
            "item": "Palavras descritivas",
            "ok": False,
            "action": "Adicione cor, tamanho, material ou especificacoes tecnicas ao titulo",
        })

    # 4. Sem termos genericos inuteis (25 pts)
    title_words = set(re.findall(r'\b\w+\b', title_lower))
    generic_found = sorted(title_words & _GENERIC_WORDS)
    if not generic_found:
        score += 25
        checks.append({
            "item": "Sem termos genericos",
            "ok": True,
        })
    else:
        sample_generic = ", ".join(f'"{w}"' for w in generic_found[:3])
        checks.append({
            "item": "Sem termos genericos",
            "ok": False,
            "detail": f"Encontrados: {sample_generic}",
            "action": "Remova palavras genericas — o ML as ignora na indexacao",
        })

    return {
        "title": title,
        "score": score,
        "length": length,
        "checks": checks,
        "suggested_title": None,  # futuro: sugestao via IA
    }
