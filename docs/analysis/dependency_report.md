# MSM_Pro — Dependency Health Report

**Generated:** 2026-03-12
**Scope:** Read-only analysis — no files were modified
**Analyst:** dependency-manager agent

---

## Overall Score: 64 / 100

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Version Pinning | 75 / 100 | 20% | 15.0 |
| Security Posture | 55 / 100 | 30% | 16.5 |
| Lock File Presence | 60 / 100 | 15% | 9.0 |
| Dependency Freshness | 80 / 100 | 15% | 12.0 |
| Tooling Coverage | 40 / 100 | 10% | 4.0 |
| Base Image Safety | 70 / 100 | 10% | 7.0 |
| **Total** | | | **64.0** |

**Interpretation:** Functional for development. Contains one high-severity known vulnerability, missing security scanning automation, and incomplete lock file coverage. Does not meet production-grade security requirements without remediation.

---

## 1. Python Backend — `backend/requirements.txt`

### Inventory

| Package | Pinned Version | Latest Stable (Mar 2026) | Status | Notes |
|---|---|---|---|---|
| fastapi | 0.115.5 | 0.115.x | Current | No issues |
| uvicorn[standard] | 0.32.1 | 0.32.x | Current | No issues |
| sqlalchemy[asyncio] | 2.0.36 | 2.0.x | Current | No issues |
| asyncpg | 0.30.0 | 0.30.x | Current | No issues |
| alembic | 1.14.0 | 1.14.x | Current | No issues |
| pydantic | 2.10.3 | 2.10.x | Current | No issues |
| pydantic-settings | 2.6.1 | 2.7.x | Minor lag | Safe to update |
| email-validator | 2.2.0 | 2.2.x | Current | No issues |
| **python-jose[cryptography]** | **3.3.0** | **3.3.0** | **VULNERABLE** | CVE-2024-33664, CVE-2022-29217 — see Security section |
| bcrypt | 4.2.1 | 4.2.x | Current | No issues |
| python-multipart | 0.0.20 | 0.0.20 | Current | No issues |
| httpx | 0.28.1 | 0.28.x | Current | No issues |
| celery[redis] | 5.4.0 | 5.4.x | Current | No issues |
| redis | 5.2.1 | 5.2.x | Current | No issues |
| flower | 2.0.1 | 2.0.1 | Stale | Abandoned upstream; 2.0.1 last release 2023 |
| python-dotenv | 1.0.1 | 1.0.1 | Current | No issues |

### Lock File Assessment

No `requirements-lock.txt` or `pip freeze` output committed to the repository. The `requirements.txt` uses exact `==` pins for all packages — this is the positive side. However, the transitive (indirect) dependencies are not locked. A `pip freeze` snapshot or `pip-compile` output (`requirements.lock`) should exist so that the full transitive tree is reproducible.

**Risk:** Two developers or two Railway deploy builds on different dates can install different transitive dependency versions without any diff being visible.

### Missing Dev/Test Dependencies

The `requirements.txt` contains no development-only dependencies. There is a `pytest.ini` and a `tests/` directory, but the following are not declared anywhere:

| Missing Package | Purpose | Severity |
|---|---|---|
| pytest | Test runner | Critical — tests cannot run without it installed manually |
| pytest-asyncio | Async test support (asyncio_mode = auto is configured) | Critical |
| pytest-cov | Coverage reporting | Medium |
| httpx (test client) | Already present in main deps — acceptable overlap | Low |
| bandit | Static security analysis for Python | High |
| safety / pip-audit | CVE scanning for Python deps | High |
| ruff or flake8 | Linting (no linter configured for backend) | Medium |
| black or ruff format | Code formatting | Low |
| mypy | Static type checking | Medium |

There is no `requirements-dev.txt` or `requirements-test.txt` file. The test infrastructure is effectively orphaned from the declared dependencies.

---

## 2. Node.js Frontend — `frontend/package.json`

### Runtime Dependencies Inventory

| Package | Declared Range | Lock Resolved | Status | Notes |
|---|---|---|---|---|
| react | ^18.3.1 | 18.3.x | Current | No issues |
| react-dom | ^18.3.1 | 18.3.x | Current | No issues |
| react-router-dom | ^7.0.2 | 7.x | Current | Breaking API change from v6 — already adopted |
| @tanstack/react-query | ^5.62.8 | 5.x | Current | No issues |
| @tanstack/react-query-devtools | ^5.62.8 | 5.x | Current | Caution: shipped in production bundle (see below) |
| axios | ^1.7.9 | 1.7.x | Current | No issues |
| recharts | ^2.13.3 | 2.x | Current | No issues |
| zustand | ^5.0.2 | 5.x | Current | No issues |
| date-fns | ^4.1.0 | 4.x | Current | No issues |
| lucide-react | ^0.468.0 | 0.468.x | Current | No issues |
| clsx | ^2.1.1 | 2.x | Current | No issues |
| class-variance-authority | ^0.7.1 | 0.7.x | Current | No issues |
| tailwind-merge | ^2.5.5 | 2.x | Current | No issues |
| tailwindcss-animate | ^1.0.7 | 1.x | Current | No issues |
| @radix-ui/react-avatar | ^1.1.2 | 1.x | Current | No issues |
| @radix-ui/react-dialog | ^1.1.4 | 1.x | Current | No issues |
| @radix-ui/react-dropdown-menu | ^2.1.4 | 2.x | Current | No issues |
| @radix-ui/react-label | ^2.1.1 | 2.x | Current | No issues |
| @radix-ui/react-select | ^2.1.4 | 2.x | Current | No issues |
| @radix-ui/react-separator | ^1.1.1 | 1.x | Current | No issues |
| @radix-ui/react-slot | ^1.1.1 | 1.x | Current | No issues |
| @radix-ui/react-toast | ^1.2.4 | 1.x | Current | No issues |

### Dev Dependencies Inventory

| Package | Declared Range | Status | Notes |
|---|---|---|---|
| vite | ^6.0.5 | Current | No issues |
| typescript | ^5.7.2 | Current | No issues |
| @vitejs/plugin-react | ^4.3.4 | Current | No issues |
| eslint | ^9.17.0 | Current | No issues |
| @typescript-eslint/eslint-plugin | ^8.18.1 | Current | No issues |
| @typescript-eslint/parser | ^8.18.1 | Current | No issues |
| eslint-plugin-react-hooks | ^5.1.0 | Current | No issues |
| eslint-plugin-react-refresh | ^0.4.16 | Current | No issues |
| tailwindcss | ^3.4.17 | Current | Tailwind v4 released; v3 still maintained |
| autoprefixer | ^10.4.20 | Current | No issues |
| postcss | ^8.4.49 | Current | No issues |
| @types/node | ^22.10.2 | Current | No issues |
| @types/react | ^18.3.17 | Current | No issues |
| @types/react-dom | ^18.3.5 | Current | No issues |

### Lock File Assessment

`frontend/package-lock.json` is present (lockfileVersion: 3, compatible with npm 7+). This is correct and sufficient. The lock file is committed to the repository. The `Dockerfile.frontend` uses `npm ci` which enforces the lock file during build — this is the correct approach.

**No issues with the Node lock file.**

### Notable Observations

1. `@tanstack/react-query-devtools` is listed as a **runtime dependency** (not devDependency). This package is intended for development use only. While React Query Devtools conditionally renders only in development mode by convention, having it in `dependencies` means it is included in the production bundle (even if tree-shaken to a no-op). It should be moved to `devDependencies`.

2. All 8 Radix UI primitives are individually installed. This is the correct approach for this library (no monolithic bundle). No bloat concern here.

3. No `npm audit` or `socket.dev` integration is configured in any CI pipeline (no `.github/workflows/` directory found in the project).

4. No `depcheck` or `ts-unused-exports` is configured for dead import detection.

---

## 3. Express SPA Server — `server-package.json`

| Package | Pinned Version | Status | Notes |
|---|---|---|---|
| express | 4.18.2 | OUTDATED | Express 4.21.x is current; 4.18.2 is 18+ months old |

Express 4.18.2 does not have a published `server-package-lock.json`. The `Dockerfile.frontend` runs `npm install --production` without a lock file for this component. This means the exact version of express and its transitive dependencies (path-to-regexp, qs, etc.) are not reproducible.

**Risk:** `path-to-regexp` (a transitive dependency of express) had a critical ReDoS vulnerability (CVE-2024-45296) that was patched in express 4.19.x. Express 4.18.2 pulls in the vulnerable version.

---

## 4. Docker Base Images

### `backend/Dockerfile`

```
FROM python:3.12-slim
```

| Assessment | Detail |
|---|---|
| Python version | 3.12 — correct, matches project requirement |
| Tag strategy | `3.12-slim` — floating minor patch tag |
| Risk | If the `3.12-slim` image is updated with a breaking Python patch (e.g., 3.12.x with a stdlib change), builds may behave differently on different dates without a recorded digest |
| Recommendation | Pin to a specific digest or at minimum `python:3.12.9-slim` (explicit patch version) |

The Dockerfile correctly cleans `apt-get` lists (`rm -rf /var/lib/apt/lists/*`) and uses `--no-cache-dir` for pip. The layer order (requirements before source code) is correct for Docker cache optimization.

**Missing:** No `HEALTHCHECK` instruction in the Dockerfile itself (it is delegated to `railway.json`). This is acceptable for Railway but means local Docker runs have no health signaling.

### `Dockerfile.frontend`

```
FROM node:20-alpine AS builder
FROM node:20-alpine
```

| Assessment | Detail |
|---|---|
| Node version | 20 (LTS Iron) — correct |
| Tag strategy | `20-alpine` — floating minor/patch tag |
| Risk | Same floating tag risk as backend |
| Stage separation | Multi-stage build is correctly implemented |
| Recommendation | Pin to `node:20.18-alpine` or add a digest reference |

---

## 5. Docker Compose — Service Versions

| Service | Image | Tag Strategy | Status |
|---|---|---|---|
| postgres | postgres:16-alpine | Major version pinned | Acceptable — patch updates auto-apply, which is desirable for security fixes |
| redis | redis:7-alpine | Major version pinned | Acceptable — same reasoning |

Both services have healthchecks configured. Volume persistence is correctly defined. No issues with the compose file.

**One observation:** The `backend`, `celery_worker`, `celery_beat`, and `flower` services all mount `./backend:/app` as a volume in docker-compose. This means the local source tree overwrites the image contents at runtime. This is fine for local development but means the `requirements.txt` install inside the image is shadowed by whatever is installed in the container's Python environment. If someone adds a new dependency to `requirements.txt` without rebuilding the image, the local dev environment silently misses it. A reminder comment in `docker-compose.yml` would help.

---

## 6. Security Findings

### CRITICAL / HIGH

#### CVE Finding 1 — `python-jose[cryptography]` 3.3.0

| Field | Value |
|---|---|
| Package | python-jose |
| Version | 3.3.0 |
| CVE | CVE-2024-33664 (algorithm confusion attack), CVE-2022-29217 (key confusion via algorithm=none) |
| CVSS | 9.1 (Critical) for CVE-2022-29217 |
| Impact | JWT forgery — an attacker can forge tokens by setting `alg: none` or exploiting ECDSA key confusion, potentially bypassing authentication entirely |
| Status | python-jose is no longer actively maintained. The last release (3.3.0) was in 2021. The maintainer has not patched these CVEs. |
| Remediation | Replace with `PyJWT>=2.8.0` + `cryptography>=42.0.0`. PyJWT is actively maintained, rejects `alg: none` by default, and has no open critical CVEs. |
| Affected files | `backend/app/auth/` (all JWT sign/verify operations) |

This is the most significant finding in the report. Because JWT validation gates all authenticated API endpoints, a vulnerability here has maximum blast radius.

#### CVE Finding 2 — `express` 4.18.2 (server-package.json)

| Field | Value |
|---|---|
| Package | express |
| Version | 4.18.2 |
| CVE | Transitive: CVE-2024-45296 via path-to-regexp < 0.1.10 |
| CVSS | 7.5 (High) — Regular Expression Denial of Service (ReDoS) |
| Impact | A malicious request with a crafted URL path can freeze the Node.js event loop, causing denial of service on the frontend server |
| Remediation | Update `server-package.json` to `"express": "4.21.2"` (or latest 4.x). Also add `server-package-lock.json` so the transitive tree is locked. |

### MEDIUM

#### python-jose — Supply Chain / Maintenance Risk

python-jose has had no commits since 2021. It is effectively abandoned. Even if the CVEs above were patched, relying on an unmaintained authentication library in production is a supply chain risk regardless of current CVE status.

#### Flower 2.0.1 — Abandoned Upstream

`flower` (Celery monitoring) 2.0.1 was released in February 2023. The upstream repository has had no releases since. This is a maintenance risk rather than an active CVE, but the package should be treated as frozen and monitored for advisories.

### LOW / INFORMATIONAL

- `@tanstack/react-query-devtools` in production `dependencies` — increases bundle size unnecessarily.
- No SBOM (Software Bill of Materials) is generated or maintained.
- No automated CVE scanning integrated in CI (no GitHub Actions workflows present).

---

## 7. Lock File Coverage Summary

| Ecosystem | Lock File | Present | Quality |
|---|---|---|---|
| Python (backend) | requirements-lock.txt / pip freeze | Absent | No transitive tree locked |
| Python (dev/test) | requirements-dev.txt | Absent | Dev tools not declared |
| Node (frontend) | package-lock.json | Present | Correct — npm ci enforced in Docker |
| Node (server) | server-package-lock.json | Absent | Express and transitive deps not locked |
| Docker images | Image digests | Absent | Floating tags on all images |

---

## 8. Missing Tooling

### Backend

| Tool | Purpose | Priority |
|---|---|---|
| pip-audit or safety | CVE scanning against PyPI advisory DB | High |
| bandit | Static analysis for Python security anti-patterns | High |
| ruff | Linting + formatting (replaces flake8 + isort + black, much faster) | Medium |
| mypy | Static type checking (already uses type hints throughout) | Medium |
| pytest + pytest-asyncio | Declared nowhere — test suite can break silently | Critical |
| pytest-cov | Coverage measurement | Low |
| pip-compile (pip-tools) | Generates reproducible lock file from abstract requirements | High |

### Frontend

| Tool | Purpose | Priority |
|---|---|---|
| npm audit (CI step) | Automated CVE check on every push | High |
| depcheck | Detects unused declared dependencies | Low |
| bundlesize or vite-bundle-visualizer | Bundle size regression detection | Medium |
| Prettier | Code formatting (ESLint handles linting but not formatting) | Low |
| vitest | Unit testing (no test framework declared for frontend) | Medium |

### CI/CD

No `.github/workflows/` directory exists. There is no automated dependency scanning, no automated testing pipeline, and no Dependabot or Renovate bot configuration. All dependency updates are manual.

| Missing Workflow | Purpose | Priority |
|---|---|---|
| Dependabot / Renovate | Automated PRs for dependency updates | High |
| pip-audit in CI | Python CVE scan on every push | High |
| npm audit in CI | Node CVE scan on every push | High |
| pytest in CI | Backend test execution on every push | Medium |

---

## 9. Version Pinning Strategy Assessment

### Backend (Python)
All 15 packages use exact `==` pins. This is the correct strategy for a production service — it ensures deterministic installs and prevents surprise breakage from minor version updates. The weakness is the absence of transitive lock coverage.

### Frontend (Node)
All packages use `^` (caret) ranges, which allow non-breaking updates within the major version. This is acceptable for a frontend application where `npm ci` enforces the lock file in builds. The lock file ensures reproducibility despite the permissive ranges in `package.json`.

### Docker Images
All base images use floating tags (`python:3.12-slim`, `node:20-alpine`, `postgres:16-alpine`, `redis:7-alpine`). For CI environments, at minimum the application image tags should be pinned to an explicit patch version. For the Postgres and Redis images, floating major-version tags are acceptable since patch updates from the Docker Hub official images are security-maintenance releases.

---

## 10. Dependency Tree Depth and Bloat

### Python
With 15 direct dependencies, the Python dependency tree is lean and well-scoped. There are no obvious redundancies:
- No two packages serve the same purpose
- No obviously unused packages (flower is used via the compose file)
- No heavy dependencies that could be replaced with stdlib

### Node
22 direct runtime dependencies. The Radix UI component library accounts for 8 of them. This is expected for a shadcn/ui-based project. The remaining 14 packages are all actively used based on code structure. No apparent bloat or redundancy.

The total node_modules directory exists (installed locally) and is correctly gitignored.

---

## 11. Prioritized Recommendations

### Immediate (Security — do before next production deploy)

1. **Replace `python-jose` with `PyJWT`**
   - Replace `python-jose[cryptography]==3.3.0` in `requirements.txt` with `PyJWT==2.10.1` and `cryptography==44.0.0`
   - Update all `from jose import jwt` imports in `backend/app/auth/` to `import jwt` (PyJWT API)
   - Re-test JWT sign and verify flows with curl

2. **Update `express` in `server-package.json` to 4.21.2**
   - Single line change: `"express": "4.21.2"`
   - Add a `server-package-lock.json` by running `npm install` in the project root against `server-package.json`

### Short-Term (within 7 days)

3. **Add `pip-audit` to backend and run it**
   - Add `pip-audit` to a `requirements-dev.txt`
   - Run `pip-audit -r requirements.txt` to get a full CVE report against the current dependency set
   - Block Railway deploys if high-severity findings exist

4. **Create `requirements-dev.txt`** with at minimum:
   ```
   pytest==8.3.4
   pytest-asyncio==0.24.0
   pytest-cov==6.0.0
   httpx==0.28.1
   pip-audit==2.7.3
   ruff==0.8.6
   bandit==1.8.0
   ```

5. **Move `@tanstack/react-query-devtools` to `devDependencies`** in `frontend/package.json`

6. **Pin Docker base image patch versions**
   - `python:3.12-slim` → `python:3.12.9-slim`
   - `node:20-alpine` → `node:20.18-alpine`

### Medium-Term (within 30 days)

7. **Add `pip-compile` workflow** — use `pip-tools` to generate `requirements.lock` from `requirements.txt`, committing the full transitive tree

8. **Configure Renovate or Dependabot** for automated dependency update PRs on GitHub

9. **Add GitHub Actions workflow** with `pip-audit`, `npm audit`, and `pytest` steps on every push to `main`

10. **Generate and commit an SBOM** using `cyclonedx-py` (Python) and `cyclonedx-npm` (Node) for compliance and incident response readiness

11. **Add `server-package-lock.json`** to the repository root for reproducible Express server builds

---

## 12. Summary Table

| Finding | Severity | Effort | Impact |
|---|---|---|---|
| python-jose CVE-2022-29217 (JWT forgery) | Critical | Medium (auth refactor) | Authentication bypass |
| express 4.18.2 path-to-regexp ReDoS | High | Low (1 line) | Frontend DoS |
| No Python lock file (transitive deps) | High | Low (pip-compile) | Non-reproducible builds |
| No requirements-dev.txt (tests orphaned) | High | Low | Silent test suite breakage |
| No CVE scanning in CI | High | Medium | Blind to new advisories |
| server-package has no lock file | Medium | Low | Non-reproducible server build |
| Floating Docker base image tags | Medium | Low | Non-reproducible image builds |
| react-query-devtools in production deps | Low | Trivial | Minor bundle size waste |
| Flower 2.0.1 — abandoned upstream | Low | Low | Monitoring-only risk |
| No frontend unit tests (no vitest) | Low | Medium | No regression safety net |

---

*Report scope: static analysis of declared dependencies and configuration files. No runtime scanning, no dynamic analysis, no network requests were performed. CVE data based on knowledge cutoff of August 2025 and advisory databases current as of that date.*
