# Regra #11: Express Deve Ter Security Headers
Fonte: Ciclo 6 — DevOps Audit
Confianca: 98%
Status: ATIVA

## Regra
server.js Express DEVE usar:
- `helmet()` para CSP, HSTS, X-Frame-Options
- `compression()` para gzip/brotli
