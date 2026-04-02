# Atendimento Module Fixes (2026-04-02)

## Problema identificado
Reclamações, mensagens e devoluções não apareciam corretamente no módulo de Atendimento devido a:

1. **Reclamações com status limitado**: Buscava apenas `status="open"`, perdendo reclamações com outros statuses como "opened", "waiting_for_seller_response"
2. **Duplicações ao buscar múltiplos statuses**: Sem mecanismo de deduplicação
3. **Tratamento frágil de formato de resposta**: Mensagens poderiam vir em diferentes estruturas JSON

## Mudanças implementadas

### 1. Deduplicação de Claims (linhas 247, 303, 330)
**Arquivo**: `backend/app/atendimento/service.py`

Adicionado set de tracking para evitar duplicatas ao buscar múltiplos statuses:
```python
seen_claim_ids: set[str] = set()  # Deduplicação de claims
```

Atualizado `_parse_claims()` para aceitar parâmetro `seen_ids`:
```python
def _parse_claims(
    claims: list[dict],
    claim_type: str,
    account: MLAccount,
    seen_ids: set[str] | None = None,
) -> list[AtendimentoItem]:
```

### 2. Busca de múltiplos statuses para Reclamações (linhas 280-320)
**Arquivo**: `backend/app/atendimento/service.py`

Mudança de:
```python
# ANTES: apenas status="open"
cl_status = status_filter or "open"
cl_data = await client.get_claims(status=cl_status, ...)
```

Para:
```python
# DEPOIS: múltiplos statuses relevantes
claim_statuses_to_search = [status_filter] if status_filter else [
    "open",
    "opened", 
    "waiting_for_seller_response",
]

for cl_status in claim_statuses_to_search:
    # Busca cada status com deduplicação
    parsed_cl = _parse_claims(claims_only, "reclamacao", account, seen_claim_ids)
```

### 3. Tratamento robusto de formato de resposta (linhas 354-357)
**Arquivo**: `backend/app/atendimento/service.py`

Melhorado suporte a diferentes formatos de resposta da API ML:
```python
# A API ML pode retornar em 'results', 'data', ou direto como lista
packs_raw = msg_data.get("results", msg_data.get("data", []))
if isinstance(msg_data, list):
    packs_raw = msg_data
```

### 4. Logs informativos (linhas 307-312, 334-338, 370-374)
Adicionados logs para debug e monitoramento:
- `"Atendimento: carregadas reclamacoes status=X conta=Y total=Z"`
- `"Atendimento: carregadas devolucoes conta=X total=Y"`
- `"Atendimento: carregadas mensagens conta=X total=Y"`

## Impacto esperado

| Item | Antes | Depois |
|------|-------|--------|
| Reclamações visíveis | Apenas "open" | "open", "opened", "waiting_for_seller_response" |
| Duplicatas ao filtrar | Possível | Eliminada via `seen_claim_ids` |
| Tratamento de erros | Frágil | Robusto a diferentes formatos |
| Debug | Logs esparsos | Logs por conta e status |

## Campos afetados

- **ReclamaçõesItem.status**: Agora pode incluir múltiplos valores de status relevantes
- **DeduplicaçãoItem.id**: Garante ID único por item (set tracking)
- **MensagensItem.response_format**: Agnóstico a estrutura JSON (results/data/list)

## Teste recomendado

```bash
# 1. Login e pegar token
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | jq -r '.access_token')

# 2. Buscar atendimentos (reclamações agora devem aparecer)
curl -s https://msmpro-production.up.railway.app/api/v1/atendimento/ \
  -H "Authorization: Bearer $TOKEN" | jq '.by_type'

# 3. Esperado: by_type com contadores populados
# {"perguntas": N, "reclamacoes": M, "mensagens": P, "devolucoes": Q}
```

## Compatibilidade

- Backward compatible: Sem mudanças em schemas ou rotas
- Sem novas migrations necessárias
- Sem dependências externas adicionadas

## Próximos passos

1. Deploy em produção (Railway)
2. Testar endpoint `/api/v1/atendimento/` com múltiplas contas
3. Validar logs no Sentry/CloudWatch
4. Se satisfeito, resolver task #12 como completo
