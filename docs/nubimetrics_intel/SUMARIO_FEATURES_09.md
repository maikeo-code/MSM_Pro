# Sumário Executivo - Features 09: Explorador de Categorias e Buscador

**Data**: 2026-03-18
**Documentação Completa**: `/analises_brutas/09_explorador_categorias_buscador.md`

---

## 1. EXPLORADOR DE CATEGORIAS

### O que é?
Ferramenta de descoberta de novas oportunidades de negócio analisando métricas de categorias do Mercado Livre em escala 1-10.

### Objetivo Principal
Permitir que vendedores identifiquem categorias com potencial de crescimento e rentabilidade, adaptadas ao seu perfil (iniciante/avançado).

### Como Funciona
```
1. Visualiza lista de categorias com índices 1-10
2. Seleciona colunas de métricas (botão "Colunas")
3. Aplica filtros (Preset ou Personalizado)
4. Clica em "Ver Detalhes" para análise L1 vs. Mercado
5. Identifica oportunidade e planeja entrada
```

### Métricas Principais
| Métrica | Descrição | Escala |
|---------|-----------|--------|
| Crescimento | Taxa de mudança de vendas | % |
| Vendedores Ativos | Competição | Contagem |
| Unidades Vendidas | Volume | Contagem |
| Faturamento | Receita | R$ |
| Catálogo | Quantidade de anúncios | Contagem |
| Competição | Intensidade de competição | Score 1-10 |

### Filtros Disponíveis
**Presets:**
- Alto Crescimento
- Baixo Catálogo
- Baixa Concorrência
- Crescimento Moderado
- Alto Potencial

**Custom:**
- Crescimento >= X%
- Vendedores <= N
- Faturamento > R$ Y
- Marca contém "Z"

### Resultado
Tabela filtrável com categorias ranqueadas + detalhes expandidos por categoria.

### Para MSM_Pro
- [ ] Implementar Explorador de Categorias no Sprint 3-4
- [ ] Consumir ML API para category metrics
- [ ] Cache em Redis (dados mensais estáveis)

---

## 2. EXPLORADOR DE CATEGORIAS - OVERVIEW

### O que é?
Vídeo educacional / introdução ao Explorador de Categorias.

### Público-Alvo
- Vendedores iniciantes
- Vendedores em expansão
- Qualquer um querendo descobrir novas oportunidades

### Mensagem Principal
"Encontre produtos com maior potencial para seu negócio, adaptados ao seu perfil e experiência."

### Diferenciais
- Segmentação automática por nível (iniciante/avançado)
- Filtros pre-configurados para cada nível
- Interface simplificada para iniciantes
- Acesso total a métricas para avançados

---

## 3. MUDANÇAS NO BUSCADOR

### O que mudou?
Mercado Livre removeu dados históricos de unidades e faturamento da tela de buscador principal.

### Impacto
- Dados de unidades vendidas NÃO aparecem mais no buscador
- Dados de faturamento histórico NÃO aparecem mais no buscador
- **MAS**: Dados ainda existem na ferramenta Nubimetrics

### Solução (Workaround)
```
Buscador Principal
    ↓ (Não tem mais dados históricos)

Usar: Explorador de Anúncios
    ↓
    Menu > Exploradores > Explorador de Anúncios
    ↓
    Pesquisa Expandida: "sua palavra-chave"
    ↓
    Clica no anúncio
    ↓
    Acessa: Faturamento Histórico + Unidades Históricas
```

### Alternativa: Compare Anúncios
```
Menu > Concorrência > Anúncios > Compare Anúncios
    ↓
Cria grupo de anúncios
    ↓
Acompanhamento diário automático
    ↓
Análise de dinâmica (preço, volume, alterações)
```

### Dados Disponíveis Agora

| Dado | Antes | Agora | Local |
|------|-------|-------|-------|
| Unidades Vendidas | ✓ Buscador | Explorador Anúncios |
| Faturamento Histórico | ✓ Buscador | Explorador Anúncios |
| Dias Publicados | ✗ N/A | ✓ | Explorador Anúncios |
| Média Diária (calc) | ✗ N/A | ✓ | User calc |
| Concorrência Detalhada | ✓ Básica | ✓ Avançada | Compare Anúncios |

### Cálculo de Média Diária
```
Média Diária = Faturamento Total / Dias Publicados
Exemplo: R$ 50.000 / 30 dias = R$ 1.667/dia
```

---

## 4. TABELA COMPARATIVA

| Aspecto | Explorador Categorias | Explorador Anúncios | Compare Anúncios |
|---------|---------------------|-------------------|------------------|
| **Nível de Análise** | Macro (categorias) | Micro (produtos) | Micro (competição) |
| **Objetivo** | Descobrir oportunidades | Analisar produto específico | Monitorar concorrência |
| **Públicoalvo** | Planejamento estratégico | Análise tática diária | Pricing & monitoring |
| **Dados** | 12 meses agregado | Histórico completo | Por dia |
| **Filtros** | Presets + Custom | Keyword + filters | Grupo + drill-down |
| **Exportação** | Implícita | Implícita | Implícita |

---

## 5. JORNADA DE USUÁRIO INTEGRADA

```
┌─────────────────────────────────────────────────────────┐
│ NÍVEL 1: Descoberta (Explorador de Categorias)         │
│ → Identifica categoria com score 8.5/10                 │
├─────────────────────────────────────────────────────────┤
│ NÍVEL 2: Análise de Produtos (Explorador Anúncios)     │
│ → Encontra 50 produtos similares na categoria           │
├─────────────────────────────────────────────────────────┤
│ NÍVEL 3: Seleção de Alvo (Pesquisa Expandida)          │
│ → Escolhe 5 principais concorrentes                     │
├─────────────────────────────────────────────────────────┤
│ NÍVEL 4: Monitoramento (Compare Anúncios)              │
│ → Acompanhamento diário de preço e vendas               │
├─────────────────────────────────────────────────────────┤
│ NÍVEL 5: Ação Operacional (Seu Sistema)                │
│ → Ajusta preço, estoque, descrição                      │
└─────────────────────────────────────────────────────────┘
```

---

## 6. TERMINOLOGIA CRÍTICA

### Explorador de Categorias
- **Índice**: Métrica normalizada 1-10 (1 = baixo, 10 = alto)
- **L1**: Categoria vertical (ex: Eletrônicos)
- **Leaf Category**: Categoria folha (mais específica)
- **Filtro Preset**: Template pré-configurado
- **Filtro Custom**: Critério personalizado

### Explorador de Anúncios
- **Pesquisa Expandida**: Retorna TODOS os produtos relacionados (recomendado)
- **MLB**: Anúncio no Mercado Livre
- **Dias Publicados**: Quantos dias o anúncio está online
- **Média Diária**: Total ÷ Dias Publicados

### Compare Anúncios
- **Grupo**: Segmento de anúncios monitorados
- **Acompanhamento Diário**: Coleta automática de dados por dia
- **Drill-down**: Expandir detalhes de um anúncio

---

## 7. IMPLICAÇÕES PARA MSM_PRO

### MVP 1 - Explorador de Categorias
```python
GET /api/v1/categories/explore
  # Listar categorias com índices 1-10
  # Filtros preset + custom
  # Seleção de colunas
```
**Prioridade**: Sprint 3-4
**Data**: Q2 2026
**Effort**: M

### MVP 2 - Explorador de Anúncios
```python
GET /api/v1/ads/search
  # Busca expandida por keyword
  # Histórico de vendas + faturamento

GET /api/v1/ads/{id}/history
  # Vendas por dia
  # Preço por dia
```
**Prioridade**: Sprint 4-5
**Data**: Q2 2026
**Effort**: L

### MVP 3 - Compare Anúncios
```python
POST /api/v1/competition/groups
  # Criar grupo de anúncios
  # Acompanhamento diário

GET /api/v1/competition/groups/{id}/daily
  # Dados por dia
  # Comparação
```
**Prioridade**: Sprint 5-6
**Data**: Q3 2026
**Effort**: L

---

## 8. CHECKLIST DE IMPLEMENTAÇÃO

- [ ] **Spike**: Investigar ML API para category metrics
- [ ] **DB Design**: Tabelas CategoryMetric + AdHistory + CompetitionGroup
- [ ] **Backend**: Endpoints /explore, /ads/search, /competition/groups
- [ ] **Frontend**: Pages Explorador/Categorias, Explorador/Anuncios, Concorrencia/Compare
- [ ] **Cache**: Redis para category metrics (estáveis mensalmente)
- [ ] **Jobs**: Celery task para coleta diária de ad_history
- [ ] **Tests**: Cobertura mínima 80% dos endpoints
- [ ] **Docs**: Update API docs + user guide
- [ ] **Deploy**: Stagingenv antes de produção

---

## 9. REFERÊNCIAS

- Documentação Completa: `/analises_brutas/09_explorador_categorias_buscador.md`
- Vídeos Oficiais Nubimetrics no YouTube
- Nubimetrics Support Chat (integrado na plataforma)

---

*Sumário preparado para MSM_Pro Development Team*
*Confidencialidade: Internal - Product Intelligence*
*Última atualização: 2026-03-18*
