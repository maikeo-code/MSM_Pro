# Plano: Adicionar Constraints Faltantes no Schema
Data: 2026-03-13
Baseado em: Ciclo 4 — DBA Analysis (6 constraints faltantes)
Prioridade: P1

## Problema Identificado
6 constraints criticos faltando no schema que permitem dados inconsistentes:
1. Sem UNIQUE(user_id, ml_user_id) em ml_accounts
2. Sem UNIQUE(listing_id, mlb_id) em competitors
3. Sem UNIQUE por snapshot/listing/dia
4. Sem CHECK em listing_type e status
5. products CASCADE deveria ser SET NULL
6. nullable mismatch entre migrations e ORM

## Solucao Proposta
Criar migration 0013_add_missing_constraints.py:

```python
# 1. UNIQUE em ml_accounts
op.create_unique_constraint('uq_ml_accounts_user_ml', 'ml_accounts', ['user_id', 'ml_user_id'])

# 2. UNIQUE em competitors
op.create_unique_constraint('uq_competitors_listing_mlb', 'competitors', ['listing_id', 'mlb_id'])

# 3. Partial unique index para 1 snapshot/listing/dia
op.execute("CREATE UNIQUE INDEX uq_snapshot_listing_day ON listing_snapshots (listing_id, (captured_at::date))")

# 4. CHECK constraints
op.execute("ALTER TABLE listings ADD CONSTRAINT chk_listing_type CHECK (listing_type IN ('classico', 'premium', 'full'))")
op.execute("ALTER TABLE listings ADD CONSTRAINT chk_status CHECK (status IN ('active', 'paused', 'closed', 'under_review'))")

# 5. Mudar CASCADE para SET NULL
op.drop_constraint('listings_product_id_fkey', 'listings', type_='foreignkey')
op.create_foreign_key('listings_product_id_fkey', 'listings', 'products', ['product_id'], ['id'], ondelete='SET NULL')

# 6. Fix nullable em sync_logs
op.alter_column('sync_logs', 'items_processed', nullable=False, server_default='0')
op.alter_column('sync_logs', 'items_failed', nullable=False, server_default='0')
```

## Arquivos Afetados
- backend/migrations/versions/0013_add_missing_constraints.py (novo)
- backend/app/produtos/models.py (mudar cascade no relationship)

## Riscos
- UNIQUE constraints podem falhar se ja existirem duplicatas no banco
- Mitigacao: rodar SELECT para verificar duplicatas ANTES da migration
- CHECK constraint pode falhar se ML retornar status nao previsto
- Mitigacao: incluir status extras conhecidos do ML

## Metricas de Sucesso
- Migration aplica sem erro
- Tentativa de inserir duplicata retorna IntegrityError
- Deletar produto nao apaga listings

## Status: PENDENTE
