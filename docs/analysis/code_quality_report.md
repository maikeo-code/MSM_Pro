# MSM_Pro — Code Quality Analysis Report

**Date:** 2026-03-12
**Scope:** Read-only analysis of 7 key files
**Analyst:** Code Reviewer Agent (Claude Sonnet 4.6)

---

## Executive Summary

| Category | Score | Rating |
|---|---|---|
| Naming Conventions | 88/100 | Good |
| DRY / Code Duplication | 54/100 | Needs Work |
| SOLID Principles | 62/100 | Acceptable |
| Cyclomatic Complexity | 48/100 | Needs Work |
| Code Smells | 55/100 | Needs Work |
| Type Safety | 72/100 | Good |
| Error Handling | 78/100 | Good |
| **Overall** | **65/100** | **Acceptable** |

The project is functional and well-intentioned. The core architecture (FastAPI + async SQLAlchemy + Celery) is solid. The main quality debt comes from files that outgrew their original scope — `vendas/service.py` at ~1980 lines is the single largest risk. DRY violations between Dashboard and Anuncios pages are the most immediately fixable issue.

---

## 1. Naming Conventions — Score: 88/100

### Python (backend)

PASS: Modules use `snake_case.py`, classes use `PascalCase`, async functions use `async def snake_case`.

PASS: Internal helpers consistently prefixed with `_` (e.g., `_kpi_single_day`, `_aggregate_snaps`, `_formatar_listing`, `_buscar_concorrentes`).

PASS: Celery tasks follow `verb_noun_noun` pattern (`sync_all_snapshots`, `evaluate_alerts`).

MINOR ISSUE — Mixed language in identifiers. Business logic uses Portuguese variable names throughout (`vendas_brutas`, `taxas_ml_total`, `dias_para_zerar`), while infrastructure code uses English. This is a deliberate product decision (domain terms stay in Portuguese), but it creates cognitive switching cost for any future contributors.

```python
# backend/app/financeiro/service.py:170-176
vendas_brutas = Decimal("0")
taxas_ml_total = Decimal("0")
frete_total = Decimal("0")
custo_total = Decimal("0")
total_pedidos = 0
total_cancelamentos = 0
total_devolucoes = 0
```

MINOR ISSUE — `base_price` declared but never used:

```python
# backend/app/vendas/service.py:29
base_price = 409.0  # unused variable — dead code
```

MINOR ISSUE — Variable `date` shadows the stdlib `date` type in a loop:

```python
# backend/app/vendas/service.py:37
for i in range(days):
    date = now - timedelta(days=days - i - 1)  # shadows datetime.date
```

### TypeScript (frontend)

PASS: Components use `PascalCase` (`KpiCard`, `ConversionFunnel`, `HeatmapHourly`).

PASS: Services use `camelCase` (`listingsService`, `consultorService`).

PASS: Constants use `UPPER_SNAKE_CASE` (`DAY_ABBR`, `PERIOD_OPTIONS`).

MINOR ISSUE — Local component functions inside page files use PascalCase which is correct, but they are large enough to warrant their own files (`HeatmapHourly`, `HeatmapDaily`, `ConversionFunnel` are each 40-80 lines and defined inside `Dashboard/index.tsx`).

---

## 2. DRY Violations — Score: 54/100

This is the most significant quality issue in the project. The same logic is copy-pasted in multiple locations.

### CRITICAL: exportCSV duplicated verbatim across two pages

`frontend/src/pages/Dashboard/index.tsx:87-116` and `frontend/src/pages/Anuncios/index.tsx:43-73` contain essentially identical `exportCSV` functions. The only difference is the `Anuncios` version adds a `Tipo` column. Both share 95%+ of their code.

```typescript
// Dashboard/index.tsx:87 — identical to Anuncios/index.tsx:43 except headers array
function exportCSV(listings: ListingOut[]) {
  const headers = ["MLB", "Titulo", "SKU", ...];
  const rows = listings.map((l) => { ... });
  // ... blob/URL/anchor pattern repeated identically
}
```

**Fix:** Extract to `frontend/src/lib/exportUtils.ts` with a `columns` parameter.

### CRITICAL: Variacao component duplicated verbatim

`frontend/src/pages/Dashboard/index.tsx:12-23` and `frontend/src/pages/Anuncios/index.tsx:29-40` define identical `Variacao` components with byte-for-byte matching implementation.

```typescript
// Identical in both files
function Variacao({ value, unit = "%" }: { value?: number | null; unit?: string }) {
  if (value == null) return null;
  const isPositive = value >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-green-600" : "text-red-500";
  return ( ... );
}
```

**Fix:** Move to `frontend/src/components/Variacao.tsx` (already has a pattern for shared components like `DiasBadge`).

### CRITICAL: KPI "Resumo por Periodo" table duplicated

The entire KPI period table (Hoje/Ontem/Anteontem/7dias/30dias) is copy-pasted from `Dashboard/index.tsx:591-636` into `Anuncios/index.tsx:167-212`. These are structurally identical with minor text differences.

**Fix:** Extract to `frontend/src/components/KpiPeriodTable.tsx`.

### HIGH: Participacao % bar-with-color-badge pattern duplicated

The participation percentage cell (text + mini progress bar with color thresholds at 30% and 10%) appears identically in `Dashboard/index.tsx:840-857` and `Anuncios/index.tsx:415-434`.

### HIGH: mlb_id normalization duplicated across 9 locations

The pattern `item_id.upper().replace("-", "")` + MLB prefix check appears in:

- `backend/app/mercadolivre/client.py:113-115` (`get_item`)
- `backend/app/mercadolivre/client.py:124-126` (`update_item_price`)
- `backend/app/mercadolivre/client.py:139-141` (`get_item_visits`)
- `backend/app/mercadolivre/client.py:170-172` (`get_item_orders_by_status`)
- `backend/app/mercadolivre/client.py:210-212` (`get_item_orders`)
- `backend/app/mercadolivre/client.py:240-242` (`get_full_stock`)
- `backend/app/mercadolivre/client.py:265-267` (`get_item_promotions`)
- `backend/app/mercadolivre/client.py:296-298` (`create_promotion`)
- `backend/app/mercadolivre/client.py:324-326` (`update_promotion`)

This normalization belongs in one place.

**Fix:**

```python
# backend/app/mercadolivre/client.py
def _normalize_mlb_id(self, mlb_id: str) -> str:
    item_id = mlb_id.upper().replace("-", "")
    return item_id if item_id.startswith("MLB") else f"MLB{item_id}"
```

Then all 9 callers become `item_id = self._normalize_mlb_id(mlb_id)`.

### HIGH: _aggregate service logic duplicated between get_financeiro_resumo and get_financeiro_detalhado

`backend/app/financeiro/service.py:127-216` (inner `_aggregate` function) and `backend/app/financeiro/service.py:251-338` (`get_financeiro_detalhado`) both execute nearly the same JOIN + GROUP BY query and apply the same fee/shipping calculation loop. The join structure, column selection, and per-row calculation (taxa, frete, margem) are almost identical.

### MEDIUM: sortedListings + filteredListings logic duplicated

`Dashboard/index.tsx:391-407` and `Anuncios/index.tsx:101-117` both implement the identical sort-by-sales-then-filter-by-term logic. This would make a good `useFilteredListings(listings, searchTerm)` custom hook.

### MEDIUM: Total row calculations duplicated

`Dashboard/index.tsx:410-424` and `Anuncios/index.tsx:120-136` both compute `totalPedidos`, `totalUnidades`, `totalReceita`, `totalEstoque`, `totalVisitas`, `avgConversao`, `avgPrecoMedio` from `filteredListings` via identical reduce calls.

### MEDIUM: Deferred imports inside functions

In `backend/app/vendas/service.py`, several functions defer imports to avoid circular dependencies:

```python
# vendas/service.py:997
from app.concorrencia.models import Competitor, CompetitorSnapshot

# tasks.py:264
from sqlalchemy import cast, Date
from datetime import date as date_type

# financeiro/service.py:118-119
from app.vendas.models import Listing, ListingSnapshot
from app.produtos.models import Product
```

This pattern appears in 6+ places and is a signal of circular dependency issues that should be resolved at the module level.

---

## 3. SOLID Principles — Score: 62/100

### Single Responsibility Principle (SRP)

FAIL — `backend/app/vendas/service.py` (~1980 lines) is the primary SRP violation. It contains:
- Listing CRUD operations (`create_listing`, `get_listing`, `link_sku_to_listing`)
- Business analytics (`list_listings` with aggregation, period comparisons, RPV calculation)
- KPI computations (`get_kpi_by_period`, `_kpi_single_day`, `_kpi_date_range`)
- Health score calculation (`_calculate_health_score`, `calculate_quality_score_quick`)
- Price band analysis (`_calculate_price_bands`)
- Stock projection (`_calculate_stock_projection`)
- Alert generation (`_generate_alerts`)
- Mock data generation (`_generate_mock_snapshots`, `_generate_mock_analysis`)
- ML API synchronization (`sync_listings_from_ml`)
- Promotion management (`create_or_update_promotion`)
- Heatmap analytics (`get_sales_heatmap`)

These are at least 5 distinct responsibilities. Recommended split:

| New Module | Functions |
|---|---|
| `vendas/analytics.py` | `list_listings`, `get_funnel_analytics`, `get_sales_heatmap` |
| `vendas/kpi.py` | `get_kpi_by_period`, `_kpi_single_day`, `_kpi_date_range` |
| `vendas/health.py` | `_calculate_health_score`, `calculate_quality_score_quick` |
| `vendas/pricing.py` | `_calculate_price_bands`, `_calculate_stock_projection`, `_generate_alerts` |
| `vendas/sync.py` | `sync_listings_from_ml` |
| `vendas/mock.py` | `_generate_mock_snapshots`, `_generate_mock_analysis` |
| `vendas/crud.py` | `create_listing`, `get_listing`, `get_listing_snapshots`, `update_listing_price`, `link_sku_to_listing` |

FAIL — `backend/app/jobs/tasks.py` (~1283 lines) mixes Celery task orchestration with complex async business logic. Each `task_name()` + `_task_name_async()` pair carries significant processing logic that belongs in service files.

PASS — `backend/app/mercadolivre/client.py` is cleanly single-purpose: all ML API communication, one class, well organized.

PASS — `backend/app/financeiro/service.py` is acceptably focused on P&L calculations.

### Open/Closed Principle (OCP)

PARTIAL — The ML fee lookup uses a dict constant (`ML_FEES`) which is extensible without modification. But `calcular_taxa_ml` in `financeiro/service.py:14-31` has a hardcoded string comparison (`listing_type_lower not in ML_FEES`) that requires code change to add new types.

### Dependency Inversion (DIP)

PARTIAL — Services accept `AsyncSession` (interface) rather than concrete implementations, which is good. However, `consultor/service.py:474` constructs an `httpx.AsyncClient` inline rather than injecting it, making the Anthropic API call untestable without monkey-patching.

```python
# consultor/service.py:474
async with httpx.AsyncClient(timeout=90.0) as client:
    response = await client.post(ANTHROPIC_API_URL, ...)
```

### Interface Segregation (ISP)

FAIL — `list_listings` (`vendas/service.py:348`) is called by at least 3 different consumers (Dashboard, Anuncios, Consultor) but always returns the same large dict with 20+ fields, even when the caller needs only 3. There is no lightweight listing variant.

---

## 4. Cyclomatic Complexity — Score: 48/100

Functions exceeding cyclomatic complexity 10 are high-risk for bugs and maintenance.

### CRITICAL — `_sync_listing_snapshot_async` (tasks.py:65)

Estimated complexity: ~22. This function handles token refresh, item data extraction, SKU extraction from attributes, original_price logic, sale_price logic, promotion fetch fallback, listing_fees fetch, visits (bulk override or individual), paid orders loop, cancelled orders loop, returns loop, questions fetch, upsert logic (update vs insert), and finally listing field updates. It is a 290-line function with 7+ try/except blocks.

```
tasks.py:65-352 — _sync_listing_snapshot_async: ~290 lines, 22+ decision points
```

### CRITICAL — `list_listings` (vendas/service.py:348)

Estimated complexity: ~18. The function runs 5 separate database queries, has nested conditionals for period mode vs today mode, an inner `_aggregate_snaps` function, `_SnapProxy` class, and computes ~10 derived fields per listing in a 340-line body.

```
vendas/service.py:348-685 — list_listings: ~338 lines
```

### HIGH — `_formatar_listing` (consultor/service.py:233)

Estimated complexity: ~14. The function unpacks snapshot attributes using dual dict/object access patterns, formats 15+ conditional fields, and calls two sub-formatters.

```
consultor/service.py:233-350 — _formatar_listing: ~118 lines, 14+ branches
```

### HIGH — `get_listing_analysis` (vendas/service.py:908)

Estimated complexity: ~12. Has a mock fallback path, product lookup, snapshot conversion, multiple optional competitor/snapshot queries, and conditional alert generation.

```
vendas/service.py:908-1058 — get_listing_analysis: ~150 lines
```

### HIGH — `_sync_competitor_snapshots_async` (tasks.py:581)

Estimated complexity: ~11. Bulk visit fetch, per-competitor listing + account lookup, item fetch, delta calculation, title/seller_id update, visit lookup.

```
tasks.py:581-730 — _sync_competitor_snapshots_async: ~150 lines
```

### Acceptable Complexity (6-9)

- `calcular_margem` (financeiro/service.py:34): 4 — good
- `get_financeiro_resumo` (financeiro/service.py:109): 8 — acceptable
- `_kpi_single_day` (vendas/service.py:1112): 7 — acceptable
- `analisar_listings` (consultor/service.py:385): 8 — acceptable
- `HeatmapHourly` (Dashboard/index.tsx:143): 9 — at the limit

---

## 5. Code Smells — Score: 55/100

### CRITICAL — Mock data mixed with production code in vendas/service.py

Lines 20-131 of `vendas/service.py` contain a fully functional mock data generator that returns fake snapshots, price bands, promotions, and ads. This mock is served to real users when no token is available. This is:

1. Production code serving synthetic data without clear user notification
2. A 112-line block that inflates the module size
3. Named with `is_mock: True` flag but that flag is only checked client-side (and inconsistently)

The mock should either be in a `tests/` fixture or behind a clear `MOCK_ENABLED=true` env flag, not inlined in the production service.

### HIGH — `_SnapProxy` class defined inside a function body

```python
# vendas/service.py:520-523
class _SnapProxy:
    def __init__(self, d: dict):
        self.__dict__.update(d)
```

This dynamically-typed proxy object is created inside `list_listings` to make aggregated dict snapshots compatible with attribute access. It bypasses type checking entirely. It also appears to be a workaround for the fact that aggregated snapshots are returned as dicts while ORM snapshots are model instances — a symptom of the mixed data representation problem.

### HIGH — Magic numbers without named constants

```python
# vendas/service.py:39-40
visits = 400 + (i % 400)  # what does 400 mean?
sales = max(1, int(visits * (0.01 + (i % 8) * 0.01)))  # why 8?

# tasks.py:543
expires_in = token_data.get("expires_in", 21600)  # 21600 seconds not explained at use site

# consultor/service.py:17
MAX_LISTINGS = 20  # this one IS a named constant — good

# Dashboard/index.tsx:879-882
(estoque ?? 0) < 10  # magic 10 (low stock threshold) used in 2 places
Number(conversao) >= 3  # magic 3 for "green" conversion threshold
Number(conversao) >= 1  # magic 1 for "yellow" conversion threshold
```

The stock threshold of `10` appears independently in `Dashboard/index.tsx:879`, `Anuncios/index.tsx:457`, and potentially in backend alert generation — a triple-copy of the same business rule.

### HIGH — Bare `except Exception` swallowing too broadly

```python
# vendas/service.py:926-941
try:
    listing = await get_listing(db, mlb_id, user_id)
except HTTPException:
    # Returns mock without re-raising — silently serves fake data
    return _generate_mock_analysis(mock_listing, None)
```

Catching `HTTPException` to silently return mock data is a control-flow anti-pattern. If the listing is not found, a 404 is appropriate; the caller should decide whether to fall back to mock mode, not the data layer.

```python
# tasks.py:136, 157, 205, 227, 247, 255 — bare except Exception
except Exception:
    logger.debug(f"Não conseguiu buscar promoções para {listing.mlb_id}")
```

Some `except Exception` blocks at debug level have no fallback handling. This is acceptable in bulk sync tasks but should at minimum log the exception type.

### MEDIUM — Long inline lambda in sort key

```python
# vendas/service.py:231
return sorted(result, key=lambda x: float(x["price_range_label"].split("R$ ")[1].split("-")[0]))
```

This parses a formatted string label to extract the sort key. The sort key should instead be stored as a numeric field in `band_entry` during construction, not re-parsed from the display string.

### MEDIUM — Hardcoded BRT string in date formatting

```python
# backend/app/mercadolivre/client.py:175
date_from_str = f"{date_from.isoformat()}T00:00:00.000-03:00"
```

The `-03:00` offset is hardcoded in two places in client.py (lines 175-177 and 213-218). Brazil observes daylight saving time changes historically and the fixed offset is potentially incorrect for parts of the year.

### MEDIUM — Dead/stub code in production

```python
# vendas/service.py:1050
"promotions": [],  # TODO: integrar com ML API quando tiver token
```

```python
# vendas/service.py:1064-1078
async def update_listing_price(...) -> dict:
    """Altera preço de um anúncio (será integrado com ML API)."""
    listing.price = new_price  # only updates DB, does not call ML API
```

Stub implementations with TODO comments are acceptable in development but these have been present long enough to appear in sprint-5 scope. They should be tracked as known limitations in a TODO registry rather than inline comments.

### MINOR — f-strings used in logging calls (performance)

```python
# tasks.py:60
logger.error(f"Erro ao sincronizar snapshot de {listing_id}: {exc}")
```

Using f-strings in `logger.error()` evaluates the string even when the log level would suppress it. Prefer `logger.error("Erro ao sincronizar snapshot de %s: %s", listing_id, exc)` or `logger.error(...)` with lazy formatting. This pattern appears ~40 times across tasks.py.

---

## 6. Type Safety — Score: 72/100

### Python

PASS — `calcular_taxa_ml` and `calcular_margem` have complete type annotations with `Decimal | None`.

PASS — Most async service functions declare return types (`-> dict`, `-> list[dict]`, `-> Listing`).

FAIL — `list_listings` at `vendas/service.py:348` has return type `list[dict]` but the dict structure is undocumented and contains mixed types (`_SnapProxy` objects, ORM instances, computed floats). Callers receive no type safety.

```python
# vendas/service.py:348 — return type is a lie
async def list_listings(db: AsyncSession, user_id: UUID, period: str = "today") -> list[dict]:
```

The dict contains `last_snapshot` which can be either a `ListingSnapshot` ORM object, a `_SnapProxy` object, or `None`. This ambiguity causes the dual access pattern in `consultor/service.py:274-281`:

```python
# consultor/service.py:274-281
stock = snap.get("stock") if isinstance(snap, dict) else getattr(snap, "stock", None)
visits = snap.get("visits") if isinstance(snap, dict) else getattr(snap, "visits", None)
# ... 6 more lines of the same dual-access pattern
```

**Fix:** Define a `SnapshotData` TypedDict or Pydantic model and use it consistently.

FAIL — `run_async` in `tasks.py:31` has no type annotations:

```python
def run_async(coro):  # no annotation on coro or return type
```

Should be:
```python
from typing import TypeVar, Coroutine, Any
T = TypeVar("T")
def run_async(coro: Coroutine[Any, Any, T]) -> T:
```

PARTIAL — `get_financeiro_resumo` parameter `user_id` is untyped (just `user_id` with no annotation), as is `user_id` in `get_financeiro_detalhado` and `get_financeiro_timeline`.

```python
# financeiro/service.py:109
async def get_financeiro_resumo(
    db: AsyncSession,
    user_id,        # missing type annotation: should be UUID
    period: str = "30d",
) -> dict[str, Any]:
```

This appears in all 3 financeiro service functions.

### TypeScript

PASS — Service types are defined (`ListingOut`, `FunnelData`, `HeatmapData`).

FAIL — The `kpi` response object is accessed with unvalidated string keys:

```tsx
// Dashboard/index.tsx:613
{ label: "7 dias", data: kpi?.["7dias"] },
```

The `["7dias"]` bracket access bypasses TypeScript's type checker. The KPI type should have explicit properties.

PARTIAL — `Dashboard/index.tsx:411` uses broad fallback chaining without type narrowing:

```tsx
const totalPedidos = filteredListings.reduce(
  (sum, l) => sum + (l.last_snapshot?.orders_count ?? l.last_snapshot?.sales_today ?? 0),
  0
);
```

The `orders_count ?? sales_today` fallback is a business logic decision (use orders when available, fall back to sales units) that is repeated 4 times in the codebase without documentation.

---

## 7. Error Handling — Score: 78/100

### PASS — MLClient has structured retry logic

`client.py:55-105` implements a clean retry loop with exponential backoff for timeouts and 5xx errors, rate-limit handling for 429, and explicit 401 propagation. This is above average quality for a production HTTP client.

### PASS — Celery tasks use self.retry with countdown

```python
# tasks.py:62
raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

Exponential backoff on task retry is correct.

### PASS — consultor/service.py has granular exception handling

`consultor/service.py:478-496` distinguishes `HTTPStatusError`, `TimeoutException`, and `RequestError` with appropriate HTTP status codes returned to the caller. This is clean and production-ready.

### FAIL — Token refresh on 401 is not automatic in MLClient

When `get_item()` raises `MLClientError(status_code=401)`, callers in tasks.py do not automatically attempt a token refresh. The token refresh is only done by the separate `refresh_expired_tokens` task. If a token expires mid-sync, all remaining items in that sync run will fail with 401 errors.

```python
# client.py:79-80
if response.status_code == 401:
    raise MLClientError("Token ML expirado ou inválido", status_code=401)
# No retry-with-refresh here
```

### FAIL — `_sync_orders_async` does not rollback on per-order errors

```python
# tasks.py:858-898
for order_raw in results:
    try:
        # ... process order
    except Exception as e:
        logger.warning(f"Erro ao processar pedido {ml_order_id}: {e}")
        total_errors += 1
        continue
```

A partial exception mid-loop can leave some orders committed and others not. The outer `await db.commit()` at the end of the function commits all successfully processed orders, but if an exception occurs after a partial write within the order processing (e.g., flush succeeds, then relationship assignment fails), the session may be in an inconsistent state.

### FAIL — `get_listing_analysis` silently returns mock on any 404

```python
# vendas/service.py:927-941
try:
    listing = await get_listing(db, mlb_id, user_id)
except HTTPException:
    return _generate_mock_analysis(mock_listing, None)
```

Any `HTTPException` (including 403, 500, or database errors recast as HTTPException) triggers the mock path. The catch should be narrowed to `status_code == 404`.

### PARTIAL — Missing connection pool exhaustion handling

`run_async` in tasks.py creates a new event loop per task. Combined with `AsyncSessionLocal()` context managers inside each task, there is no explicit limit on concurrent database connections during a bulk sync. Under load, this could exhaust the PostgreSQL connection pool.

---

## 8. Additional Observations

### Thread-Safety Issue — Global Rate Limiter

```python
# client.py:12-13
_last_request_time: float = 0.0
_RATE_LIMIT_DELAY = 1.0

# client.py:46-53
async def _rate_limit(self):
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _RATE_LIMIT_DELAY:
        await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.monotonic()
```

The global `_last_request_time` is a module-level variable shared across all `MLClient` instances. In a multi-worker (Celery) deployment, each worker process has its own copy of this variable, so the rate limiter only throttles within a single worker — not across all workers. If 4 Celery workers each have 1 `MLClient` instance, they can collectively fire 4 requests/second against the ML API's 1 req/sec limit.

**Fix:** Use Redis as a distributed rate limiter, or at minimum document that the per-worker limit needs to be adjusted based on worker count.

### Missing Pagination in list_listings

`vendas/service.py:356-361` loads all listings for a user with no limit:

```python
result = await db.execute(
    select(Listing)
    .where(Listing.user_id == user_id)
    .order_by(Listing.created_at.desc())
)
listings = result.scalars().all()
```

For a user with 500+ listings, this also loads 5 separate subqueries (latest snap, 7d snaps, yesterday snaps, period snaps, prev-period snaps) per listing. At 500 listings this would be 2500+ snapshot rows loaded into memory on every dashboard load.

### N+1 Pattern Risk in _sync_competitor_snapshots_async

`tasks.py:648-677` runs 2 database queries per competitor inside a loop:

```python
for comp in competitors:
    listing_result = await db.execute(select(Listing).where(...))
    acc_result = await db.execute(select(MLAccount).where(...))
    client = MLClient(account.access_token)
    item_data = await client.get_item(...)
```

For 50 competitors this is 100+ DB queries plus 50 ML API calls. The DB queries should be batched before the loop using a single JOIN or IN() query.

---

## 9. Prioritized Recommendations

### Priority 1 — Immediate (high impact, low risk)

1. **Extract `Variacao` component** from Dashboard and Anuncios into `frontend/src/components/Variacao.tsx`. Zero logic change, eliminates a copy-paste bug vector. Estimated effort: 15 minutes.

2. **Extract `exportCSV` utility** into `frontend/src/lib/exportUtils.ts` with a `columns` parameter. Eliminates divergent copies. Estimated effort: 30 minutes.

3. **Extract KPI period table** into `frontend/src/components/KpiPeriodTable.tsx`. Eliminates ~50 lines of JSX duplication between pages. Estimated effort: 45 minutes.

4. **Add `_normalize_mlb_id` helper** to `MLClient`. Replaces 9 duplicated normalization blocks. Estimated effort: 20 minutes.

5. **Add type annotation to `user_id` parameters** in `financeiro/service.py` (3 functions). Zero behavior change. Estimated effort: 5 minutes.

### Priority 2 — Short-term (this sprint)

6. **Move `Variacao`, `HeatmapHourly`, `HeatmapDaily`, `ConversionFunnel` components** out of page files into `frontend/src/components/`. Reduces Dashboard/index.tsx from ~930 lines to ~400 lines.

7. **Replace `_SnapProxy` with a `SnapshotData` TypedDict** and enforce consistent dict-vs-object access. This fixes the dual `isinstance(snap, dict)` pattern in `consultor/service.py`.

8. **Move mock data** to `backend/tests/fixtures/mock_snapshots.py` or gate behind `MOCK_MODE=true` env variable. Remove from production service.

9. **Extract `list_listings` into `vendas/analytics.py`** and `get_kpi_by_period` + helpers into `vendas/kpi.py`. This is the single highest-impact refactor for long-term maintainability.

10. **Fix narrowing in `get_listing_analysis`** — catch only `HTTPException` with `status_code == 404`, not all HTTPExceptions.

### Priority 3 — Technical debt (next sprint)

11. **Split `_sync_listing_snapshot_async`** into smaller composable steps: `_fetch_item_data`, `_fetch_orders_for_item`, `_build_snapshot_fields`, `_upsert_snapshot`. Each under 50 lines and individually testable.

12. **Batch competitor DB queries** in `_sync_competitor_snapshots_async`. Load all listings and accounts in 2 queries before the loop instead of 2 per competitor.

13. **Implement distributed rate limiting** for MLClient using Redis counter to enforce the 1 req/sec limit across all Celery workers.

14. **Add type annotations for `run_async`** and audit for bare `except Exception` blocks that suppress exceptions at debug level without re-raising.

15. **Extract frontend aggregation logic** (`totalPedidos`, `totalUnidades`, `totalReceita`, etc.) into a `useListingTotals(filteredListings)` custom hook shared by Dashboard and Anuncios.

---

## 10. Files with Highest Risk

| File | Lines | Risk Level | Primary Issue |
|---|---|---|---|
| `backend/app/vendas/service.py` | ~1980 | CRITICAL | God class — 11+ responsibilities, complexity ~18 in list_listings |
| `backend/app/jobs/tasks.py` | ~1283 | HIGH | _sync_listing_snapshot_async complexity ~22, N+1 in competitors |
| `frontend/src/pages/Dashboard/index.tsx` | ~929 | HIGH | 5 copy-paste violations, 6 inline components |
| `frontend/src/pages/Anuncios/index.tsx` | ~518 | MEDIUM | Copy-paste from Dashboard, all 5 violations present |
| `backend/app/mercadolivre/client.py` | ~596 | LOW | DRY only — global rate limiter thread-safety |
| `backend/app/financeiro/service.py` | ~553 | LOW | Minor: DRY in query structure, missing type annotations |
| `backend/app/consultor/service.py` | ~502 | LOW | Dual-access pattern, untestable httpx client |

---

## Conclusion

The codebase is functional and demonstrates good domain understanding and business logic correctness. Security practices are acceptable (IDOR checks present, JWT enforced, no secrets in code). The error handling in the ML client is notably good.

The core quality debt is structural rather than logical: two files (`vendas/service.py` and `tasks.py`) have accumulated too many responsibilities over rapid sprint development. The frontend has clear copy-paste debt between Dashboard and Anuncios that is straightforward to fix.

Addressing Priority 1 items (5 quick wins) would improve the DRY score from 54 to ~75 with minimal risk. Addressing Priority 2 (structural refactors) would bring the overall score from 65 to approximately 80.

The global rate limiter issue in `client.py` is the only finding with potential production impact — it can cause ML API rate limit errors under concurrent worker deployments and should be documented or fixed before scaling to multiple Celery workers.
