# Análise Detalhada: Explorador de Categorias e Mudanças no Buscador
## Nubimetrics Matrix (NOB Matrix)

**Data da Análise**: 2026-03-18
**Fontes**: 3 vídeos do canal Nubimetrics
**Objetivo**: Inteligência competitiva - Features de descoberta de oportunidades

---

## 1. EXPLORADOR DE CATEGORIAS (How to Use - EdSY51tKfUE)

### 1.1 Nome da Feature
**Explorador de Categorias** (Category Explorer / NOB Matrix)

### 1.2 Descrição Completa - Step by Step

O Explorador de Categorias é uma ferramenta de descoberta de produtos e análise de mercado baseada em banco de dados de categorias do Mercado Livre. A ferramenta permite identificar oportunidades de negócio filtrando e analisando métricas de desempenho por categoria.

#### Fluxo Principal de Uso:

**PASSO 1: Acessar a Ferramenta**
- Menu principal: "Exploradores"
- Selecionar "Explorador de Categorias"
- A interface exibe uma lista de todas as categorias folhas (leaf categories) do Mercado Livre

**PASSO 2: Entender a Estrutura de Dados**
- Banco de dados organizado em lista de categorias
- Cada categoria inclui métricas e índices específicos
- Dados basicamente: médias mensais dos últimos 12 meses
- Indicadores classificados de 1 a 10
- Métricas diferenciadas por categoria (L1 específica) vs. mercado geral

**PASSO 3: Personalizar Colunas**
- Clicar no botão "Colunas"
- Interface de seleção de métricas aparece
- Opções: selecionar TODAS as métricas ou APENAS algumas
- Possibilidade de organizar (reordenar) as colunas selecionadas
- A ordem das colunas pode ser customizada para facilitar leitura

**PASSO 4: Aplicar Filtros**
- Dois modos de filtragem:

  **A) Modo 1 - Filtros Pré-determinados (Preset Filters)**
  - Localizam-se à direita da tela
  - Exemplos de filtros disponíveis:
    - "Alto Crescimento" (vendas em unidades crescimento >= 100, vendedores >= 5)
    - "Baixo Nível de Catálogo"
    - "Baixa Concorrência"
  - Para vendedores iniciantes: filtro específico com critérios benignos
  - Para vendedores avançados: filtros mais agressivos

  **B) Modo 2 - Filtros Personalizados**
  - Clicar em "Filtros" para abrir painel de customização
  - Adicionar múltiplos critérios:
    - Critério 1: Métrica X >= / <= valor Y
    - Critério 2: Métrica Z contém / não contém valor W
    - Aplicação sequencial e combinada (AND logic)
  - Exemplos de filtros custom:
    - Crescimento em unidades >= 85%
    - Unidades de vendas de mercado = X
    - Marca contém "palavra-chave"
    - Unidades vendidas no período > valor
    - Crescimento em unidades no período > 100

**PASSO 5: Analisar Resultados**
- Tabela filtrável com todas as categorias que atendem critérios
- Clicar em "Ver Mais Detalhes" em uma categoria
- Detalhes expandidos mostram contexto da categoria
- Análise comparativa entre a categoria específica (L1) vs. mercado geral

**PASSO 6: Exportação Implícita**
- Dados podem ser copiados/exportados para análise externa
- Não é explicitamente mencionado, mas sugerido pelo contexto

### 1.3 Termos e Vocabulário

| Termo | Significado | Contexto |
|-------|------------|---------|
| **NOB Matrix** | Nome da ferramenta | Nubimetrics Matrix - plataforma analytics |
| **Explorador de Categorias** | Feature principal | Discovers new product opportunities |
| **Categoria Folha (Leaf Category)** | Categorias mais específicas | Menor nível hierárquico no ML |
| **L1** | Categoria vertical de nível 1 | Primeira hierarquia categórica (ex: Eletrônicos) |
| **Índices** | Métricas normalizadas em escala 1-10 | Indicadores de desempenho relativo |
| **Crescimento de Unidades** | Incremento em vendas (qty) | Métrica crucial de oportunidade |
| **Catálogo** | Volume de anúncios/listings | Quantidade de produtos na categoria |
| **Concorrência** | Número/intensidade de vendedores | Métrica de competitividade |
| **Snapshot Mensal** | Foto de dados em períodos de 30 dias | Histórico rolling de 12 meses |
| **Filtro Preset** | Combinação pré-configurada de critérios | Templates para usuários iniciantes/avançados |
| **Filtro Personalizado** | Critério customizado by user | Flexibilidade máxima de análise |
| **Coluna** | Métrica exibida em uma coluna da tabela | Selecionável via button "Colunas" |
| **Mercado Geral** | Benchmark contra TODAS as categorias ML | Referência vs. L1 específica |
| **Rendimento** | Performance relativa em escala 1-10 | Nível 1 = baixo, nível 10 = excelente |

### 1.4 Métricas/KPIs Mencionados

#### Métricas Principais de Oportunidade:

| Métrica | Tipo | Descrição | Granularidade | Período |
|---------|------|-----------|---------------|---------|
| **Unidades de Vendas (Quantidade)** | Contagem | Volume em número de produtos vendidos | Por categoria, por período | Rolling 12 meses |
| **Crescimento de Unidades** | % Crescimento | Taxa de mudança do volume | % YoY ou período a período | Comparativa |
| **Vendedores Ativos** | Contagem | Número de vendedores na categoria | Total | Snapshot |
| **Visitas** | Contagem | Traffic/visualizações de anúncios | Estimada | Por período |
| **Conversão** | % | Taxa de conversão (vendas/visitas) | Percentual | Estimada |
| **Faturamento** | Moeda (R$) | Receita total da categoria | Total monetário | Rolling 12 meses |
| **Nível de Catálogo** | Contagem | Quantidade de produtos (anúncios) | Total | Snapshot |
| **Concorrência (Intensidade)** | Score 1-10 | Avaliação de competitividade | Índice normalizado | Snapshot |
| **Crescimento de Faturamento** | % | Taxa de mudança da receita | Percentual | Comparativa |
| **Estoque Disponível** | Contagem | Quantidade total em estoque na categoria | Agregada | Snapshot |

#### Escala de Índices (1-10):
- **Nível 1**: Baixo rendimento, espaço para melhoria
- **Níveis 2-9**: Progresso gradual
- **Nível 10**: Alto rendimento, categoria se destaca

### 1.5 Fluxo do Usuário - Interação Detalhada

```
[Usuário entra no Explorador]
         ↓
[Visualiza lista de categorias com índices 1-10]
         ↓
   [2 caminhos]
         ↓
   A) Usar Filtros Preset          B) Personalizar Filtros + Colunas
         ↓                                    ↓
[Clica em "Alto Crescimento"   [Clica em "Colunas"]
 (ou Iniciante/Avançado)]          ↓
         ↓                    [Seleciona/desseleciona métricas]
[Sistema aplica critérios]         ↓
         ↓                    [Reorganiza ordem de colunas]
[Mostra categorias filtradas]      ↓
         ↓                    [Clica em "Filtros"]
[Usuário identifica categoria]     ↓
         ↓                    [Adiciona múltiplos critérios]
   [Clica em categoria]            ↓
         ↓                    [Combina AND logic]
[Ver Mais Detalhes]                ↓
         ↓                    [Aplica filtro]
[Análise comparativa:               ↓
 L1 vs. Mercado Geral]        [Visualiza resultados filtrados]
         ↓                          ↓
[Usuário avalia oportunidade] [Clica em categoria de interesse]
         ↓                          ↓
[Decide exportar/agir]        [Ver Mais Detalhes]
                                   ↓
                          [Análise aprofundada]
```

### 1.6 Dados Necessários / Data Sources

#### Origem dos Dados:
1. **API Mercado Livre**: Endpoint `/categories/` para lista hierárquica
2. **Histórico Interno de Transações**: 12 meses rolling de vendas/visitas
3. **Banco de Dados de Produtos**: Catalogo atualizado diariamente
4. **Analytics Pipeline**: Cálculo de índices 1-10 normalizado

#### Estrutura de Dados Esperada:
```json
{
  "category": {
    "id": "MLB1234567890",
    "name": "Eletrônicos > Smartphones > iPhone",
    "level": 3,
    "L1_name": "Eletrônicos",
    "metrics": {
      "units_sold_12m": 15234,
      "units_growth": 45.2,
      "revenue_12m": 45670000.00,
      "revenue_growth": 38.5,
      "active_sellers": 234,
      "listings_count": 1856,
      "conversion_rate": 2.34,
      "visits_12m": 650000,
      "competition_index": 8.5,
      "catalog_level": 7.2,
      "opportunity_score": 6.8
    },
    "benchmarks": {
      "market_units_sold": 245670,
      "market_growth": 12.3,
      "market_sellers": 5234,
      "market_conversion": 1.8
    }
  }
}
```

### 1.7 Endpoints ML API / Arquitetura de Dados

#### Endpoints Necessários (extraídos do contexto):

| Endpoint | Método | Propósito | Nota |
|----------|--------|----------|------|
| `/categories` | GET | Listar categorias ML | Inclui hierarquia L1/L2/L3 |
| `/categories/{category_id}/sales_analytics` | GET | Dados de vendas por categoria | Presumido, interno Nub |
| `/categories/{category_id}/sellers` | GET | Listar vendedores ativos | Dados de competição |
| `/items/search?category={cat_id}` | GET | Listar produtos (listings) na categoria | Contagem de catalogo |
| `/marketplace/analytics/visits` | GET | Visitas por categoria | Dados de tráfego |

#### Presunção de Arquitetura Nubimetrics:
```
[ML API]
   ↓ (webhooks/batch)
[Data Lake - Raw Layer]
   ↓ (ETL pipeline)
[Analytics DB - Metrics Layer]
   ↓ (cálculo de índices 1-10)
[NOB Matrix Frontend]
```

### 1.8 UI/Telas Descritas

#### Tela Principal - Explorador de Categorias:

```
┌─────────────────────────────────────────────────────────────┐
│ NUBIMETRICS MATRIX - EXPLORADOR DE CATEGORIAS              │
├─────────────────────────────────────────────────────────────┤
│ [Filtros Preset ▼]  [Colunas ▼]  [Filtros Custom ▼]       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Categoria               Crescim. Vendas Catalogo Compet.  │
│ ─────────────────────────────────────────────────────────  │
│ Eletrônicos > Celular    8.5      234k    7.2      8.5    │
│ └ → [Ver Detalhes +]                                      │
│                                                             │
│ Moda > Vestuário         6.2      156k    5.8      6.1    │
│ └ → [Ver Detalhes +]                                      │
│                                                             │
│ Casa > Móveis            4.3      89k     4.1      5.2    │
│ └ → [Ver Detalhes +]                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Tela de Detalhes - Análise Comparativa (L1 vs. Mercado):

```
┌─────────────────────────────────────────────────────────────┐
│ VER MAIS DETALHES - Eletrônicos > Celular                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ MÉTRICAS CATEGORIA ESPECÍFICA (L1)                         │
│ ─────────────────────────────────────────────────────────  │
│ Unidades Vendidas (12m): 234,567 unidades                │
│ Crescimento de Unidades: 45.2%                             │
│ Faturamento (12m): R$ 45.670.000                           │
│ Vendedores Ativos: 234                                     │
│ Índice de Competição: 8.5/10                               │
│                                                             │
│ COMPARATIVA COM MERCADO GERAL                             │
│ ─────────────────────────────────────────────────────────  │
│ Crescimento Mercado: 12.3%    | Categoria: 45.2%         │
│ Vendedores Mercado: 5234      | Categoria: 234            │
│ Conversão Mercado: 1.8%       | Categoria: 2.34%          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Painel de Seleção de Colunas:

```
┌────────────────────────────┐
│ SELEÇÃO DE COLUNAS        │
├────────────────────────────┤
│ ☑ Unidades de Vendas      │
│ ☑ Crescimento             │
│ ☑ Faturamento             │
│ ☑ Vendedores              │
│ ☐ Visitas                 │
│ ☑ Índice Competição       │
│ ☐ Estoque                 │
│                            │
│ [↑ ↓] Reordenar colunas   │
│                            │
│ [Aplicar] [Cancelar]       │
└────────────────────────────┘
```

### 1.9 Filtros Disponíveis

#### Filtros Pré-determinados (Preset):

| Nome | Critérios | Target User | Propósito |
|------|-----------|-------------|----------|
| **Alto Crescimento** | Crescimento >= 100% + Vendedores >= 5 | Iniciante | Identificar categorias em expansão |
| **Baixo Catálogo** | Num. Listings < Median | Iniciante | Menos competição inicial |
| **Baixa Concorrência** | Competição Score < 5/10 | Iniciante | Entrada fácil no mercado |
| **Crescimento Moderado** | Crescimento 30-100% | Intermediário | Oportunidades balanceadas |
| **Alto Potencial** | Crescimento > 100% + Conversão > 3% | Avançado | Máxima oportunidade |
| **Nicho Premium** | Faturamento alto + Catalogo baixo | Avançado | Mercado especializado |

#### Filtros Personalizáveis (Custom):

| Operador | Métrica | Exemplo | Lógica |
|----------|---------|---------|--------|
| **>=** | Crescimento de Unidades | `>= 85%` | Mínimo threshold |
| **<=** | Número de Vendedores | `<= 100` | Máximo de competidores |
| **=** | Unidades de Vendas Mercado | `= 500000` | Exatidão |
| **contains** | Marca/Nome | `contém "Nike"` | Filtragem textual |
| **não contém** | Categoria | `não contém "usado"` | Exclusão |
| **>** | Faturamento | `> R$ 10 Milhões` | Range superior |
| **<** | Catálogo (listings) | `< 5000` | Range inferior |

#### Combinação de Filtros (AND Logic):
```
Filtro 1: Crescimento >= 100%
  AND
Filtro 2: Vendedores >= 5
  AND
Filtro 3: Marca contém "Eletrônico"
  AND
Filtro 4: Catálogo < 10000
```

### 1.10 Regras de Negócio

#### Regra 1: Hierarquia de Categorias
- Dados são organizados por categoria folha (leaf level)
- Cada categoria possui identificação em hierarquia L1, L2, L3
- Análises separam categoria específica vs. benchmarks de mercado

#### Regra 2: Períodos de Análise
- Dados históricos: últimos 12 meses sempre (rolling window)
- Métricas agregadas em snapshots mensais
- Crescimento calculado como: (Mês Atual - Mês Anterior) / Mês Anterior

#### Regra 3: Normalização de Índices
- Todas as métricas são normalizadas em escala 1-10
- Nível 1 = baixo rendimento (espaço para melhoria)
- Nível 10 = alto rendimento (categoria destaca-se)
- Cálculo: `(valor - min) / (max - min) * 10`

#### Regra 4: Visibilidade de Dados
- Valores nominais (absolutos) não aparecem na listagem inicial
- Apenas índices 1-10 são exibidos na tabela principal
- "Ver Mais Detalhes" revela valores nominais em R$ e quantidade

#### Regra 5: Segmentação por Perfil
- **Iniciante**: Filtros pré-determinados benignos, colunas essenciais
- **Avançado**: Acesso a todos os filtros e métricas, análise customizada

#### Regra 6: Comparativa Automática
- Cada categoria pode ser comparada contra L1 (vertical) ou Mercado Geral
- Sistema calcula diferenciais (delta) automaticamente
- Indicador visual (ex: "95% da métrica alcançada")

---

## 2. EXPLORADOR DE CATEGORIAS - OVERVIEW (xqQRFpzur0Q)

### 2.1 Nome da Feature
**Explorador de Categorias - Overview** (Introduction/Getting Started Guide)

### 2.2 Descrição Completa

O vídeo de overview é uma introdução executiva ao Explorador de Categorias, voltada para vendedores que buscam identificar as melhores oportunidades de produtos para seu negócio.

#### Propósito Principal:
Permitir que vendedores (iniciantes e experientes) encontrem oportunidades adaptadas às suas necessidades e experiência, focando em produtos com maior potencial de rentabilidade.

#### Estrutura Conceitual:

O Explorador de Categorias funciona como um **banco de dados normalizado** que:
1. Organiza informações de categorias em listas estruturadas
2. Inclui métricas e índices específicos por categoria
3. Mostra médias mensais dos últimos 12 meses
4. Classifica indicadores de 1 a 10
5. Reflete métricas relevantes tanto para categoria específica (L1) quanto para mercado em geral

### 2.3 Termos e Vocabulário (Específico do Overview)

| Termo | Significado |
|-------|------------|
| **Oportunidade de Produto** | Categoria com potencial de crescimento baseado em análise de dados |
| **Perfil do Vendedor** | Experiência (iniciante, intermediário, avançado) e estilo de venda |
| **Potencial de Rentabilidade** | Capacidade de geração de lucro em uma categoria |
| **Estratégia** | Conjunto de ações para expandir negócio no mercado ML |
| **Expansão** | Crescimento para novas categorias complementares |
| **Foco em Potencial** | Priorizar categorias com maior chance de sucesso |

### 2.4 Fluxo de Uso - Simplificado

```
1. Vendedor acessa Explorador de Categorias
2. Sistema identifica perfil (iniciante/experiente)
3. Sistema apresenta categorias com índices 1-10
4. Vendedor personaliza busca (colunas, filtros)
5. Vendedor identifica categorias de interesse
6. Vendedor ajusta estratégia com base em oportunidades
7. Vendedor expande negócio para nova categoria
```

### 2.5 Objetivos Alcançáveis com a Feature

- [x] Identificar melhores oportunidades de produtos
- [x] Descobrir categorias adequadas ao perfil e experiência
- [x] Comparar categorias por métricas relevantes
- [x] Focar em produtos com maior potencial
- [x] Ajustar estratégia de vendas
- [x] Expandir negócio para novas categorias
- [x] Tomar decisões data-driven

### 2.6 Diferencial vs. Competitors

A feature permite **segmentação automática por perfil**:
- **Iniciantes**: Filtros pre-configurados, menos opções, menos risco
- **Experientes**: Acesso total a métricas, filtros customizáveis, análise profunda

---

## 3. MUDANÇAS NO BUSCADOR (2zaB1O5DyDw)

### 3.1 Nome da Feature
**Mudanças no Buscador** (Search Feature Updates / Ads Explorer Evolution)

### 3.2 Descrição Completa - O que Mudou

#### Mudança Principal Anunciada:
**Remoção de dados históricos de unidades e faturamento da tela de search principal**

Mercado Livre removeu recentemente a disponibilidade de **unidades vendidas históricas** e **dados de faturamento históricos** da tela principal de search/buscador.

#### Importante:
- Esta remoção é **APENAS da tela de buscador**
- Os dados **ainda existem na ferramenta** Nubimetrics
- Necessário navegar para outra tela para acessá-los
- Suporte criou um guide de workaround

### 3.3 Mudança Detalhada

#### O que Saiu (Do Buscador):
- Dados de unidades vendidas (históricos)
- Dados de faturamento (históricos)
- Visualização direta na tela de search

#### Por quê:
- Mercado Livre (oficial) retirou esses dados
- Decisão estratégica do marketplace

#### Dados Ainda Disponíveis em Outra Tela:
- Explorador de Anúncios (Ads Explorer)
- Pesquisa expandida por palavra-chave
- Análise de concorrência

### 3.4 Solução / Workaround Recomendado

#### Passo 1: Navegar para Explorador de Anúncios
```
Menu Principal
    ↓
Exploradores
    ↓
Explorador de Anúncios ← (Nova tela)
```

#### Passo 2: Usar Pesquisa Expandida
- **Recomendação**: Sempre usar "Pesquisa Expandida"
- **Motivo**: Traz todos os produtos relacionados à palavra-chave
- **Resultado**: Anúncios com vendas referentes ao período analisado

#### Passo 3: Acessar Dados Históricos
Na tela Explorador de Anúncios, você encontra:
- [x] Vendas em faturamento (históricas)
- [x] Unidades vendidas (históricas)
- [x] Quantidade de dias publicados
- [x] Possibilidade calcular média de vendas diárias

#### Passo 4: Análise de Média Diária
Com os dados históricos disponíveis:
```
Média de Vendas Diárias = Vendas Totais / Dias Publicados
Exemplo: R$ 50.000 / 30 dias = R$ 1.667 por dia
```

### 3.5 Análise de Concorrência - Funcionalidade Paralela

#### Recomendação Alternativa: Usar "Concorrência"

Se o objetivo é fazer acompanhamento diário de um produto:

```
Menu
    ↓
Concorrência
    ↓
Anúncios
    ↓
Compare Anúncios
```

#### Funcionalidade "Compare Anúncios":
- Cria **grupo específico** de produtos (seu + concorrentes)
- Faz **acompanhamento diário** automático
- Exibe por dia TODOS os produtos do grupo
- Mostra variações de preço, volume, visitas

#### Drill-down de Detalhes:
Dentro da tela "Compare Anúncios", clicar em um anúncio específico mostra:
- **Preço** (histórico + atual)
- **Volume de Vendas** (em R$ e unidades, diário)
- **Todas as alterações** que o anúncio sofreu recentemente
- **Seguimento** do anúncio (tanto do anúncio quanto do vendedor)

### 3.6 Termos e Vocabulário

| Termo | Significado | Contexto |
|-------|------------|---------|
| **Buscador** | Ferramenta de search na tela "O que se oferece" | Primeira camada de busca |
| **Explorador de Anúncios** | Nova tela de análise detalhada de produtos | Alternative depois remoção ML |
| **Pesquisa Expandida** | Busca que traz produtos relacionados | Mais resultados, mais contexto |
| **Unidades Vendidas (Históricas)** | Quantidade de itens vendidos em período | Dado agora acessível em Ads Explorer |
| **Faturamento Histórico** | Receita total gerada no período | Dado agora acessível em Ads Explorer |
| **Dias Publicados** | Quantos dias o anúncio está online | Métrica de cálculo de média |
| **Média Diária** | Vendas/Faturamento por dia | Métrica calculada pelo usuário |
| **Compare Anúncios** | Feature de comparação de múltiplos produtos | Parte da tela de Concorrência |
| **Grupo Específico** | Segmento de produtos monitorados | Customizável pelo usuário |
| **Acompanhamento Diário** | Monitoramento recorrente de métricas | Automático na tela Compare |
| **Alterações Recentes** | Histórico de mudanças de preço/dados | Rastreamento de dinâmica |

### 3.7 Métricas/KPIs Acessíveis

#### No Explorador de Anúncios:

| Métrica | Tipo | Acessibilidade | Período |
|---------|------|----------------|---------|
| **Vendas em Faturamento** | Moeda (R$) | Históricas | Desde publicação |
| **Unidades Vendidas** | Contagem | Históricas | Desde publicação |
| **Dias Publicados** | Contagem (dias) | Atual | Snapshot |
| **Média Diária (Calculada)** | R$ ou unid./dia | User calc | Período |
| **Preço** | Moeda (R$) | Histórico + atual | Histórico completo |
| **Visitas Estimadas** | Contagem | Implícita | Período |
| **Alterações de Preço** | Histórico | Rastreado | Recente |
| **Posição de Ranking** | Posição | Implícita | Atual |

### 3.8 Fluxo do Usuário - Busca de Dados Históricos

```
[Usuário quer analisar vendas históricas de um produto]
         ↓
[CAMINHO A: Direto no Buscador]
         ↓
[Menu "O que se oferece"] → [Busca "iPhone 13"]
         ↓
[PROBLEMA: Dados de unidades/faturamento NÃO aparecem mais]
         ↓
[SOLUÇÃO: Ir para Explorador de Anúncios]
         ↓
[CAMINHO B: Explorador de Anúncios]
         ↓
[Menu] → [Exploradores] → [Explorador de Anúncios]
         ↓
[Pesquisa Expandida: "iPhone 13"]
         ↓
[Sistema retorna TODOS os produtos relacionados]
         ↓
[Seleciona produto específico]
         ↓
[Acessa: Faturamento Histórico + Unidades Históricos]
         ↓
[Calcula: Média Diária = Total / Dias Publicados]
         ↓
[CAMINHO C: Análise de Concorrência (Alternativa)]
         ↓
[Menu] → [Concorrência] → [Anúncios] → [Compare Anúncios]
         ↓
[Cria Grupo: [Seu Anúncio] + [Concorrentes]]
         ↓
[Acompanhamento Diário Automático]
         ↓
[Clica em anúncio] → [Drill-down de Detalhes]
         ↓
[Analisa: Preço, Volume, Alterações Recentes]
```

### 3.9 Dados Acessíveis - Nova Arquitetura

#### Localização dos Dados:

| Dado | Antes (Buscador) | Agora | Acesso |
|------|------------------|-------|--------|
| Unidades Vendidas | ✓ Visível | ✗ Removido da UI | Explorador de Anúncios |
| Faturamento Histórico | ✓ Visível | ✗ Removido da UI | Explorador de Anúncios |
| Preço Atual | ✓ Visível | ✓ Visível | Buscador ou Ads Explorer |
| Dias Publicados | ✗ N/A | ✓ Novo | Explorador de Anúncios |
| Vendas Diárias (Média) | ✗ N/A | ✓ Calculável | Explorador de Anúncios |
| Análise de Concorrência | ✗ Básica | ✓ Avançada | Concorrência > Compare |

### 3.10 UI/Telas Descritas

#### Tela do Buscador (Antes da Mudança):
```
┌────────────────────────────────────────────┐
│ O QUE SE OFERECE (BUSCADOR)               │
├────────────────────────────────────────────┤
│ [Busca: "iPhone 13"______]                │
├────────────────────────────────────────────┤
│ Produto         Preço    Unidades  Faturamento
│ iPhone 13 Pro   R$ 7.999   234      R$ 1.8M
│ iPhone 13       R$ 6.500   456      R$ 2.9M
│ iPhone 13 Mini  R$ 5.999   123      R$ 738k
│                                          │
│ [Dados de unidades e faturamento        │
│  AGORA NÃO APARECEM AQUI]               │
└────────────────────────────────────────────┘
```

#### Tela do Explorador de Anúncios (Nova):
```
┌────────────────────────────────────────────────────┐
│ EXPLORADOR DE ANÚNCIOS                            │
├────────────────────────────────────────────────────┤
│ [Pesquisa Expandida: "iPhone 13"___] [Filtros ▼] │
├────────────────────────────────────────────────────┤
│ Anúncio              Faturamento  Unidades  Dias  │
│ ─────────────────────────────────────────────────  │
│ [Seu Anúncio 1]      R$ 50.000    23 un.   60 dias
│ └ → [Ver Detalhes] → Preço, Volume Diário, Hist.│
│                                                   │
│ [Concorrente A]      R$ 120.000   45 un.   90 dias
│ └ → [Ver Detalhes] → Alterações, Posição Ranking│
│                                                   │
│ [Concorrente B]      R$ 85.000    38 un.   75 dias
│ └ → [Ver Detalhes]                               │
│                                                   │
└────────────────────────────────────────────────────┘
```

#### Tela "Compare Anúncios" (Concorrência):
```
┌────────────────────────────────────────────────────┐
│ CONCORRÊNCIA > ANÚNCIOS > COMPARE ANÚNCIOS       │
├────────────────────────────────────────────────────┤
│ Seu Grupo: [Iphone 13 - Análise de Preço]        │
│                                                   │
│ DIA     | SEU ANÚNCIO | CONCORRENTE A | CONC. B │
│ ─────────────────────────────────────────────────  │
│ 18/03   │ R$ 6.500   │ R$ 6.450      │ R$ 6.600│
│ 17/03   │ R$ 6.500   │ R$ 6.500      │ R$ 6.700│
│ 16/03   │ R$ 6.499   │ R$ 6.550      │ R$ 6.550│
│                                                   │
│ [Clicar em anúncio → Detalhes Aprofundados]     │
│                                                   │
│ Clique em [Seu Anúncio]                         │
│   ↓                                              │
│ Preço: R$ 6.500                                 │
│ Volume Diário: R$ 2.333 (média)                │
│ Unidades Diárias: 7.67 (média)                 │
│ Alterações Recentes: Preço reduzido em 18/03   │
│ Posição Ranking: #2 entre similares             │
│ Seguimento: [Ativar acompanhamento]             │
│                                                   │
└────────────────────────────────────────────────────┘
```

### 3.11 Filtros e Opções de Busca

#### Explorador de Anúncios - Pesquisa Expandida:

| Opção | Efeito |
|-------|--------|
| **Pesquisa Expandida** | Retorna TODOS os produtos relacionados à palavra-chave (recomendado) |
| **Pesquisa Exata** | Retorna apenas matches exatos (menos resultados) |
| **Por Marca** | Filtra apenas uma marca específica |
| **Por Categoria** | Limita a uma categoria específica |
| **Por Preço Range** | Filtra por faixa de preço |
| **Por Número de Vendas** | Filtra por volume mínimo de vendas |

#### Compare Anúncios - Opções de Análise:

| Opção | Propósito |
|-------|----------|
| **Criar Grupo** | Selecionar múltiplos anúncios para monitorar |
| **Acompanhamento Diário** | Ativa coleta automática de dados por dia |
| **Seguir Anúncio** | Notificações de mudanças de preço/estoque |
| **Seguir Vendedor** | Notificações de todas as ações do seller |
| **Drill-down** | Clicar em anúncio para detalhes aprofundados |
| **Exportar Dados** | Possibilidade de copiar/salvar dados (implícita) |

### 3.12 Regras de Negócio

#### Regra 1: Transparência de Mudança
- Dados de unidades/faturamento **não foram deletados**
- Apenas **removidos da UI principal do buscador**
- Nubimetrics informou o workaround imediatamente

#### Regra 2: Acesso Alternativo Garantido
- Dados acessíveis via Explorador de Anúncios
- Pesquisa Expandida garante resultados completos
- Análise de Concorrência oferece acompanhamento diário

#### Regra 3: Cálculo de Médias
- Usuário pode calcular média diária: Total ÷ Dias
- Exemplo: R$ 50.000 / 30 dias = R$ 1.667/dia
- Sistema fornece "Dias Publicados" para facilitar cálculo

#### Regra 4: Monitoramento Diário
- Compare Anúncios permite acompanhamento automático
- Dados coletados por dia permitem rastreamento de tendências
- Alterações rastreadas e historicizadas

#### Regra 5: Granularidade de Dados
- Dados diários disponíveis para análise
- Possibilidade de calcular médias por períodos (semanal, mensal, etc.)
- Rastreamento de mudanças permite análise de dinâmica

---

## 4. ANÁLISE COMPARATIVA DAS 3 FEATURES

### 4.1 Propósitos Distintos

| Feature | Propósito | Usuário-Alvo | Quando Usar |
|---------|-----------|-------------|-----------|
| **Explorador de Categorias** | Descobrir NOVAS oportunidades de mercado | Vendedor em expansão | Planejamento estratégico |
| **Explorador de Categorias (Overview)** | Educação + introdução à ferramenta | Todos (iniciantes e avançados) | Onboarding |
| **Mudanças no Buscador** | Adaptação a mudanças da API ML + documentação de workaround | Todos (especialmente analistas) | Análise diária de produtos |

### 4.2 Complementaridade

```
[Vendedor Novo]
         ↓
[Lê Overview] → Entende propósito de Explorador
         ↓
[Acessa Explorador de Categorias] → Identifica categorias com potencial
         ↓
[Escolhe categoria alvo] → Ex: "Eletrônicos > Celulares"
         ↓
[Inicia operação nessa categoria]
         ↓
[Precisa analisar concorrentes especificamente]
         ↓
[Usa Explorador de Anúncios + Compare Anúncios]
         ↓
[Acompanha concorrência diariamente]
         ↓
[Ajusta preço/estoque com base em dados]
```

### 4.3 Jornada de Dados

```
NÍVEL 1: Descoberta Macro
[Explorador de Categorias]
         ↓ (Identifica categoria com índice 8.5/10)
         ↓
NÍVEL 2: Análise de Produtos Específicos
[Explorador de Anúncios + Pesquisa Expandida]
         ↓ (Encontra 50 produtos similares)
         ↓
NÍVEL 3: Monitoramento de Concorrência
[Compare Anúncios + Acompanhamento Diário]
         ↓ (Rastreia 5 concorrentes principais)
         ↓
NÍVEL 4: Ação Operacional
[Ajuste de Preço, Estoque, Descrição]
```

---

## 5. IMPLICAÇÕES PARA MSM_PRO DEVELOPMENT

### 5.1 Features para Implementar (Roadmap Sugerido)

#### MVP 1 - Explorador de Categorias (Sprint X)
```python
# Backend
POST /api/v1/categories/explore
  - Listar categorias com índices 1-10
  - Filtros pre-configurados (preset)
  - Filtros customizáveis (custom)
  - Seleção de colunas

# Frontend
/pages/Exploradores/Categorias/
  - Table com categorias
  - Filter sidebar (presets + custom)
  - Column selector modal
  - Detail view (L1 vs. Market)
```

#### MVP 2 - Explorador de Anúncios (Sprint Y)
```python
# Backend
GET /api/v1/ads/search
  - Busca expandida por keyword
  - Retorna lista de anúncios
  - Histórico de vendas + faturamento

GET /api/v1/ads/{id}/history
  - Vendas históricas
  - Faturamento histórico
  - Dias publicados
  - Preço por dia

# Frontend
/pages/Exploradores/Anuncios/
  - Search expandida
  - Tabela de resultados
  - Detail modal (histórico)
```

#### MVP 3 - Compare Anúncios (Sprint Z)
```python
# Backend
POST /api/v1/competition/groups
  - Criar grupo de anúncios
  - Acompanhamento diário

GET /api/v1/competition/groups/{id}/daily
  - Dados por dia
  - Comparação de preços

# Frontend
/pages/Concorrencia/CompareAnuncios/
  - Tabela diária
  - Drill-down detalhes
  - Seguimento on/off
```

### 5.2 Data Model Implications

```python
# Novas tabelas necessárias:

class CategoryMetric(Base):
    __tablename__ = "category_metrics"

    id = Column(UUID, primary_key=True)
    category_id = Column(String)  # ML category ID
    category_name = Column(String)
    l1_category = Column(String)  # Vertical

    # Métricas normalizadas 1-10
    units_sold_index = Column(Integer)  # 1-10
    growth_index = Column(Integer)
    competition_index = Column(Integer)
    catalog_level_index = Column(Integer)

    # Valores absolutos
    units_sold_12m = Column(Integer)
    revenue_12m = Column(Numeric)
    sellers_active = Column(Integer)
    listings_count = Column(Integer)

    # Benchmarks
    market_units_12m = Column(Integer)
    market_revenue_12m = Column(Numeric)

    # Timestamps
    snapshot_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)

class AdHistory(Base):
    __tablename__ = "ad_history"

    id = Column(UUID, primary_key=True)
    mlb_id = Column(String)  # Anúncio ML

    # Histórico por dia
    date = Column(Date)
    daily_revenue = Column(Numeric)
    daily_units = Column(Integer)
    price = Column(Numeric)
    days_published = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

class CompetitionGroup(Base):
    __tablename__ = "competition_groups"

    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"))
    name = Column(String)  # "iPhone 13 - Preço"

    # Anúncios no grupo
    ads = relationship("AdGroupMember")

    # Acompanhamento
    daily_tracking = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AdGroupMember(Base):
    __tablename__ = "ad_group_members"

    id = Column(UUID, primary_key=True)
    group_id = Column(UUID, ForeignKey("competition_groups.id"))
    mlb_id = Column(String)  # Anúncio ML
    is_own = Column(Boolean)  # True se é próprio
    following = Column(Boolean, default=False)
```

### 5.3 API Endpoints Necessários

```python
# Explorador de Categorias
GET /api/v1/categories/explore
  Params:
    - page: int (default: 1)
    - preset_filter: str (alto_crescimento | baixo_catalogo | etc)
    - custom_filters: JSON
    - columns: list[str]
    - sort_by: str

GET /api/v1/categories/{category_id}/details
  Returns:
    - category_metrics
    - l1_benchmarks
    - market_benchmarks

# Explorador de Anúncios
GET /api/v1/ads/search
  Params:
    - q: str (keyword)
    - expanded: bool (default: true)
    - filters: JSON
  Returns:
    - list[ads] com histórico

GET /api/v1/ads/{mlb_id}/history
  Params:
    - date_from: ISO date
    - date_to: ISO date
  Returns:
    - daily_history[]

# Compare Anúncios
POST /api/v1/competition/groups
  Body: { name, ad_ids[] }
  Returns: group_id

GET /api/v1/competition/groups/{group_id}/daily
  Params:
    - date_from, date_to
  Returns:
    - daily_comparison[]
```

### 5.4 Recomendações de Stack

- **Frontend**: React components para tabelas filtráveis + modal details
- **Backend**: FastAPI endpoints + PostgreSQL para históricos
- **Caching**: Redis para category_metrics (snapshot mensal estável)
- **Jobs**: Celery para coleta diária de ad_history
- **Integration**: ML API para sincronização de categorias

---

## 6. CONCLUSÕES E INSIGHTS

### 6.1 Posicionamento Nubimetrics

Nubimetrics (NOB Matrix) é um **data intelligence platform** focado em:
1. **Descoberta de Oportunidades** (Explorador de Categorias)
2. **Análise de Produtos Específicos** (Explorador de Anúncios)
3. **Monitoramento de Concorrência** (Compare Anúncios)

Todas as features trabalham em **sinergia** para uma jornada completa de análise.

### 6.2 Diferenças vs. MSM_Pro Current

| Aspecto | Nubimetrics | MSM_Pro (Atual) |
|---------|------------|-----------------|
| **Scope** | Discovery + Analysis | Tracking + Pricing |
| **Nível Macro** | Categorias inteiras | Anúncios específicos |
| **Nível Micro** | Anúncios específicos | Snapshots diários |
| **Competição** | Nativa na plataforma | Módulo separado (futuro) |
| **Filtros** | Presets + Custom | N/A (não implementado) |

### 6.3 Oportunidades de Diferenciação para MSM_Pro

1. **+ Inteligência Preditiva**: ML model para predizer sucesso de categoria
2. **+ Automação**: Auto-suggest de preço baseado em Compare
3. **+ Integração**: 1-click para adicionar nova categoria descoberta
4. **+ Alertas**: Notificação quando categoria cruza threshold
5. **+ Reportes**: Export automático de oportunidades (semanal)

### 6.4 Priorização para Development

**Curto Prazo (Sprint 2-3)**:
- [ ] Explorador de Categorias (básico)
- [ ] Filtros preset + custom

**Médio Prazo (Sprint 4-5)**:
- [ ] Explorador de Anúncios
- [ ] Histórico de preços por dia

**Longo Prazo (Sprint 6+)**:
- [ ] Compare Anúncios com acompanhamento diário
- [ ] Alertas automáticos
- [ ] Recomendações preditivas

---

## 7. REFERÊNCIAS E FONTES

### Vídeos Analisados:
1. **Explorador_de_Categorias__EdSY51tKfUE.pt.vtt** - Tutorial completo (4k+ words)
2. **Explorador_de_categorias_overview__xqQRFpzur0Q.pt.vtt** - Introdução (1.3k words)
3. **Mudancas_no_buscador__2zaB1O5DyDw.pt.vtt** - Comunicado de mudança (2.3k words)

### Canais Oficiais:
- YouTube: Nubimetrics Channel
- Website: www.nubimetrics.com.br
- Documentação: Integrada à plataforma (chat support)

### Endpoints ML API Referenciados:
- `/categories/` - Hierarquia
- `/items/search/` - Listagem
- `/users/{id}/items_visits/` - Visitas
- `/orders/search/` - Vendas

---

**Análise Concluída**: Document preparado para referência técnica e product development.

**Próximas Ações Recomendadas**:
1. Discussão com product team sobre priorização
2. Spike de investigação em ML API para coleta de category metrics
3. Prototipagem de UI para Explorador de Categorias
4. Integração com arquitetura atual do MSM_Pro

---

*Documento gerado para: MSM_Pro Development Team*
*Classificação: Internal - Product Intelligence*
*Confidencialidade: Informações públicas (vídeos Nubimetrics)*
