# MSM_Pro - Test Coverage Analysis Report

Generated: 2026-03-12  
Analyst: QA Expert Agent  
Project: MSM_Pro (Mercado Livre Sales Intelligence Dashboard)  
Scope: Read-only static analysis - no test execution performed

---

## Overall Coverage Score: 3 / 100

The project has exactly 2 test cases covering 2 trivial routes (GET /health, GET /).
Zero business logic, zero security paths, zero integrations, and zero frontend are covered by automated tests.

---

## 1. What Currently Exists

### Test Infrastructure

| Item | Status | Details |
|------|--------|---------|
| Test runner | Present | pytest configured via backend/pytest.ini |
| Async mode | Configured | asyncio_mode = auto - correct for FastAPI async |
| Test directory | Present | backend/tests/ with __init__.py |
| Test dependencies | Absent | pytest-asyncio not declared in requirements.txt |
| Coverage plugin | Absent | pytest-cov not installed or configured |
| Frontend test runner | Absent | No Vitest, Jest, or any test library in package.json |
| Frontend test config | Absent | No vitest.config.ts, no jest.config.ts |

### Existing Test File

backend/tests/test_health.py has 2 test cases:

1. test_health_check - asserts GET /health returns status ok, version 1.0.0, environment development
2. test_root_redirect - asserts GET / returns 200 with MSM_Pro API in message

CRITICAL OBSERVATION: test_health_check hardcodes the string development as the expected environment value. This assertion passes locally but is a false positive in production where settings.environment differs. It masks environment mismatches.

### Source Files Inventory

| Layer | Files | Service files | Test files |
|-------|-------|--------------|----------|
| Backend Python | 57 | 9 | 1 (health only) |
| Frontend TypeScript/TSX | 31 | 7 service files | 0 |
---

## 2. Gap Analysis - What Is Missing

### Backend Service Layer (9 services, 0% coverage)

#### auth/service.py - 0% coverage
- verify_password: bcrypt comparison
- hash_password: bcrypt hashing
- create_access_token: JWT generation and expiry
- create_user: duplicate email detection, password hashing
- authenticate_user: credential validation, wrong password handling
- get_ml_auth_url: OAuth URL construction with urlencode
- exchange_code_for_token: external HTTP call to ML OAuth
- refresh_ml_token: token renewal via refresh_token
- get_ml_user_info: ML user info fetch
- save_ml_account: upsert logic for ML accounts

#### financeiro/service.py - 0% coverage
- calcular_taxa_ml: fee rate lookup with fallback for unknown listing types
- calcular_margem: core P&L calculation (price - cost - fee - shipping)
- _parse_period: period string to date range conversion
- get_financeiro_resumo: aggregated P&L with period comparison
- get_financeiro_detalhado: per-listing breakdown
- get_financeiro_timeline: daily time series with BRT timezone conversion
- get_cashflow: D+8 cash release projection

#### vendas/service.py - 0% coverage (largest service, approximately 700 lines)
- sync_listings_from_ml: full sync pipeline from ML API to database
- list_listings: listing query with filters
- get_listing_detail: per-listing analytics with mock fallback
- get_kpi_by_period: KPI aggregation using COUNT(DISTINCT listing_id)
- get_health_score: composite score calculation
- get_heatmap_data: sales heatmap from Order model

#### alertas/service.py - 0% coverage
Alert evaluation engine with 5 alert types, all untested:
- _check_conversion_below
- _check_stock_below
- _check_no_sales_days
- _check_competitor_price_change
- _check_competitor_price_below
- evaluate_single_alert: wraps conditions, creates AlertEvent

#### concorrencia/service.py - 0% coverage
- add_competitor: MLB ID normalization, ownership validation, duplicate detection
- remove_competitor: soft delete via is_active=False
- get_competitor_history: snapshot retrieval with ownership check
- get_competitors_by_sku: multi-listing competitor aggregation

#### reputacao/service.py - 0% coverage
- calculate_revenue_60d and calculate_orders_60d: aggregation queries
- fetch_and_save_reputation: ML API call + upsert logic
- get_reputation_risk: risk buffer calculation (critical/warning/safe classification)

#### mercadolivre/client.py - 0% coverage
The entire ML HTTP client is untested:
- _rate_limit: 1 req/sec enforcement
- _request: retry with exponential backoff, 429 handling, 401 detection, 5xx backoff
- All 18 public methods (get_item, get_orders, get_campaigns, get_seller_reputation, etc.)

#### jobs/tasks.py - 0% coverage
All Celery tasks are untested:
- sync_listing_snapshot: full snapshot sync for a single listing
- sync_all_snapshots: orchestrates all account syncs
- refresh_expired_tokens: token renewal scheduler
- sync_competitor_snapshots: competitor price monitoring
- evaluate_alerts: alert evaluation loop
- sync_orders: order ingestion pipeline

### Frontend - 0% coverage

All 31 TypeScript/TSX files are untested. No test framework installed (no Vitest, no Jest, no Testing Library in package.json devDependencies).

Critical untested frontend paths:
- store/authStore.ts: Zustand state, setAuth() + setStoredToken() synchronization. Known recurring bug class documented in CLAUDE.md.
- services/api.ts: Axios interceptor reading msm_access_token from localStorage
- ProtectedRoute.tsx: auth guard redirect logic
- All service files: listingsService.ts, financeiroService.ts, reputacaoService.ts, adsService.ts
- All page components: Dashboard, Anuncios, Financeiro, Reputacao, Publicidade, Concorrencia, Alertas
---

## 3. Risk Matrix - Critical Untested Paths

Risk levels: CRITICAL (data loss/security/money), HIGH (feature breakage), MEDIUM (degraded UX)

| Rank | Path | Risk | Impact |
|------|------|------|--------|
| 1 | calcular_margem fee calculation | CRITICAL | Wrong P&L for every transaction; Decimal rounding errors compound across thousands of orders |
| 2 | calcular_taxa_ml unknown listing_type fallback | CRITICAL | Silent wrong fee (16% default); already triggered in production per MEMORY.md bug log |
| 3 | authenticate_user credential validation | CRITICAL | Auth bypass or lockout if bcrypt logic breaks |
| 4 | create_access_token JWT expiry | CRITICAL | Tokens never expiring or expiring too early |
| 5 | sync_listings_from_ml full sync pipeline | CRITICAL | Silent data corruption on every daily 06:00 BRT Celery sync |
| 6 | get_kpi_by_period COUNT(DISTINCT) | HIGH | KPI shows 176 instead of 16; this exact bug occurred in production with no regression guard |
| 7 | _request retry and backoff in MLClient | HIGH | Silent failures during ML API outages; 429 and 5xx handling completely untested |
| 8 | refresh_ml_token token renewal | HIGH | All ML syncs fail after 6h with no visible alert to user |
| 9 | get_cashflow D+8 projection logic | HIGH | Wrong cash flow release dates; date arithmetic with delivery estimation is error-prone |
| 10 | get_reputation_risk buffer calculation | HIGH | Wrong risk classification; integer rounding on small sales volumes changes result |
| 11 | Zustand setAuth + setStoredToken sync | HIGH | Auth token desync - documented as recurring bug class in CLAUDE.md causing login loops |
| 12 | evaluate_single_alert and condition checkers | HIGH | Revenue-critical notifications silently broken or never firing |
| 13 | add_competitor MLB ID normalization | MEDIUM | Duplicate competitors created with different formatting (MLB-123 vs MLB123) |
| 14 | _parse_period period to date range | MEDIUM | Charts show wrong date range; off-by-one with yesterday boundary |
| 15 | get_financeiro_timeline BRT timezone cast | MEDIUM | Sales appear on wrong day in P&L timeline under DST or midnight edge cases |
| 16 | test_health_check hardcoded environment | LOW | Existing test assertion is meaningless in non-development environments |

---

## 4. Missing Test Types

### Unit Tests - Not Present

Pure logic functions requiring no database or network connection:

| Function | Module | What to assert |
|----------|--------|---------------|
| hash_password / verify_password | auth/service.py | Correct bcrypt round-trip; wrong password returns False not exception |
| create_access_token | auth/service.py | JWT sub equals UUID string; exp is correct future timestamp |
| get_ml_auth_url | auth/service.py | URL contains client_id, redirect_uri; state param conditional on input |
| calcular_taxa_ml | financeiro/service.py | classico=11.5%, premium=17%, full=17%, unknown=16% fallback, sale_fee_pct override |
| calcular_margem | financeiro/service.py | Correct arithmetic; negative margin when cost > price; zero price does not crash |
| _parse_period | financeiro/service.py | 7d/30d/90d produce correct (start, end) dates relative to yesterday |
| MLClient._rate_limit | mercadolivre/client.py | Second call within 1s is delayed; calls after 1s gap are not |
| get_reputation_risk buffer math | reputacao/service.py | 100 sales at 0.8% claims gives buffer=1 (critical); at 0.3% gives buffer=7 (safe) |

### Integration Tests - Not Present

Tests requiring a database (test PostgreSQL or aiosqlite in-memory via conftest.py):
- Full auth flow: create_user -> authenticate_user -> create_access_token -> protected endpoint 200
- Listing sync pipeline with mocked ML API -> verify Listing + ListingSnapshot rows in DB
- KPI query: insert known snapshot data -> verify COUNT(DISTINCT) result
- Competitor CRUD: add -> duplicate rejection -> soft-delete -> history empty
- Alert lifecycle: create config -> insert trigger snapshots -> evaluate -> verify AlertEvent row
- Financial aggregation: insert multi-listing snapshots -> verify tax deductions

### API Endpoint Tests - Not Present (only /health and / are covered)

FastAPI endpoint tests using httpx.AsyncClient:
- POST /api/v1/auth/login: valid credentials returns token; wrong password 401; missing fields 422
- GET /api/v1/listings/: no auth returns 401; valid token returns 200
- GET /api/v1/listings/kpi/summary: response has hoje, ontem, anteontem keys; COUNT(DISTINCT) guard
- POST /api/v1/concorrencia/: add returns 201; duplicate 409; wrong owner 404 (IDOR)
- GET /api/v1/financeiro/resumo: valid shape; invalid period 422
- DELETE /api/v1/concorrencia/{id}: user A cannot delete user B record (IDOR protection)

### End-to-End Tests - Not Present

No Playwright or Cypress installed. Critical user journeys unvalidated:
- Login flow -> Dashboard renders with KPI cards
- OAuth ML connect flow (requires mocked callback)
- Sync button trigger -> listings table refreshes
- Add competitor -> appears in monitoring list

### Contract Tests - Not Present

No validation that ML API response shapes match service.py expectations. The project has a documented history of field name mismatches (sale_price vs original_price, wrong visits endpoint). Contract tests would catch these regressions before deployment.
---

## 5. Test Infrastructure Assessment

### Backend

| Component | Status | Gap |
|-----------|--------|-----|
| pytest | Present (pytest.ini exists) | Not listed in requirements.txt |
| pytest-asyncio | Used implicitly | Not in requirements.txt - fragile in CI |
| pytest-cov | Not installed | No coverage measurement possible |
| conftest.py | Absent | No fixtures, no test database, no auth helpers |
| Test database | Not configured | No test DATABASE_URL; no SQLite fallback |
| Mocking library | Not installed | unittest.mock available; pytest-mock not in requirements |

Missing requirements.txt entries needed for testing:



### Frontend

| Component | Status | Gap |
|-----------|--------|-----|
| Vitest | Not installed | Needs vitest, @vitest/coverage-v8 |
| Testing Library | Not installed | Needs @testing-library/react, @testing-library/user-event |
| jsdom | Not installed | Needed for DOM simulation |
| MSW | Not installed | Needed to mock Axios API calls |
| Test scripts | Absent | No test script in package.json |

---

## 6. Recommended Test Plan - Prioritized

### Phase 1 - Safety Net (Week 1, approximately 2 days effort)
Pure unit tests with zero infrastructure dependencies. Run in milliseconds.
Guard the highest-risk financial and auth logic.

**Priority 1A - Financial calculations (highest business risk)**
File: backend/tests/test_financeiro_unit.py

- test_calcular_taxa_ml_classico: verifies Decimal(0.115) for classico
- test_calcular_taxa_ml_premium: verifies Decimal(0.17) for premium
- test_calcular_taxa_ml_full: verifies Decimal(0.17) for full
- test_calcular_taxa_ml_unknown_type_uses_default: unknown string returns Decimal(0.16) with warning
- test_calcular_taxa_ml_sale_fee_pct_override: provided Decimal takes precedence over table lookup
- test_calcular_margem_basic: price=100, cost=50, classico -> margem_bruta=38.50, margem_pct=38.50%
- test_calcular_margem_zero_price: price=0 does not raise ZeroDivisionError; margem_pct returns 0
- test_calcular_margem_negative_result: cost=200, price=100 produces negative margem_bruta
- test_parse_period_7d: returns 7-day window ending yesterday not today
- test_parse_period_excludes_today: data_fim is yesterday for all period strings

**Priority 1B - Auth unit tests**
File: backend/tests/test_auth_unit.py

- test_hash_and_verify_password_correct: hash then verify same password returns True
- test_verify_password_wrong_returns_false: different password returns False, no exception
- test_create_access_token_contains_sub: JWT sub field equals str(user_id)
- test_create_access_token_expires: JWT exp is approximately now + ACCESS_TOKEN_EXPIRE_MINUTES
- test_get_ml_auth_url_contains_client_id
- test_get_ml_auth_url_includes_state_when_provided
- test_get_ml_auth_url_omits_state_when_none

**Priority 1C - MLClient unit tests with mock HTTP**
File: backend/tests/test_ml_client_unit.py

- test_rate_limit_delays_second_call: elapsed time between two rapid calls is >= 1.0s
- test_request_retries_on_5xx: 500 response triggers retry up to max_retries
- test_request_raises_on_401: raises MLClientError with status_code=401
- test_request_handles_429_with_retry_after: respects Retry-After header before retry
- test_request_raises_after_max_retries: after exhausting retries raises MLClientError
- test_get_item_normalizes_mlb_id: MLB-123, 123, and MLB123 all result in request to /items/MLB123

### Phase 2 - Integration Safety (Week 2, approximately 3 days effort)
Requires backend/tests/conftest.py with async SQLite engine and per-test transaction rollback.

**Priority 2A - Auth integration**
File: backend/tests/test_auth_integration.py

- test_create_user_success: user row in DB with hashed not plain password
- test_create_user_duplicate_email_raises_409
- test_authenticate_user_correct_credentials: returns User object
- test_authenticate_user_wrong_password_returns_none: returns None, does not raise
- test_authenticate_user_nonexistent_email_returns_none

**Priority 2B - KPI regression guard (prevents recurrence of COUNT(DISTINCT) bug)**
File: backend/tests/test_vendas_kpi.py

- test_kpi_counts_distinct_listings_not_snapshots: 1 listing + 11 snapshots returns count=1 not 11
- test_kpi_today_filters_by_date: yesterday snapshots do not appear in today KPI
- test_kpi_zero_when_no_snapshots: returns all zeros not crash

**Priority 2C - Financial aggregation**
File: backend/tests/test_financeiro_integration.py

- test_get_financeiro_resumo_basic: known revenue and fee produces correct P&L
- test_get_financeiro_resumo_period_comparison: variation percentages calculated correctly
- test_get_financeiro_resumo_no_snapshots: returns zeros for all fields not crash
- test_get_cashflow_d8_projection: order with delivery today has release date = today + 8

**Priority 2D - Alert evaluation**
File: backend/tests/test_alertas_integration.py

- test_stock_below_threshold_fires: stock=2 with threshold=5 creates AlertEvent
- test_stock_above_threshold_does_not_fire: stock=10 with threshold=5 returns None
- test_no_sales_for_n_days_fires: three days of sales_today=0 triggers alert
- test_competitor_price_change_detected: price difference in latest two snapshots fires alert
- test_unknown_alert_type_returns_none: unknown alert_type does not raise, returns None

### Phase 3 - API Endpoint Tests (Week 3, approximately 2 days effort)
File: backend/tests/test_endpoints.py
Uses httpx.AsyncClient with in-memory FastAPI app (same pattern as test_health.py).

- test_login_success_returns_token
- test_login_wrong_password_returns_401
- test_listings_without_auth_returns_401
- test_listings_with_auth_returns_200
- test_kpi_summary_shape: response has hoje, ontem, anteontem keys
- test_add_competitor_duplicate_returns_409
- test_add_competitor_wrong_owner_returns_404 (IDOR protection)
- test_financeiro_resumo_invalid_period_returns_422
- test_ml_notifications_webhook_returns_received

### Phase 4 - Frontend Unit Tests (Week 3-4, approximately 3 days effort)

Install required packages:
  npm install -D vitest @vitest/coverage-v8 @testing-library/react @testing-library/user-event jsdom msw

Add to package.json scripts:
  test: vitest
  test:coverage: vitest run --coverage

Files to create:
- frontend/src/store/authStore.test.ts: setAuth() must call setStoredToken(); token readable from
  localStorage key msm_access_token. Guards the recurring bug class documented in CLAUDE.md.
- frontend/src/services/api.test.ts: Axios interceptor attaches Bearer token from msm_access_token.
- frontend/src/components/ProtectedRoute.test.tsx: unauthenticated user redirected to /login.
- frontend/src/services/financeiroService.test.ts: correct endpoint called with period param.
- frontend/src/services/listingsService.test.ts: sync() calls correct endpoint.
---

## 7. Coverage Targets by Phase

| Module | Current | After Phase 1 | After Phase 2-4 |
|--------|---------|---------------|------------------|
| financeiro/service.py | 0% | 85% | 95% |
| auth/service.py | 0% | 70% | 90% |
| mercadolivre/client.py | 0% | 60% | 80% |
| vendas/service.py | 0% | 0% | 75% |
| alertas/service.py | 0% | 0% | 80% |
| concorrencia/service.py | 0% | 0% | 75% |
| reputacao/service.py | 0% | 40% | 80% |
| jobs/tasks.py | 0% | 0% | 50% |
| Frontend | 0% | 0% | 60% |
| **Overall** | **~3%** | **~25%** | **~70%** |

---

## 8. Immediate Actions (under 30 minutes each, zero infrastructure required)

**Action 1: Fix the flawed existing test**
File: backend/tests/test_health.py
Remove the assertion checking environment equals development.
The hardcoded value is a false positive in staging and production.
Corrected assertion: assert response.json()["status"] == "ok"

**Action 2: Add testing dependencies to requirements.txt**
File: backend/requirements.txt
Add these lines: pytest>=8.0, pytest-asyncio>=0.24, pytest-cov>=6.0, pytest-mock>=3.14, aiosqlite>=0.20
These are currently used implicitly without declaration, which is fragile in CI environments.

**Action 3: Write test_calcular_taxa_ml**
File: backend/tests/test_financeiro_unit.py
Pure function with no I/O. Single highest-risk untested function in the codebase.
Controls every financial calculation in the system. Approximately 5 test cases and 20 lines.

**Action 4: Write test_calcular_margem basic case**
File: backend/tests/test_financeiro_unit.py
Equally trivial to write, equally high business risk. Validates Decimal arithmetic correctness.

**Action 5: Write test_verify_password**
File: backend/tests/test_auth_unit.py
Pure bcrypt logic with no I/O. Protects against auth regressions from dependency updates.

---

## Summary

MSM_Pro is a production system handling real financial data (P&L, cash flow projections, ML fees)
with NO automated test coverage on any business logic, financial calculations, authentication flows,
or external API integrations.

The 2 existing tests verify only that the HTTP server starts and the /health endpoint responds.
One of those tests contains a defect: a hardcoded environment string creates a false positive
that provides no signal in non-development deployments.

The three highest-priority risks requiring tests immediately:

1. Financial calculations (calcular_margem, calcular_taxa_ml) running silently wrong with no
   regression guards. These two functions control every P&L number shown to the user and both
   have edge cases (unknown listing_type, zero price) that have already caused production bugs.

2. The KPI COUNT(DISTINCT listing_id) query has already produced wrong results in production
   (showing 176 instead of 16). There is no regression test preventing this from happening
   again after any future refactoring of the vendas service.

3. The Zustand auth token synchronization pattern is explicitly documented as a recurring
   bug class in CLAUDE.md. Every time setAuth() is called without setStoredToken(), the
   application enters a login loop. There is no frontend test preventing this regression.

The path to 70% overall coverage is achievable in 3-4 weeks of focused effort following the
phased plan above. Phase 1 alone (pure unit tests, no infrastructure needed) can be completed
in 2 days and raises coverage from 3% to approximately 25% while addressing the most
critical financial and auth regression risks.
