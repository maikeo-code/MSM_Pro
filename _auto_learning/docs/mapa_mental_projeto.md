# MAPA MENTAL — MSM_Pro
# Gerado pelo Sistema de Auto-Aprendizado (5 ciclos, 8 agentes)
# Data: 2026-03-13

```
MSM_Pro — Dashboard de Inteligencia ML
|
+-- BACKEND (FastAPI + Python 3.12)
|   |
|   +-- AUTH (/api/v1/auth/)
|   |   +-- JWT HS256, 24h expiry
|   |   |   +-- [P0 BUG] Secret key hardcoded como fallback
|   |   |   +-- [P0 GAP] Sem token blacklist
|   |   |   +-- [P1 GAP] Sem endpoint logout server-side
|   |   |   +-- [P1 GAP] Sem endpoint change-password
|   |   |   +-- [P2 GAP] Sem jti claim (revocacao granular)
|   |   |
|   |   +-- OAuth ML Multi-conta
|   |   |   +-- [P0 BUG] Tokens ML em plaintext (comentario diz criptografado)
|   |   |   +-- [P1 BUG] State param sem nonce CSRF
|   |   |   +-- [P2 GAP] Delete conta nao revoga token no ML
|   |   |   +-- [P2 GAP] Refresh falho nao marca conta invalida
|   |   |
|   |   +-- Login
|   |       +-- [P0 GAP] Sem rate limiting (brute force possivel)
|   |       +-- [P2 GAP] Sem complexidade de senha (min 8 chars apenas)
|   |
|   +-- VENDAS (/api/v1/listings/)
|   |   +-- Listings (MLB)
|   |   |   +-- CRUD + sync ML
|   |   |   +-- [P2 DUP] Listing-to-dict em 3 lugares
|   |   |   +-- [P2 DUP] Price extraction duplicada (service + tasks)
|   |   |   +-- [P2 DUP] SKU extraction duplicada
|   |   |   +-- [P3] Pagination aceita mas nao aplicada (200 default)
|   |   |
|   |   +-- ListingSnapshots (historico diario)
|   |   |   +-- [P0 BUG] Race condition: 2 workers podem duplicar snapshot
|   |   |   +-- [P1 GAP] Sem UNIQUE(listing_id, date) no DB
|   |   |   +-- [P3 GAP] Sem data retention/cleanup
|   |   |   +-- [P2 BUG] datetime.utcnow() em 1 lugar (naive vs aware)
|   |   |
|   |   +-- KPI (Hoje/Ontem/Anteontem/7d/30d)
|   |   |   +-- [OK] COUNT(DISTINCT listing_id) correto
|   |   |   +-- [P2 DUP] KPI result builder copy-paste
|   |   |
|   |   +-- Orders (pedidos)
|   |   |   +-- [P0 BUG] UTC offset -03:00 hardcoded em date_from UTC
|   |   |   +-- [P1 BUG] Multi-item orders perdem itens 2+
|   |   |   +-- [P2 GAP] listing_id NULL nunca reconciliado
|   |   |   +-- [P2 GAP] Sem buyer_id (apenas nickname)
|   |   |   +-- [P2] Partial commit em paginacao
|   |   |
|   |   +-- Analise (UpSeller-style)
|   |       +-- [OK] Mock data para quando sem token
|   |       +-- [P3] Mock data 130 linhas no service producao
|   |
|   +-- CONCORRENCIA (/api/v1/concorrencia/)
|   |   +-- Competitors CRUD
|   |   |   +-- [P2 GAP] Sem UNIQUE(listing_id, mlb_id) — duplicatas possiveis
|   |   +-- CompetitorSnapshots
|   |   |   +-- [P1 N+1] 2 queries por competitor no loop sync
|   |   |   +-- [P2 GAP] sold_quantity tracking OK
|   |   +-- Visits Bulk
|   |       +-- [OK] Reduz 94% chamadas API
|   |
|   +-- ALERTAS (/api/v1/alertas/)
|   |   +-- 5 tipos configuraveis + 1 auto (competitor_stockout)
|   |   +-- [P0 BUG] Sem deduplicacao — 12 emails/dia se condicao persiste
|   |   +-- [P1 BUG] conversion_rate Decimal("0") excluido por if falsy
|   |   +-- [P1 BUG] sales_today inflado por snapshots duplicados/dia
|   |   +-- [P2 BUG] competitor_stockout cria AlertConfig nao avaliavel
|   |   +-- [P2 GAP] Webhook channel nao implementado
|   |   +-- [P2 GAP] Listings pausados geram falso positivo
|   |   +-- [P2 N+1] O(listings x competitors) em price checks
|   |   +-- [P3 UX] Frontend soft-delete confuso, sem edicao
|   |
|   +-- FINANCEIRO (/api/v1/financeiro/)
|   |   +-- P&L Resumido + Timeline + Detalhado
|   |   +-- Cashflow D+8
|   |   |   +-- [OK] Formula margem correta
|   |   |   +-- [P1 BUG] Taxas divergem: code 11.5%/17% vs doc 11%/16%
|   |   |   +-- [P3] Rounding acumula antes dos totais
|   |   |   +-- [P3] Cashflow inclui orders nao enviados
|   |   +-- [P3] dict[str, Any] return types (sem TypedDict)
|   |
|   +-- CONSULTOR IA (/api/v1/consultor/)
|   |   +-- Analise Claude enriquecida
|   |   +-- [P0 GAP] Sem rate limiting — custo descontrolado
|   |   +-- [P2] Prompt injection medium risk (titulos sem sanitizacao)
|   |   +-- [P2] Response parsing pode crashar (KeyError)
|   |   +-- [OK] XSS seguro (RenderAnalise.tsx escapeHtml)
|   |
|   +-- REPUTACAO (/api/v1/reputacao/)
|   |   +-- Snapshots + Risk Simulator
|   |   +-- [P2 BUG] Race condition duplica snapshot (sem UNIQUE)
|   |   +-- [P2 BUG] date.today() usa timezone server
|   |
|   +-- ADS (/api/v1/ads/)
|   |   +-- Campanhas + ROAS/ACOS
|   |   +-- [P0 BUG] _sync_ads_async sem db.commit() — dados perdidos
|   |   +-- [INFO] API ML Ads nao e publica — fallback gracioso
|   |
|   +-- PRODUTOS (/api/v1/produtos/)
|   |   +-- SKU + custo
|   |   +-- [P1 BUG] CASCADE products->listings deveria ser SET NULL
|   |
|   +-- CELERY (jobs/tasks.py — 1200 linhas)
|   |   +-- 8 tasks agendadas (beat schedule)
|   |   +-- [P1 DEBT] Monolito — todos dominios em 1 arquivo
|   |   +-- [P1 BUG] Token 401 silenciosamente ignorado mid-sync
|   |   +-- [P2 BUG] Reputation double-commit rollback total
|   |   +-- [P2 BUG] Stale sync_logs ficam "running" forever
|   |   +-- [P2 GAP] sync_recent_snapshots sem try/except
|   |   +-- [P3] logger.error sem traceback (precisa logger.exception)
|   |
|   +-- ML CLIENT (mercadolivre/client.py)
|   |   +-- Rate limit 1 req/seg + retry backoff
|   |   +-- [P1 BUG] asyncio.Lock nao funciona entre workers
|   |   +-- [P1 BUG] Retry bypassa rate limiter
|   |
|   +-- CORE
|   |   +-- config.py
|   |   |   +-- [P0] secret_key fallback inseguro
|   |   |   +-- [P2] debug=True por padrao
|   |   +-- database.py
|   |   |   +-- [P2 GAP] Sem pool_timeout configurado
|   |   +-- constants.py
|   |       +-- [P1] Taxas ML divergem da documentacao
|   |
|   +-- MIGRATIONS (0001-0012)
|       +-- [OK] Chain linear integra
|       +-- [P1] 6 constraints faltando
|       +-- [P2] nullable mismatch ORM vs migration
|       +-- [P2] Sem functional index DATE(captured_at)
|
+-- FRONTEND (React 18 + TypeScript + Vite)
|   |
|   +-- PAGES
|   |   +-- Dashboard (885 linhas)
|   |   |   +-- [P2] Sort/filter sem useMemo
|   |   |   +-- [P2] 5 sub-components inline (nao extraidos)
|   |   |   +-- [P2 DUP] Period table duplicada com Anuncios
|   |   |
|   |   +-- AnuncioDetalhe (1314 linhas — GOD COMPONENT)
|   |   |   +-- [P1] Maior component, importado eagerly
|   |   |   +-- [P1] Deveria ser decomposto em 5+ sub-components
|   |   |
|   |   +-- Anuncios (473 linhas)
|   |   |   +-- [P2 DUP] Sort/filter/totals duplicado com Dashboard
|   |   |   +-- [P3] Error handling inconsistente
|   |   |
|   |   +-- Financeiro (565 linhas)
|   |   |   +-- [P3 DUP] Variacao local duplica componente shared
|   |   |
|   |   +-- Alertas (524 linhas)
|   |   |   +-- [P2 UX] Sem edicao de alertas
|   |   |   +-- [P3 UX] Soft-delete confuso
|   |   |
|   |   +-- Reputacao (563 linhas)
|   |   |   +-- [P2] Bypassa React Query (useEffect raw)
|   |   |
|   |   +-- Concorrencia (294 linhas)
|   |       +-- [P2 A11Y] Labels sem htmlFor
|   |
|   +-- STATE
|   |   +-- Zustand (authStore) + React Query
|   |   +-- [P2] Token duplicado em 2 localStorage keys
|   |   +-- [P2] Logout nao limpa queryClient cache
|   |
|   +-- BUNDLE
|   |   +-- [P1 BUG] react-query-devtools em dependencies (vai pra prod)
|   |   +-- [P2] 7/9 rotas sem lazy loading
|   |   +-- [P2] Recharts sem chunk separado (~500KB)
|   |   +-- [P3] noUncheckedIndexedAccess nao habilitado
|   |
|   +-- A11Y
|       +-- [P2] Zero error boundaries
|       +-- [P2] Heatmap sem keyboard navigation
|       +-- [P2] Botoes icon-only sem aria-label
|       +-- [P3] Cor como unica indicacao de status
|
+-- INFRA (Railway + PostgreSQL + Redis)
|   |
|   +-- Deploy via GitHub push
|   +-- [OK] CORS regex *.railway.app (mitigado por JWT)
|   +-- [P2] Health check raso (sem verificar DB/Redis)
|   +-- [P3] Sem monitoring/alerting de infra
|
+-- SEGURANCA (resumo cross-cutting)
|   +-- [OK] Zero SQL injection
|   +-- [OK] IDOR protegido em todos endpoints
|   +-- [OK] XSS seguro no Consultor
|   +-- [P0] JWT secret, tokens plaintext, sem blacklist
|   +-- [P1] OAuth CSRF, rate limit login
|   +-- [P2] Webhook sem auth, error bodies vazam
|
+-- QUALIDADE
    +-- Cobertura testes: ~3% (2 testes triviais)
    +-- Code duplication: 7 pontos significativos
    +-- Dead code: 4 pontos
    +-- N+1 queries: 5 pontos
    +-- Error handling: silent swallow em 6+ pontos
```

## PRIORIZACAO FINAL — 37 Issues

### P0 — Corrigir AGORA (8 items)
1. JWT startup guard (config.py secret_key)
2. _sync_ads_async db.commit() fix
3. Rate limiting /auth/login
4. ML tokens criptografia (Fernet)
5. Race condition snapshot UNIQUE constraint
6. UTC offset orders date_from
7. Alertas deduplicacao (cooldown 24h)
8. Consultor rate limiting (Redis cooldown)

### P1 — Proximo Sprint (12 items)
1. OAuth state nonce CSRF
2. CASCADE products SET NULL
3. Token 401 retry mid-sync
4. Multi-item orders
5. Taxas ML alinhar code vs doc
6. asyncio.Lock distribuido (Redis)
7. react-query-devtools para devDependencies
8. AnuncioDetalhe decomposicao
9. 6 constraints faltando (migration 0013)
10. tasks.py split por dominio
11. Endpoint logout server-side
12. Endpoint change-password

### P2 — Debt Tecnica (11 items)
1. Health check deep
2. Error boundaries React
3. useMemo sort/filter
4. Lazy loading rotas
5. Code duplication extraction
6. N+1 queries fix
7. datetime.utcnow() fix
8. Webhook auth
9. debug=False default
10. pool_timeout DB
11. Reputacao migrar para React Query

### P3 — Backlog (6 items)
1. Data retention snapshots
2. noUncheckedIndexedAccess
3. Cashflow orders nao enviados
4. Rounding precision
5. Mock data extraction
6. A11Y color-only indicators
