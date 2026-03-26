# GitHub Actions Workflows — MSM_Pro

## Workflows Disponíveis

### 1. `ci.yml` — Pipeline CI/CD Completo (Recomendado)
**Trigger**: Push/PR em `main` ou `staging`

**Jobs**:
- ✅ Backend Tests (Python 3.12, pytest, cobertura)
- ✅ Frontend Tests & Build (Node 20, vitest, vite, type-check, lint)
- ✅ CI Status Check (bloqueador de merge se falhar)

**Duração**: ~3-5 minutos

**Ideal para**: Garantir qualidade em todo push e PRs

---

### 2. `test.yml` — Backend Tests Only (Legado)
**Trigger**: Push/PR em `main` ou `staging`, apenas mudanças em `backend/`

**Jobs**:
- ✅ Backend Tests (Python 3.12, pytest)

**Duração**: ~1-2 minutos

**Status**: Mantido para backward-compatibility (deprecated em favor de `ci.yml`)

---

## Como Visualizar Resultados

1. Acesse: https://github.com/maikeo-code/MSM_Pro/actions
2. Clique no workflow desejado
3. Selecione a execução (run)
4. Veja logs em tempo real ou artefatos gerados

---

## Qual Workflow Usar?

| Situação | Usar |
|----------|------|
| Desenvolvimento normal (push em main) | `ci.yml` |
| Pull Request | `ci.yml` |
| Staging | `ci.yml` |
| Debugging de testes backend | `test.yml` |

---

## Status Badge (add ao README.md)

```markdown
[![CI/CD](https://github.com/maikeo-code/MSM_Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/maikeo-code/MSM_Pro/actions)
```

Resultado:
[![CI/CD](https://github.com/maikeo-code/MSM_Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/maikeo-code/MSM_Pro/actions)

---

## Próximos Passos

- [ ] Integrar com Codecov para cobertura
- [ ] Adicionar SAST scanning (Bandit, SonarQube)
- [ ] E2E tests com Playwright
- [ ] Auto-deploy em staging após tests
- [ ] Performance benchmarks

Ver: `docs/CI_CD_PIPELINE.md` para detalhes técnicos completos.
