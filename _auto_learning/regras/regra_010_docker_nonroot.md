# Regra #10: Container Docker Non-Root
Fonte: Ciclo 6 — DevOps Audit
Confianca: 99%
Status: ATIVA

## Regra
Dockerfile DEVE ter `USER appuser` (ou `USER node` para frontend).
NUNCA rodar container como root em producao.
