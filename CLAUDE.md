# MSM_Pro — Portal do Cérebro

> Este arquivo é PORTAL, não documentação.
> Toda informação detalhada está no vault Obsidian unificado:
> `C:/Users/Maikeo/MSM_Imports_Mercado_Livre/Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/`

---

## REGRA #0 — CONSULTAR CÉREBRO ANTES DE TOCAR CÓDIGO

ANTES de qualquer modificação:

1. Identifique o domínio (endpoint? auth? migration? deploy? bug?)
2. Leia a(s) nota(s) relevante(s):
   - Endpoints: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/02 - API Mercado Livre/Endpoints Usados.md`
   - Bugs: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/08 - Bugs e Fixes/`
   - Decisões: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/14 - ADR/`
   - Módulos: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/05 - Módulos/`
   - Regras: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/06 - Regras/Regras Absolutas.md`
3. Verifique se já existe ADR ou bug sobre o tema
4. Se a tarefa tem impacto cross-domínio (margem, financeiro, advocacia), navegue WIKILINKS para fora da sub-pasta MSM_Pro
5. Só então execute

Sem essa consulta, você está alucinando. Não é opcional.

---

## Sequência de boot OBRIGATÓRIA

Em toda sessão nova, leia (nesta ordem):

1. `Cerebro_Obsidian/⚡ CONTEXT.md` (estado global)
2. `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/00 - Home.md`
3. `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/_AI/Contexto para Claude.md`
4. `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/06 - Regras/Regras Absolutas.md`
5. `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/_Dashboard/🧠 Cérebro Central.md`

---

## As 7 Regras Absolutas (resumo — detalhe no vault)

1. **Git primeiro, deploy depois** — `git push origin main` → Railway auto. NUNCA `railway up`
2. **Testar com curl + token real** antes de declarar pronto
3. **Um agente por arquivo**
4. **URL ML:** `api.mercadolibre.com` (libre, não livre)
5. **`authStore.setAuth()` chama `setStoredToken()`** (Zustand ↔ localStorage)
6. **`alembic current`** antes de assumir migration aplicada
7. **KPI com `COUNT(DISTINCT listing_id)`** — nunca COUNT(snapshot.id)

Detalhe: `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/06 - Regras/Regras Absolutas.md`

---

## Stack rápido

Backend FastAPI + PostgreSQL + Redis + Celery | Frontend React 18 + TS + Vite | Deploy Railway auto.

URLs:
- Backend: https://msmpro-production.up.railway.app
- Frontend: https://msmprofrontend-production.up.railway.app
- Login teste: maikeo@msmrp.com / Msm@2026

---

## Onde escrever ao terminar tarefa

| Ação | Onde |
|------|------|
| Sprint fechada | `07 - Sprints/Sprint X.md` + `_Dashboard/📋 Sprint Tracker.md` |
| Bug corrigido | `08 - Bugs e Fixes/` + `_Dashboard/🐛 Bug Tracker.md` |
| Decisão arquitetural | `14 - ADR/ARCH-XXX.md` + `_Dashboard/🏗️ ADR Log.md` |
| Nova feature | `12 - Ideias/` com status approved |
| Módulo novo | `05 - Módulos/` usando template |
| Migration nova | `03 - Arquitetura/Migrations.md` |

Paths relativos a `Cerebro_Obsidian/05 - Projetos Tech/MSM_Pro/`.

---

## Auto-Learning (READ-ONLY)

`_auto_learning/` em `MSM_Imports_Mercado_Livre/` rodando. Consultar antes de mudança grande:
- `python _auto_learning/loop_runner.py get-context`
- `python _auto_learning/loop_runner.py status`

NUNCA modificar arquivos fora de `_auto_learning/`.

---

## Comandos críticos

```bash
python obsidian_brain.py --full-sync       # sync completo
python obsidian_brain.py --update-metrics  # métricas (hook após git commit)
python obsidian_brain.py --daily-note      # daily note
```

---

## Agentes Claude (subagents)

- `/dev` — implementa features
- `/qa` — revisa e testa
- `/insights` — pesquisa mercado / sugere
- `/ml-api` — valida endpoints ML antes de implementar
- Usar **3 simultâneos no máximo**

---

## Regras de execução do Plano Definitivo (Fable 5, 2026-07-09)

> Plano completo: `docs/handoff/PLANO_DEFINITIVO_MSM_PRO.md` (161 etapas para estabilizar os dados —
> "um fato, um dono", ingestão provada, catálogo completo). Contexto: `docs/handoff/HANDOFF_*.md` +
> `docs/handoff/BRIEFING_FABLE5.md`. Ao executar QUALQUER etapa, seguir estas 9 regras:

1. **1 etapa = 1 commit pequeno.** Mensagem: `fix|feat|test|refactor: [E##] descrição`.
2. **Vermelho = reverter.** Teste quebrou sem intenção → reverter, NUNCA "ajustar o teste p/ passar".
   Mudou número de propósito → atualizar golden master no MESMO commit, com justificativa.
3. **Nada é pronto sem prova.** Cada etapa tem seção *Prova* — executar e mostrar a saída. Número tem
   que bater com o painel do ML.
4. **Antes de todo commit:** `cd backend && python -m pytest tests/test_metrics_characterization.py tests/test_metrics_parity.py -q`. O pre-commit já bloqueia (instale com `bash scripts/install_hooks.sh`).
5. **Deploy = `git push origin main`** (Railway auto). NUNCA `railway up`. Após deploy: `/health` 200.
6. **Endpoint ML novo/duvidoso → MCP oficial (`mercadolibre-official`) ANTES de codar.** Só a sessão
   principal autentica no MCP — nunca delegar validação ML a subagente.
7. **Ao terminar cada FASE:** atualizar o vault (Plano Mestre + Bugs + ADR) e reportar ao Maikeo.
8. **Escopo travado:** sem poda, sem feature nova (fora do plano), sem reescrita. Remoção só com OK do Maikeo.
9. **Travou >2 tentativas:** parar, registrar o bloqueio, perguntar ao Maikeo. Não inventar.

Gate de paridade contra o ML real: `TOKEN="<jwt>" scripts/check_parity.sh`.

---

## REGRA FINAL

Se você está aqui sem ter lido o vault, **PARE**. Volte e leia. Sem cérebro, você quebra coisa.

Para detalhes completos do projeto (570+ linhas que estavam aqui), ver `CLAUDE_backup_2026-05-25.md` ou — preferido — o vault.
