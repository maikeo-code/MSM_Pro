# PLANO MASTER: Implementacao dos 8 P0
Data: 2026-03-13
Status: APROVADO (consenso 8 agentes, 95% agreement)
Prioridade: P0 — EXECUTAR ANTES DE QUALQUER FEATURE

## Ordem de Execucao (risco crescente)

### BATCH 1 — One-liners (5 min, 0 risco)

**P0-2: _sync_ads_async db.commit()**
- Arquivo: backend/app/jobs/tasks.py (~linha 1155)
- Acao: Adicionar `await db.commit()` antes do return
- Risco: Zero

**P0-6: UTC offset em orders**
- Arquivo: backend/app/jobs/tasks.py (linha 878-879)
- Acao: Mudar offset de `-03:00` para `+00:00` (usar UTC puro)
- Risco: Baixo

### BATCH 2 — Config + Guard (15 min)

**P0-1: JWT startup guard**
- Arquivo: backend/app/core/config.py
- Acao: Adicionar model_validator que crashe se secret_key == default em producao
- Pre-req: Verificar que SECRET_KEY esta setado no Railway

### BATCH 3 — Rate Limiting (30 min)

**P0-3: Rate limit /auth/login**
- Novos: backend/app/core/limiter.py, slowapi em requirements.txt
- Modificar: main.py (middleware), auth/router.py (decorator + Request param)
- Limit: 5/minute

**P0-8: Rate limit /consultor/analisar**
- Modificar: consultor/router.py (decorator + Request param)
- Limit: 3/minute, 10/hour, 50/day

### BATCH 4 — Migration Alert Cooldown (20 min)

**P0-7: Alert deduplication**
- Nova migration: 0014 (cooldown_hours INT DEFAULT 24, last_triggered_at TIMESTAMP)
- Modificar: alertas/models.py, alertas/service.py (cooldown guard)

### BATCH 5 — Migration Snapshot UNIQUE (30 min)

**P0-5: Race condition snapshot**
- PRE-REQ: Rodar dedup SQL no banco primeiro
- Nova migration: 0013 (CREATE UNIQUE INDEX uq_snapshot_listing_day)
- Modificar: tasks.py (trocar SELECT+INSERT por ON CONFLICT DO UPDATE)

### BATCH 6 — Token Encryption (1h)

**P0-4: ML tokens criptografia**
- Novo: backend/app/core/crypto.py (encrypt_token, decrypt_token com Fernet)
- Modificar: core/config.py (token_encryption_key), auth/service.py, tasks.py (6 pontos)
- PRE-REQ: Gerar Fernet key e setar TOKEN_ENCRYPTION_KEY no Railway

## Checklist Pre-Deploy
- [ ] SECRET_KEY verificado no Railway
- [ ] TOKEN_ENCRYPTION_KEY gerado e setado no Railway
- [ ] Dedup SQL rodado no banco (P0-5)
- [ ] slowapi em requirements.txt
- [ ] Migrations 0013 + 0014 testadas localmente
- [ ] Todos endpoints testados com curl apos deploy

## Dependencias pip novas
- slowapi==0.1.9
- cryptography==42.0.8 (pin explicito)

## Arquivos novos
- backend/app/core/limiter.py
- backend/app/core/crypto.py
- backend/migrations/versions/0013_add_snapshot_unique_constraint.py
- backend/migrations/versions/0014_add_alert_cooldown.py

## Tempo estimado total: ~2.5 horas de implementacao
