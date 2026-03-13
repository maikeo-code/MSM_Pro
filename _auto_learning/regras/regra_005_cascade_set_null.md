# Regra #5: FK Optional Deve Usar SET NULL (Nao CASCADE)
Fonte: Ciclo 4 — DBA Analysis
Confianca: 95%
Status: ATIVA

## Regra
Se um FK e nullable (ex: product_id em listings), o ondelete DEVE ser SET NULL, nao CASCADE.
CASCADE so e correto para FKs NOT NULL onde o filho nao faz sentido sem o pai.

## Caso Concreto
products.id -> listings.product_id: Deletar SKU nao deve deletar anuncios ativos.
