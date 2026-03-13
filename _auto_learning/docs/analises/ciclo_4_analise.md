# Analise do Ciclo 4 — Auth Lifecycle, Migrations, Frontend Bundle
Data: 2026-03-13

## Subagentes Utilizados
- **Security Engineer**: auth lifecycle completo
- **Database Administrator**: migrations e schema
- **Frontend Developer**: bundle, performance, a11y

## Metricas Acumuladas (Ciclos 1-4)
- Perguntas: 20 geradas | 20 respondidas | 20 relevantes
- Sucessos: 9 total
- Falhas: 11 total (todas nao resolvidas)
- Regras: 6 ativas | 0 deprecadas
- Consensos: 1

## Descobertas do Ciclo 4

### Auth Lifecycle (Security Engineer)
| Severidade | Issue |
|-----------|-------|
| CRITICO | ML tokens em plaintext (comentario diz criptografado, codigo nao faz) |
| CRITICO | Sem token blacklist - JWT valido 24h apos logout |
| HIGH | Sem endpoint POST /auth/logout no backend |
| HIGH | Sem endpoint POST /auth/change-password |
| HIGH | OAuth state sem nonce CSRF (confirmado novamente) |
| HIGH | Token duplicado em 2 localStorage keys |
| MEDIUM | ML account delete nao revoga token no ML |
| MEDIUM | Refresh token falho nao marca conta como invalida |

### Database Schema (DBA)
| Prioridade | Issue |
|-----------|-------|
| HIGH | CASCADE em products->listings deveria ser SET NULL |
| HIGH | Sem UNIQUE(user_id,ml_user_id) em ml_accounts |
| HIGH | Sem UNIQUE de snapshot por listing por dia (race condition) |
| MEDIUM | Sem UNIQUE(listing_id,mlb_id) em competitors |
| MEDIUM | nullable mismatch entre migrations e ORM |
| MEDIUM | Sem CHECK em listing_type e status |
| MEDIUM | orders.listing_id NULL nunca reconciliado |
| LOW | sold_quantity nao armazenado em listings |
| LOW | buyer_id falta em orders |

### Frontend (Frontend Developer)
| Prioridade | Issue |
|-----------|-------|
| HIGH | react-query-devtools em dependencies (vai pra prod) |
| HIGH | AnuncioDetalhe.tsx = 1314 linhas God component |
| MEDIUM | 7/9 rotas sem lazy loading |
| MEDIUM | Recharts sem chunk separado (~500KB) |
| MEDIUM | Reputacao bypassa React Query (usa useEffect raw) |
| MEDIUM | Labels sem htmlFor em Concorrencia |
| LOW | noUncheckedIndexedAccess nao habilitado |
| LOW | Heatmap sem keyboard navigation |

## Novas Regras (3)
4. Tokens ML devem ser criptografados no banco
5. FK products->listings deve ser SET NULL
6. react-query-devtools deve estar em devDependencies

## Planos Acumulados
1. plano_health_check_deep.md (P2)
2. plano_fix_ads_sync_commit.md (P0)
3. plano_data_retention.md (P3)
4. plano_security_hardening_p0.md (P0)
