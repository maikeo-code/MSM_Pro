# Regra #2: Logica Duplicada Deve Ser Extraida
Fonte: Ciclo 3 — Code Review
Confianca: 90%
Status: ATIVA

## Regra
Logica que aparece em 2+ lugares DEVE ser extraida para helper.
Prioridades atuais:
- Price extraction (vendas/service.py + tasks.py)
- Listing serialization (3 lugares)
- SKU extraction (2 lugares)
- KPI result builder (2 funcoes)

## Quando Aplicar
Antes de copiar logica entre arquivos. Verificar se ja existe helper.
