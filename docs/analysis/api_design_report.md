# MSM_Pro API Design Report

**Generated:** 2026-03-12
**Scope:** REST API — FastAPI backend (`backend/app/`)
**Specification standard evaluated against:** OpenAPI 3.1 / REST maturity model

---

## Overall Score: 72 / 100

| Category | Score | Max |
|---|---|---|
| REST Conventions (HTTP methods, status codes) | 16 | 20 |
| Endpoint Naming Consistency | 11 | 15 |
| Schema Design (Pydantic) | 14 | 15 |
| Error Handling | 9 | 15 |
| Authentication / Authorization | 9 | 10 |
| Pagination | 4 | 10 |
| API Versioning | 5 | 5 |
| Query Parameter Design | 7 | 10 |
| Response Envelope Consistency | 4 | 10 |
| OpenAPI / Swagger Completeness | 3 | 5 |

---

## Endpoint Inventory

### Auth (`/api/v1/auth`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| POST | `/auth/register` | No | 201 | `UserOut` | Correct |
| POST | `/auth/login` | No | 200 | `Token` | Correct |
| GET | `/auth/me` | JWT | 200 | `UserOut` | Correct |
| GET | `/auth/ml/connect` | JWT | 200 | `MLConnectURL` | Returns URL, non-mutating — GET is appropriate |
| GET | `/auth/ml/callback` | No | 302 | Redirect | OAuth callback, GET is correct per OAuth 2.0 spec |
| GET | `/auth/ml/accounts` | JWT | 200 | `list[MLAccountOut]` | Correct |
| DELETE | `/auth/ml/accounts/{account_id}` | JWT | 204 | None | Soft-delete, but returns 204 correctly |

### Listings / Vendas (`/api/v1/listings`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| POST | `/listings/sync` | JWT | 200 | `dict` (untyped) | Missing `response_model` |
| GET | `/listings/` | JWT | 200 | `list[ListingOut]` | Correct |
| POST | `/listings/` | JWT | 201 | `ListingOut` (manual dict) | Returns raw dict, bypasses response_model |
| GET | `/listings/kpi/summary` | JWT | 200 | `dict` (untyped) | Missing `response_model` |
| GET | `/listings/analytics/funnel` | JWT | 200 | `FunnelOut` | Correct |
| GET | `/listings/analytics/heatmap` | JWT | 200 | `HeatmapOut` | Correct |
| GET | `/listings/orders/` | JWT | 200 | `list[OrderOut]` | Trailing slash inconsistency (see below) |
| GET | `/listings/{mlb_id}` | JWT | 200 | `ListingOut` | Correct |
| GET | `/listings/{mlb_id}/snapshots` | JWT | 200 | `list[SnapshotOut]` | Correct |
| GET | `/listings/{mlb_id}/analysis` | JWT | 200 | `ListingAnalysisOut` | Correct |
| GET | `/listings/{mlb_id}/margem` | JWT | 200 | `MargemResult` | PT-BR path segment; param via Query |
| GET | `/listings/{mlb_id}/health` | JWT | 200 | `dict` (untyped) | Missing `response_model`; bare `except` swallows errors |
| PATCH | `/listings/{mlb_id}/price` | JWT | 200 | `dict` (untyped) | Missing `response_model` |
| POST | `/listings/{mlb_id}/promotions` | JWT | 200 | `dict` (untyped) | Should be 201; missing `response_model` |
| PATCH | `/listings/{mlb_id}/sku` | JWT | 200 | `ListingOut` | Correct |

### Competitors / Concorrencia (`/api/v1/competitors`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/competitors/` | JWT | 200 | `list[CompetitorOut]` | Correct |
| POST | `/competitors/` | JWT | 201 | `CompetitorOut` | Correct |
| GET | `/competitors/listing/{listing_id}` | JWT | 200 | `list[CompetitorOut]` | Sub-resource path is non-standard (see below) |
| GET | `/competitors/sku/{product_id}` | JWT | 200 | `list[CompetitorOut]` | Sub-resource path is non-standard |
| DELETE | `/competitors/{competitor_id}` | JWT | 204 | None | Correct |
| GET | `/competitors/{competitor_id}/history` | JWT | 200 | `CompetitorHistoryOut` | Correct |

### Alerts / Alertas (`/api/v1/alertas`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/alertas/` | JWT | 200 | `list[AlertConfigOut]` | Correct |
| POST | `/alertas/` | JWT | 201 | `AlertConfigOut` | Correct |
| GET | `/alertas/events/` | JWT | 200 | `list[AlertEventOut]` | `events` should be a sub-collection, not a fixed path |
| GET | `/alertas/events/{alert_id}` | JWT | 200 | `list[AlertEventOut]` | Misleading: `alert_id` in path suggests it's the event's own ID |
| GET | `/alertas/{alert_id}` | JWT | 200 | `AlertConfigOut` | Correct |
| PUT | `/alertas/{alert_id}` | JWT | 200 | `AlertConfigOut` | Should be PATCH (partial update) |
| DELETE | `/alertas/{alert_id}` | JWT | 204 | None | Soft-delete; 204 correct |

### Products / Produtos (`/api/v1/produtos`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/produtos/` | JWT | 200 | `list[ProductOut]` | Correct |
| POST | `/produtos/` | JWT | 201 | `ProductOut` | Correct |
| GET | `/produtos/{product_id}` | JWT | 200 | `ProductOut` | Correct |
| PUT | `/produtos/{product_id}` | JWT | 200 | `ProductOut` | Full-replace PUT; payload is `ProductUpdate` with all-Optional fields — should be PATCH |
| DELETE | `/produtos/{product_id}` | JWT | 204 | None | Soft-delete; 204 correct |

### Financeiro (`/api/v1/financeiro`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/financeiro/resumo` | JWT | 200 | `FinanceiroResumoOut` | Correct |
| GET | `/financeiro/detalhado` | JWT | 200 | `FinanceiroDetalhadoOut` | Correct |
| GET | `/financeiro/timeline` | JWT | 200 | `FinanceiroTimeSeriesOut` | Correct |
| GET | `/financeiro/cashflow` | JWT | 200 | `CashFlowOut` | Correct |

### Ads / Publicidade (`/api/v1/ads`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/ads/` | JWT | 200 | `AdsDashboardOut` | Correct |
| GET | `/ads/{campaign_id}` | JWT | 200 | `AdsCampaignDetailOut` | Correct |
| POST | `/ads/sync` | JWT | 200 | `dict` (untyped) | Missing `response_model`; `status_code=200` on POST is non-standard action |

### Reputation / Reputacao (`/api/v1/reputation`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| GET | `/reputation/current` | JWT | 200 | `ReputationCurrentOut` | Correct |
| GET | `/reputation/history` | JWT | 200 | `list[ReputationSnapshotOut]` | Correct |
| POST | `/reputation/sync` | JWT | 200 | `dict` (untyped) | Missing `response_model` |
| GET | `/reputation/risk-simulator` | JWT | 200 | `ReputationRiskOut` | Correct; but "simulator" is not a REST noun |

### Consultor IA (`/api/v1/consultor`)

| Method | Path | Auth | Status Code | Response Model | Notes |
|---|---|---|---|---|---|
| POST | `/consultor/analisar` | JWT | 200 | `ConsultorResponse` | PT-BR verb; should return 200 (not 201, no resource created); acceptable for RPC-style action |

### System / Webhook

| Method | Path | Auth | Status Code | Notes |
|---|---|---|---|---|
| GET | `/health` | No | 200 | Health check; outside `/api/v1/` prefix (intentional) |
| GET | `/` | No | 200 | Root info |
| POST | `/api/v1/notifications` | No | 200 | Webhook receiver lacks auth; registered in `main.py` directly (not a router) |

---

## Design Pattern Analysis

### 1. REST Conventions — 16/20

**What is done well:**

- HTTP verbs are largely correct. `GET` for reads, `POST` for creates, `DELETE` for deletes.
- `DELETE` consistently returns `204 No Content` with no body.
- `POST /register` correctly returns `201 Created`.
- `OAuth2PasswordBearer` is declared against `/api/v1/auth/login`, which matches the login endpoint path. OpenAPI's Authorize widget will work correctly.
- `PATCH` is used for partial updates (`/price`, `/sku`) which is semantically correct.

**Issues found:**

- **F-01 (Medium):** `POST /listings/{mlb_id}/promotions` returns `200 OK`. Creating a promotion is a resource creation and should return `201 Created`.
- **F-02 (Low):** `PUT /produtos/{product_id}` and `PUT /alertas/{alert_id}` use `PUT` but accept all-`Optional` schemas (`ProductUpdate`, `AlertConfigUpdate`). This is semantically PATCH, not PUT. PUT implies a full replacement of the resource. Using `PUT` with a sparse body is misleading to API consumers.
- **F-03 (Low):** `POST /listings/sync`, `POST /ads/sync`, `POST /reputation/sync` are action endpoints (RPC-style). They are not creating resources. `200 OK` is correct, but the design could be improved with a consistent sync pattern (see Recommendations).

### 2. Endpoint Naming Consistency — 11/15

**What is done well:**

- Most resource collections use plural nouns: `/listings`, `/competitors`, `/produtos`, `/alertas`.
- Sub-resources follow the pattern `/{id}/history`, `/{id}/snapshots`, `/{id}/analysis`.

**Issues found:**

- **N-01 (High):** Language mixing. The codebase mixes Portuguese and English in URL paths. Examples:
  - `/alertas` (PT) vs `/competitors` (EN) vs `/reputation` (EN)
  - `/financeiro` (PT) vs `/ads` (EN)
  - `/listings/{mlb_id}/margem` (PT) vs `/listings/{mlb_id}/health` (EN)
  - `/consultor/analisar` (PT verb) vs `/reputation/risk-simulator` (EN noun-compound)
  - This creates an inconsistent developer experience and makes the API harder to document and consume for non-PT developers. **A single language should be chosen throughout all URL paths.**

- **N-02 (Medium):** `/competitors/listing/{listing_id}` and `/competitors/sku/{product_id}` use a non-standard pattern for filtering. The standard REST approach is query parameters: `GET /competitors?listing_id={uuid}` and `GET /competitors?product_id={uuid}`. Fixed-path sub-routes like `/listing/{id}` create an unnested resource relationship that implies a sub-resource exists under `/listing`, which is incorrect.

- **N-03 (Medium):** `/alertas/events/` is a sibling route to `/alertas/{alert_id}`. The trailing slash on `events/` is inconsistent with all other collection routes that do not have trailing slashes (e.g., `GET /alertas/`). More importantly, `GET /alertas/events/{alert_id}` uses `alert_id` as the path variable but the intent is to list events *for* a config with that ID — the variable name is ambiguous.

- **N-04 (Low):** `/listings/orders/` has a trailing slash while `GET /listings/` and `GET /competitors/` technically also have trailing slashes defined in the router, but FastAPI normalizes them. The inconsistency is minor but worth noting.

- **N-05 (Low):** `/reputation/risk-simulator` uses a hyphenated noun-compound. The standard REST pattern would be `/reputation/risk` with the simulator being a query parameter or a sub-path. Hyphens are valid in URLs but the pattern is unusual in REST; consistent use of underscores or hyphens should be decided.

### 3. Schema Design — 14/15

**What is done well:**

- Pydantic v2 is used correctly with `model_config = {"from_attributes": True}` on all ORM-mapped output schemas.
- Input schemas use `Field` with validators (`min_length`, `ge`, `le`, `pattern`, `decimal_places`), which is excellent practice.
- `AlertConfigCreate` uses `@model_validator` for cross-field validation (threshold required for certain types, listing_id or product_id required). This is a strong pattern.
- `Decimal` is used for monetary amounts throughout — correct for financial precision.
- Separate Input/Output schemas are maintained (`Create`, `Update`, `Out` suffixes).
- `UUID | None` with proper optionality in `ListingOut` and other models.

**Issues found:**

- **S-01 (Medium):** `ListingAnalysisOut.snapshots` is typed as `list[dict]` instead of `list[SnapshotOut]`. This loses all OpenAPI schema generation for that field. Same issue with `AdsCampaignDetailOut.summary` typed as `dict`. These untyped fields produce incomplete documentation.
- **S-02 (Low):** `ConsultorRequest` uses `Optional[str]` (legacy typing) instead of `str | None`. Minor but inconsistent with the rest of the codebase.

### 4. Error Handling — 9/15

**What is done well:**

- `HTTPException` with explicit status codes is used throughout.
- `WWW-Authenticate: Bearer` header is correctly returned on 401 responses.
- Auth errors use 401 (invalid credentials) and 403 (inactive user) correctly — these are semantically distinct and the distinction is properly made.
- `404 Not Found` is used when resources are not found.
- `400 Bad Request` is used for invalid input (OAuth state validation).

**Issues found:**

- **E-01 (High):** `GET /listings/{mlb_id}/health` has a bare `except Exception` that catches all errors and silently returns a hardcoded degraded response:
  ```python
  try:
      listing = await service.get_listing(db, mlb_id, current_user.id)
  except Exception:
      return {"mlb_id": mlb_id, "score": 0, ...}
  ```
  This swallows legitimate errors (database failures, auth failures, etc.) and returns a `200 OK` with a fake payload. Any infrastructure error will appear to the client as a healthy-but-critical listing. The correct pattern is to catch only `HTTPException` or a domain-specific `ListingNotFoundError` and re-raise or convert unknown exceptions.

- **E-02 (Medium):** Error responses are inconsistent in format. Some return `{"detail": "message"}` (FastAPI default) while others return custom dicts like `{"success": True, "synced": N}`. There is no standard error envelope. An API-wide error schema with fields like `code`, `detail`, and `field` (for validation errors) would help consumers.

- **E-03 (Medium):** Validation errors from `@model_validator` in Pydantic produce `422 Unprocessable Entity` with FastAPI's default error structure. This is correct behavior but is not documented in the OpenAPI spec (no `responses: 422` entries with example payloads in the route decorators).

- **E-04 (Low):** `POST /api/v1/notifications` (the ML webhook endpoint in `main.py`) accepts any payload (`dict`) with no validation and no authentication, and always returns `200`. A malicious actor could flood this endpoint. It should at minimum validate a signature header.

- **E-05 (Low):** `GET /reputation/current` contains service-layer logic (fetching and committing a real-time snapshot) embedded in the router function itself (lines 34–53 in `reputacao/router.py`). This bypasses the service layer pattern and complicates error handling — a DB commit error inside a GET handler is hard to recover from cleanly.

### 5. Authentication / Authorization — 9/10

**What is done well:**

- JWT-based auth via `OAuth2PasswordBearer` is applied consistently across all protected endpoints using `Depends(get_current_user)`.
- `get_current_user` validates the JWT signature, checks `sub` claim, loads the user from the database, and checks `is_active`. This is a correct, complete implementation.
- Ownership checks are implemented in services: users can only access their own listings, competitors, alerts, and ML accounts.
- `DELETE /auth/ml/accounts/{account_id}` checks `MLAccount.user_id == current_user.id` before soft-deleting — correct IDOR protection.
- `GET /ads/{campaign_id}` joins through `MLAccount` to verify the campaign belongs to the current user — correct IDOR protection.

**Issues found:**

- **A-01 (Medium):** `POST /api/v1/notifications` (ML webhook receiver) has no authentication at all. Mercado Livre signs webhook payloads with an `x-signature` header. Without signature verification, any HTTP client can post to this endpoint and trigger processing logic once the TODO is implemented.

### 6. Pagination — 4/10

**Issues found:**

- **P-01 (High):** No pagination is implemented on any list endpoint. The following endpoints return unbounded lists with no `limit`, `offset`, `cursor`, or `page` parameters:
  - `GET /listings/` — returns all user listings (could be thousands after months of sync)
  - `GET /alertas/` — returns all alert configs
  - `GET /alertas/events/` — returns all events for N days
  - `GET /alertas/events/{alert_id}` — returns all events for an alert
  - `GET /competitors/` — returns all competitors
  - `GET /produtos/` — returns all products

- **P-02 (Medium):** `GET /listings/orders/` has a hardcoded `LIMIT 500` in the SQLAlchemy query but no `offset` or cursor, and no pagination metadata is returned to the client. The client cannot know if results were truncated.

- **P-03 (Low):** `GET /listings/{mlb_id}/snapshots` accepts `dias` (days, max 365) which bounds the result, but a very active listing with 3 snapshots/day could return 1095 records. A `limit` parameter would be appropriate.

**Recommendation:** At minimum, implement limit/offset pagination for the three highest-volume collections: `listings`, `orders`, and `alertas/events`. Use a standard envelope:
```json
{
  "items": [...],
  "total": 120,
  "limit": 50,
  "offset": 0
}
```

### 7. API Versioning — 5/5

- All routes are registered under `/api/v1/` via `API_PREFIX = "/api/v1"` in `main.py`.
- The prefix is applied consistently at the `app.include_router()` call, not scattered in individual router prefixes.
- `FastAPI(version="1.0.0")` is set.
- This is the correct approach and requires no changes.

### 8. Query Parameter Design — 7/10

**What is done well:**

- `period` parameter uses a regex-validated string (`pattern=r"^(today|7d|15d|30d|60d)$"`) in listings, which is clean and self-documenting.
- `dias` and `days` parameters use `ge`/`le` constraints, preventing abuse.
- `listing_id` and `is_active` as optional filters on `GET /alertas/` are well-designed.
- `mlb_id` filter on `GET /listings/orders/` is correct.

**Issues found:**

- **Q-01 (Medium):** Inconsistent naming for the same concept. The "time window" parameter is named differently across endpoints:
  - `dias` (PT) in `GET /listings/{mlb_id}/snapshots`
  - `days` (EN) in `GET /listings/{mlb_id}/analysis`, `GET /listings/{mlb_id}/health`, `GET /ads/{campaign_id}`, `GET /alertas/events/`
  - `period` (string enum) in `GET /listings/`, `GET /financeiro/*`, `GET /listings/analytics/*`

  A consumer calling multiple endpoints will encounter three different parameter names meaning roughly the same thing. Standardize on `days` (integer) or `period` (string enum) and use it consistently.

- **Q-02 (Low):** `GET /listings/{mlb_id}/margem` requires `preco` (PT) as a mandatory query parameter. Mandatory query parameters on GET requests are unusual (typically path parameters or request bodies). This endpoint is essentially a calculation action — `preco` as a query param is acceptable but should be documented with `...` (required) explicitly in the `Query()` call, which it already does. However, the PT naming (`preco` vs `price` elsewhere) is inconsistent.

- **Q-03 (Low):** `GET /ads/` and `GET /reputation/*` use `ml_account_id` as an optional query parameter to select which ML account to query. This is a reasonable pattern for multi-account support. However, the fallback behavior (silently using the first active account when omitted) is not surfaced in the OpenAPI description, making it invisible to consumers.

### 9. Response Envelope Consistency — 4/10

**Issues found:**

- **R-01 (High):** The API has no standard response envelope. Endpoints return:
  - Direct Pydantic models (majority — correct)
  - Raw Python dicts bypassing `response_model` (`/sync` endpoints, `/health` endpoint, `/kpi/summary`, `/listings/{mlb_id}/health`, `/listings/{mlb_id}/price`)
  - Lists directly (all collection endpoints)
  - A `{"status": "received"}` (webhook)
  - A `{"success": True, "synced": N}` (reputation/sync, listings/sync)
  - A `{"results": [...], "accounts_synced": N}` (ads/sync)

  The three sync endpoints return different response shapes from each other. There is no consistent "action result" schema.

- **R-02 (Medium):** `POST /listings/sync` has no `response_model` declaration, so the sync result dict is not validated or documented in OpenAPI. Same applies to `POST /ads/sync` and `POST /reputation/sync`.

- **R-03 (Medium):** `POST /listings/` (create listing) bypasses the `response_model` by returning a manually constructed dict instead of returning the ORM object and letting Pydantic serialize it. This creates a maintenance risk: if `ListingOut` schema changes, the manual dict will silently diverge.

- **R-04 (Low):** Action endpoints like `/listings/sync`, `/reputation/sync`, `/ads/sync` return `{"success": True}` style responses with varying field names. A standard `SyncResultOut` schema with consistent fields (`synced_count`, `errors`, `duration_ms`) would make these predictable.

### 10. OpenAPI / Swagger Completeness — 3/5

**What is done well:**

- `FastAPI` is instantiated with `title`, `description`, and `version`.
- All routers have `tags=["..."]` for grouping in Swagger UI.
- Most endpoints have docstrings that appear as OpenAPI `description` fields.
- `response_model` is declared on most endpoints, enabling schema generation.
- `Query()` with `description` is used on parameters, which is good.

**Issues found:**

- **O-01 (Medium):** Multiple endpoints lack `response_model`:
  - `POST /listings/sync`
  - `GET /listings/kpi/summary`
  - `GET /listings/{mlb_id}/health`
  - `PATCH /listings/{mlb_id}/price`
  - `POST /listings/{mlb_id}/promotions`
  - `POST /ads/sync`
  - `POST /reputation/sync`

  These endpoints generate no schema in the OpenAPI output, appearing as `{}` response bodies in Swagger UI. Clients have no contract to code against.

- **O-02 (Low):** No `responses` declarations for error cases (e.g., `responses={404: {"description": "Listing not found"}, 401: {...}}`). While FastAPI documents `422 Unprocessable Entity` automatically, `401`, `403`, and `404` responses are not documented. This is common but makes the API spec incomplete.

- **O-03 (Low):** The `GET /auth/ml/callback` endpoint returns a `302 Redirect` but FastAPI will document it as `200 OK` in OpenAPI. A `response_class=RedirectResponse` or `responses={302: {"description": "Redirect to frontend"}}` would make this accurate.

- **O-04 (Low):** `FastAPI` is missing `contact`, `license_info`, and `servers` metadata. These are optional but improve the quality of the generated spec, especially if the spec is shared with external consumers.

---

## Prioritized Recommendations

### Priority 1 — Critical (affects correctness and client contract)

**R1.1 — Add `response_model` to all untyped endpoints**

The following endpoints should have typed response models:
- `POST /listings/sync` → create `SyncResultOut(synced: int, errors: list[str])`
- `GET /listings/kpi/summary` → promote `KpiPeriodOut` as the response model (it already exists in schemas.py)
- `GET /listings/{mlb_id}/health` → create `ListingHealthOut` schema
- `PATCH /listings/{mlb_id}/price` → return `ListingOut` or a `PriceUpdateOut`
- `POST /listings/{mlb_id}/promotions` → create `PromotionOut` schema and return 201
- `POST /ads/sync` → return a typed `SyncResultOut`
- `POST /reputation/sync` → return a typed `SyncResultOut`

**R1.2 — Fix the bare `except` in `GET /listings/{mlb_id}/health`**

Replace the current pattern with explicit error handling:
```python
# Current (bad):
try:
    listing = await service.get_listing(db, mlb_id, current_user.id)
except Exception:
    return {"mlb_id": mlb_id, "score": 0, ...}  # swallows all errors

# Recommended:
from fastapi import HTTPException
try:
    listing = await service.get_listing(db, mlb_id, current_user.id)
except HTTPException:
    raise  # let 401, 403, 404 propagate normally
except Exception as exc:
    # log the real error for observability
    logger.error("Health score failed for %s: %s", mlb_id, exc)
    raise HTTPException(status_code=500, detail="Erro interno ao calcular health score")
```

**R1.3 — Add pagination to high-volume list endpoints**

At minimum: `GET /listings/`, `GET /listings/orders/`, `GET /alertas/events/`.
Suggested standard query parameters: `limit: int = Query(default=50, ge=1, le=200)` and `offset: int = Query(default=0, ge=0)`.
Return a typed envelope:
```python
class PaginatedOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
```

### Priority 2 — High (developer experience and consistency)

**R2.1 — Standardize URL language**

Choose one language for all URL path segments. Given the target audience includes ML Brasil sellers, Portuguese is acceptable, but the current mixing is the worst of both worlds. Recommended approach: use English for all technical URLs (it is the universal API standard) while keeping Portuguese in field names and documentation where appropriate.

Proposed rename map:
| Current | Proposed |
|---|---|
| `/alertas` | `/alerts` |
| `/financeiro` | `/financeiro` (OR `/finance`) |
| `/produtos` | `/products` |
| `/consultor/analisar` | `/advisor/analyze` |
| `/{mlb_id}/margem` | `/{mlb_id}/margin` |
| `dias` query param | `days` |
| `preco` query param | `price` |

**R2.2 — Replace non-standard competitor filter paths with query parameters**

```
# Current (non-standard):
GET /competitors/listing/{listing_id}
GET /competitors/sku/{product_id}

# Proposed (REST-correct):
GET /competitors?listing_id={uuid}
GET /competitors?product_id={uuid}
```

The existing `GET /competitors/` already returns all competitors. Adding optional filter parameters to that endpoint eliminates two routes.

**R2.3 — Change `PUT` to `PATCH` where payload is partial**

- `PUT /produtos/{product_id}` → `PATCH /produtos/{product_id}` (all fields optional in `ProductUpdate`)
- `PUT /alertas/{alert_id}` → `PATCH /alertas/{alert_id}` (all fields optional in `AlertConfigUpdate`)

**R2.4 — Standardize the period query parameter**

Adopt a single pattern across all endpoints. Current inconsistency:

| Pattern | Used in |
|---|---|
| `period: str` enum (`"7d"`, `"30d"`) | listings, financeiro, analytics |
| `days: int` | analysis, health, ads, alerts/events |
| `dias: int` (PT) | snapshots |

Recommendation: use `period: str` with enum validation everywhere, as it is more self-documenting and prevents arbitrary integer abuse. Define `PeriodEnum` as a shared `Literal` type in `app/core/constants.py` and reuse it.

### Priority 3 — Medium (long-term maintainability)

**R3.1 — Add webhook signature verification**

`POST /api/v1/notifications` must verify the Mercado Livre `x-signature` header before processing. Reference: ML Notifications documentation. Without this, the endpoint is an unauthenticated write surface.

**R3.2 — Move router-level business logic to service layer**

`GET /reputation/current` in `reputacao/router.py` contains ~30 lines of DB queries and commits. This logic belongs in `service.py`. Routers should call one service function and return its result.

**R3.3 — Create a `SyncResultOut` schema shared by all sync endpoints**

```python
class SyncResultOut(BaseModel):
    synced: int
    errors: list[str] = []
    duration_ms: int | None = None
```

Apply to `POST /listings/sync`, `POST /ads/sync`, `POST /reputation/sync`.

**R3.4 — Type `ListingAnalysisOut.snapshots` and `AdsCampaignDetailOut.summary`**

Replace `list[dict]` with `list[SnapshotOut]` and create a typed `AdsCampaignSummaryOut` schema. This restores OpenAPI schema generation for these fields and enables client-side type safety.

**R3.5 — Document error responses in OpenAPI**

Add `responses` to the most important endpoints:
```python
@router.get(
    "/{mlb_id}",
    response_model=ListingOut,
    responses={
        404: {"description": "Listing not found"},
        401: {"description": "Invalid or expired token"},
    },
)
```

**R3.6 — Add `POST /listings/{mlb_id}/promotions` status code 201**

```python
@router.post("/{mlb_id}/promotions", status_code=status.HTTP_201_CREATED)
```

---

## Summary Table of All Issues

| ID | Severity | Category | Description |
|---|---|---|---|
| F-01 | Medium | REST Conventions | `POST /promotions` returns 200 instead of 201 |
| F-02 | Low | REST Conventions | `PUT` used for partial-update schemas (should be PATCH) |
| F-03 | Low | REST Conventions | Sync endpoints are RPC-style; acceptable but should be consistent |
| N-01 | High | Naming | Mixed PT/EN language in URL paths |
| N-02 | Medium | Naming | `/competitors/listing/{id}` and `/competitors/sku/{id}` should be query params |
| N-03 | Medium | Naming | `/alertas/events/{alert_id}` — ambiguous path variable name |
| N-04 | Low | Naming | Trailing slash inconsistency on `/orders/` |
| N-05 | Low | Naming | `/reputation/risk-simulator` uses hyphenated noun-compound |
| S-01 | Medium | Schema | `ListingAnalysisOut.snapshots: list[dict]` loses OpenAPI type information |
| S-02 | Low | Schema | `ConsultorRequest` uses legacy `Optional[str]` |
| E-01 | High | Error Handling | Bare `except` in health endpoint swallows all errors |
| E-02 | Medium | Error Handling | No standard error envelope across the API |
| E-03 | Medium | Error Handling | 422 validation errors not documented in OpenAPI spec |
| E-04 | Low | Error Handling | Webhook endpoint has no auth and no input validation |
| E-05 | Low | Error Handling | Business logic + DB commit inside GET handler in reputation router |
| A-01 | Medium | Auth | Webhook endpoint lacks signature verification |
| P-01 | High | Pagination | No pagination on any list endpoint |
| P-02 | Medium | Pagination | `orders` list has hardcoded LIMIT 500 with no offset or metadata |
| P-03 | Low | Pagination | Snapshots endpoint could return thousands of records |
| Q-01 | Medium | Query Params | Inconsistent naming: `dias` vs `days` vs `period` for time window |
| Q-02 | Low | Query Params | `preco` uses PT while rest of API uses EN for param names |
| Q-03 | Low | Query Params | Silent fallback behavior for `ml_account_id` not documented |
| R-01 | High | Response Envelope | No standard response envelope; sync endpoints return different shapes |
| R-02 | Medium | Response Envelope | Multiple `response_model=None` endpoints are invisible in OpenAPI |
| R-03 | Medium | Response Envelope | `POST /listings/` returns manual dict that can diverge from schema |
| R-04 | Low | Response Envelope | No standard `SyncResultOut` schema shared across sync actions |
| O-01 | Medium | OpenAPI | 7 endpoints missing `response_model` |
| O-02 | Low | OpenAPI | No `responses` declarations for error codes |
| O-03 | Low | OpenAPI | OAuth callback documents wrong response code |
| O-04 | Low | OpenAPI | Missing `contact`, `license_info`, `servers` in FastAPI metadata |

---

## Conclusion

The MSM_Pro API is well-structured for an internal dashboard product. The authentication implementation is solid, the use of Pydantic v2 features is correct, and the overall module organization (one `router.py` + `service.py` + `schemas.py` per domain) is clean and scalable.

The most impactful improvements are pagination (currently absent on all list endpoints), fixing the bare `except` in the health endpoint, and adding `response_model` to the ~7 untyped endpoints. These three changes alone would close the gap between the current 72/100 score and approximately 85/100 without requiring any breaking API changes.

The language mixing in URL paths (Portuguese vs English) is the most visible design debt. It should be resolved in a planned v2 migration with backward compatibility via redirect aliases during the transition period.
