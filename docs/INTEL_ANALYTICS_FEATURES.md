# Intel/Analytics — Novas Features (Sprint 2.5)

## Resumo
Implementadas 3 features avançadas de análise no módulo Intel/Analytics do MSM_Pro:
1. Comparação Temporal (MoM) — Período a Período
2. Classificação ABC por Giro de Estoque
3. Análise de Saúde do Estoque

---

## 1. Comparação Temporal (MoM)

### Endpoint
```
GET /api/v1/intel/analytics/comparison?period=30d
```

**Query Parameters:**
- `period`: `7d`, `15d` ou `30d` (default: `30d`)

**Response:**
```json
{
  "items": [
    {
      "mlb_id": "MLB123456789",
      "title": "Produto A",
      "revenue_current": 1500.00,
      "revenue_previous": 1200.00,
      "revenue_delta_pct": 25.00,
      "sales_current": 50,
      "sales_previous": 40,
      "sales_delta_pct": 25.00
    }
  ],
  "period_days": 30,
  "total_revenue_current": 15000.00,
  "total_revenue_previous": 12000.00,
  "total_revenue_delta_pct": 25.00,
  "total_sales_current": 500,
  "total_sales_previous": 400,
  "total_sales_delta_pct": 25.00
}
```

### Lógica
- **Período Atual**: últimos N dias
- **Período Anterior**: N dias antes do período atual
- Compara receita (`revenue`) e vendas (`sales_today`) entre períodos
- Calcula delta percentual para cada anúncio e totais
- Inclui todos os anúncios (mesmo com zero vendas em um dos períodos)

### Frontend
- **Página**: `/intel/comparison`
- **Seletor**: 3 botões (7d, 15d, 30d)
- **KPI Cards**: 4 cards mostrando totais e variações com cores (verde/vermelho)
- **Tabela**: 7 colunas com setas de tendência ↑↓
- **Cores**:
  - Verde: variação positiva
  - Vermelho: variação negativa
  - Cinza: variação zero

### Use Cases
- Acompanhar crescimento MoM
- Identificar anúncios em queda
- Planejar ações corretivas baseadas em dados reais

---

## 2. Classificação ABC

### Endpoint
```
GET /api/v1/intel/analytics/abc?period=30d&metric=revenue
```

**Query Parameters:**
- `period`: `7d`, `15d` ou `30d` (default: `30d`)
- `metric`: `revenue`, `units` ou `margin` (default: `revenue`)

**Response:**
```json
{
  "items": [
    {
      "mlb_id": "MLB123456789",
      "title": "Produto Premium",
      "classification": "A",
      "revenue_30d": 5000.00,
      "revenue_pct": 35.50,
      "cumulative_pct": 35.50,
      "units_sold": 100,
      "current_stock": 50,
      "turnover_rate": 2.0,
      "metric": "revenue"
    }
  ],
  "period_days": 30,
  "metric_used": "revenue",
  "total_revenue": 15000.00,
  "class_a_revenue_pct": 80.00,
  "class_b_revenue_pct": 15.00,
  "class_c_revenue_pct": 5.00
}
```

### Classificação
- **Classe A** (0-80%): Produtos core — foco máximo em disponibilidade e margem
  - São os pilares do negócio
  - Alto turnover rate esperado

- **Classe B** (80-95%): Produtos produtivos — monitorar regularly
  - Complementam a receita
  - Taxa de giro moderada

- **Classe C** (95-100%): Long tail — revisar e considerar descontinuar
  - Baixa contribuição
  - Capital parado (low turnover)

### Métricas
- **revenue** (padrão): Receita total do período
- **units**: Quantidade de unidades vendidas
- **margin**: Estimativa de margem (placeholder: 20% da receita)

### Cálculo de Giro (Turnover Rate)
```
turnover_rate = unidades_vendidas / estoque_atual
```

### Frontend
- **Página**: `/intel/abc`
- **Seletores**:
  - Período: 7d, 15d, 30d
  - Métrica: Receita, Unidades, Margem
- **KPI Cards**: Total receita + % por classe (A, B, C)
- **Tabela**:
  - Badge com cor por classe (verde A, azul B, âmbar C)
  - Giro com ícone ⚠️ se <0.1 (estoque parado)
- **Legenda**: Explicação de capital parado

### Use Cases
- Identificar produtos core a proteger
- Detectar estoque parado (Class C com alto giro negativo)
- Decidir quais produtos promover vs descontinuar
- Planejamento de compra baseado em giro

---

## 3. Análise de Saúde do Estoque

### Endpoint
```
GET /api/v1/intel/analytics/inventory-health?period=30d
```

**Query Parameters:**
- `period`: `7d`, `15d` ou `30d` (default: `30d`)

**Response:**
```json
{
  "items": [
    {
      "mlb_id": "MLB123456789",
      "title": "Produto A",
      "current_stock": 50,
      "avg_daily_sales": 1.67,
      "sell_through_rate": 0.95,
      "days_of_stock": 29.94,
      "health_status": "healthy"
    }
  ],
  "period_days": 30,
  "total_items": 100,
  "healthy_count": 78,
  "overstocked_count": 15,
  "critical_low_count": 7,
  "avg_days_of_stock": 45.23
}
```

### Classificação de Saúde
- **healthy** (30-90 dias): ✓ Equilíbrio ideal
  - 30-90 dias de estoque em mão
  - Reduz risco de falta
  - Evita capital excessivamente parado

- **overstocked** (>90 dias): ⚠️ Capital parado
  - Mais de 90 dias de estoque
  - Considerar promoção ou redução de preço
  - Caixa congelado

- **critical_low** (<7 dias): 🚨 Risco de desabastecimento
  - Menos de 7 dias de estoque
  - Alerta imediato
  - Pode resultar em perda de vendas

### Métricas Calculadas
```
avg_daily_sales = total_sales_period / period_days

sell_through_rate = sales / (sales + stock)
  • Próximo a 100% = alta rotatividade
  • Próximo a 0% = baixa rotatividade

days_of_stock = current_stock / avg_daily_sales
  • Quantos dias o estoque atual dura
```

### Frontend
- **Página**: `/intel/inventory`
- **Seletor**: Período (7d, 15d, 30d)
- **KPI Cards**:
  - Total anúncios
  - Saudáveis (verde com %)
  - Overstockados (amarelo)
  - Críticos (vermelho)
- **Card Destaque**: Média de dias de estoque com interpretação
- **Tabela**:
  - Ordenada por prioridade (crítico → overstocked → healthy)
  - Background colorido por status
  - Dias de estoque com destaque vermelho <7 ou amarelo >90
  - Ícones de status (✓ ⚠️ 🚨)
- **Legendas**: Explicação de cada métrica

### Use Cases
- Evitar desabastecimentos
- Reduzir capital congelado
- Otimizar planejamento de compra
- Comunicar com fornecedores alertas de estoque

---

## Arquivos Criados/Modificados

### Backend
```
backend/app/intel/analytics/
├── schemas.py                    # +66 linhas (3 novas interfaces)
├── router.py                     # +84 linhas (3 novos endpoints)
├── service_comparison.py         # Novo (171 linhas)
├── service_abc.py               # Novo (156 linhas)
└── service_inventory.py          # Novo (129 linhas)
```

### Frontend
```
frontend/src/
├── pages/Intel/index.tsx         # Atualizado: 7 cards (era 4)
├── pages/Intel/Analytics/
│   ├── Comparison.tsx            # Novo (173 linhas)
│   ├── ABC.tsx                   # Novo (191 linhas)
│   └── InventoryHealth.tsx       # Novo (236 linhas)
├── services/intel/
│   └── analyticsService.ts       # Atualizado: +6 funções
└── App.tsx                        # Atualizado: +3 rotas
```

---

## Stack Técnico

### Backend
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL
- **Query**: SQLAlchemy select() com aggregates (func.sum, func.coalesce)
- **Tipos**: Pydantic BaseModel + Literal unions

### Frontend
- **Framework**: React 18 + TypeScript
- **State**: TanStack Query (useQuery)
- **UI**: shadcn/ui (Button, Card, Badge, Skeleton)
- **Ícones**: lucide-react
- **Routing**: React Router v6 (lazy loading com Suspense)

---

## Testes e Validação

### Endpoints Testados
```bash
# Comparação
curl -H "Authorization: Bearer $TOKEN" \
  https://msmpro-production.up.railway.app/api/v1/intel/analytics/comparison?period=30d

# ABC
curl -H "Authorization: Bearer $TOKEN" \
  https://msmpro-production.up.railway.app/api/v1/intel/analytics/abc?period=30d&metric=revenue

# Inventory Health
curl -H "Authorization: Bearer $TOKEN" \
  https://msmpro-production.up.railway.app/api/v1/intel/analytics/inventory-health?period=30d
```

### Dados Esperados
- Endpoints retornam dados vazios se não houver histórico de snapshots
- Sistema de validação de périodos (`7d|15d|30d`)
- Tratamento de divisão por zero (avg_daily_sales, days_of_stock)
- Cálculos em float com arredondamento a 2 casas decimais

---

## Melhorias Futuras

1. **Export CSV/PDF**: Adicionar botão de download dos relatórios
2. **Gráficos**: Charts temporais de dias_de_estoque ao longo do tempo
3. **Alertas Automáticos**: Integração com módulo de alertas para notificar:
   - Estoque crítico (<7 dias)
   - Overstocking (>90 dias)
   - Queda abrupta em MoM (>30%)
4. **Previsão**: ABC com previsão de próximo período baseada em trends
5. **Recomendações IA**: Claude Opus sugerindo ações por produto

---

## Commits

```
c9da261 feat: add temporal comparison, ABC classification, inventory health analytics
d86ae4a feat: add UI for temporal comparison, ABC classification, inventory health pages
```

---

## Acesso

- **Backend API Docs**: https://msmpro-production.up.railway.app/docs
- **Frontend Navigation**: Dashboard → Inteligência de Negócios → [Comparação | ABC | Saúde do Estoque]

