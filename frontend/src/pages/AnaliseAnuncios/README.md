# Página: Análise de Anúncios

## Visão Geral
Página de análise completa de anúncios do Mercado Livre com tabela interativa (20 colunas), filtros avançados e indicadores visuais de performance.

## Arquivos
- `index.tsx` — Componente principal (718 linhas)

## Features

### 1. Tabela Interativa
- **20 colunas** de análise completa
- **Ordenação**: Clique em qualquer header para ordenar (toggle asc/desc)
- **Busca**: Filtro em tempo real por título ou MLB ID
- **Responsivo**: Scroll horizontal em mobile/tablet

### 2. Filtros & Busca
```
Search box → filtra por:
  • titulo (case-insensitive)
  • mlb_id (case-insensitive)

Ordenação → clique em header para:
  • Primeiro clique: ordenar desc
  • Segundo clique: ordenar asc
  • Suporta todos os campos numerados
```

### 3. Indicadores Visuais
| Métrica | Verde | Amarelo | Vermelho |
|---------|-------|---------|----------|
| Conversão | >5% | 2-5% | <2% |
| ROAS | >3x | 1-3x | <1x |
| Estoque | ≥30 un | 10-29 un | <10 un |
| Quality Score | ≥80 | 60-79 | <60 |

### 4. Cards de Resumo (topo)
- **Anúncios**: Total de itens listados
- **Vendas 7d**: Unidades vendidas últimos 7 dias
- **Estoque**: Total de unidades em estoque
- **Conv. 7d**: Média de conversão dos últimos 7 dias

### 5. Linha de Totais
Agregação de:
- Visitas (hoje + ontem)
- Vendas (hoje + ontem + anteontem + 7d)
- Estoque (soma)
- Conversão média (7d)

### 6. Estados UI
- **Loading**: Skeleton com mensagem "Carregando..."
- **Erro**: Toast com mensagem de reconexão
- **Vazio**: Ícone + mensagem "Nenhum anúncio encontrado"
- **Com Dados**: Tabela completa com linhas hover

## Colunas (em ordem)

| # | Nome | Campo | Formato | Observações |
|----|------|-------|---------|------------|
| 1 | Anúncio | thumb+titulo | img 40x40 + texto | Truncated a 40 chars |
| 2 | MLB | mlb_id | badge monospace | Clicável? Não (somente read) |
| 3 | Tipo | tipo | badge colorido | full=roxo, premium=azul, classico=cinza |
| 4 | Preço | preco | R$ formatado | Desconto em verde se existe original_price |
| 5 | Vis. Hoje | visitas_hoje | número | Inteiro, alinhado direita |
| 6 | Vis. Ontem | visitas_ontem | número | Inteiro, alinhado direita |
| 7 | Conv. 7d | conversao_7d | X.X% | Cores: verde/amarelo/vermelho |
| 8 | Conv. 15d | conversao_15d | X.X% | Cores: verde/amarelo/vermelho |
| 9 | Conv. 30d | conversao_30d | X.X% | Cores: verde/amarelo/vermelho |
| 10 | Vend. Hoje | vendas_hoje | número | Texto verde, alinhado direita |
| 11 | Vend. Ontem | vendas_ontem | número | Inteiro, alinhado direita |
| 12 | Vend. Ant. | vendas_anteontem | número | Inteiro, alinhado direita |
| 13 | Vend. 7d | vendas_7d | número | Texto azul, alinhado direita |
| 14 | Estoque | estoque | número | Cores: vermelho(<10)/amarelo(<30)/normal |
| 15 | ROAS 7d | roas_7d | X.XXx | "N/D" se null, cores |
| 16 | ROAS 15d | roas_15d | X.XXx | "N/D" se null, cores |
| 17 | ROAS 30d | roas_30d | X.XXx | "N/D" se null, cores |
| 18 | Score | quality_score | badge | 0-100, cores: verde/amarelo/vermelho |
| 19 | Link | permalink | botão | ExternalLink icon, abre em nova aba |

## Integração com Backend

### Endpoint Esperado
```
GET /api/v1/analysis/listings
Authorization: Bearer {token}
```

### Response Format
```json
{
  "total": 16,
  "anuncios": [
    {
      "mlb_id": "MLB1234567890",
      "titulo": "Kit 10 Peças...",
      "descricao": null,
      "tipo": "fulfillment|classico|premium|full",
      "preco": 139.90,
      "preco_original": 189.90,
      "visitas_hoje": 45,
      "visitas_ontem": 62,
      "conversao_7d": 3.2,
      "conversao_15d": 2.8,
      "conversao_30d": 2.5,
      "vendas_hoje": 2,
      "vendas_ontem": 3,
      "vendas_anteontem": 1,
      "vendas_7d": 15,
      "estoque": 120,
      "roas_7d": 2.5,
      "roas_15d": 2.3,
      "roas_30d": 2.1,
      "thumbnail": "https://...",
      "permalink": "https://...",
      "quality_score": 75
    }
  ]
}
```

## Service Layer

### analysisService.ts
```typescript
export interface AnuncioAnalise {
  mlb_id: string;
  titulo: string;
  // ... 21 mais campos
}

export interface AnalysisResponse {
  total: number;
  anuncios: AnuncioAnalise[];
}

analysisService.getListingsAnalysis(): Promise<AnalysisResponse>
```

## Hooks & State Management
- `useQuery` (TanStack Query) — fetch data com cache automático
- `useState` — busca, ordenação, direção
- `useMemo` — filtro, ordenação, totais (otimizado)

## Styling
- Tailwind CSS com `cn()` utility
- Responsivo com `overflow-x-auto` para tabelas largas
- Dark mode via theme sistema existente

## Performance
- **Query Cache**: 5 min padrão (TanStack Query)
- **Filtro Client-side**: O(n) onde n = anúncios
- **Ordenação Client-side**: O(n log n)
- **Totais**: Calculados com useMemo (otimizado)

## Próximas Features (Sugestões)
- [ ] Exportar tabela para CSV/Excel
- [ ] Adicionar filtros por tipo ou faixa de preço
- [ ] Coluna de "Ação recomendada" (IA)
- [ ] Comparação com concorrentes lado a lado
- [ ] Simulador "E se eu mudar o preço para X?"
- [ ] Salvar filtros como "views" personalizadas

## Rota
- Path: `/analise-anuncios`
- Protegido: Sim (via ProtectedRoute)
- Layout: Sim (com sidebar)
- Menu: "Analise" com ícone BarChart3

## Testes Manuais
1. Acessar `/analise-anuncios`
2. Verificar se tabela carrega
3. Clicar em headers para ordenar
4. Digitar no search box
5. Verificar cores dos indicadores
6. Clicar em link ML (deve abrir em nova aba)

## Commit
- Hash: 9cb2492
- Mensagem: "feat: add Analise de Anuncios page with advanced filtering and sorting"
- Autores: Claude Opus 4.6 + usuário

## Deploy
- Branch: main (auto-deploy Railway)
- Frontend URL: https://msmprofrontend-production.up.railway.app
- Acessível em: https://msmprofrontend-production.up.railway.app/analise-anuncios
