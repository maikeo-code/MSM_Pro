"""
Dados mock para testes e preview sem token ML real.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.vendas.service_calculations import _calculate_price_bands


def _generate_mock_snapshots(days: int = 30) -> list[dict]:
    """Gera 30 dias de snapshots mock realistas para testes."""
    snapshots = []
    now = datetime.now(timezone.utc)

    # Prices oscilam entre 239 e 499
    price_trend = [
        239.0, 239.0, 245.0, 249.0, 259.0, 269.0, 299.0, 349.0, 409.0, 459.0,
        499.0, 489.0, 479.0, 459.0, 429.0, 399.0, 369.0, 349.0, 319.0, 299.0,
        279.0, 259.0, 249.0, 269.0, 289.0, 309.0, 329.0, 349.0, 369.0, 389.0,
    ]

    for i in range(days):
        dt = now - timedelta(days=days - i - 1)
        price = Decimal(str(price_trend[i % len(price_trend)]))
        visits = 400 + (i % 400)  # 400-799 visitas
        sales = max(1, int(visits * (0.01 + (i % 8) * 0.01)))  # 1-8% conversão
        conversion = Decimal(str(round((sales / max(1, visits)) * 100, 2)))

        revenue_mock = float(price) * sales
        snapshots.append({
            "id": str(UUID(int=i)),
            "listing_id": str(UUID(int=0)),
            "price": price,
            "visits": visits,
            "sales_today": sales,
            "questions": i % 5,
            "stock": 100 + (i % 50),
            "conversion_rate": conversion,
            "captured_at": dt,
            # Campos de analytics — simulados no mock
            "orders_count": max(1, sales - (i % 2)),
            "revenue": revenue_mock,
            "avg_selling_price": float(price),
            "cancelled_orders": 1 if i % 7 == 0 else 0,
            "cancelled_revenue": float(price) if i % 7 == 0 else 0.0,
            "returns_count": 1 if i % 15 == 0 else 0,
            "returns_revenue": float(price) if i % 15 == 0 else 0.0,
        })

    return snapshots


def _generate_mock_analysis(listing, product) -> dict:
    """Gera análise completa mock para testes."""
    custo = Decimal(str(product.cost)) if product else Decimal("100.00")
    listing_type = listing.listing_type or "classico"

    snapshots = _generate_mock_snapshots(30)
    price_bands = _calculate_price_bands(snapshots, custo, listing_type)

    return {
        "is_mock": True,
        "listing": {
            "mlb_id": listing.mlb_id,
            "title": listing.title,
            "price": float(listing.price),
            "listing_type": listing_type,
            "status": listing.status,
            "thumbnail": listing.thumbnail,
            "permalink": listing.permalink,
        },
        "sku": {
            "id": str(product.id) if product else None,
            "sku": product.sku if product else "N/A",
            "cost": float(custo),
        },
        "snapshots": snapshots,
        "price_bands": price_bands,
        "full_stock": {
            "available": 121,
            "in_transit": 0,
            "days_until_stockout_7d": 12,
            "days_until_stockout_30d": 19,
            "status": "warning",
            "velocity_7d": 3.8,
            "velocity_30d": 2.1,
        },
        "promotions": [
            {
                "id": "promo_001",
                "type": "desconto_direto",
                "discount_pct": 39.0,
                "original_price": 409.0,
                "final_price": 249.0,
                "start_date": "2026-03-08",
                "end_date": "2026-03-12",
                "status": "active",
            }
        ],
        "ads": {
            "roas": 5.19,
            "impressions": 442390,
            "clicks": 1131,
            "cpc": 1.41,
            "ctr": 0.26,
            "spend": 1595.31,
            "attributed_sales": 8279.89,
        },
        "competitor": None,
        "alerts": [
            {
                "type": "promotion_expiring",
                "message": "Promoção 'Desconto 39%' vence em 2 dias",
                "severity": "warning",
            }
        ],
    }
