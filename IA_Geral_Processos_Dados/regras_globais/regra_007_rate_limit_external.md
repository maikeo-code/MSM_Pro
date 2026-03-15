# Regra #7: Endpoints de API Paga Devem Ter Rate Limit
Fonte: Ciclo 5 — Consultor sem controle de custo
Confianca: 98%
Status: ATIVA

## Regra
Qualquer endpoint que chama API externa paga DEVE ter:
1. Rate limiting por usuario (slowapi ou Redis)
2. Cache de resultado recente (Redis, TTL 5-10 min)
3. Limite diario de chamadas por usuario
