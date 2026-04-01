# Roadmap: Melhorias Futuras no Sistema de OAuth Token

**Data:** 2026-04-01  
**Versão:** 1.0

---

## Resumo Executivo

O sistema de OAuth token refresh está **100% implementado e testado em produção**. Abaixo estão oportunidades de melhoria para aumentar ainda mais a resiliência e observabilidade.

---

## MELHORIAS PRIORITÁRIAS (P0)

### 1. Dashboard de Saúde de Tokens

**Problema:** Usuário não sabe quando seu token expirou ou está prestes a expirar.

**Solução:**
- Criar nova página `/dashboard/tokens` mostrando:
  - Data de expiração por conta
  - Última renovação com sucesso
  - Contagem de falhas de refresh
  - Status "Ativo", "Expirando em X horas", "Expirado"

**Estimativa:** 4-6 horas (backend + frontend)

**Arquivo para criar:**
```
backend/app/auth/router.py → GET /auth/tokens/health
  ├─ Retorna lista de tokens com status
  └─ Campo: id, nickname, status, expires_at, last_refresh_at, failures

frontend/src/pages/Configuracoes/TokenHealth.tsx
  ├─ Tabela com status por conta
  ├─ Cores: ✅ Verde (OK), ⚠️ Amarelo (< 2h), 🔴 Vermelho (expirado)
  └─ Botão "Reconectar" quando status = expirado
```

**Impacto:** Visibilidade total do status de OAuth + ação rápida do usuário

---

### 2. Webhook de Alertas para Token Expirado

**Problema:** Se `token_refresh_failures >= 5`, o usuário fica sem notificação clara.

**Solução:**
- Enviar email quando `needs_reauth = true` é setado
- Incluir link para reconectar OAuth

**Código existente:**
```python
# backend/app/jobs/tasks_tokens.py (linhas 164-175)
await create_notification(...)  # ✅ Já cria notificação in-app
# Adicionar: await send_token_expiration_email(user, account)
```

**Estimativa:** 2-3 horas (integração com SMTP)

**Referência:**
- `backend/app/notifications/service.py` — modelo para notificações
- SMTP configurado em `.env` → `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`

**Impacto:** Usuário recebe alerta por email quando conta desconecta

---

## MELHORIAS SECUNDÁRIAS (P1)

### 3. Histórico de Refresh de Tokens

**Problema:** Não há auditoria de quando/por que tokens foram renovados.

**Solução:**
- Criar tabela `token_refresh_logs` para rastrear cada tentativa
- Registrar: account_id, timestamp, status (sucesso/falha), motivo, worker_id

**Migration necessária:**
```sql
CREATE TABLE token_refresh_logs (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES ml_accounts(id),
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20),  -- 'success', 'failed_400', 'failed_401', 'failed_5xx'
    reason TEXT,
    worker_id VARCHAR(100),  -- Para rastrear qual worker fez refresh
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_token_refresh_logs_account ON token_refresh_logs(account_id, timestamp);
```

**Estimativa:** 3-4 horas (migration + logging + query)

**Benefício:**
- Auditoria completa de renovações
- Debug de problemas intermitentes
- Análise de padrões de falha

---

### 4. Exponential Backoff no Retry de Refresh

**Problema:** Atualmente o retry é fixo (5s, 15s, 25s). Se houver fila pesada, pode falhar.

**Solução:**
- Implementar exponential backoff com jitter:
  ```python
  base_delay = 5  # segundos
  for attempt in range(max_retries):
      delay = min(base_delay * (2 ** attempt) + random(0, 5), 300)  # Cap em 5 min
      await asyncio.sleep(delay)
  ```

**Arquivo:** `backend/app/jobs/tasks_tokens.py` (linhas 110-150)

**Estimativa:** 1-2 horas

**Impacto:** Maior resiliência em momentos de alta carga

---

## MELHORIAS TERCIÁRIAS (P2)

### 5. Redis Persistence para Token State

**Problema:** Se Redis falhar, lock distribuído não funciona (fall-open).

**Solução:**
- Usar Redis Sentinel ou Redis Cluster (já em produção via Railway)
- Configurar AOF (Append-Only File) para persistência
- Considerar PostgreSQL como fallback para lock

**Estimativa:** 2-3 horas (configuration + testing)

**Benefício:** Maior confiabilidade do lock distribuído

---

### 6. Simulador de Expiração de Token

**Problema:** Não há forma fácil de testar comportamento em caso de expiração.

**Solução:**
- Criar endpoint `/admin/simulate-token-expiration?account_id=...`
- Settar `token_expires_at = NOW()` e disparar refresh
- Log de teste diferenciado

**Estimativa:** 1-2 horas

**Código:**
```python
@router.post("/admin/simulate-token-expiration")
async def simulate_token_expiration(account_id: UUID, db: AsyncSession):
    """Apenas para testes — não em produção"""
    account = await db.get(MLAccount, account_id)
    account.token_expires_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Token marcado para expiração imediata"}
```

---

### 7. Observabilidade com Prometheus Metrics

**Problema:** Não há métricas de refresh de token para Prometheus.

**Solução:**
- Adicionar counters:
  ```python
  token_refresh_success = Counter('ml_token_refresh_success_total', 'Token refreshes successful')
  token_refresh_failures = Counter('ml_token_refresh_failures_total', 'Token refresh failures')
  token_refresh_duration = Histogram('ml_token_refresh_duration_seconds', 'Token refresh latency')
  ```

**Estimativa:** 2-3 horas (prometheus library + integration)

**Benefício:** Alertas em Grafana/Datadog sobre falhas de refresh

---

### 8. Circuit Breaker para Refresh Failures

**Problema:** Se ML API está offline, tentamos refresh a cada 30min por 5 falhas.

**Solução:**
- Implementar padrão Circuit Breaker:
  - Estado: CLOSED (OK) → OPEN (falhando muito) → HALF_OPEN (testando)
  - Quando OPEN, skip refresh por 2h (reduz chamadas desnecessárias)
  - Quando HALF_OPEN, tenta 1 vez; se OK → volta CLOSED

**Estimativa:** 4-5 horas (implementação + testes)

**Benefício:** Menos logs de erro, melhor performance em degradação parcial

---

## NÃO PRIORIZAR

### ❌ Múltiplos Refresh Tokens

**Por quê:** Mercado Livre emite apenas 1 refresh_token por autorização. A API não suporta múltiplos.

---

### ❌ Token Rotation (trocar refresh_token a cada uso)

**Por quê:** Mercado Livre não suporta. Refresh_token reutilizável indefinidamente.

---

### ❌ WebSocket para Notificação Real-time de Expiração

**Por quê:** Custo-benefício baixo. Polling a cada 30min é suficiente.

---

## MATRIZ DE PRIORIZAÇÃO

| # | Melhoria | P | Horas | Impacto | Complexidade | Status |
|---|----------|---|-------|---------|-------------|--------|
| 1 | Dashboard de Tokens | P0 | 4-6 | Alto | Média | Backlog |
| 2 | Email de Alerta | P0 | 2-3 | Alto | Baixa | Backlog |
| 3 | Histórico de Refresh | P1 | 3-4 | Médio | Média | Backlog |
| 4 | Exponential Backoff | P1 | 1-2 | Médio | Baixa | Backlog |
| 5 | Redis Persistence | P2 | 2-3 | Médio | Alta | Backlog |
| 6 | Simulador de Expiração | P2 | 1-2 | Baixo | Baixa | Backlog |
| 7 | Prometheus Metrics | P2 | 2-3 | Médio | Baixa | Backlog |
| 8 | Circuit Breaker | P2 | 4-5 | Médio | Alta | Backlog |

---

## RECOMENDAÇÃO PARA PRÓXIMA SPRINT

**Executar P0 + P0:**
1. **Dashboard de Saúde de Tokens** (4-6h)
2. **Email de Alerta** (2-3h)

**Total:** 6-9 horas = 1 dia e meio de desenvolvimento

**ROI:** Visibilidade total + Reatividade do usuário

---

## TESTES FINAIS RECOMENDADOS

Antes de colocar qualquer melhoria em produção:

```bash
# 1. Testar lock distribuído com 10 workers simultâneos
# 2. Simular falha de Redis durante refresh
# 3. Verificar que refresh_token é sempre salvo
# 4. Confirmar que sync não continua se refresh falha
# 5. Validar logs detalhados de cada tentativa
```

---

## REFERÊNCIAS

- RFC 6749 — OAuth 2.0 Authorization Framework
- Mercado Livre OAuth Docs: https://developers.mercadolivre.com.br/pt_br/oauth-documentation
- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html
- Redis Distributed Lock: https://redis.io/docs/manual/patterns/distributed-locks/

