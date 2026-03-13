# MSM_Pro — Architecture Review Report

**Date:** 2026-03-12
**Reviewer:** Senior Architecture Reviewer
**Scope:** Read-only analysis of full codebase at `C:\Users\Maikeo\MSM_Imports_Mercado_Livre\MSM_Pro`
**Overall Score: 74 / 100**

---

## Summary

MSM_Pro is a well-structured sales-intelligence dashboard for Mercado Livre sellers. In five sprints the team assembled a FastAPI + Celery + PostgreSQL backend with a React/TypeScript SPA frontend. The layered module pattern (models / schemas / service / router) is applied consistently across 13 backend modules, and the data model is carefully version-controlled through 10 incremental Alembic migrations.

The score of 74 reflects a healthy foundation with several concrete gaps that will create friction as the product scales beyond a single seller account. The most significant issues are: a monolithic `vendas/service.py` carrying business logic that belongs to other domains, a global mutable rate-limiter in the ML client that will break under concurrent Celery workers, OAuth tokens stored in plain text in the database, and a missing query-optimization layer (no indexes on composite filter columns most queries use).

---

## Architecture Diagram

```
                         EXTERNAL
                        +---------+
                        |  ML API |  (api.mercadolibre.com)
                        | Anthropic|  (claude-sonnet-4)
                        +---------+
                             |
         +-----------+  httpx  |  httpx  +----------+
         |  Celery   |<--------+-------->|  FastAPI  |
         |  Worker   |                   |  Backend  |
         |  + Beat   |                   |           |
         +-----------+                   +----------+
               |                              |
         async via                     async SQLAlchemy
         asyncio.new_event_loop()             |
               |                             \|/
        +------+------+               +--------------+
        |  PostgreSQL  |<------------->|  PostgreSQL  |
        |  (Railway)   |               |  (Railway)   |
        +--------------+               +--------------+
               |
        +------+------+
        |    Redis     |
        |  broker/bknd |
        +--------------+

  FRONTEND (React SPA / Railway)
  +-----------------------------------+
  |  BrowserRouter                    |
  |   /login         Login            |
  |   /dashboard     Dashboard        |
  |   /anuncios      Anuncios         |
  |   /anuncios/:id  AnuncioDetalhe   |
  |   /produtos      Produtos         |
  |   /concorrencia  Concorrencia     |
  |   /reputacao     Reputacao        |
  |   /financeiro    Financeiro (lazy)|
  |   /publicidade   Publicidade(lazy)|
  |   /alertas       Alertas          |
  |   /configuracoes Configuracoes    |
  +-----------------------------------+
  Auth: Zustand (persist) + localStorage(msm_access_token)
  HTTP:  Axios + request/response interceptors
  Query: TanStack React Query (assumed per stack; not verified in all pages)

  BACKEND MODULE MAP
  +------------------------------------------------------------------+
  |  app/                                                            |
  |  +- core/         config, database, celery_app, deps, constants  |
  |  +- auth/         User, MLAccount, JWT login, OAuth ML callback  |
  |  +- produtos/     Product (SKU + cost)                          |
  |  +- vendas/       Listing, ListingSnapshot, Order — CORE MODULE  |
  |  +- concorrencia/ Competitor, CompetitorSnapshot                 |
  |  +- alertas/      AlertConfig, AlertEvent, email engine          |
  |  +- financeiro/   P&L, timeline, cash-flow D+8                  |
  |  +- reputacao/    ReputationSnapshot, risk simulator             |
  |  +- ads/          AdCampaign, AdSnapshot (ML API fallback)       |
  |  +- consultor/    Claude AI analysis (httpx -> Anthropic)        |
  |  +- mercadolivre/ MLClient (httpx async, retry, rate-limit)      |
  |  +- jobs/         Celery tasks (8 scheduled tasks)               |
  |  +- ws/           WebSocket placeholder (not deployed)           |
  +------------------------------------------------------------------+

  DATABASE TABLES (10 migrations)
  users -> ml_accounts -> listings -> listing_snapshots
                       -> orders
                       -> competitors -> competitor_snapshots
                       -> alert_configs -> alert_events
       -> products (linked to listings via product_id nullable)
  ml_accounts -> reputation_snapshots
              -> ad_campaigns -> ad_snapshots
```

---

## Section 1 — Folder Structure and Module Organization

**Score: 8 / 10**

### Findings

The `backend/app/` tree contains 13 modules, each owning its `models.py`, `schemas.py`, `service.py`, and `router.py`. This is the correct layered decomposition for a FastAPI monolith at this scale and team size.

The `core/` package correctly centralises cross-cutting concerns: `config.py` (Pydantic Settings), `database.py` (engine + session factory), `celery_app.py` (beat schedule), `deps.py` (JWT dependency), and `constants.py` (ML fee table). The separation of `constants.py` to hold `ML_FEES` is a good decision — it provides a single source of truth referenced by both `financeiro/service.py` and `vendas/service.py`.

The `jobs/tasks.py` orchestrator imports directly from multiple domain services, which is unavoidable in a single-process monolith but means all module contracts are indirectly exercised via Celery at runtime.

The `ws/` stub directory exists in the source tree but is not wired into `main.py`. It creates confusion about what is live vs planned.

### Recommendations

- Remove or archive `ws/` until WebSocket is actually implemented. Empty stubs rot and mislead new contributors.
- Consider a `shared/` or `utils/` package for the `run_async` helper in `tasks.py`, which is a cross-cutting concern. Currently it is private to `tasks.py` but will be needed in any future scheduled task that calls async code.

---

## Section 2 — Separation of Concerns

**Score: 6 / 10**

### Findings

The models/schemas/service/router separation is formally observed, but there are meaningful violations worth addressing.

**Violation 1 — Business logic in the router layer.**
`backend/app/vendas/router.py` lines 139-178 embed a full database query for the `list_orders` endpoint directly inside the route handler. It builds the SQLAlchemy query, resolves ML account IDs, filters and pages results — all without calling a service function. This is identical logic that belongs in `vendas/service.py`.

**Violation 2 — Health score calculation called from the router with private service function.**
`router.py` line 278 calls `service._calculate_health_score(...)` using the leading-underscore convention that signals "private to this module." The router is reaching into the service's private API, indicating the health-score endpoint's controller logic belongs entirely in the service layer.

**Violation 3 — Cross-domain imports inside `financeiro/service.py`.**
`financeiro/service.py` contains lazy imports inside functions: `from app.vendas.models import Listing, ListingSnapshot` and `from app.auth.models import MLAccount`. While functional, this pattern hides dependency edges and makes the module graph harder to reason about. The imports should appear at module level.

**Violation 4 — `consultor/service.py` imports and calls `vendas/service.list_listings` and `vendas/service.get_kpi_by_period`.**
This creates a direct module dependency from `consultor` to `vendas`, which is acceptable, but neither the `consultor` module nor `vendas` has an explicit interface contract (e.g. a protocol or abstract base). If `list_listings` signature changes, `consultor` will fail silently at runtime.

**Violation 5 — Inline DB queries in `jobs/tasks.py`.**
The tasks file executes raw SQLAlchemy queries (select(Listing), select(MLAccount), etc.) rather than calling service functions. This duplicates query logic that also lives in the service layer.

### Recommendations

1. Move the `list_orders` inline query from `vendas/router.py` to a `service.list_orders(...)` function. Priority: medium.
2. Rename `_calculate_health_score` to `calculate_health_score` (no leading underscore) or restructure the endpoint to let the service return the full health payload. Priority: low.
3. Move lazy in-function imports in `financeiro/service.py` to top of file. Priority: low.
4. Extract Celery task DB queries into service-layer calls. This reduces duplication and means service tests automatically validate what Celery runs. Priority: medium.

---

## Section 3 — Dependency Flow Between Modules

**Score: 7 / 10**

### Findings

The dependency graph is mostly acyclic and flows in the expected direction: `core` is the root, domain modules depend on `core`, and `jobs` + `consultor` depend on domain modules.

```
core
 +-- auth         (no outgoing domain deps)
 +-- produtos     (no outgoing domain deps)
 +-- mercadolivre (no outgoing domain deps)
 +-- vendas       --> financeiro (calcular_margem, calcular_taxa_ml)
                  --> core.constants (ML_FEES_FLOAT)
                  --> produtos (Product model)
 +-- concorrencia --> (no outgoing domain deps)
 +-- alertas      --> vendas (Listing, ListingSnapshot models, implicit)
 +-- financeiro   --> vendas (Listing, ListingSnapshot, Order — lazy)
                  --> produtos (Product — lazy)
                  --> auth (MLAccount — lazy)
 +-- reputacao    --> auth (MLAccount)
 +-- ads          --> auth (MLAccount)
 +-- consultor    --> vendas (list_listings, get_kpi_by_period)
                  --> concorrencia (Competitor, CompetitorSnapshot)
 +-- jobs         --> auth, vendas, concorrencia, reputacao, ads (direct)
```

There are no circular imports. The longest dependency chain is `jobs -> vendas -> financeiro -> [vendas, produtos, auth]`, which is three levels deep and manageable.

The `financeiro` module indirectly depends on `vendas` models but lives at the same hierarchy level. This hints that `financeiro` should be positioned architecturally below `vendas`, which it effectively is at runtime. The implicit topology should be made explicit in the module documentation.

### Recommendations

- Document the module dependency graph in a single file (`docs/module_dependencies.md`). As the codebase grows, undocumented implicit edges become bugs.
- Consider extracting the `calcular_taxa_ml` and `calcular_margem` functions from `financeiro/service.py` into `core/` or a dedicated `pricing/` module, since both `vendas` and `financeiro` consume them. Currently `vendas/service.py` imports from `financeiro/service.py`, which inverts the expected "financeiro is a consumer, not a provider" semantic.

---

## Section 4 — Database Design

**Score: 7 / 10**

### Findings

**Schema design is solid.** UUIDs as primary keys, timezone-aware timestamps everywhere, `CASCADE` deletes that correctly propagate deletions from users down to all owned data, and `NOT NULL` constraints applied appropriately.

**Migration history is clean.** Ten sequential Alembic revisions with clear names, no skipped branches. `down_revision` chains have been corrected (the memory file notes `0010` had an incorrect `down_revision` that was fixed from `0008` to `0009`).

**ListingSnapshot growth is unbounded.** There is no partition strategy or archival policy. With a daily sync of 16 listings across all active accounts, the table grows at approximately 5,840 rows per year per account. At current scale this is trivial. At 100 accounts with 100 listings each, the table grows at 3.65 million rows per year. Without a `captured_at` range partition or a retention job, query performance for the analytics endpoints will degrade as this table grows.

**Missing composite indexes.** The most common query pattern — `WHERE listing_id = $1 AND captured_at >= $2` — has individual indexes on both columns but no composite index. PostgreSQL can use an index merge but a composite index `(listing_id, captured_at DESC)` is more efficient for this exact access pattern. The same applies to `competitor_snapshots(competitor_id, captured_at)` and `orders(ml_account_id, order_date)`.

**ML tokens stored in plain text.** `ml_accounts.access_token` and `refresh_token` are `String(2000)` columns with no encryption at rest. If the database is compromised, all connected ML accounts are immediately exposed. The comment in the model (`# Tokens armazenados criptografados`) incorrectly suggests encryption is applied — it is not visible in any migration or model code.

**Order deduplication relies on unique constraint only.** `orders.ml_order_id` has a `UNIQUE` constraint. The sync task must handle the `UniqueConstraint` violation with an upsert pattern (`ON CONFLICT DO UPDATE`) rather than catching database exceptions. Verify the sync logic does this correctly.

### Recommendations

1. Add composite indexes on `(listing_id, captured_at DESC)`, `(competitor_id, captured_at DESC)`, and `(ml_account_id, order_date DESC)` via a new migration. Priority: high — will have measurable impact on dashboard load time at scale.
2. Implement token encryption: use `cryptography.fernet` to encrypt `access_token` and `refresh_token` before storage, decrypt on read. Update the model comment to reflect actual behavior. Priority: high — security risk.
3. Plan a snapshot retention policy: after 90 days, migrate snapshots to a cheaper `listing_snapshots_archive` table or delete them. Priority: medium.
4. Add a `captured_at` range partition to `listing_snapshots` when row count exceeds 5 million. Priority: low/future.

---

## Section 5 — API Design Patterns

**Score: 8 / 10**

### Findings

All routes use the consistent prefix `/api/v1/` with module-level sub-prefixes (`/listings`, `/competitors`, `/alerts`, `/financeiro`, etc.). Route handlers are thin wrappers that delegate to service functions — this is correct.

**Fixed-path routes before dynamic-path routes is handled correctly.** The comment on line 79 of `vendas/router.py` explicitly notes that `/kpi/summary`, `/analytics/funnel`, etc. must precede `/{mlb_id}`. This is correct and shows awareness of FastAPI's path matching order.

**Validation is applied at the schema level.** `ListingCreate` validates `mlb_id` format with a regex pattern. `CreatePromotionIn` bounds `discount_pct` to 5–60. `period` query parameters use regex patterns. This is appropriate.

**The webhook endpoint is a stub.** `POST /api/v1/notifications` at the bottom of `main.py` accepts the ML notification payload and returns `{"status": "received"}` without processing it. This endpoint is registered on the main app object rather than through a router, mixing concerns. If ML sends real webhook events to production, they are silently dropped.

**Health check lacks database and Redis probes.** The `GET /health` endpoint returns `{"status": "ok"}` unconditionally without checking database or Redis connectivity. Railway uses this path as the health check (`healthcheckPath: /health`). A false positive means Railway considers the service healthy even when the database connection pool is exhausted.

**No API versioning strategy beyond the prefix.** Breaking changes to a schema require clients to update simultaneously. For the current single-tenant, single-frontend setup this is acceptable, but it should be documented as a constraint.

### Recommendations

1. Implement the ML webhook endpoint in a proper `webhooks/router.py` module. At minimum, log the payload and trigger an async sync for the affected listing. Priority: medium.
2. Enhance the health check to probe database and Redis: execute a `SELECT 1` and `redis.ping()` and return 503 if either fails. Priority: high — misleading health probes cause silent production failures.
3. Document the v1 API contract as frozen. When v2 is needed, create a `v2` prefix rather than modifying existing responses. Priority: low.

---

## Section 6 — Frontend Architecture

**Score: 8 / 10**

### Findings

The frontend is a well-structured React 18 SPA with TypeScript, Vite, Tailwind CSS, and shadcn/ui. The routing layer in `App.tsx` is clean: `ProtectedRoute` wraps all authenticated pages, `Login` is exposed publicly, and the catch-all redirects to `/login`. Two heavy modules (`Financeiro`, `Publicidade`) are lazily loaded with `React.lazy` and `Suspense` — a correct code-splitting decision.

**Token synchronisation is correctly implemented.** `authStore.setAuth()` calls `setStoredToken()` which writes to `localStorage(msm_access_token)`. The Axios interceptor reads from the same key. The Zustand store also persists under `msm-auth-storage` via the `persist` middleware. Both storage locations are kept in sync on login and cleared together on logout. This matches the documented requirement in `CLAUDE.md`.

**Single Zustand store for auth.** There is only one `authStore.ts`. As the product grows (notifications, preferences, feature flags), a single store file risks becoming a catch-all. Modular stores (one per domain) are preferable.

**Service layer is well-structured.** Ten service files mirror the backend module map. Each calls `api.ts` (the shared Axios instance) and returns typed responses. This is the correct abstraction boundary.

**No global error boundary.** If a lazy-loaded component throws, the entire app unmounts with no user-facing fallback. Adding `<ErrorBoundary>` wrapping at the route level would contain failures.

**`Layout.tsx` has no Suspense or loading state for nav transitions.** Since `Financeiro` and `Publicidade` are lazily loaded, fast navigation to those pages shows the `<div>Carregando...</div>` fallback. This is functional but the fallback text is hardcoded Portuguese — it should use a proper `Skeleton` component from the shared UI library.

### Recommendations

1. Add a top-level `ErrorBoundary` component wrapping the router. This is a one-file change with high defensive value. Priority: medium.
2. Replace the `Carregando...` fallback divs with a `PageSkeleton` component that matches the layout. Priority: low.
3. Split Zustand into domain slices as the store grows (e.g., `uiStore` for sidebar state, `settingsStore` for preferences). Priority: low.

---

## Section 7 — Infrastructure

**Score: 7 / 10**

### Findings

**Docker Compose is production-complete for local development.** Five services (postgres, redis, backend, celery_worker, celery_beat) with health-check `depends_on` conditions, named volumes, and an optional Flower dashboard. This is a solid local development environment.

**The backend Dockerfile is minimal and correct.** Python 3.12-slim base, system dependencies (gcc, libpq-dev), pip-installed requirements, then source copy. The `CMD` runs `alembic upgrade head` before `uvicorn`, which means migrations are applied on every container start. This is safe for Railway's single-instance deployment but is a race condition risk when running multiple replicas simultaneously (two containers running `alembic upgrade head` in parallel against the same database is safe due to Alembic's locking but adds latency).

**The frontend Dockerfile uses a multi-stage build correctly.** Stage 1 builds the Vite SPA, stage 2 serves it with Express (`server.js`) for SPA routing. The `npx vite build` approach avoids the TypeScript `tsc` path-alias failures documented in `CLAUDE.md`.

**No secrets management.** Secrets (ML_CLIENT_SECRET, SECRET_KEY, ANTHROPIC_API_KEY) are passed as plain Railway environment variables. There is no Vault, AWS Secrets Manager, or equivalent. For the current single-team setup this is acceptable but represents a risk if Railway environment variables are ever exposed in logs or deployment configs.

**Celery worker concurrency is hardcoded at 4.** `celery -A app.core.celery_app worker --loglevel=info --concurrency=4`. This value should be an environment variable (`CELERY_CONCURRENCY`) to allow tuning on Railway without a code change.

**Beat and Worker are separate containers (correct).** Running `celery beat` as a separate process prevents the common mistake of running both in the same container with `--beat`, which can cause double-scheduling.

**No Celery task deduplication.** If a scheduled task is still running when the next schedule fires (e.g., `sync_all_snapshots` takes longer than 24 hours for large accounts), a second instance will start concurrently. Celery's `task_acks_late=True` combined with `task_time_limit=600` prevents most stuck-task scenarios, but a task lock pattern (Redis SETNX) should be added for the daily sync tasks.

### Recommendations

1. Add a `CELERY_CONCURRENCY` environment variable. Priority: low.
2. Implement a task deduplication lock for `sync_all_snapshots` and `sync_competitor_snapshots` using `celery-singleton` or a manual Redis lock. Priority: medium.
3. Move `alembic upgrade head` to a Railway deployment hook or a separate one-off container rather than running on every uvicorn startup. This is safer for future multi-replica deployments. Priority: medium.
4. Document the Railway environment variable list with descriptions and required/optional status. Currently this exists in `CLAUDE.md` but not in a machine-readable format. Priority: low.

---

## Section 8 — Scalability Assessment

**Score: 5 / 10**

This is the area with the most potential technical debt. The current architecture serves one seller account well. The following constraints will become friction points as the user base grows.

### Finding 1 — Global rate limiter in `MLClient` is a shared mutable state

`backend/app/mercadolivre/client.py` lines 12-13:
```python
_last_request_time: float = 0.0
_RATE_LIMIT_DELAY = 1.0
```

These are module-level globals. Inside a single `uvicorn` worker process, all concurrent async tasks share the same `_last_request_time`. This means:
- Two concurrent `MLClient` instances (e.g., two requests for different users both syncing) correctly contend on the rate limit within one process.
- But with 4 Celery workers, each worker process has its own `_last_request_time`. Four workers can each fire 1 request per second to the ML API, resulting in 4 requests/second per ML account — potentially exceeding the per-seller rate limit if they all happen to be processing the same seller's account simultaneously.

**Recommendation:** Replace the in-process global with a Redis-backed rate limiter using a token-bucket or sliding-window algorithm. Use a key like `ml_rate_limit:{ml_user_id}` to apply the limit per ML account rather than per process. Priority: high.

### Finding 2 — `vendas/service.py` is a god service

The service file at `backend/app/vendas/service.py` is 92 KB per the tool output. It contains: sync logic, listing analytics, KPI aggregation, health scores, heatmap generation, funnel analytics, promotion management, price update, SKU linking, and order management. This single file handles the majority of the product's business logic. At this size it is already difficult to navigate and will become harder to test and maintain as features accumulate.

**Recommendation:** Extract into sub-services: `vendas/sync_service.py` (ML sync), `vendas/analytics_service.py` (heatmap, funnel, KPI), `vendas/listing_service.py` (CRUD + health). This is a refactor, not a rewrite. Priority: medium.

### Finding 3 — No caching layer for read-heavy endpoints

The `/listings/` endpoint, called on every dashboard page load, executes multiple SQL queries: one to fetch all listings for the user, one per listing to get the latest snapshot (if not using a join), then computed fields. The KPI summary runs aggregation queries on every request. These queries have no cache TTL — every frontend polling cycle issues a fresh database query.

**Recommendation:** Add Redis-backed response caching with a 60-second TTL for `list_listings` and `get_kpi_by_period`. Use `user_id` as the cache key. Invalidate on sync completion. Priority: medium.

### Finding 4 — ML sync is sequential, not parallel

In `jobs/tasks.py`, the `sync_all_snapshots` task iterates over all active ML accounts and listings in a loop, making one API call per listing per ML account. With 1 request/second rate limit and 100 listings, a full sync takes at least 100 seconds. With 10 accounts of 100 listings each, it takes at least 1,000 seconds — breaking the 600-second Celery task time limit.

The code does use `asyncio.gather` in some sub-functions, but the top-level loop over accounts appears sequential.

**Recommendation:** Use `celery.group` or `chord` to fan out one Celery task per ML account, running accounts in parallel with independent rate limiters. Priority: high for multi-account growth.

### Finding 5 — No pagination on `list_listings`

`GET /listings/` returns all listings for the authenticated user with no `limit`/`offset` pagination. At 16 listings this is fine. At 500 listings this would serialize a large JSON payload on every dashboard load.

**Recommendation:** Add pagination (`offset`, `limit`, default 100) to `list_listings`. Priority: low for current scale, medium for future.

---

## Section 9 — Coupling Assessment

**Score: 7 / 10**

### Findings

**Low coupling at the module boundary level.** Each domain module exposes its functionality through `service.py` functions. The router never reaches into another module's models directly — it calls its own service, which may in turn call another service.

**Medium coupling through the `Listing` model.** The `Listing` model in `vendas/models.py` is referenced by five other modules: `concorrencia` (FK on `competitors.listing_id`), `alertas` (FK on `alert_configs.listing_id`), `financeiro` (JOIN), `consultor` (via `list_listings` return), and `jobs/tasks.py` (direct select). The `Listing` model is the central domain object — this is appropriate — but any schema change to it cascades to all these modules.

**Tight coupling in `consultor/service.py`.** The Consultor IA module calls `vendas.service.list_listings` and `vendas.service.get_kpi_by_period` to build the prompt. It receives raw `dict` objects returned by those functions and accesses specific field names like `l["id"]`, `l["mlb_id"]`, `l.get("last_snapshot")`. If the `list_listings` response shape changes (e.g., a field is renamed), the consultor will either fail silently or send incomplete data to Claude. There is no typed contract between the two modules.

**The `financeiro/service.py` functions accept `user_id` without type annotation** (they use a plain Python `user_id` parameter, not `UUID`). This means type checkers cannot catch calls with the wrong type.

### Recommendations

1. Add type annotations to all service function signatures that accept `user_id`. Use `UUID` from the `uuid` module. Priority: low but cumulative.
2. Define a `ListingData` TypedDict or Pydantic model for the dict returned by `list_listings` and consumed by `consultor/service.py`. This makes the contract explicit and catches field renames at check time. Priority: medium.
3. When adding the next major feature module, consider using a domain event system (even a simple in-process one) rather than direct service imports, to reduce coupling between modules like `consultor` and `vendas`. Priority: low/future.

---

## Section 10 — Security Architecture

**Score: 5 / 10**

This section has the most critical findings.

### Finding 1 — ML OAuth tokens stored unencrypted

`ml_accounts.access_token` and `ml_accounts.refresh_token` are `VARCHAR(2000)` columns. The model source file has the comment `# Tokens armazenados criptografados` on line 63 but no encryption is applied in the model, service, or migration code. If the Railway PostgreSQL database is compromised (credential leak, snapshot exposure), all ML OAuth tokens are exposed in plaintext.

**Recommendation:** Encrypt tokens using `cryptography.Fernet` symmetric encryption with a `TOKEN_ENCRYPTION_KEY` env variable. Encrypt on write in `auth/service.py`, decrypt on read. Priority: critical.

### Finding 2 — JWT secret has an insecure default

`config.py` line 25:
```python
secret_key: str = "insecure-default-secret-change-in-production"
```
If the `SECRET_KEY` environment variable is not set in Railway, the application starts with this known-plaintext secret. Any JWT signed with the default key can be forged by anyone who reads this source file.

**Recommendation:** Change the default to `None` and add a startup validation that raises `ValueError` if `SECRET_KEY` is not set in non-development environments. Priority: high.

### Finding 3 — No rate limiting on authentication endpoints

`POST /api/v1/auth/login` has no rate limiting. An attacker can attempt unlimited password combinations against the single `maikeo@msmrp.com` account. FastAPI has no built-in rate limiting; add `slowapi` (a FastAPI-compatible rate limiter backed by Redis) to the login and token-refresh endpoints.

**Recommendation:** Add `slowapi` with a limit of 10 login attempts per minute per IP. Priority: high.

### Finding 4 — CORS configuration includes hardcoded production URLs in code

`main.py` lines 42-47 hardcode `https://msmprofrontend-production.up.railway.app` alongside the configurable `settings.frontend_url`. If the frontend URL changes, both the env variable and the hardcoded list need updating.

**Recommendation:** Remove the hardcoded URL from the list and rely solely on `settings.frontend_url` + the `allow_origin_regex`. Priority: low.

### Finding 5 — No HTTPS enforcement or HSTS headers

Railway terminates TLS at the load balancer, so the application itself does not need to handle HTTPS, but adding `Strict-Transport-Security` headers via a middleware would protect against accidental HTTP fallbacks.

---

## Section 11 — Technical Debt Assessment

**Score: 7 / 10**

### High-Priority Debt

| Item | Location | Impact | Effort |
|------|----------|--------|--------|
| Global rate limiter (race condition under concurrency) | `mercadolivre/client.py:12` | High — silent API throttling with multiple workers | Medium |
| Unencrypted ML tokens | `auth/models.py:64` | Critical — security exposure | Medium |
| Insecure JWT secret default | `core/config.py:25` | High — authentication bypass risk | Low |
| Missing composite DB indexes | migrations | Medium — query degradation at scale | Low |
| Inline query in router (`list_orders`) | `vendas/router.py:139` | Medium — unmaintainable, untestable | Low |

### Medium-Priority Debt

| Item | Location | Impact | Effort |
|------|----------|--------|--------|
| God service `vendas/service.py` (92 KB) | `vendas/service.py` | Medium — onboarding friction, test coverage gaps | High |
| Mock data path in production service | `vendas/service.py:23` | Low-Medium — mock data can pollute production responses | Low |
| No health check DB/Redis probe | `main.py:73` | Medium — false-positive health status | Low |
| No pagination on `list_listings` | `vendas/router.py:39` | Medium — latency at scale | Medium |
| Celery tasks bypass service layer | `jobs/tasks.py` | Low-Medium — logic duplication | Medium |

### Low-Priority Debt

| Item | Location | Impact | Effort |
|------|----------|--------|--------|
| Dead `ws/` module stub | `app/ws/` | Low — confusion, dead code | Low |
| Hardcoded CORS URL | `main.py:46` | Low — deployment friction | Low |
| No error boundary in frontend | `App.tsx` | Low — UX degradation on error | Low |
| Untyped `user_id` parameters | Multiple services | Low — type safety gap | Low |
| Missing module dependency docs | N/A | Low — onboarding friction | Low |

---

## Prioritised Recommendations

### P1 — Critical Security (do now)

1. **Encrypt ML OAuth tokens at rest.** Implement `Fernet` symmetric encryption in `auth/service.py`. Requires a new `TOKEN_ENCRYPTION_KEY` env variable and a data migration to re-encrypt existing tokens. File: `/backend/app/auth/service.py`, `/backend/app/auth/models.py`.

2. **Harden JWT secret configuration.** Change the default in `config.py` from the plaintext string to `None`, and add a startup assertion: `if settings.environment != "development" and not settings.secret_key: raise ValueError("SECRET_KEY must be set")`. File: `/backend/app/core/config.py`.

3. **Fix health check to probe dependencies.** Add SQLAlchemy `SELECT 1` and Redis `PING` to the `/health` endpoint and return HTTP 503 on failure. File: `/backend/app/main.py`.

### P2 — High Impact Performance and Reliability (next sprint)

4. **Add composite database indexes.** Add a migration with: `CREATE INDEX ix_listing_snapshots_listing_captured ON listing_snapshots (listing_id, captured_at DESC)`, and equivalent indexes on `competitor_snapshots` and `orders`. File: new migration `0011_add_composite_indexes.py`.

5. **Replace global rate limiter with Redis-backed per-account limiter.** Replace `_last_request_time` global with `aioredis`-backed sliding window. File: `/backend/app/mercadolivre/client.py`.

6. **Add rate limiting to the login endpoint.** Add `slowapi` to `requirements.txt` and apply `@limiter.limit("10/minute")` to the login route. File: `/backend/app/auth/router.py`.

### P3 — Maintainability (backlog)

7. **Move `list_orders` query from router to service.** Create `service.list_orders(db, user_id, period, mlb_id)`. File: `/backend/app/vendas/service.py`, `/backend/app/vendas/router.py`.

8. **Implement ML webhook handler** in a proper router module. File: new `/backend/app/webhooks/router.py`.

9. **Add response caching for `list_listings` and `get_kpi_by_period`** using Redis with a 60-second TTL. File: `/backend/app/vendas/service.py`.

10. **Break `vendas/service.py` into sub-modules**: `sync_service.py`, `analytics_service.py`, `listing_service.py`. This is a refactor sprint of its own.

### P4 — Future Architecture (planning horizon)

11. **Partition `listing_snapshots` by `captured_at` month** when row count exceeds 5 million. Use PostgreSQL declarative partitioning.

12. **Fan-out Celery sync with `group`** to parallelize across ML accounts.

13. **Add pagination to `GET /listings/`** before user count grows beyond 50.

---

## Final Scorecard

| Dimension | Score |
|-----------|-------|
| Folder structure and module organisation | 8/10 |
| Separation of concerns | 6/10 |
| Dependency flow | 7/10 |
| Database design | 7/10 |
| API design patterns | 8/10 |
| Frontend architecture | 8/10 |
| Infrastructure | 7/10 |
| Scalability | 5/10 |
| Coupling | 7/10 |
| Security | 5/10 |
| **Overall** | **74/100** |

The architectural foundation is sound and the codebase reflects a team that has accumulated real operational experience (the `CLAUDE.md` documents 10 hard-won lessons from production incidents). The gap between the current 74 and a score above 85 is closed primarily by addressing the three security findings (P1) and four reliability/performance findings (P2). None of these require architectural rewrites — they are targeted improvements to existing code.
