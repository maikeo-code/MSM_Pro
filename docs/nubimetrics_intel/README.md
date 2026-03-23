# Nubimetrics Intelligence Database

**Última Atualização**: 2026-03-18
**Documentos**: 3 análises de features
**Status**: Completo

---

## Índice de Documentos

### 1. Sumário Executivo
📄 `SUMARIO_FEATURES_09.md`
- Overview rápido das 3 features
- Comparação lado a lado
- Checklist de implementação
- **Tempo de leitura**: 5-10 minutos

### 2. Análise Completa
📄 `analises_brutas/09_explorador_categorias_buscador.md`
- Análise profunda de cada feature
- Termos e vocabulário
- Métricas e KPIs
- Fluxos de usuário
- Regras de negócio
- **Tempo de leitura**: 30-45 minutos

### 3. Especificação Técnica
📄 `analises_brutas/09_SPEC_TECNICA.md`
- Modelos de dados (SQLAlchemy)
- Schemas (Pydantic)
- Endpoints do backend
- Service layer
- Celery tasks
- Migrations Alembic
- **Tempo de leitura**: 20-30 minutos

---

## Features Analisadas

### Feature 1: Explorador de Categorias
**Objetivo**: Descobrir novas oportunidades de categorias com potencial

**Tipo**: Market Intelligence
**Nível**: Macro (categorias inteiras)
**Usuários**: Vendedores em expansão, planejadores estratégicos

**Componentes**:
- Lista de categorias com índices 1-10
- Filtros pré-determinados (presets)
- Filtros customizáveis
- Seleção de colunas
- Detalhes comparativos (L1 vs. Mercado)

**Dados**: 12 meses rolling, atualizado mensalmente
**Métricas**: Crescimento, Vendedores, Catálogo, Competição, Oportunidade

---

### Feature 2: Explorador de Anúncios
**Objetivo**: Analisar produtos específicos com dados históricos detalhados

**Tipo**: Product Analysis
**Nível**: Micro (anúncios específicos)
**Usuários**: Analistas, operacionais diários

**Componentes**:
- Busca expandida por palavra-chave
- Histórico diário de vendas e preço
- Cálculo de média diária
- Dias publicados

**Dados**: Desde publicação até hoje, diário
**Métricas**: Preço, Faturamento, Unidades, Dias Online

**Nota**: Feature criada como workaround para remoção da API ML

---

### Feature 3: Compare Anúncios
**Objetivo**: Monitorar concorrência com acompanhamento diário

**Tipo**: Competitive Intelligence
**Nível**: Micro (grupo de anúncios)
**Usuários**: Pricing managers, analistas de concorrência

**Componentes**:
- Criar grupo de anúncios
- Acompanhamento diário automático
- Comparação por dia
- Drill-down de detalhes
- Rastreamento de alterações

**Dados**: Diário, customizável por período
**Métricas**: Preço, Volume, Posição, Alterações

---

## Quick Reference

### Endpoints a Implementar

```
GET  /api/v1/exploradores/categorias/          (Listar)
GET  /api/v1/exploradores/categorias/{id}      (Detalhe)
GET  /api/v1/exploradores/anuncios/search      (Busca)
GET  /api/v1/exploradores/anuncios/{id}/history (Histórico)
POST /api/v1/concorrencia/grupos/               (Criar)
GET  /api/v1/concorrencia/grupos/{id}/daily     (Comparativa)
```

### Tabelas Principais

- `category_metrics` (índices 1-10 + benchmarks)
- `ad_history` (histórico diário de anúncios)
- `competition_groups` (grupos de monitoramento)
- `group_members` (membros de grupos)

### Celery Tasks

- `sync_category_metrics` → 1º dia/mês @ 02:00 BRT
- `sync_ad_history` → Todo dia @ 06:00 BRT
- `sync_competition_groups` → Todo dia @ 06:15 BRT

### Filtros Principais

**Categorias:**
- Alto Crescimento (>= 100%)
- Baixa Concorrência (<= 5)
- Baixo Catálogo
- Crescimento Moderado
- Alto Potencial

**Anúncios:**
- Busca expandida (recomendado)
- Por marca
- Por categoria
- Por range de preço
- Por volume mínimo

---

## Roadmap de Implementação

### MVP 1: Explorador de Categorias
**Sprint**: 3-4
**Effort**: Médio
**Prioridade**: Alta
**Data Estimada**: Q2 2026

- [ ] DB schema + migrations
- [ ] Sync de category metrics via Celery
- [ ] Backend endpoints (/explore, /details)
- [ ] Frontend pages (lista + detalhes)
- [ ] Filtros (presets + custom)
- [ ] Testes

### MVP 2: Explorador de Anúncios
**Sprint**: 4-5
**Effort**: Grande
**Prioridade**: Alta
**Data Estimada**: Q2 2026

- [ ] DB schema + migrations
- [ ] Sync de ad_history via Celery
- [ ] Backend endpoints (/search, /history)
- [ ] Frontend pages (busca + histórico)
- [ ] Cálculo de médias
- [ ] Testes

### MVP 3: Compare Anúncios
**Sprint**: 5-6
**Effort**: Grande
**Prioridade**: Média
**Data Estimada**: Q3 2026

- [ ] DB schema + migrations
- [ ] Backend endpoints (groups, daily, details)
- [ ] Frontend pages (criar, acompanhar)
- [ ] Drill-down de detalhes
- [ ] Testes

---

## Dados Críticos para Sucesso

### Métricas de Oportunidade (Explorador de Categorias)
1. **Crescimento de Unidades** (0-200%)
2. **Número de Vendedores** (competição)
3. **Volume de Catálogo** (saturação)
4. **Taxa de Conversão** (eficiência)
5. **Faturamento Total** (tamanho do mercado)

### Dados Históricos (Explorador de Anúncios)
1. **Preço Diário** (histórico completo)
2. **Faturamento Diário** (desde publicação)
3. **Unidades Vendidas** (diárias)
4. **Dias Publicados** (idade do anúncio)
5. **Alterações** (rastreamento de mudanças)

### Dados de Concorrência (Compare Anúncios)
1. **Preço** (múltiplos concorrentes, histórico)
2. **Volume de Vendas** (diário)
3. **Posição no Ranking** (posicionamento)
4. **Estoque** (disponibilidade)
5. **Mudanças Recentes** (dinâmica)

---

## Integração com MSM_Pro

### Compatibilidade
- [x] Stack: FastAPI + React (compatível)
- [x] DB: PostgreSQL async (compatível)
- [x] Cache: Redis (compatível)
- [x] Jobs: Celery + Beat (compatível)
- [x] Auth: JWT + OAuth ML (compatível)

### Sinergia
1. **Descoberta** (Explorer) → Identifica categoria
2. **Análise** (Ads Explorer) → Valida viabilidade
3. **Monitoramento** (Compare) → Operacional diário
4. **Pricing** (MSM_Pro atual) → Executa preço

---

## Perguntas Frequentes

### P: Por quê 3 telas separadas?
**R**: Cada uma serve a um propósito diferente:
- Descoberta (macro) → Análise (micro) → Monitoramento (operacional)

### P: Qual é o volume de dados esperado?
**R**:
- ~5.000 categorias
- ~1M de anúncios
- ~100K history records/dia
- Growth: ~3-5% ao mês

### P: Como lidar com remoção da API ML de dados históricos?
**R**: Nubimetrics resolveu via Explorador de Anúncios + Compare Anúncios

### P: Qual é o padrão de acesso esperado?
**R**:
- Pico @ 06:00 BRT (sync diária)
- Uso steady durante expediente (08:00-18:00)
- Cache reduz load significativamente

---

## Próximas Ações

1. **Validação**: Compartilhar com product team
2. **Spike**: Investigar ML API para category metrics
3. **Design**: Prototipar UI das 3 features
4. **Estimativa**: Sprint planning com time
5. **Começar**: MVP 1 (Explorador de Categorias)

---

## Referências

### Documentação Interna
- MSM_Pro CLAUDE.md
- Nubimetrics Transcripts (3 vídeos)
- ML API Reference

### Recursos Externos
- Nubimetrics.com.br
- YouTube: Nubimetrics Channel
- ML API: developers.mercadolivre.com.br

---

**Análise Preparada para**: MSM_Pro Development Team
**Confidencialidade**: Internal - Product Intelligence
**Status**: Pronto para Implementação
