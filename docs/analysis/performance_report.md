# MSM_Pro — Performance Analysis Report

**Date:** 2026-03-12
**Scope:** Read-only static analysis (no runtime profiling)
**Analyst:** Performance Engineer Agent
**Codebase:** FastAPI + React + PostgreSQL + Celery + Redis

---

## Overall Score: 58 / 100

The system is architecturally sound for its current scale (16 active listings, 1 seller account) but carries several design patterns that will degrade non-linearly as listings, snapshots, and orders grow. The most critical issues are in the Celery sync task (sequential API calls with 1 req/s delay per listing), the `list_listings` function running 4-6 database queries per request, and a missing composite index that forces full snapshot table scans on the most common query pattern. The frontend is lean and well-structured, with only minor bundling concerns.

---

## Findings by Severity

### CRITICAL

---

#### C-1: Sequential ML API Calls in `sync_listing_snapshot` — O(n) Blocking at 1 req/s

**File:** `backend/app/jobs/tasks.py`, lines 181-256
**Impact:** For 16 listings, each sync fires 4 sequential ML API calls: `get_item`, `get_item_orders_by_status(paid)`, `get_item_orders_by_status(cancelled)`, `get_item_orders_by_status(returned)`. With rate limiting at 1 req/s enforced by a global lock, one listing takes a minimum of 4 seconds to sync, plus retry overhead.

At 16 listings this means approximately 64 seconds minimum per individual sync. The `sync_all_snapshots` task dispatches 16 sub-tasks via Celery `.delay()`, which helps parallelism only if multiple workers are running. With a single Celery worker (the typical Railway free-tier deployment), all 16 tasks queue sequentially.

The rate limit in `client.py` line 51-53 uses a **process-global** variable `_last_request_time`. When Celery tasks run in separate OS processes (not threads), this global is per-process and provides no cross-task coordination. Each worker process enforces rate limiting only within itself, risking 429 responses when multiple workers are active simultaneously.

```python
# client.py line 11-13 — global variable is per-process, not cluster-wide
_last_request_time: float = 0.0
_RATE_LIMIT_DELAY = 1.0
```

**Cost at scale:** 100 listings × 4 calls × 1s/call = 400s minimum with 1 worker. ML will return 429s without cluster-level coordination.

**Recommendation:** Consolidate cancelled and returned orders into the single `get_item_orders_by_status` call (fetch all statuses, filter locally). This cuts 4 calls per listing to 2 (get_item + orders). Rate limit coordination should move to Redis using a sliding window counter.

---

#### C-2: `list_listings` Issues 4-6 Database Queries Per Request

**File:** `backend/app/vendas/service.py`, lines 356-685
**Impact:** Every call to `GET /listings/` executes the following sequential database round-trips:

1. `SELECT * FROM listings WHERE user_id = ?` — fetches all listings
2. `SELECT listing_snapshots WHERE listing_id IN (...) AND captured_at >= period_date` — period snapshots (if period mode)
3. `SELECT listing_snapshots WHERE listing_id IN (...) AND captured_at BETWEEN prev_dates` — previous period for variation (if period mode)
4. Subquery join for latest snapshot per listing — always executed
5. `SELECT listing_snapshots WHERE listing_id IN (...) AND captured_at >= 7d ago` — 7-day velocity window — always executed
6. Subquery join for yesterday's snapshot — always executed (for today mode variation)

Even in `today` mode, queries 4, 5, and 6 all run. All of these are correctly using `IN (listing_ids)` so they are not N+1 queries — they are bulk fetches. However, 4-6 sequential async round-trips to PostgreSQL across Railway's internal network add 20-80ms of latency each, totaling 80-480ms per request before any Python computation.

**Recommendation:** Consolidate queries 4, 5, and 6 into a single SQL query using window functions (`ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY captured_at DESC)`). This would reduce to 2 round-trips total: one for listings, one for all snapshot data needed.

---

### HIGH

---

#### H-1: Missing Composite Index on `listing_snapshots(listing_id, captured_at)`

**File:** `backend/migrations/versions/0001_initial.py`, lines 158-159
**Impact:** The two most frequent query patterns against `listing_snapshots` are:

```sql
-- Pattern A (latest snapshot per listing)
SELECT * FROM listing_snapshots
WHERE listing_id IN (...)
ORDER BY captured_at DESC

-- Pattern B (date range filter)
SELECT * FROM listing_snapshots
WHERE listing_id IN (...)
AND captured_at >= ?
AND captured_at <= ?
```

Currently there are two separate single-column indexes: `ix_listing_snapshots_listing_id` and `ix_listing_snapshots_captured_at`. PostgreSQL cannot use both simultaneously in a single scan for the above patterns. It will pick one index (typically `listing_id`) and then re-filter the matching rows by date in memory.

For a table with 365 days × 16 listings = 5,840 rows (1 year), this is acceptable. At 3 years × 100 listings = 109,500 rows, the post-index filter becomes a meaningful cost.

**Missing index:**
```sql
CREATE INDEX ix_listing_snapshots_listing_captured
ON listing_snapshots (listing_id, captured_at DESC);
```

This composite index covers both patterns in a single index scan. The migration should also add this for `competitor_snapshots(competitor_id, captured_at DESC)` for the same reason.

**Additional missing index:** `orders(ml_account_id, order_date DESC)` — the `get_cashflow` function at `financeiro/service.py` line 468-478 joins `Order` to `MLAccount` and filters by `payment_status` + `shipping_status`. None of the status columns are indexed.

---

#### H-2: N+1 Pattern in `_sync_competitor_snapshots_async` — DB Query Inside Loop

**File:** `backend/app/jobs/tasks.py`, lines 648-720
**Impact:** For each competitor in the outer loop, two database queries execute:

```python
# Line 651-654: Query 1 — fetch listing for this competitor
listing_result = await db.execute(
    select(Listing).where(Listing.id == comp.listing_id)
)

# Line 659-662: Query 2 — fetch ML account for this listing
acc_result = await db.execute(
    select(MLAccount).where(MLAccount.id == listing.ml_account_id)
)
```

With 10 competitors (one per listing), this is 20 extra queries. With 50 competitors, it is 100 queries. These relationships are predictable and should be loaded eagerly at the beginning using a JOIN or `selectinload`.

```python
# Current: 2N queries for N competitors
# Fix: 1 query with joined load
result = await db.execute(
    select(Competitor)
    .options(selectinload(Competitor.listing).selectinload(Listing.ml_account))
    .join(Listing, Competitor.listing_id == Listing.id)
    .where(Competitor.is_active == True)
)
```

---

#### H-3: `sync_orders` Processes Only `order_items[0]` — Multi-Item Orders Silently Dropped

**File:** `backend/app/jobs/tasks.py`, line 869 (`first_item = order_items[0]`)
**Impact:** This is a correctness and revenue-accuracy issue with performance implications. Orders with multiple line items (different MLB IDs in a single checkout) only record the first item. The revenue and order count stored in the `orders` table is therefore undercounted, which cascades into incorrect cashflow projections from `get_cashflow`.

This also means the `net_amount` accumulated in the cashflow query will undercount released funds, making the D+8 projection unreliable for sellers who bundle products.

**Recommendation:** Iterate over all `order_items`, upsert one `Order` row per line item (using `ml_order_id + mlb_id` as composite unique key rather than just `ml_order_id`). Migration 0009 uses `ml_order_id` as unique — this constraint would need to change.

---

#### H-4: Rate Limit Global State is Not Thread/Process Safe

**File:** `backend/app/mercadolivre/client.py`, lines 11-53
**Impact:** `_last_request_time` is a module-level float. In the FastAPI application (uvicorn, async), this is safe because all coroutines share one process. But Celery workers run in separate processes — the global is not shared between them. Two Celery workers can both read `_last_request_time = 0`, both decide no sleep is needed, and fire simultaneous requests. With more than 2 workers, this will cause 429 rate limit errors systematically.

The fix requires moving rate limit state to Redis:
```python
# Redis sliding window: max 1 request per second per access_token
pipe = redis.pipeline()
pipe.incr(f"ml_ratelimit:{token_hash}")
pipe.expire(f"ml_ratelimit:{token_hash}", 2)
count = pipe.execute()[0]
if count > 1:
    await asyncio.sleep(1.0)
```

---

### MEDIUM

---

#### M-1: `list_listings` Performs Client-Side Sort After DB Fetch

**File:** `frontend/src/pages/Dashboard/index.tsx`, lines 391-395
**File:** `backend/app/vendas/service.py`, line 358-360

The backend returns listings ordered by `Listing.created_at DESC`, but the frontend immediately re-sorts by `sales_today`:

```typescript
// Dashboard/index.tsx lines 391-395
const sortedListings = [...displayListings].sort((a, b) => {
    const salesA = a.last_snapshot?.sales_today ?? 0;
    const salesB = b.last_snapshot?.sales_today ?? 0;
    return salesB - salesA;
});
```

This client-side sort is acceptable for 16 listings but means the API is returning rows in a useless order. The backend should sort by `sales_today DESC` from the database so the frontend gets pre-ordered data. This also means any pagination added in future will page over an already-sorted result set.

The `service.py` query at line 358 uses `.order_by(Listing.created_at.desc())` which is a stub sort that gets thrown away.

---

#### M-2: `get_kpi_by_period` Executes 5 Separate DB Queries (Today + Ontem + Anteontem + 7d + 30d)

**File:** `backend/app/vendas/service.py` — `get_kpi_by_period` function
**Impact:** The KPI summary endpoint runs 5 independent date-range aggregation queries. Each query filters `listing_snapshots` by `user_id` (via join to `listings`) and a date range. With the missing composite index (H-1), these 5 queries each do a listing_id index scan followed by date filtering.

A single query grouping by `cast(captured_at, Date)` and then filtering in Python would reduce this to 1 round-trip.

---

#### M-3: `_calculate_price_bands` Inner Loop with O(n) Linear Search for Optimal Band

**File:** `backend/app/vendas/service.py`, lines 219-228

```python
if total_margin > max_margin:
    if optimal_band_key is not None:
        # O(n) linear scan through result list to clear previous optimal
        for item in result:
            if item.get("is_optimal"):
                item["is_optimal"] = False
                break
```

For each new band that beats the current max, the code scans the entire `result` list to find and clear the previous optimal. This is O(n²) in the worst case where margins keep increasing. With 30 days of data and price band sizes of R$15, there are approximately 10-20 bands, making this O(200-400) operations. Not critical now, but trivially fixable:

```python
# Track optimal index instead of scanning
optimal_idx = None
for i, (band_key, band_data) in enumerate(sorted(price_bands.items())):
    ...
    if total_margin > max_margin:
        if optimal_idx is not None:
            result[optimal_idx]["is_optimal"] = False
        optimal_idx = len(result)
        max_margin = total_margin
        band_entry["is_optimal"] = True
    result.append(band_entry)
```

---

#### M-4: `financeiro/service.py` Runs `_aggregate` Twice — Doubled Query Cost

**File:** `backend/app/financeiro/service.py`, lines 218-219

```python
atual = await _aggregate(data_inicio, data_fim)
anterior = await _aggregate(prev_inicio, prev_fim)
```

`_aggregate` itself runs 2 queries (snapshots + product costs). Calling it twice means 4 queries per `/financeiro/resumo` request. The two date ranges could be fetched in one query using `CASE WHEN` or `FILTER` aggregation:

```sql
SELECT
    CASE WHEN captured_at >= current_start THEN 'atual' ELSE 'anterior' END as period,
    SUM(revenue) as revenue, ...
FROM listing_snapshots
JOIN listings ON ...
WHERE captured_at >= prev_start AND captured_at <= current_end
GROUP BY period, listing_id, ...
```

---

#### M-5: `get_cashflow` Loads All Pending Orders into Python Memory

**File:** `backend/app/financeiro/service.py`, lines 468-478

```python
rows = await db.execute(
    select(Order)
    .join(MLAccount, ...)
    .where(...)
    .order_by(Order.order_date.asc())
)
orders = rows.scalars().all()
```

Full ORM objects (all columns) are loaded for every pending order. With 500+ orders, this loads unnecessary columns (`buyer_nickname`, `mlb_id`, etc.) that are not used in the cashflow calculation. The query only needs `delivery_date`, `order_date`, `shipping_status`, and `net_amount`.

Use `.with_only_columns()` or a targeted `select()` to fetch only required columns.

---

#### M-6: `sync_orders` Has No Pagination Safeguard Beyond 50 Orders

**File:** `backend/app/jobs/tasks.py`, lines 838-856
**Impact:** The sync task paginates with `limit=50` and continues while `results` is non-empty. However, the `get_orders` method at `client.py` line 562 also defaults to `limit=50`. For sellers with high order volume (>50 orders in 2 days), the pagination loop is correct. But there is no maximum page guard — a seller with 10,000 orders could cause the task to page through 200 ML API calls, each rate-limited to 1/s, taking 200+ seconds and blocking the Celery worker for the entire `task_time_limit=600s` window.

**Recommendation:** Add a max-pages safeguard (e.g., 20 pages = 1,000 orders) with a log warning when the limit is hit.

---

### LOW

---

#### L-1: Frontend — 7 of 9 Heavy Pages Missing Lazy Loading

**File:** `frontend/src/App.tsx`, lines 3-12

Only `Financeiro` and `Publicidade` use `lazy()`. The other 7 routes (`Dashboard`, `Anuncios`, `AnuncioDetalhe`, `Concorrencia`, `Alertas`, `Configuracoes`, `Reputacao`, `Produtos`) are eagerly imported. `Dashboard/index.tsx` is 929 lines and imports from Recharts, lucide-react, and multiple services — it is the largest page and ironically the one that should be loaded fastest (it's the landing page), so eager loading here is correct. However `Anuncios`, `Concorrencia`, and `Reputacao` are secondary pages that could be lazy-loaded.

`Dashboard` eager loading is intentional and correct. `AnuncioDetalhe` (detail view) should be lazy-loaded as it is only accessed from the listings table.

**Recommendation:**
```typescript
const AnuncioDetalhe = lazy(() => import("@/pages/Anuncios/AnuncioDetalhe"));
const Concorrencia = lazy(() => import("@/pages/Concorrencia"));
const Reputacao = lazy(() => import("@/pages/Reputacao"));
```

---

#### L-2: Dashboard Computes 7 `reduce()` Aggregations on Every Render

**File:** `frontend/src/pages/Dashboard/index.tsx`, lines 410-424

```typescript
const totalPedidos = filteredListings.reduce(...)
const totalUnidades = filteredListings.reduce(...)
const totalReceita = filteredListings.reduce(...)
const totalEstoque = filteredListings.reduce(...)
const totalEstoqueValor = filteredListings.reduce(...)
const totalVisitas = filteredListings.reduce(...)
```

Six sequential `reduce` calls iterate over `filteredListings` once each. These should be combined into a single pass:

```typescript
const totals = useMemo(() =>
  filteredListings.reduce((acc, l) => {
    acc.pedidos += l.last_snapshot?.orders_count ?? 0;
    acc.unidades += l.last_snapshot?.sales_today ?? 0;
    // ...
    return acc;
  }, { pedidos: 0, unidades: 0, ... }),
[filteredListings]);
```

All six values also recalculate on every re-render (including hover events over the heatmap grid), because they are not wrapped in `useMemo`. With `setTooltip` state changes in `HeatmapHourly` (line 144), the parent `Dashboard` component re-renders, recomputing all six reduces.

---

#### L-3: Heatmap Inner Computation Not Memoized — Recalculates on Every Tooltip Hover

**File:** `frontend/src/pages/Dashboard/index.tsx`, lines 147-159

The `HeatmapHourly` component builds a `Map` lookup and finds `peakCell` on every render. Each `onMouseEnter` triggers `setTooltip` which re-renders `HeatmapHourly`, rebuilding the `Map` from `data.data` (which is constant). These should be inside `useMemo`:

```typescript
const lookup = useMemo(() => {
  const m = new Map<string, number>();
  for (const cell of data.data) m.set(`${cell.day_of_week}-${cell.hour}`, cell.count);
  return m;
}, [data.data]);
```

---

#### L-4: `get_competitor_history` Uses Two Sequential Queries (Auth Check + Data Fetch)

**File:** `backend/app/concorrencia/service.py`, lines 204-230

The function first validates competitor ownership (1 query), then fetches snapshots (1 query). These can be combined into a single query with a JOIN that simultaneously validates ownership and returns snapshot data:

```python
result = await db.execute(
    select(CompetitorSnapshot)
    .join(Competitor, CompetitorSnapshot.competitor_id == Competitor.id)
    .join(Listing, Competitor.listing_id == Listing.id)
    .where(
        Competitor.id == competitor_id,
        Listing.user_id == user_id,
        CompetitorSnapshot.captured_at >= cutoff,
    )
    .order_by(CompetitorSnapshot.captured_at.asc())
)
```

Return 0 rows when competitor doesn't belong to user (raise 404).

---

#### L-5: `run_async` Creates a New Event Loop Per Celery Task

**File:** `backend/app/jobs/tasks.py`, lines 31-38

```python
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

Each Celery task creates and destroys an event loop. This is the correct pattern for sync Celery workers running async code, and there is no practical alternative without switching to a `gevent` or `asyncio` Celery pool. This is a known overhead. Considered for documentation only.

---

#### L-6: `_sync_recent_snapshots_async` — Hourly Task Uses Wrong Trigger

**File:** `backend/app/jobs/tasks.py`, lines 474-498
**File:** `backend/app/core/celery_app.py`, line 50

`sync_recent_snapshots` runs every hour and re-syncs listings where `updated_at >= now - 2h`. However, `updated_at` is updated by `sync_listing_snapshot` itself (line 322: `listing.updated_at = datetime.now(timezone.utc)`), so every listing that was synced in the last daily run will be re-synced hourly for 2 hours after the daily run. This means 16 listings × 2 hourly re-syncs = 32 redundant syncs per day. The intent is to capture price changes, but the trigger should be based on `price` or `status` change, not `updated_at`.

---

#### L-7: Connection Pool Sizing — Max Overflow May Be Too High for Railway Single Instance

**File:** `backend/app/core/database.py`, lines 8-13

```python
engine = create_async_engine(
    ...
    pool_size=10,
    max_overflow=20,
)
```

Max connections = 30. Railway's PostgreSQL free tier limits to 25 connections. If the Celery worker and FastAPI server share the same database, the combined pool could reach 30 + (Celery) = 50+ connections, exceeding PostgreSQL's `max_connections`. Celery workers should use a separate, smaller pool (pool_size=3, max_overflow=5) initialized at worker startup, not shared with the web server pool.

---

## Caching Opportunities

Redis is deployed but underutilized for application-level caching. The following endpoints serve data that changes at most once per sync cycle (daily or every 2 hours):

| Endpoint | Cache Key | TTL | Benefit |
|---|---|---|---|
| `GET /listings/kpi/summary` | `kpi:{user_id}` | 1h | 5 DB queries → 0 |
| `GET /listings/analytics/funnel?period=*` | `funnel:{user_id}:{period}` | 30m | 2 DB queries → 0 |
| `GET /listings/analytics/heatmap?period=*` | `heatmap:{user_id}:{period}` | 30m | 1 DB query → 0 |
| `GET /financeiro/resumo?period=*` | `fin_resumo:{user_id}:{period}` | 1h | 4 DB queries → 0 |
| `GET /financeiro/timeline?period=*` | `fin_timeline:{user_id}:{period}` | 1h | 1 DB query → 0 |

Cache invalidation: Celery tasks call `cache.delete_pattern(f"kpi:{user_id}*")` at the end of `sync_listing_snapshot`. This would make the most-used dashboard endpoints instant for the duration between syncs.

---

## Optimizations Prioritized by Impact

| Priority | Fix | Estimated Gain | Effort |
|---|---|---|---|
| 1 | Add composite index `listing_snapshots(listing_id, captured_at DESC)` | 40-60% query time reduction for all snapshot queries | 30 min (1 migration) |
| 2 | Cache KPI, funnel, heatmap, financeiro in Redis | Near-zero latency for dashboard loads between syncs | 2-3h |
| 3 | Consolidate 4 ML API calls per listing to 2 (get_item + one orders call) | 50% sync time reduction | 2h |
| 4 | Eager-load Listing + MLAccount in competitor sync loop | Eliminate N+1, ~20 queries → 1 | 30 min |
| 5 | Merge 6 `reduce()` calls in Dashboard into 1 with `useMemo` | Smoother UI on hover/filter | 30 min |
| 6 | Move rate limit state to Redis | Correct multi-worker behavior, prevent 429s at scale | 3h |
| 7 | Consolidate `list_listings` 4-6 queries using window functions | 70% reduction in DB round-trips | 4h |
| 8 | Lazy-load `AnuncioDetalhe`, `Concorrencia`, `Reputacao` | Faster initial bundle parse | 30 min |
| 9 | Add orders composite index on `(ml_account_id, order_date DESC)` | Faster cashflow queries | 15 min |
| 10 | Deduplicate `_aggregate` double-call in financeiro resumo | 2 queries saved per KPI load | 1h |

---

## Architecture Notes

### What is Working Well

- Bulk visits fetch (`get_items_visits_bulk`) correctly batches 50 items per call, reducing N visits calls to ceil(N/50). This is a good pattern.
- Connection pool has `pool_pre_ping=True` which prevents stale connection errors on Railway.
- `task_acks_late=True` + `worker_prefetch_multiplier=1` in Celery config are correct for reliability.
- The `upsert` pattern in `sync_listing_snapshot` (update existing day's snapshot vs insert new) prevents duplicate rows and is correct.
- `selectinload` is imported in `vendas/service.py` and is available for use — it just needs to be applied to the competitor sync and other query sites.
- Pagination is implemented in `sync_orders` (while loop with offset/limit).
- All ownership checks are present (no IDOR vulnerabilities in the sampled endpoints).
- `expire_on_commit=False` on the session factory prevents lazy-load AttributeErrors after commit.

### Data Volume Projections

| Metric | Current | 1 Year | 3 Years |
|---|---|---|---|
| Listings | 16 | 50 | 150 |
| Snapshots per listing per year | 365 | 365 | 365 |
| Total snapshot rows | 5,840 | 18,250 | 164,250 |
| Orders per day (estimated) | ~20 | ~100 | ~500 |
| Total order rows | ~720 | ~36,500 | ~547,500 |

The composite index (Priority 1) becomes critical before 50,000 snapshot rows. The caching layer (Priority 2) becomes essential before 100 listings where the KPI query scans 36,500+ snapshot rows for a single user.

---

## Files Referenced

| File | Lines of Interest |
|---|---|
| `backend/app/vendas/service.py` | 348-685 (`list_listings`), 688-746 (`get_funnel_analytics`) |
| `backend/app/jobs/tasks.py` | 65-353 (`_sync_listing_snapshot_async`), 581-730 (`_sync_competitor_snapshots_async`), 806-1000+ (`_sync_orders_async`) |
| `backend/app/mercadolivre/client.py` | 11-53 (rate limiter global state) |
| `backend/app/financeiro/service.py` | 127-233 (`get_financeiro_resumo` double aggregate) |
| `backend/app/concorrencia/service.py` | 194-250 (two-query ownership check pattern) |
| `backend/app/core/database.py` | 8-13 (pool sizing) |
| `backend/migrations/versions/0001_initial.py` | 158-159 (missing composite index) |
| `backend/migrations/versions/0009_create_ads_and_orders.py` | 181 (no composite index on orders) |
| `frontend/src/App.tsx` | 3-12 (missing lazy imports) |
| `frontend/src/pages/Dashboard/index.tsx` | 147-159 (heatmap memo), 391-424 (six reduces) |
