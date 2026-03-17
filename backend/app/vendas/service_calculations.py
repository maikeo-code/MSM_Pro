"""
Funções puras de cálculo — sem dependência de DB.
Usadas por service_analytics.py, service_mock.py e service_health.py.
"""
from decimal import Decimal

from app.financeiro.service import calcular_margem


def _calculate_price_bands(
    snapshots: list[dict], cost: Decimal, listing_type: str
) -> list[dict]:
    """
    Agrupa snapshots por faixa de preço e calcula métricas.
    Faixas de R$5 a R$10 dependendo do valor.
    """
    if not snapshots:
        return []

    price_bands = {}

    for snap in snapshots:
        price = Decimal(str(snap["price"]))

        # Define tamanho da faixa baseado no valor
        if price < 50:
            band_size = Decimal("5")
        elif price < 200:
            band_size = Decimal("10")
        elif price < 500:
            band_size = Decimal("15")
        else:
            band_size = Decimal("25")

        # Calcula o início da faixa
        band_start = (price // band_size) * band_size

        band_key = str(band_start)

        if band_key not in price_bands:
            price_bands[band_key] = {
                "price_start": band_start,
                "price_end": band_start + band_size,
                "prices": [],
                "sales_list": [],
                "visits_list": [],
                "revenue": Decimal("0"),
                "days_count": 0,
            }

        price_bands[band_key]["prices"].append(price)
        price_bands[band_key]["sales_list"].append(snap["sales_today"])
        price_bands[band_key]["visits_list"].append(snap["visits"])
        # Usa revenue real se disponível; caso contrário estima price * qty
        snap_revenue = snap.get("revenue")
        if snap_revenue is not None and snap_revenue > 0:
            price_bands[band_key]["revenue"] += Decimal(str(snap_revenue))
        else:
            price_bands[band_key]["revenue"] += price * snap["sales_today"]
        price_bands[band_key]["days_count"] += 1

    # Calcula médias e margens
    result = []
    max_margin = Decimal("-999999")
    optimal_band_key = None

    for band_key, band_data in sorted(price_bands.items()):
        avg_price = sum(band_data["prices"]) / len(band_data["prices"])
        avg_sales = sum(band_data["sales_list"]) / len(band_data["sales_list"])
        total_visits = sum(band_data["visits_list"])
        avg_conversion = (
            (sum(band_data["sales_list"]) / max(1, total_visits)) * 100
            if total_visits > 0
            else 0
        )

        margem_info = calcular_margem(avg_price, cost, listing_type)
        avg_margin = margem_info["margem_bruta"]
        total_margin = avg_margin * Decimal(str(sum(band_data["sales_list"])))

        band_entry = {
            "price_range_label": f"R$ {band_data['price_start']:.0f}-{band_data['price_end']:.0f}",
            "avg_sales_per_day": float(avg_sales),
            "avg_conversion": float(avg_conversion),
            "total_revenue": float(band_data["revenue"]),
            "avg_margin": float(avg_margin),
            "days_count": band_data["days_count"],
            "is_optimal": False,
        }

        if total_margin > max_margin:
            if optimal_band_key is not None:
                # Remove optimal da banda anterior
                for item in result:
                    if item.get("is_optimal"):
                        item["is_optimal"] = False
                        break
            max_margin = total_margin
            optimal_band_key = band_key
            band_entry["is_optimal"] = True

        result.append(band_entry)

    def _sort_key(x):
        try:
            return float(x["price_range_label"].split("R$ ")[1].split("-")[0].replace(",", ""))
        except (IndexError, ValueError):
            return 0.0

    return sorted(result, key=_sort_key)


def _calculate_stock_projection(stock_qty: int, snapshots: list[dict]) -> dict:
    """
    Calcula projeção de estoque baseado em velocidade de venda.
    """
    if not snapshots or stock_qty <= 0:
        return {
            "available": stock_qty,
            "in_transit": 0,
            "days_until_stockout_7d": None,
            "days_until_stockout_30d": None,
            "velocity_7d": 0,
            "velocity_30d": 0,
            "status": "ok",
        }

    # Últimos 7 dias
    recent_7 = snapshots[-7:] if len(snapshots) >= 7 else snapshots
    velocity_7d = sum(s["sales_today"] for s in recent_7) / len(recent_7)

    # Últimos 30 dias
    velocity_30d = sum(s["sales_today"] for s in snapshots) / len(snapshots)

    days_until_stockout_7d = stock_qty / velocity_7d if velocity_7d > 0 else None
    days_until_stockout_30d = stock_qty / velocity_30d if velocity_30d > 0 else None

    # Determina status
    if days_until_stockout_7d and days_until_stockout_7d < 7:
        status = "critical"
    elif days_until_stockout_7d and days_until_stockout_7d < 14:
        status = "warning"
    elif days_until_stockout_7d and days_until_stockout_7d > 60:
        status = "excess"
    else:
        status = "ok"

    return {
        "available": stock_qty,
        "in_transit": 0,
        "days_until_stockout_7d": round(days_until_stockout_7d, 1) if days_until_stockout_7d else None,
        "days_until_stockout_30d": round(days_until_stockout_30d, 1) if days_until_stockout_30d else None,
        "velocity_7d": round(velocity_7d, 2),
        "velocity_30d": round(velocity_30d, 2),
        "status": status,
    }


def _generate_alerts(
    snapshots: list[dict],
    stock_projection: dict,
    competitor_price: Decimal | None,
    current_price: Decimal,
) -> list[dict]:
    """
    Gera alertas inteligentes baseado em regras de negócio.
    """
    alerts = []

    if not snapshots:
        return alerts

    # Alert: Ruptura crítica
    days_until_stockout = stock_projection.get("days_until_stockout_7d")
    if days_until_stockout and days_until_stockout < 7:
        alerts.append({
            "type": "stock_critical",
            "message": f"Estoque acaba em {days_until_stockout:.0f} dias",
            "severity": "critical",
        })

    # Alert: Excesso de estoque
    if days_until_stockout and days_until_stockout > 60:
        alerts.append({
            "type": "stock_excess",
            "message": f"Mais de 60 dias de estoque ({days_until_stockout:.0f} dias)",
            "severity": "info",
        })

    # Alert: Conversão baixa
    recent_3_days = snapshots[-3:] if len(snapshots) >= 3 else snapshots
    recent_visits = sum(s["visits"] for s in recent_3_days)
    recent_sales = sum(s["sales_today"] for s in recent_3_days)

    if recent_visits > 10 and recent_sales > 0:
        recent_conversion = (recent_sales / recent_visits) * 100
        if recent_conversion < 1:
            alerts.append({
                "type": "low_conversion",
                "message": f"Conversão baixa: {recent_conversion:.2f}%",
                "severity": "warning",
            })

    # Alert: Zero vendas
    if recent_sales == 0 and recent_visits > 0:
        alerts.append({
            "type": "zero_sales",
            "message": "0 vendas nos últimos 3 dias com tráfego",
            "severity": "warning",
        })

    # Alert: Concorrente mais barato
    if competitor_price and current_price > competitor_price:
        diff_pct = ((current_price - competitor_price) / current_price) * 100
        alerts.append({
            "type": "competitor_cheaper",
            "message": f"Concorrente {diff_pct:.1f}% mais barato",
            "severity": "info",
        })

    return alerts
