# Sparklines Visual Guide

## Layout completo do card de recomendação de preço

```
╔════════════════════════════════════════════════════════════════════════╗
║  [Thumbnail] SKU-123  MLB1234567890                                   ║
║              Produto ABC XYZ                                           ║
║              R$ 50.00 → R$ 55.00 (+10%)                              ║
║                                              [Alta Confiança] [Baixo]║
║────────────────────────────────────────────────────────────────────────║
║  ↑ CONVERSAO: SUBINDO (+3%)                                           ║
║────────────────────────────────────────────────────────────────────────║
║  Tabela de Períodos:                                                   ║
║  ┌─────────────────────────────────────────────────────────────────┐  ║
║  │ Metrica    │ D-6 │ D-5 │ D-4 │ D-3 │ Ant │ Ontem │ 7d │ 15d │║  ║
║  ├─────────────────────────────────────────────────────────────────┤  ║
║  │ Conversao  │2.1% │2.3% │2.1% │2.5% │2.8% │ 3.1% │2.5%│2.3%│[📈]║  ║
║  │ Visitas    │  42 │  48 │  40 │  45 │  52 │   55 │  47│  44│[📈]║  ║
║  │ Vendas     │   1 │   1 │   1 │   1 │   1 │    2 │   1│   1│[📈]║  ║
║  └─────────────────────────────────────────────────────────────────┘  ║
║────────────────────────────────────────────────────────────────────────║
║  SPARKLINES SUMMARY (3 colunas):                                       ║
║                                                                         ║
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    ║
║  │ Conversão (%)    │  │ Visitas          │  │ Vendas           │    ║
║  │                  │  │                  │  │                  │    ║
║  │    ╱╱╱╱╱╱       │  │   ╱╱╱╱╱          │  │     ╱╱╱╱╱╱╱╱    │    ║
║  │   ╱   AZUL     │  │  ╱  VERDE       │  │    ╱  LARANJA  │    ║
║  │  ╱             │  │ ╱               │  │   ╱             │    ║
║  │ ╱──────────────│  │────────────────│  │───────────────│    ║
║  │ 3.1% ontem      │  │ 55 ontem        │  │ 2 ontem      │    ║
║  │ bg-blue-50/40   │  │ bg-green-50/40  │  │ bg-orange-50/40   ║
║  └──────────────────┘  └──────────────────┘  └──────────────────┘    ║
║                                                                         ║
║────────────────────────────────────────────────────────────────────────║
║  Estoque: 145 (15d)    │    Health Score: 75                          ║
║────────────────────────────────────────────────────────────────────────║
║  Concorrência (media): R$ 52.50                                        ║
║────────────────────────────────────────────────────────────────────────║
║  ▸ Análise da IA                                                       ║
║────────────────────────────────────────────────────────────────────────║
║  [✓ Aplicar] [📊 Simular] [✗ Ignorar]                                ║
╚════════════════════════════════════════════════════════════════════════╝
```

## Detalhe dos Sparklines

### 1. Card de Conversão (Azul)

```
┌──────────────────────────────────────┐
│ Conversão (%)                        │  ← label em text-xs font-semibold
│ (fundo: blue-50/40, border: blue-100)│
├──────────────────────────────────────┤
│                                      │
│         ╱╱╱╱╱╱╱╱╱                  │ ← LineChart h-12
│        ╱                            │
│       ╱      (line color: #3b82f6) │
│      ╱       (strokeWidth: 2)       │
│     ╱        (dot: false)           │
│    ╱                                │
│   ╱────────────────────────────────│
│                                      │
│  3.1% ontem                          │  ← valor ultimo (yesterday)
│  (text-xs text-blue-600 font-medium) │
└──────────────────────────────────────┘
```

### 2. Card de Visitas (Verde)

```
┌──────────────────────────────────────┐
│ Visitas                              │
│ (fundo: green-50/40, border: green-100)
├──────────────────────────────────────┤
│                                      │
│     ╱╱╱╱╱        (line color: #22c55e) │
│    ╱    ╲                            │
│   ╱      ╲╲╲╱╱╱                     │
│  ╱            (strokeWidth: 2)       │
│ ╱             (dot: false)           │
│╱                                    │
│────────────────────────────────────│
│                                      │
│  55 ontem                            │
│  (locale pt-BR, text-xs text-green-600)
└──────────────────────────────────────┘
```

### 3. Card de Vendas (Laranja)

```
┌──────────────────────────────────────┐
│ Vendas                               │
│ (fundo: orange-50/40, border: orange-100)
├──────────────────────────────────────┤
│                                      │
│       ╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱╱  │ ← line color: #f97316
│      ╱                              │
│     ╱    (strokeWidth: 2)           │
│    ╱     (dot: false)               │
│   ╱                                 │
│  ╱                                  │
│ ╱────────────────────────────────│
│                                      │
│  2 ontem                             │
│  (text-xs text-orange-600)           │
└──────────────────────────────────────┘
```

## Responsividade

```css
/* Desktop (3 colunas lado a lado) */
grid-cols-3
gap-4 /* 16px entre cada card */

/* Cada card */
rounded-md
p-3 /* padding interno */
border
h-12 /* altura do gráfico *)
```

## Cores exatas

| Métrica    | Cor      | Hex     | Bg Light | Border |
|-----------|----------|---------|----------|--------|
| Conversão | Azul     | #3b82f6 | blue-50/40 | blue-100 |
| Visitas   | Verde    | #22c55e | green-50/40 | green-100 |
| Vendas    | Laranja  | #f97316 | orange-50/40 | orange-100 |

## Comportamento esperado

### Ao carregar a página
1. Sparklines aparecem abaixo da tabela de períodos
2. Cada gráfico renderiza 6 pontos (d6 até yesterday)
3. Se algum período for null, o ponto é plotado como 0
4. Linha suave conecta os pontos
5. Sem animação (carrega instantaneamente)

### Ao pairar o mouse (hover)
- Tooltip padrão do Recharts pode aparecer (opcional)
- Sem interatividade adicional

### Dados em tempo real
- Sparklines usam dados de `rec.periods_data`
- Se periods_data for null, a seção inteira não aparece
- Fallback para cards simples (seção antiga)

## Integração com o fluxo

```
API Backend (/intel/pricing/recommendations)
         ↓
   periods_data (contém d6-d30)
         ↓
Frontend calcula sparklines
         ↓
Renderiza 3 LineCharts lado a lado
```

## Exemplo de dados (periods_data)

```json
{
  "d6": { "conversion": 2.1, "visits": 42, "sales": 1 },
  "d5": { "conversion": 2.3, "visits": 48, "sales": 1 },
  "d4": { "conversion": 2.1, "visits": 40, "sales": 1 },
  "d3": { "conversion": 2.5, "visits": 45, "sales": 1 },
  "day_before": { "conversion": 2.8, "visits": 52, "sales": 1 },
  "yesterday": { "conversion": 3.1, "visits": 55, "sales": 2 },
  "last_7d": { "conversion": 2.5, "visits": 47, "sales": 1 },
  ...
}
```

---

**Arquivo de implementação**: `/frontend/src/pages/PriceSuggestions/index.tsx` (linhas 514-591)
**Status**: ✅ Completo e testado em produção
