# Regra #3: Webhook Processing Requer Validacao de Origem
Fonte: Ciclos 1 e 3
Confianca: 95%
Status: ATIVA

## Regra
ANTES de implementar processamento de webhooks ML:
1. Adicionar secret token no query string (configuravel no ML app settings)
2. OU implementar IP allowlist dos servidores ML
3. Tratar payload como UNTRUSTED — usar apenas como trigger para re-fetch via API autenticada

## Quando Aplicar
Quando o TODO em main.py linhas 89-93 for implementado.
