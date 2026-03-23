# Financeiro Module - Três Novas Features

Documento de implementação das 3 features adicionadas ao módulo Financeiro do MSM_Pro em 2026-03-23.

## Features Implementadas

### 1. DRE Gerencial Simplificado (Income Statement)

**Endpoint:** `GET /api/v1/financeiro/dre?period=30d`

**Descrição:**
Retorna DRE (Demonstração de Resultado do Exercício) Gerencial Simplificado com a estrutura completa de receita e despesas, automaticamente comparada com o período anterior.

**Estrutura do DRE:**
```
Receita Bruta
  (-) Taxas ML
  (-) Frete
  (-) Cancelamentos/Devoluções
= Receita Líquida
  (-) CMV (Custo dos Produtos Vendidos)
= Lucro Bruto
  (-) Impostos Estimados
= Lucro Operacional Estimado
```

**Parâmetros:**
- `period` (optional, default: "30d") - Períodos suportados: 7d, 15d, 30d, 60d, 90d

**Response Schema (DREOut):**
```json
{
  "periodo": "30d",
  "data_inicio": "2026-02-23",
  "data_fim": "2026-03-22",
  "receita_bruta": 15000.00,
  "taxa_ml": 2400.00,
  "frete": 800.00,
  "cancelamentos_devolvidos": 200.00,
  "receita_liquida": 11600.00,
  "cmv_total": 5000.00,
  "lucro_bruto": 6600.00,
  "impostos_estimados": 1095.00,
  "lucro_operacional": 5505.00,
  "margem_bruta_pct": 44.00,
  "margem_liquida_pct": 36.70,
  "variacao_receita_pct": 12.50,
  "variacao_lucro_pct": 18.30
}
```

**Como usar:**

```bash
# Obter DRE dos últimos 30 dias
curl -X GET "https://msmpro-production.up.railway.app/api/v1/financeiro/dre?period=30d" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Obter DRE dos últimos 60 dias
curl -X GET "https://msmpro-production.up.railway.app/api/v1/financeiro/dre?period=60d" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Implementação:**
- Função `get_dre()` em `backend/app/financeiro/service.py`
- Usa dados do resumo financeiro existente
- Calcula impostos baseado em `tax_config` do usuário
- Período sempre comparado com período anterior de mesma duração
- Suporta análise de 7, 15, 30, 60, 90 dias

---

### 2. Configuração de Impostos (Simples Nacional)

**Endpoints:**
- `GET /api/v1/financeiro/tax-config` - Obter configuração
- `PUT /api/v1/financeiro/tax-config` - Criar/Atualizar configuração

**Descrição:**
Permite que o usuário configure seu regime tributário (Simples Nacional, Lucro Presumido, Lucro Real) para que o DRE calcule automaticamente os impostos estimados.

**Modelo (TaxConfig):**
- Uma configuração por usuário (unique constraint)
- Campos:
  - `regime`: simples_nacional | lucro_presumido | lucro_real
  - `faixa_anual`: Faixa de faturamento anual em R$
  - `aliquota_efetiva`: Taxa percentual em decimal (ex: 0.073 = 7.3%)

**Tabela de Referência - Simples Nacional Anexo I (Comércio):**

| Faixa de Faturamento | Alíquota |
|--|--|
| Até R$180.000 | 4% |
| R$180.001 - R$360.000 | 7.3% |
| R$360.001 - R$720.000 | 9.5% |
| R$720.001 - R$1.800.000 | 10.7% |
| R$1.800.001 - R$3.600.000 | 14.3% |
| R$3.600.001 - R$4.800.000 | 19% |

**GET Response Schema (TaxConfigOut):**
```json
{
  "regime": "simples_nacional",
  "faixa_anual": 360000.00,
  "aliquota_efetiva": 0.073
}
```

**PUT Request Schema (TaxConfigIn):**
```json
{
  "regime": "simples_nacional",
  "faixa_anual": 360000.00,
  "aliquota_efetiva": 0.073
}
```

**Como usar:**

```bash
# Obter configuração de impostos
curl -X GET "https://msmpro-production.up.railway.app/api/v1/financeiro/tax-config" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Configurar Simples Nacional (faixa R$180k-360k = 7.3%)
curl -X PUT "https://msmpro-production.up.railway.app/api/v1/financeiro/tax-config" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "regime": "simples_nacional",
    "faixa_anual": 360000,
    "aliquota_efetiva": 0.073
  }'
```

**Implementação:**
- Modelo `TaxConfig` em `backend/app/financeiro/models.py`
- Migration 0020: cria tabela `tax_configs`
- Funções `get_tax_config()` e `set_tax_config()` em service
- DRE automaticamente aplica alíquota configurada
- Se nenhuma config, retorna `None` no GET

---

### 3. Rentabilidade por SKU (Product Profitability)

**Endpoint:** `GET /api/v1/financeiro/rentabilidade-sku?period=30d`

**Descrição:**
Agrupa rentabilidade por SKU (Produto) permitindo análise de qual produto é mais lucrativo e identificar oportunidades de otimização.

**Métricas por SKU:**
- Receita total (receita líquida de taxas e frete)
- Custo total (custo unitário × quantidade vendida)
- Margem total e percentual
- Número de listings vinculados ao SKU
- Número de vendas totais
- Melhor e pior listing por margem
- Destaque em vermelho para SKUs com margem < 10%

**Response Schema (RentabilidadeSKUOut):**
```json
{
  "periodo": "30d",
  "data_inicio": "2026-02-23",
  "data_fim": "2026-03-22",
  "total_skus": 5,
  "receita_total": 15000.00,
  "margem_total": 5000.00,
  "items": [
    {
      "product_id": "550e8400-e29b-41d4-a716-446655440000",
      "sku": "SKU001",
      "nome": "Produto Premium",
      "receita_total": 8000.00,
      "custo_total": 2000.00,
      "margem_total": 6000.00,
      "margem_pct": 75.00,
      "num_listings": 2,
      "num_vendas": 40,
      "melhor_listing_mlb": "MLB-123456789",
      "pior_listing_mlb": "MLB-987654321"
    },
    {
      "product_id": "660e8400-e29b-41d4-a716-446655440001",
      "sku": "SKU002",
      "nome": "Produto Econômico",
      "receita_total": 4000.00,
      "custo_total": 3500.00,
      "margem_total": 500.00,
      "margem_pct": 12.50,
      "num_listings": 1,
      "num_vendas": 20,
      "melhor_listing_mlb": "MLB-111111111",
      "pior_listing_mlb": "MLB-111111111"
    },
    {
      "product_id": "770e8400-e29b-41d4-a716-446655440002",
      "sku": "SKU003",
      "nome": "Produto com Risco",
      "receita_total": 3000.00,
      "custo_total": 3200.00,
      "margem_total": -200.00,
      "margem_pct": -6.67,
      "num_listings": 1,
      "num_vendas": 10,
      "melhor_listing_mlb": "MLB-222222222",
      "pior_listing_mlb": "MLB-222222222"
    }
  ]
}
```

**Como usar:**

```bash
# Obter rentabilidade por SKU (últimos 30 dias)
curl -X GET "https://msmpro-production.up.railway.app/api/v1/financeiro/rentabilidade-sku?period=30d" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Obter rentabilidade por SKU (últimos 60 dias)
curl -X GET "https://msmpro-production.up.railway.app/api/v1/financeiro/rentabilidade-sku?period=60d" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Interpretação dos Dados:**

1. **SKUs Altamente Rentáveis** (margem > 50%)
   - Aumentar investimento em estoque
   - Considerar mais listings para esses produtos

2. **SKUs Moderadamente Rentáveis** (20% - 50%)
   - Estáveis, monitorar concorrência

3. **SKUs Pouco Rentáveis** (10% - 20%)
   - Revisar custos
   - Considerar aumento de preço

4. **SKUs Não Rentáveis** (margem < 10%)
   - **ALERTA**: Revisar urgentemente
   - Reduzir estoque
   - Renegociar preços com fornecedor
   - Considerar descontinuar

5. **SKUs com Margem Negativa**
   - **CRÍTICO**: Produto está gerando prejuízo
   - Investigar causa (preço muito baixo, custo muito alto)
   - Ação imediata necessária

**Implementação:**
- Função `get_rentabilidade_por_sku()` em `backend/app/financeiro/service.py`
- Agrupa por `product_id` (SKU)
- Apenas SKUs com listings vinculados
- Considera todas as taxas ML reais e frete
- Calcula best/worst listing comparando margens
- Ordenado por receita descrescente
- Suporta mesmos períodos que DRE: 7d, 15d, 30d, 60d, 90d

---

## Arquivos Modificados/Criados

### Backend

**Criados:**
- `backend/app/financeiro/models.py` - Modelo TaxConfig
- `backend/migrations/versions/0020_create_tax_config.py` - Migration para tabela tax_configs

**Modificados:**
- `backend/app/financeiro/schemas.py` - 6 novos schemas (DREOut, TaxConfigOut/In, RentabilidadeSKU*)
- `backend/app/financeiro/service.py` - 3 novas funções (get_dre, get_tax_config, set_tax_config, get_rentabilidade_por_sku)
- `backend/app/financeiro/router.py` - 3 novos endpoints (/dre, /tax-config GET/PUT, /rentabilidade-sku)
- `backend/app/main.py` - Adiciona import de app.financeiro.models

### Frontend (A Implementar)

Recomenda-se criar os seguintes componentes:

1. **Aba/Página DRE**
   - Waterfall chart visual
   - Tabela com linhas do DRE
   - Comparação período anterior

2. **Seção Configuração de Impostos**
   - Form para selecionar regime tributário
   - Dropdown com faixas de Simples Nacional
   - Mostrar alíquota automática

3. **Aba Rentabilidade por SKU**
   - Tabela com SKUs
   - Expandir para ver listings filhos
   - Destaque vermelho para margem < 10%
   - Filtros por margem mínima

---

## Detalhes Técnicos

### Período de Análise

Todos os endpoints suportam períodos: `7d`, `15d`, `30d`, `60d`, `90d`

- `data_fim` = ontem (snapshot de hoje pode estar incompleto)
- `data_inicio` = data_fim - N dias
- Período anterior sempre tem mesma duração
- Exemplo: período=30d (últimos 30 dias) vs 30 dias anteriores

### Deduplicação de Snapshots

Usa subquery para pegar apenas o snapshot mais recente por listing por dia:
- Evita contar snapshot duplicado quando há múltiplas syncs
- Usa `latest-per-day` subquery pattern
- Garante contagem única por dia

### Cálculo de Receita

```sql
revenue_expr = COALESCE(
  ListingSnapshot.revenue,
  ListingSnapshot.price * ListingSnapshot.sales_today
)
```

Fallback para `price * sales_today` quando revenue é NULL.

### Cálculo de Taxas ML

- Taxa real de `ListingSnapshot.sale_fee_pct` (quando disponível)
- Fallback para tabela fixa ML_FEES por `listing_type`
- Se desconhecido, usa 16% como default

### Tipos de Dados

- Valores monetários: `Decimal(12, 2)` com `ROUND_HALF_UP`
- Percentuais: `Decimal(8, 6)` no banco, `Decimal(0.01)` em response
- Contagens: `int`

---

## Testes Locais

### Setup de Teste

```bash
# 1. Aplicar migration localmente
cd backend
alembic upgrade 0020

# 2. Criar um usuário de teste (se necessário)
# Usar credenciais: maikeo@msmrp.com / Msm@2026

# 3. Criar alguns SKUs e listings para teste
# Via endpoint POST /api/v1/produtos/ e POST /api/v1/listings/
```

### Casos de Teste

```bash
# 1. DRE - 30 dias
curl -X GET "http://localhost:8000/api/v1/financeiro/dre?period=30d" \
  -H "Authorization: Bearer $TOKEN"

# 2. Configurar imposto
curl -X PUT "http://localhost:8000/api/v1/financeiro/tax-config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "regime": "simples_nacional",
    "faixa_anual": 360000,
    "aliquota_efetiva": 0.073
  }'

# 3. Obter tax config
curl -X GET "http://localhost:8000/api/v1/financeiro/tax-config" \
  -H "Authorization: Bearer $TOKEN"

# 4. Rentabilidade por SKU
curl -X GET "http://localhost:8000/api/v1/financeiro/rentabilidade-sku?period=30d" \
  -H "Authorization: Bearer $TOKEN"
```

### Validações

- [ ] DRE: receita_bruta >= receita_liquida
- [ ] DRE: lucro_operacional + impostos + cmv + taxas + frete = receita_bruta (se sem cancelamentos)
- [ ] DRE: variação_receita_pct é null quando período anterior tem vendas_brutas = 0
- [ ] TaxConfig: apenas uma config por usuário (PUT atualiza existente)
- [ ] TaxConfig: GET retorna None se não configurado
- [ ] Rentabilidade: num_listings = COUNT(DISTINCT mlb_id) por SKU
- [ ] Rentabilidade: margem_total = receita_total - custo_total
- [ ] Rentabilidade: margem_pct = margem_total / receita_total * 100

---

## Roadmap Frontend

### Sprint Recomendada

1. **Dashboard Tab - DRE**
   - Waterfall chart com shadcn/ui ou Recharts
   - Table com linhas do DRE
   - Period selector (7d, 15d, 30d, 60d, 90d)
   - Comparison badge (↑ X% vs período anterior)

2. **Settings Page - Tax Config**
   - Form com regime dropdown
   - Faixa anual input (NumberInput)
   - Alíquota display automática
   - Save button

3. **Financeiro Tab - SKU Profitability**
   - Table com SKUs
   - Sortable columns (receita, margem, margin%, num_listings)
   - Expandable rows para listings filhos
   - Red highlight para margem < 10%
   - Filter por margem mínima

---

## Notas de Implementação

1. **TaxConfig é ONE-TO-ONE com User**
   - Uso de `UniqueConstraint("user_id")`
   - GET retorna None se não existe
   - PUT sempre faz upsert (create or update)

2. **DRE usa dados existentes**
   - Não há nova tabela de transações
   - Calcula a partir de snapshots existentes
   - Reaproveitamento de `get_financeiro_resumo()`

3. **SKU profitability considera custos**
   - Apenas SKUs com `product_id` não-null (vinculados)
   - SKUs sem listings não aparecem no resultado
   - Custo = `product.cost * unidades_vendidas`

4. **Período sempre comparado**
   - Automático, não há toggle
   - Períodos anteriores sempre têm mesma duração
   - Útil para trend analysis

---

## Integração com Outros Módulos

- **Vendas**: usa `ListingSnapshot` para base de dados
- **Produtos**: busca custo de `Product.cost` para SKU profitability
- **Alertas**: não há alertas automáticos, apenas análise

---

Implementado em 2026-03-23 por Claude Opus 4.6
