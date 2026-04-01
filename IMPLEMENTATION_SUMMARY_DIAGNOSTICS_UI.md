# Melhoria de UI de Saúde de Tokens — Resumo de Implementação

**Data**: 2026-04-01  
**Agente**: Claude Code  
**Status**: Completo

## O que foi feito

### 1. **AccountSelector.tsx** — Indicadores visuais de problemas de token
- Adicionado import de `AlertCircle` do lucide-react
- Adicionado `useQuery` do @tanstack/react-query
- Adicionado import de `tokenDiagnosticsService`
- Implementado hook `useQuery` para buscar diagnósticos de tokens a cada 5 minutos
- Adicionada função helper `accountHasTokenIssue()` para verificar se uma conta tem problemas
- Adicionado contador `problematicAccountsCount` para saber quantas contas têm problemas
- **Melhorias visuais**:
  - Badge vermelho de alerta no botão principal quando há contas com problemas
  - Ponto vermelho no avatar de contas com token expirado/problema
  - Fundo vermelho (bg-red-50/dark:bg-red-950) na linha de contas com problema
  - Ícone AlertCircle ao lado do status badge de contas problemáticas

**Arquivo**: `frontend/src/components/AccountSelector.tsx`

### 2. **TokenHealthBanner.tsx** — Informações enriquecidas sobre tokens
- Adicionado import de `Clock` do lucide-react
- **Melhorias no conteúdo da mensagem**:
  - Título claro: "Conta "{nickname}" desconectada"
  - Descrição contextualizada: "Autenticação expirada" vs "Token expirado"
  - Ícone Clock + dias sem sincronização (ex: "3 dias sem sincronização")
  - Campo `data_gap_warning` em itálico (aviso sobre gap de dados)
  - Melhor estrutura com `<div>` e `<p>` separadas para melhor leitura
- Link "Reconectar" em vermelho para ação imediata

**Arquivo**: `frontend/src/components/TokenHealthBanner.tsx`

### 3. **Configuracoes/index.tsx** — Página de contas melhorada
- Adicionado import de `tokenDiagnosticsService`
- Adicionado `useQuery` para buscar diagnósticos (refetch a cada 5 min)
- **Lógica por conta**:
  - `diagnostic`: busca diagnóstico específico da conta
  - `hasDataGap`: verifica se tem gap de dados > 1 dia
  - `lastSyncFormatted`: formata data/hora da última sincronização
- **Melhorias visuais**:
  - Card com fundo amarelo (bg-yellow-50/dark:bg-yellow-950) quando há data gap
  - Exibição de "Última sincronização: {data}" usando dados do diagnóstico
  - Aviso em amarelo: "⚠ {data_gap_warning}" quando há gap

**Arquivo**: `frontend/src/pages/Configuracoes/index.tsx`

## Fluxo de Sincronização de Dados

```
Backend (/auth/ml/diagnostics)
├─ TokenDiagnostics
│  ├─ celery_status: 'online' | 'offline'
│  ├─ last_token_refresh_task: timestamp
│  └─ accounts: AccountDiagnostic[]
│     ├─ id, nickname, email
│     ├─ token_status: 'healthy' | 'expiring_soon' | 'expired'
│     ├─ token_expires_at: ISO8601 | null
│     ├─ remaining_hours: number
│     ├─ last_successful_sync: ISO8601 | null
│     ├─ days_since_last_sync: number
│     ├─ data_gap_warning: string | null
│     └─ needs_reauth: boolean
│
└─> Frontend (React Query)
    ├─ TokenHealthBanner.tsx (banner no Dashboard)
    ├─ AccountSelector.tsx (dropdown de seleção de conta)
    └─ Configuracoes/index.tsx (página de configurações)
```

## Indicadores Visuais

### StatusBadge (Configurações + Selector)
- 🟢 **Ativo**: "Ativo" em verde → `bg-green-100 text-green-700`
- 🟡 **Vence em Xd**: "Vence em 3d" em amarelo → `bg-yellow-100 text-yellow-700`
- 🔴 **Expirado**: "Expirado" em vermelho → `bg-red-100 text-red-700`

### TokenHealthBanner (Dashboard)
- 🔴 **needs_reauth = true**: Banner vermelho com AlertTriangle
- 🟡 **token_status = expired**: Banner amarelo com AlertCircle
- Exibe dias sem sincronização e aviso de gap de dados

### AccountSelector Dropdown
- 🔴 Ponto vermelho no avatar se `needs_reauth` ou `token_status='expired'`
- 🔴 Fundo vermelho da linha da conta
- 🔴 Ícone AlertCircle ao lado do status badge
- 🔴 Badge de alerta no botão principal se qualquer conta tem problema

### Configurações - Cards de Contas
- 🟡 Fundo amarelo se `hasDataGap` (> 1 dia sem dados)
- 🔴 Fundo vermelho se `isInactive`
- Exibição de "Última sincronização: {data}" do diagnóstico
- Aviso em amarelo: "⚠ X dias sem dados — visitas desse período foram perdidas"

## Comportamento de Refresh

- **Dashboard**: TokenHealthBanner refetch a cada 5 min
- **Selector**: Diagnósticos refetch a cada 5 min (retry: 2)
- **Configurações**: Diagnósticos refetch a cada 5 min (retry: 1)

## Testes Sugeridos

1. **Token expirado**: Fazer um token expirar manualmente e verificar se:
   - ✓ TokenHealthBanner mostra aviso vermelho
   - ✓ AccountSelector mostra indicador vermelho
   - ✓ Configurações mostra card com indicador

2. **Data gap**: Simular 3+ dias sem sincronização:
   - ✓ Configurações mostra fundo amarelo
   - ✓ Exibe aviso: "3 dias sem dados"
   - ✓ TokenHealthBanner mostra aviso de gap

3. **Multi-conta**: Ter 2+ contas:
   - ✓ AccountSelector mostra "Todas as contas"
   - ✓ Se 1 conta com problema, badge de alerta no botão
   - ✓ Dropdown mostra problema apenas dessa conta

## Arquivos Modificados

```
frontend/src/
├── components/
│   ├── AccountSelector.tsx ✓ (imports + hook + indicators)
│   └── TokenHealthBanner.tsx ✓ (Clock icon + better formatting)
└── pages/
    └── Configuracoes/index.tsx ✓ (diagnostics query + display)
```

## Notas

- Endpoint `/auth/ml/diagnostics` já existe no backend
- Interface `TokenDiagnostics` já está no `tokenDiagnosticsService.ts`
- Todas as melhorias usam componentes e estilos existentes (Tailwind + shadcn/ui)
- Nenhuma dependência nova foi adicionada
- Código segue padrão TypeScript + React do projeto

## Próximas Melhorias (Futuro)

1. **Webhook de notificação**: Alertar usuário quando token está perto de expirar
2. **Auto-reconexão**: Oferecer reconexão automática para contas expiradas
3. **Health Score**: Adicionar percentual de saúde geral de tokens
4. **Relatório**: Exportar relatório de sincronização por período
