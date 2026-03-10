---
description: Fluxo guiado para cadastrar um novo SKU e vincular anúncios MLB
allowed-tools: [Read, Bash]
---

# Novo Anúncio — MSM_Pro

Guie o usuário passo a passo para cadastrar um novo produto (SKU) e vincular seus anúncios do Mercado Livre.

## Fluxo

### Passo 1 — Dados do SKU (produto interno)
Pergunte ao usuário:
- **SKU** — código interno do produto (ex: FONE-BT-001)
- **Nome** — nome do produto
- **Custo** — custo unitário em R$ (ex: 45.90)
- **Unidade** — unidade de medida (un, kg, cx) — padrão: un
- **Observações** — notas internas opcionais

### Passo 2 — Anúncios MLB
Pergunte:
- **Conta ML** — qual conta ML está vinculada (listar as existentes se o banco estiver acessível)
- **MLB IDs** — um ou mais IDs dos anúncios (ex: MLB-3456789012)
  - Informe que pode colar múltiplos separados por vírgula

### Passo 3 — Confirmar e gerar
Exiba um resumo para confirmação:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NOVO PRODUTO — CONFIRMAR CADASTRO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SKU:    [valor]
  Nome:   [valor]
  Custo:  R$ [valor]
  Anúncios vinculados:
    - [MLB-ID-1]
    - [MLB-ID-2]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Confirma? (s/n)
```

### Passo 4 — Instrução de cadastro
Após confirmação, informe ao usuário:
- Se o backend estiver rodando, acesse: `http://localhost:8000/api/v1/produtos/`
- Ou exiba o comando curl equivalente para cadastro via API
- Lembre que após cadastrar, o próximo sync do Celery coletará os dados dos MLBs automaticamente

## Validações
- SKU não pode ter espaços (substituir por `-`)
- Custo deve ser > 0
- MLB IDs devem começar com `MLB`
