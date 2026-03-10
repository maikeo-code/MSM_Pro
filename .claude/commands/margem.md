---
description: Calcula margem de lucro de um produto (preço - custo - taxas ML - frete)
argument-hint: <preco> <custo> [tipo_anuncio] [frete]
allowed-tools: []
---

# Calculadora de Margem — MSM_Pro

Calcule a margem de lucro com base nos argumentos fornecidos.

## Tabela de taxas ML (atualizada)
- **Clássico**: 11% sobre o preço de venda
- **Premium**: 16% sobre o preço de venda
- **Full (fulfillment)**: 16% + frete grátis incluso (considerar R$15 médio)

## Fórmula
```
taxa_ml     = preço × (% tipo_anuncio / 100)
custo_frete = frete informado ou 0 se Full
lucro_bruto = preço - custo - taxa_ml - custo_frete
margem_%    = (lucro_bruto / preço) × 100
```

## Como usar
Se o usuário informar argumentos, use-os diretamente.
Se não informar, pergunte:
1. Preço de venda (R$)
2. Custo do produto (R$)
3. Tipo do anúncio (Clássico / Premium / Full) — padrão: Clássico
4. Custo de frete (R$) — padrão: 0

## Saída esperada
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CALCULADORA DE MARGEM — MSM_Pro
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Preço de venda:   R$ [valor]
  Custo do produto: R$ [valor]
  Tipo anúncio:     [tipo] ([%]%)
  Taxa ML:          R$ [valor]
  Frete:            R$ [valor]
  ─────────────────────────────
  Lucro bruto:      R$ [valor]
  Margem:           [%]%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Se a margem for negativa, alerte em vermelho e sugira o preço mínimo para 10%, 15% e 20% de margem.
Se a margem for < 10%, avise que está abaixo do recomendado.
