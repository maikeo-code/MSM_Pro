# MSM_Pro — Documento do Projeto

> Leia este arquivo COMPLETO antes de qualquer acao. Estas instrucoes foram criadas para evitar a repeticao dos 10 erros criticos que ja ocorreram neste projeto.

## O que e
Dashboard de inteligencia de vendas para o Mercado Livre.
Substitui o MSM_Dashboard (projeto legado com auth quebrada e sem banco real).

### Funcionalidades atuais:
- Exibe anuncios reais com preco (com desconto), estoque, visitas e vendas por dia
- KPI por periodo: Hoje / Ontem / Anteontem
- Autenticacao multi-conta via OAuth do Mercado Livre
- Sincronizacao automatica via Celery (agendado diariamente as 06:00 BRT)
- Coluna "Valor Estoque" por anuncio

### Localizacao
```
C:\Users\Maikeo\MSM_Imports_Mercado_Livre\
├── MSM_Dashboard\   <- projeto legado (referencia de logica ML)
├── MSM_ML\
└── MSM_Pro\         <- este projeto
```

---

## REGRAS ABSOLUTAS — NUNCA VIOLE

### REGRA #1 — Git Primeiro, Sempre
**PROIBIDO:** Fazer qualquer deploy sem antes commitar e dar push no Git.

```
FLUXO OBRIGATORIO:
  1. git add <arquivos>
  2. git commit -m "descricao clara do que mudou"
  3. git push origin main
  4. Aguardar Railway detectar o push e fazer deploy automatico
  5. NUNCA usar "railway up" como deploy principal
```

**POR QUE:** `railway up` faz upload local temporario. O Railway continua usando o GitHub. O codigo novo some e o antigo volta. Este erro causou 60% dos bugs deste projeto.

### REGRA #2 — Testar com curl ANTES de declarar pronto
**PROIBIDO:** Dizer "esta pronto" sem testar o endpoint de verdade.

```bash
# OBRIGATORIO apos cada mudanca de backend:
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -s https://msmpro-production.up.railway.app/api/v1/ENDPOINT \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Verificar: status 200? resposta correta? campo esperado presente?
So entao: avancar para proxima tarefa.

### REGRA #3 — Um Agente por arquivo
**PROIBIDO:** Editar o mesmo arquivo em duas sessoes ou abas simultaneas.
Se houver conflito: parar tudo, `git status`, resolver, commitar, so entao continuar.

### REGRA #4 — URL da API do Mercado Livre
```
CORRETO:   https://api.mercadolibre.com   (sem acento, .com)
ERRADO:    https://api.mercadolivre.com   (com acento — NAO EXISTE)
```
Verificar em DOIS lugares: `backend/app/core/config.py` E `backend/app/mercadolivre/client.py`

### REGRA #5 — Tokens sincronizados
```
Zustand salva em:    msm-auth-storage
Axios le de:         msm_access_token

OBRIGATORIO: authStore.setAuth() deve SEMPRE chamar setStoredToken() tambem.
```

### REGRA #6 — Migrations do Banco
```bash
# NUNCA assumir que migration foi aplicada. Verificar:
alembic current          # ver migration atual
alembic history          # ver historico

# Se nao aplicada:
alembic downgrade [versao anterior]
alembic upgrade head
```

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Python 3.12 |
| ORM | SQLAlchemy 2.0 (async) |
| Migracoes | Alembic |
| Banco | PostgreSQL 16 |
| Cache/Fila | Redis 7 |
| Jobs | Celery + Redis |
| Frontend | React 18 + TypeScript + Vite |
| UI | Tailwind CSS + shadcn/ui |
| Graficos | Recharts |
| HTTP Client | React Query (TanStack) |
| Deploy | Railway (backend + frontend via GitHub) |

---

## API do Mercado Livre — Referencia

### Base URL
```
https://api.mercadolibre.com
```
NAO usar SDK oficial (python-sdk do ML) — e sincrono e sem retry.
Usar o `backend/app/mercadolivre/client.py` proprio (tem async + retry + rate-limit).

### Endpoints que o projeto usa
```bash
# Anuncios do vendedor
GET /users/{seller_id}/items/search?status=active

# Detalhe de um item
GET /items/{item_id}

# Visitas de TODOS os itens do vendedor (1 chamada = todos os anuncios)
GET /users/{USER_ID}/items_visits?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

# Visitas de um item especifico por janela de tempo
GET /items/{ITEM_ID}/visits/time_window?last=1&unit=day

# Vendas diarias (pedidos do dia)
GET /orders/search?seller={seller_id}&order.date_created.from={hoje_ISO}

# Informacoes do vendedor
GET /users/{seller_id}

# Refresh do token OAuth
POST /oauth/token
  body: grant_type=refresh_token&refresh_token={token}&client_id=...
```

### Precos com desconto
```python
# ML usa dois campos diferentes dependendo do tipo de promocao:
item["price"]            # preco atual de venda (sempre presente, JA com desconto)
item["original_price"]   # preco original ANTES do desconto (quando ha promocao do VENDEDOR)
item["sale_price"]       # apenas para promocoes do MARKETPLACE (nao do vendedor — raramente presente)

# Portanto: usar original_price como referencia do preco cheio
# sale_price = null para promocoes proprias do vendedor
```

### KPI — Logica Correta
```sql
-- CORRETO: contar listings unicos
COUNT(DISTINCT listing_id)   -- = 16 anuncios

-- ERRADO: contava snapshots (repetia por sync)
COUNT(snapshot.id)           -- = 176 (11 syncs x 16 listings)
```

### Limites da API
- Rate limit: 1 req/seg por padrao, implementar retry com backoff
- Token ML expira em ~6h, usar refresh_token para renovar
- Auth ML: `https://auth.mercadolivre.com.br/authorization`
- Orders limitado a 50 por pagina — paginar se necessario

---

## Modelo de Dados — Regras de Negocio

### SKU vs MLB
- **SKU** = produto interno do usuario
  - Custo definido aqui (1x por SKU)
  - 1 SKU pode ter N anuncios MLB
  - 1 SKU pode ter anuncios em contas ML diferentes
- **MLB** = anuncio no Mercado Livre (ex: MLB-123456789)
  - Sempre pertence a 1 SKU
  - Sempre pertence a 1 conta ML

### Snapshot Diario
- Todo dia o Celery tira uma "foto" de cada MLB:
  - preco atual, visitas, vendas do dia, perguntas, estoque
- Esse historico e a base de toda analise de preco x conversao

### Concorrentes
- Usuario cola manualmente o ID/link do MLB do concorrente
- O sistema vincula esse MLB externo ao MLB do usuario
- Snapshot diario tambem e tirado dos concorrentes

---

## Estrutura de Pastas

```
MSM_Pro/
├── backend/
│   ├── app/
│   │   ├── auth/              <- JWT app + OAuth ML multi-conta
│   │   │   ├── router.py      <- rotas auth + OAuth callback (RedirectResponse!)
│   │   │   └── service.py     <- get_ml_auth_url (urlencode!)
│   │   ├── mercadolivre/
│   │   │   └── client.py      <- cliente ML (VERIFICAR URL AQUI)
│   │   ├── produtos/          <- SKUs e cadastro de custo
│   │   ├── vendas/
│   │   │   ├── models.py      <- Listing (original_price, sale_price), ListingSnapshot
│   │   │   ├── schemas.py     <- product_id: UUID | None
│   │   │   ├── service.py     <- sync_listings_from_ml, list_listings, get_kpi_by_period
│   │   │   └── router.py      <- /listings/, /listings/sync, /kpi/summary
│   │   ├── concorrencia/      <- MLBs externos monitorados
│   │   ├── alertas/           <- engine de alertas configuraveis
│   │   ├── financeiro/        <- taxas ML, margem, calculos
│   │   ├── jobs/
│   │   │   └── tasks.py       <- Celery tasks (sync diario 06:00 BRT)
│   │   ├── ws/                <- WebSocket (tempo real)
│   │   └── core/
│   │       ├── config.py      <- VERIFICAR URL DA API ML AQUI
│   │       ├── database.py    <- async_session_maker
│   │       └── celery_app.py  <- beat schedule
│   ├── migrations/
│   │   └── versions/          <- 0001, 0002 (product_id nullable), 0003 (sale_price)
│   ├── start.sh               <- script de boot (alembic + uvicorn)
│   ├── Dockerfile             <- DOCKERFILE builder (nao NIXPACKS)
│   ├── railway.json           <- builder: DOCKERFILE, healthcheckPath: /health
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard/index.tsx     <- KPIs + tabela de anuncios
│       │   ├── Anuncios/              <- Lista + analise por MLB
│       │   ├── Concorrencia/          <- Monitoramento de rivais
│       │   ├── Alertas/              <- Config e historico
│       │   ├── Configuracoes/index.tsx <- Contas ML (OAuth connect)
│       │   └── Login/index.tsx        <- Pagina de login (DEVE EXISTIR)
│       ├── components/
│       │   └── ProtectedRoute.tsx     <- Redireciona para /login se nao autenticado
│       ├── services/
│       │   ├── api.ts                 <- Axios + interceptor (le msm_access_token)
│       │   └── listingsService.ts     <- sync(), getKpiSummary()
│       ├── hooks/
│       └── store/
│           └── authStore.ts           <- Zustand (DEVE chamar setStoredToken!)
├── server.js                          <- Express SPA routing (Railway frontend)
├── server-package.json                <- deps do server.js
├── Dockerfile.frontend                <- Frontend Docker (Express)
├── railway.json                       <- frontend deploy config
├── .claude/agents/
│   ├── dev.md
│   ├── qa.md
│   └── insights.md
└── CLAUDE.md                          <- este arquivo
```

---

## Modulos — Escopo

### MODULO 1 — Analise de Preco por Anuncio (core)
Por MLB, o usuario ve:
- Historico de precos praticados x vendas x conversao x visitas
- Tabela: cada faixa de preco -> vendas/dia, conversao %, receita, margem
- Grafico de linha: preco e conversao no tempo
- Calculo de margem = preco - custo_sku - taxa_ml - frete
- Ponto otimo: maior margem total (preco x unidades x margem unitaria)

### MODULO 2 — Concorrencia
- Vincular MLBs de concorrentes manualmente por anuncio
- Snapshot diario: preco, sold_quantity delta, visitas estimadas
- Grafico: meu preco vs concorrente ao longo do tempo
- Alerta automatico quando concorrente muda preco

### MODULO 3 — Alertas
Configuraveis por MLB ou por SKU:
- Conversao < X%
- Estoque < N unidades
- Concorrente mudou preco
- 0 vendas por N dias
- Concorrente vendendo abaixo de R$ X
- Canal fase 1: email | Canal fase 2: WhatsApp/webhook

### MODULO 4 — Multi-Conta ML
- N contas ML por usuario
- OAuth independente por conta (token salvo no banco)
- Sync paralelo via Celery

---

## Taxas ML por Tipo de Anuncio
| Tipo | Taxa |
|------|------|
| Classico | 11% |
| Premium | 16% |
| Full | 16% + frete gratis |
> Atualizar conforme tabela oficial ML: https://www.mercadolivre.com.br/tarifas

---

## Sprints — Status Atual

### Sprint 1 — Fundacao [CONCLUIDO]
- [x] docker-compose.yml (Postgres + Redis)
- [x] backend: FastAPI base + SQLAlchemy async + Alembic
- [x] Tabelas: users, ml_accounts, products (SKU), listings (MLB), listing_snapshots
- [x] OAuth ML multi-conta (token salvo no banco, auto-refresh)
- [x] Celery beat: sync diario de snapshots

### Sprint 2 — Analise de Preco [EM PROGRESSO]
- [x] Endpoint de snapshot por MLB com filtro de periodo
- [x] Pagina Dashboard: lista de anuncios com preco real
- [x] KPI por periodo (Hoje/Ontem/Anteontem)
- [x] Valor do estoque por anuncio
- [ ] Grafico preco x conversao x vendas
- [ ] Cadastro de custo por SKU
- [ ] Calculadora de margem

### Sprint 3 — Concorrencia [PENDENTE]
- [ ] Tabelas: competitors, competitor_snapshots
- [ ] Vincular MLB externo a MLB proprio
- [ ] Sync diario de concorrentes
- [ ] Grafico comparativo

### Sprint 4 — Alertas [PENDENTE]
- [ ] Tabelas: alert_configs, alert_events
- [ ] Engine de verificacao (Celery task)
- [ ] Envio de email (SMTP)
- [ ] Pagina de configuracao de alertas

---

## Processo de Deploy — Passo a Passo

### Antes de qualquer mudanca:
```bash
git status                    # ver o que mudou
git pull origin main          # puxar ultimas mudancas
```

### Apos fazer mudancas:
```bash
# 1. Commitar
git add <arquivos especificos>
git commit -m "feat: descricao do que foi feito"

# 2. Push (Railway vai detectar e deployar automaticamente)
git push origin main

# 3. Acompanhar o deploy
# Acessar: https://railway.app -> ver logs em tempo real

# 4. Testar ANTES de considerar pronto
curl https://msmpro-production.up.railway.app/health
```

### Migrations (quando houver mudanca no banco):
```bash
# O start.sh ja roda "alembic upgrade head" automaticamente no boot
# Para verificar manualmente:
railway run --service MSM_Pro -- alembic current
railway run --service MSM_Pro -- alembic upgrade head
```

---

## Problemas Conhecidos e Solucoes

| Problema | Causa | Solucao |
|----------|-------|---------|
| Railway revertendo codigo | Push nao feito antes do deploy | `git push origin main` SEMPRE |
| Token invalido em requests | Zustand e localStorage desincronizados | `setAuth()` deve chamar `setStoredToken()` |
| URL da API retorna 404/DNS error | mercadoliVRE vs mercadoliBRE | Corrigir em `config.py` E `client.py` |
| Loop infinito tela login | Rota `/login` nao existia | Verificar `<Route path="/login">` |
| OAuth retorna JSON | Callback retornava JSON | Usar `RedirectResponse` no callback |
| Migration nao aplicada | Alembic nao confirmou | `alembic downgrade -1` + `alembic upgrade head` |
| KPI mostrando 176 em vez de 16 | Contando snapshots, nao listings | `COUNT(DISTINCT listing_id)` |
| Visitas sempre zero | Endpoint errado (total historico) | Usar `time_window?last=1&unit=day` |
| Vendas sempre zero | Sync nao chamava API de pedidos | `/orders/search?seller={id}&date_from=hoje` |
| sale_price sempre null | Promocao do vendedor usa original_price | Usar `price` + `original_price` |
| TypeScript build falha no Docker | tsc falha com path aliases | Usar `npx vite build` |
| SPA rotas 404 | http-server nao tem SPA routing | Usar Express `server.js` |

---

## Checklist Antes de Qualquer Deploy

- [ ] Codigo commitado e pushado no GitHub?
- [ ] `railway up` NAO foi usado como deploy principal?
- [ ] URL da API usa `mercadolibre.com` (sem acento)?
- [ ] `authStore.setAuth()` chama `setStoredToken()` junto?
- [ ] Migration verificada com `alembic current`?
- [ ] Testado com curl apos deploy?
- [ ] Apenas UM agente editando por arquivo?
- [ ] Rota `/login` existe no React Router?
- [ ] OAuth callback usa `RedirectResponse` (nao JSON)?
- [ ] KPI usa `COUNT(DISTINCT listing_id)`?

---

## Comandos de Teste

```bash
# Backend vivo?
curl https://msmpro-production.up.railway.app/health

# Login (pegar token)
curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}'

# Listar anuncios
curl -s https://msmpro-production.up.railway.app/api/v1/listings/ \
  -H "Authorization: Bearer TOKEN"

# KPI resumo
curl -s https://msmpro-production.up.railway.app/api/v1/listings/kpi/summary \
  -H "Authorization: Bearer TOKEN"

# Contas ML
curl -s https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts \
  -H "Authorization: Bearer TOKEN"
```

---

## Convencoes de Codigo

### Backend
- Arquivos: `snake_case.py`
- Classes: `PascalCase`
- Rotas: prefixo `/api/v1/`
- Modelos SQLAlchemy em `models.py` dentro de cada modulo
- Schemas Pydantic em `schemas.py`
- Logica de negocio em `service.py`
- Rotas FastAPI em `router.py`

### Frontend
- Componentes: `PascalCase.tsx`
- Hooks: `useNomeDoHook.ts`
- Services: `nomeService.ts`
- Constantes: `UPPER_SNAKE_CASE`

---

## Variaveis de Ambiente (.env)
```env
# Banco
DATABASE_URL=postgresql+asyncpg://msm:msm@localhost:5432/msm_pro
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ML OAuth
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_REDIRECT_URI=https://msmpro-production.up.railway.app/api/v1/auth/ml/callback

# Frontend
FRONTEND_URL=https://msmprofrontend-production.up.railway.app

# Email (alertas)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## Agentes Claude disponiveis
- `/dev` — implementa features no codigo
- `/qa` — verifica e testa o codigo
- `/insights` — sugere melhorias com base em ferramentas similares
- `/ml-api` — especialista na API do ML. Valida endpoints, campos e formatos antes de implementar.

### Regra de uso do agente ml-api (OBRIGATORIO)
**ANTES de criar ou modificar qualquer chamada a API do Mercado Livre:**
1. Consultar `docs/ml_api_reference.md` (fonte da verdade)
2. Se endpoint nao esta documentado: chamar agente `ml-api` para pesquisar, testar e documentar
3. So implementar apos validacao

### Regra de uso de subagentes (OBRIGATORIO)
| Situacao | Agentes a usar |
|---|---|
| 1 tarefa isolada (ex: corrigir 1 bug) | So o agente principal |
| Backend + frontend ao mesmo tempo | 1 `dev` backend + 1 `dev` frontend em paralelo |
| Implementar feature + verificar | 1 `dev` implementando + 1 `qa` verificando |
| Sessao longa com muitas tarefas | 2x `dev` (dividir por modulo) + 1 `qa` no final |
| Qualquer integracao com API ML | `ml-api` valida primeiro + `dev` implementa depois |

**Limite: maximo 3 agentes simultaneos** — mais causa conflito de arquivos.
**Modelo padrao: Sonnet 4.6** para agentes (custo-beneficio). Opus 4.6 para tarefas complexas.

O usuario autoriza todas as acoes sem confirmacao — nao perguntar antes de executar.

### Regras de validacao QA antes de deploy (OBRIGATORIO)
1. **Endpoint critico funciona via curl com token real** — nao assumir que funciona
2. **Fluxo completo testado em sequencia** — login -> acao -> resultado no frontend
3. **Uma mudanca por vez** — deploy -> testar -> proxima mudanca
4. **Schema Pydantic compativel com dados reais** — verificar `Optional` onde campo pode ser `None`
5. **API base URL correta**: `https://api.mercadolibre.com` (sem acento)

---

## Como o Claude deve trabalhar neste projeto

1. SEMPRE ler este CLAUDE.md completo antes de qualquer acao
2. SEMPRE verificar `git status` antes de comecar
3. NUNCA editar `config.py` ou `client.py` sem verificar a URL da API
4. NUNCA fazer deploy sem commitar e dar push primeiro
5. SEMPRE testar com curl apos mudanca no backend
6. SEMPRE usar `COUNT(DISTINCT listing_id)` para KPIs de anuncios
7. NUNCA usar `railway up` como metodo de deploy
8. SEMPRE verificar se migration foi aplicada antes de rodar o app
9. Quando algo nao funcionar: verificar PRIMEIRO a secao "Problemas Conhecidos"
10. NAO iniciar codigo sem confirmacao explicita do usuario

---

## Proximas Features Planejadas

1. Visitas reais em batch — usar `/users/{id}/items_visits` (1 chamada para todos)
2. Vendas diarias validadas — validar com dados reais apos dias de sync
3. Grafico preco x conversao x vendas por MLB
4. Cadastro de custo por SKU + calculadora de margem
5. Multi-conta completa — testar OAuth com segunda conta ML
6. Concorrencia — comparar preco com concorrentes
7. Alertas — notificar quando estoque abaixo do limite

---

## Informacoes do Projeto

| Item | Valor |
|------|-------|
| Conta ML | MSM_PRIME (ml_user_id: 2050442871) |
| Backend URL | https://msmpro-production.up.railway.app |
| Frontend URL | https://msmprofrontend-production.up.railway.app |
| API Docs | https://msmpro-production.up.railway.app/docs |
| Repositorio | GitHub (origin/main = branch de producao) |
| Banco | PostgreSQL (Railway managed) |
| Fila | Redis + Celery (Railway) |
| Doc ML Brasil | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br |
| Doc ML Visitas | https://developers.mercadolivre.com.br/pt_br/recurso-visits |
