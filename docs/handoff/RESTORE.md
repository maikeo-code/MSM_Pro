# RESTORE — backup/restore do Postgres (Plano Definitivo, Bloco A / E117)

> Ritual de segurança ANTES de cada fase que toca dados/migrations (Fases 4 e 5).
> Faça um backup fresco, guarde-o, e só então mexa nos dados.

## Por que não é `pg_dump`
`pg_dump` não está instalado nesta máquina (sem PostgreSQL client, sem Docker). O
backup usa o **COPY BINÁRIO do próprio Postgres** via `asyncpg` — os mesmos bytes
por tabela que o `pg_dump` produziria, sem conversão de tipos em Python. Cobre 100%
das linhas (verificado por contagem). O schema vem do Alembic (é versionado no git),
então o par "Alembic + dump de dados" reconstrói o banco inteiro.

## Fazer um backup
```bash
cd msm_pro
python scripts/backup_db.py          # usa DATABASE_URL do .env da raiz (produção)
```
Gera `backups/backup_<timestamp>/` com:
- um `<tabela>.bin` por tabela (COPY binário)
- `manifest.json` — contagem de linhas, `alembic_version`, ordem FK-safe de restore

`backups/` é **gitignored** — o dump contém dados de clientes (orders, users) e
NUNCA pode ir para o git.

### Verificar integridade de um backup (contra o banco vivo)
```bash
python scripts/restore_db.py <dir_backup> --verify-only
```
Compara as contagens do manifest com o banco apontado por `DATABASE_URL`. "contagens
idênticas" = backup íntegro.

## Restaurar (em STAGING ou banco descartável)
> ⚠️ O restore TRUNCA as tabelas do alvo antes de carregar. Nunca aponte para
> produção. O script recusa hosts `*.rlwy.net` sem `--force`.

1. **Schema primeiro** — no alvo, subir o schema na MESMA versão do backup
   (`manifest.json → alembic_version`):
   ```bash
   DATABASE_URL=<dsn_do_alvo> alembic upgrade head
   ```
2. **Carregar os dados:**
   ```bash
   DATABASE_URL=<dsn_do_alvo> python scripts/restore_db.py <dir_backup>
   ```
   FKs são desabilitadas durante a carga (`session_replication_role=replica`) e a
   ordem vem do manifest.
3. **Conferir:**
   ```bash
   DATABASE_URL=<dsn_do_alvo> python scripts/restore_db.py <dir_backup> --verify-only
   ```

## Estado atual do teste de restore
- ✅ **Backup + integridade provados** (2026-07-15): 29 tabelas, 27.440 linhas, contagens
  idênticas ao banco vivo. `alembic_version=0034_competitor_prices`.
- ⏳ **Round-trip completo (restore de verdade) pendente:** exige um Postgres alvo
  descartável. Será feito assim que o **staging (E118)** existir — restaurar este dump
  no staging É o teste de restore E o passo de clonar prod→staging do E118, de uma vez.
  Bloqueio atual do E118: `railway login` expirado (rodar `railway login` de novo).

## Regra operacional
Antes de virar a chave da Fase 4 (E52) ou aplicar migration nova (Fase 5):
`python scripts/backup_db.py` → guardar o diretório → só então prosseguir.
