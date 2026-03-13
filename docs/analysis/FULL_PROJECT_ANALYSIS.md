# MSM_Pro — Full Project Analysis Report

**Date:** 2026-03-12
**Mode:** ANALYZE (read-only audit)
**Analyzed by:** 9 specialized Claude agents (Sonnet 4.6)
**Orchestrated by:** Claude Opus 4.6

---

## Executive Summary

MSM_Pro is a Mercado Livre sales intelligence dashboard built with FastAPI + React + PostgreSQL + Celery. The project has a solid architectural foundation with consistent module patterns, strong SQL injection prevention, and excellent operational documentation. However, it carries significant security debt (exposed secrets, missing CSRF in OAuth), near-zero test coverage, and performance patterns that will degrade as data grows.

---

## Overall Score

| Area | Score | Weight | Weighted |
|------|-------|--------|----------|
| Architecture | 74 | 15% | 11.1 |
| Code Quality | 65 | 15% | 9.8 |
| Security | 54 | 20% | 10.8 |
| Performance | 58 | 15% | 8.7 |
| Test Coverage | 3 | 15% | 0.5 |
| Dependencies | 64 | 5% | 3.2 |
| Documentation | 72 | 10% | 7.2 |
| API Design | 72 | 5% | 3.6 |
| **TOTAL** | | **100%** | **54.8 / 100** |

### Grade: **D+** — Functional but not production-hardened

---

## Score Breakdown

### 1. Architecture — 74/100
**Strengths:** Consistent models/schemas/service/router pattern across 13 modules. Clean migration history (10 sequential). Docker + Railway infra well-configured.
**Weaknesses:** `vendas/service.py` is a 1980-line god-class. Celery tasks bypass service layer. Health check doesn't probe DB/Redis.

### 2. Code Quality — 65/100
**Strengths:** Good naming conventions. Pydantic v2 used correctly.
**Weaknesses:** DRY violations (Variacao, exportCSV copied between pages). Cyclomatic complexity ~22 in `_sync_listing_snapshot_async`. Rate limiter global not thread-safe.

### 3. Security — 54/100 ⚠️
**Strengths:** Zero SQL injection risk. IDOR prevention solid. bcrypt correct. XSS safe.
**Weaknesses:**
- CRITICAL: `.env` with live production secrets on disk
- CRITICAL: OAuth state has no CSRF nonce
- CRITICAL: `/register` open with no rate limit
- HIGH: JWT default secret in source code
- HIGH: ML tokens stored unencrypted in DB

### 4. Performance — 58/100
**Strengths:** Bulk-fetched queries (no N+1 on main paths). Celery task timeouts configured.
**Weaknesses:**
- CRITICAL: 4 sequential API calls per listing at 1 req/s during sync
- CRITICAL: 4-6 DB queries per dashboard request
- HIGH: Missing composite index on `listing_snapshots(listing_id, captured_at)`
- HIGH: N+1 in competitor sync (40 extra queries for 20 competitors)

### 5. Test Coverage — 3/100 ⚠️⚠️
**Strengths:** pytest is configured. Health test exists.
**Weaknesses:** 2 test cases total. 57 Python files with 0% coverage. Zero frontend tests. No test framework installed in frontend. Critical financial calculations (`calcular_margem`) completely untested.

### 6. Dependencies — 64/100
**Strengths:** All Python deps pinned with `==`. Frontend lock file present.
**Weaknesses:**
- CRITICAL: `python-jose 3.3.0` has CVE-2022-29217 (CVSS 9.1, token forgery)
- HIGH: `express 4.18.2` has CVE-2024-45296 (ReDoS)
- No CI/CD pipeline with CVE scanning

### 7. Documentation — 72/100
**Strengths:** CLAUDE.md is exceptional (88/100). ML API reference is production-quality (92/100). Architecture blueprint comprehensive.
**Weaknesses:** No README.md at project root. Sparse Python docstrings in largest files. No TypeScript JSDoc.

### 8. API Design — 72/100
**Strengths:** JWT auth end-to-end. Proper HTTP status codes. API versioning clean.
**Weaknesses:** Zero pagination on any list endpoint. Mix of PT/EN in URL paths. 7 endpoints missing `response_model`. Webhook endpoint has no auth.

---

## Top 10 Findings (Prioritized)

| # | Severity | Area | Finding | Fix Effort |
|---|----------|------|---------|-----------|
| 1 | 🔴 CRITICAL | Security | `.env` with live secrets (DB, Redis, ML, Anthropic, JWT) | 1h — rotate all credentials |
| 2 | 🔴 CRITICAL | Security | OAuth `state` lacks CSRF nonce — account takeover possible | 2h |
| 3 | 🔴 CRITICAL | Deps | `python-jose` CVE-2022-29217 (CVSS 9.1) — JWT forgery | 1h — migrate to PyJWT |
| 4 | 🔴 CRITICAL | Tests | 3/100 coverage — financial calcs completely untested | 2 days (Phase 1) |
| 5 | 🟠 HIGH | Security | `/register` open, no rate limit, account enumeration | 1h |
| 6 | 🟠 HIGH | Security | ML tokens stored plaintext in PostgreSQL | 3h — add Fernet encryption |
| 7 | 🟠 HIGH | Perf | Missing composite index `listing_snapshots(listing_id, captured_at)` | 30min |
| 8 | 🟠 HIGH | Perf | 4 sequential API calls per listing during sync (4s each) | 2h — merge order calls |
| 9 | 🟡 MEDIUM | Quality | `vendas/service.py` god-class (1980 lines, 11+ responsibilities) | 1 day — split into 3 |
| 10 | 🟡 MEDIUM | Docs | No README.md at project root | 2h |

---

## Remediation Roadmap

### Phase 1 — Security Emergency (This Week)
- [ ] Rotate ALL production credentials (DB, Redis, ML OAuth, Anthropic, JWT secret)
- [ ] Audit git history for `.env` commits
- [ ] Add CSRF nonce to OAuth state parameter
- [ ] Replace `python-jose` with `PyJWT>=2.8.0`
- [ ] Remove or restrict `/register` endpoint
- [ ] Update `express` to `4.21.2+` in `server-package.json`

### Phase 2 — Critical Infrastructure (Next 2 Weeks)
- [ ] Add composite index migration `0011` for listing_snapshots
- [ ] Implement ML token encryption at rest (Fernet)
- [ ] Add rate limiting on login/register (slowapi)
- [ ] Reduce JWT expiry to 30-60 min + add refresh tokens
- [ ] Fix health check to probe DB + Redis
- [ ] Merge 3 orders-by-status API calls into 1

### Phase 3 — Test Foundation (Next Month)
- [ ] Phase 1 tests: pure unit tests for financial calcs, auth, ML client (target: 25%)
- [ ] Phase 2 tests: integration tests for KPI, auth flow, alert engine (target: 50%)
- [ ] Install Vitest in frontend, test authStore sync + ProtectedRoute
- [ ] Add CI pipeline with test + CVE scan

### Phase 4 — Code Health (Ongoing)
- [ ] Split `vendas/service.py` into sync/analytics/listing services
- [ ] Extract shared frontend components (Variacao, exportCSV, KpiPeriodTable)
- [ ] Add pagination to all list endpoints
- [ ] Standardize URL paths (choose PT or EN)
- [ ] Add `response_model` to all 7 missing endpoints
- [ ] Create README.md
- [ ] Refactor Celery tasks to call service layer functions

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Backend Python files | 73 |
| Frontend TS/TSX files | 33 |
| Total lines (backend) | ~9,600 |
| Total lines (frontend) | ~3,900 |
| Backend modules | 13 |
| Frontend pages | 11 |
| Migrations | 10 |
| Test files | 1 |
| Test cases | 2 |
| Claude agents | 9 |
| Celery tasks | 6 |
| API endpoints | ~40 |
| Known CVEs | 2 (python-jose, express) |

---

## Positive Findings (Keep Doing)

1. **Zero SQL injection** — 100% parameterized ORM queries
2. **IDOR prevention** — every service filters by `user_id`
3. **bcrypt password hashing** — correctly implemented
4. **CLAUDE.md** — exceptional operational documentation (88/100)
5. **ML API reference** — production-quality endpoint docs (92/100)
6. **Consistent module pattern** — models/schemas/service/router everywhere
7. **Pydantic v2** — proper validation, `Decimal` for money
8. **Celery task timeouts** — soft 300s, hard 600s
9. **React XSS safety** — no `dangerouslySetInnerHTML`
10. **Docker multi-stage builds** — correctly implemented

---

## Conclusion

MSM_Pro has a solid foundation for a sales intelligence tool. The module architecture, data model, and operational documentation are above average for a project at this stage. The two areas that need urgent attention are **security** (credential rotation + OAuth CSRF fix) and **test coverage** (from 3% to at least 50%). Addressing the top 10 findings would move the overall score from **55 to approximately 75/100**.

---

*Generated by: Claude Opus 4.6 orchestrating 9 Sonnet 4.6 analysis agents*
*Analysis method: Static code analysis, configuration review, dependency audit*
*Total analysis time: ~25 minutes*
*Files reviewed: 120+ source files across backend and frontend*
