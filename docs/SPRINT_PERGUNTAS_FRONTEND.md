# Sprint Frontend — Perguntas e Respostas Master-Detail

## Resumo
Reescrita completa da página de Perguntas com layout master-detail, sugestão IA integrada e modo batch. Frontend 100% tipado, sem erros TypeScript.

## Arquivos Modificados

### 1. frontend/src/services/perguntasService.ts
Reescrito completamente com tipos expandidos:
- QuestionDB — modelo com campos IA (ai_suggestion_text, ai_suggestion_confidence)
- QuestionsListResponse — resposta paginada
- QuestionStats — KPIs (total, unanswered, answered, urgent, avg_response_time_hours)
- AISuggestion — sugestão com { suggestion, confidence, question_type, cached, latency_ms }
- SyncResult — resultado de sincronização

Funções:
- listQuestions(params) — lista com filtros
- getQuestionStats(mlAccountId?) — KPIs
- syncQuestions() — sincroniza do ML
- answerQuestion(..., source, suggestionWasEdited)
- getSuggestion(questionId, regenerate)
- getQuestionsByListing(mlbId)

### 2. frontend/src/pages/Perguntas/index.tsx
Novo layout master-detail (~600 linhas, 0 TypeScript errors)

#### Componentes Inline

**UrgenciaBadge**
- Vermelho: >= 24h (Urgente)
- Amarelo: >= 12h (Atenção)
- Verde: < 12h (Recente)

**ConfidenceBadge**
- high → Verde, medium → Amarelo, low → Laranja

**KpiCard**
- 4 cards: Total Pendentes, Urgentes (+24h), Tempo Médio, Taxa Resposta
- Ícones com bg colorido

**QuestionList (left panel)**
- Input de busca
- Lista scrollável com seleção visual
- Card mostra: buyer + urgência + texto truncado + tempo + MLB ID
- Loading e empty states

**QuestionDetail (right panel)**
- Header: MLB + título + buyer + data
- Pergunta em bloco cinza
- Resposta existente em bloco verde (se respondida)
- Sugestão IA em bloco violet (se existe)
  - Botão "Usar resposta" + "Regenerar"
- Gerar IA (se sem sugestão)
- Textarea: max 2000 caracteres, contador, auto-detect edição
- Botões: Enviar (azul) + Pular (cinza)
- Feedback: sucesso/erro

#### Layout Responsivo
- Mobile: coluna única (lista OU detalhe)
- Desktop: md:grid-cols-3 (left: 1 col, right: 2 cols)

#### Queries e Mutations
- listQuestions — staleTime 60s, invalidada após responder
- getQuestionStats — staleTime 120s, invalidada após sync
- syncMutation — RefreshCw button
- suggestMutation — regenerate: boolean
- answerMutation — source: 'manual' | 'ai', suggestion_was_edited

#### Integração AccountSelector
- Dropdown no header
- Filtra por ml_account_id
- Auto-reset de tab/offset ao mudar

## Features Implementadas

✅ Layout master-detail com seleção visual
✅ KPI cards (4 métricas)
✅ Sugestão IA: gerar + regenerar + usar + confidence badge
✅ Busca em tempo real
✅ Abas: Pendentes / Respondidas
✅ Textarea: max 2000 chars, contador, auto-detect edição
✅ Resposta existente em verde
✅ Sync manual com RefreshCw
✅ AccountSelector integrado
✅ Responsive mobile/desktop
✅ Loading states
✅ Mensagens sucesso/erro
✅ Sem TypeScript errors

## Validação

- ✅ Sem erros TypeScript
- ✅ Imports corretos (AccountSelector como named export)
- ✅ Query invalidation funcionando
- ✅ Responsive layout
- ✅ Edge cases (sem seleção, lista vazia, etc)

## Deploy

Push automático para Railway via `git push origin main`.
Commit: 2f17e10

## Próximas Melhorias

1. Batch Mode UI (checkboxes + "Batch IA" button)
2. Templates de resposta pré-salvos
3. Chat do Consultor IA (drawer)
4. Exportação (CSV/PDF)
5. Webhooks em tempo real (WebSocket)
