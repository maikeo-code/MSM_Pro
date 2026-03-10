---
description: Mostra status do Celery, última sincronização e saúde geral do MSM_Pro
allowed-tools: [Bash, Read]
---

# Status do Sistema — MSM_Pro

Verifique e exiba o status completo de todos os serviços do MSM_Pro.

## Verificações a realizar

### 1. Docker / Infraestrutura
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "msm|postgres|redis"
```

### 2. PostgreSQL — conexão e dados
```bash
docker exec msm_postgres psql -U msm -d msm_pro -c "
SELECT
  (SELECT COUNT(*) FROM ml_accounts WHERE ativo = true) AS contas_ativas,
  (SELECT COUNT(*) FROM listings WHERE status = 'active') AS anuncios_ativos,
  (SELECT COUNT(*) FROM listing_snapshots WHERE data = CURRENT_DATE) AS snapshots_hoje,
  (SELECT MAX(data) FROM listing_snapshots) AS ultimo_snapshot;
" 2>/dev/null
```

### 3. Celery — workers e tasks
```bash
celery -A backend.app.jobs.celery_app inspect active 2>/dev/null || echo "Celery offline"
celery -A backend.app.jobs.celery_app inspect scheduled 2>/dev/null || true
```

### 4. Última sincronização por conta ML
```bash
docker exec msm_postgres psql -U msm -d msm_pro -c "
SELECT
  a.nickname,
  a.email,
  MAX(ls.created_at) AS ultima_sync
FROM ml_accounts a
LEFT JOIN listings l ON l.account_id = a.id
LEFT JOIN listing_snapshots ls ON ls.listing_id = l.id
GROUP BY a.id, a.nickname, a.email;
" 2>/dev/null
```

## Saída esperada
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STATUS DO SISTEMA — MSM_Pro
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🐳 Docker
     msm_postgres  ✅ Up (porta 5432)
     msm_redis     ✅ Up (porta 6379)
     msm_backend   ✅ Up (porta 8000)

  🗄️  Banco de Dados
     Contas ML ativas:    2
     Anúncios ativos:    47
     Snapshots hoje:     47 / 47

  ⚙️  Celery
     Workers online:      1
     Próximo sync:        23:00

  🔄 Última Sincronização por Conta
     conta1@email.com  →  hoje 14:32
     conta2@email.com  →  hoje 14:35
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Se algum serviço estiver offline, exiba o comando para iniciá-lo.
