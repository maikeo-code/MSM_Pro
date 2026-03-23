# Account Selector — Guia de Implementação

## Visão Geral

O seletor de conta ML foi implementado para permitir que usuários com múltiplas contas escolham qual conta visualizar. O seletor é integrado na Topbar e automaticamente filtra dados em tempo real.

## Componentes

### 1. Store Zustand (`frontend/src/store/accountStore.ts`)

Gerencia qual conta está ativa:

```typescript
import { useAccountStore } from "@/store/accountStore";

// Usar no componente
const { activeAccountId, setActiveAccount, clearActiveAccount } = useAccountStore();

// activeAccountId: string | null (null = todas as contas)
```

### 2. Hooks Customizados (`frontend/src/hooks/useActiveAccount.ts`)

#### `useActiveAccount()`
Retorna apenas o ID da conta ativa:

```typescript
import { useActiveAccount } from "@/hooks/useActiveAccount";

const accountId = useActiveAccount();
// accountId: string | null
```

#### `useAccountQueryParams()`
Retorna objeto pronto para usar em query params:

```typescript
import { useAccountQueryParams } from "@/hooks/useActiveAccount";

const params = useAccountQueryParams();
// params: { ml_account_id: "..." } ou {}
```

### 3. Componente AccountSelector (`frontend/src/components/AccountSelector.tsx`)

Dropdown visual que lista todas as contas:

```typescript
import { AccountSelector } from "@/components/AccountSelector";

// Integrado na Topbar do Layout.tsx
<AccountSelector className="hidden md:block" />
```

**Features:**
- Carrega contas do endpoint `/api/v1/auth/ml/accounts`
- Exibe status de expiração de token (Ativo/Vence em Xd/Expirado)
- Opção "Todas as contas" no topo (valor: null)
- Badge colorida com primeira letra do nickname
- Persiste seleção em localStorage (chave: `msm-active-account`)
- Invisível quando usuário tem apenas 1 conta

## Como Usar em Páginas

### Exemplo 1: Dashboard com filtro de conta

```typescript
import { useActiveAccount } from "@/hooks/useActiveAccount";
import { useQuery } from "@tanstack/react-query";
import listingsService from "@/services/listingsService";

export default function Dashboard() {
  const accountId = useActiveAccount();

  // QueryKey inclui accountId — ao trocar conta, refaz a query
  const { data: listings } = useQuery({
    queryKey: ["listings", "today", accountId],
    queryFn: () => listingsService.list("today", accountId),
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary", accountId],
    queryFn: () => listingsService.getKpiSummary(accountId),
  });

  // Rest do componente...
}
```

### Exemplo 2: Múltiplas queries com conta

```typescript
import { useAccountQueryParams } from "@/hooks/useActiveAccount";

export default function FinanceiroPage() {
  const params = useAccountQueryParams();

  const { data: resumo } = useQuery({
    queryKey: ["financeiro-resumo", "30d", params.ml_account_id],
    queryFn: () => financeiroService.getResumo("30d", params.ml_account_id),
  });

  const { data: timeline } = useQuery({
    queryKey: ["financeiro-timeline", "30d", params.ml_account_id],
    queryFn: () => financeiroService.getTimeline("30d", params.ml_account_id),
  });

  // Rest do componente...
}
```

### Exemplo 3: Invalidar queries ao trocar conta

```typescript
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useActiveAccount } from "@/hooks/useActiveAccount";

export default function MyPage() {
  const accountId = useActiveAccount();
  const queryClient = useQueryClient();

  // Invalidar queries relacionadas ao mudar conta
  useEffect(() => {
    if (accountId !== undefined) {
      // Invalidar todas as queries que dependem da conta
      queryClient.invalidateQueries({
        predicate: (query) =>
          query.queryKey.includes(accountId) ||
          query.queryKey.includes("listings") ||
          query.queryKey.includes("kpi")
      });
    }
  }, [accountId, queryClient]);

  // Rest do componente...
}
```

## Services Atualizados

Todos os métodos agora aceitam um parâmetro opcional `ml_account_id`:

### listingsService
```typescript
list(period, mlAccountId?)
getSnapshots(mlbId, dias, mlAccountId?)
getAnalysis(mlbId, days, mlAccountId?)
getKpiSummary(mlAccountId?)
sync(mlAccountId?)
// ... outros métodos também atualizado
```

### financeiroService
```typescript
getResumo(period, mlAccountId?)
getTimeline(period, mlAccountId?)
getDetalhado(period, mlAccountId?)
getCashflow(mlAccountId?)
```

### ordersService
```typescript
listOrders(period, mlAccountId?)
```

### adsService
```typescript
list(mlAccountId?)
getCampanha(campaignId, period, mlAccountId?)
sync(mlAccountId?)
```

### analysisService
```typescript
getListingsAnalysis(mlAccountId?)
```

## Padrão de Implementação

Para adicionar suporte a múltiplas contas em uma página:

1. **Import o hook:**
   ```typescript
   import { useActiveAccount } from "@/hooks/useActiveAccount";
   ```

2. **Use na página:**
   ```typescript
   const accountId = useActiveAccount();
   ```

3. **Passe para a query:**
   ```typescript
   const { data } = useQuery({
     queryKey: ["dados", periodo, accountId],
     queryFn: () => service.metodo(periodo, accountId),
   });
   ```

4. **Pronto!** O seletor na Topbar fará o resto automaticamente.

## Comportamento

- **Quando accountId é null**: Endpoint retorna dados agregados de TODAS as contas
- **Quando accountId tem valor**: Endpoint filtra dados da conta específica
- **localStorage**: Salva a escolha do usuário (chave: `msm-active-account`)
- **Invisibilidade**: AccountSelector fica invisível em mobile (hidden md:block) e quando há apenas 1 conta

## Exemplo de POST/PATCH com conta

Para criar/atualizar anúncios ou fazer sync apenas de uma conta:

```typescript
// Criar anúncio em conta específica
async createListing(payload, accountId?: string) {
  const params = accountId ? { ml_account_id: accountId } : {};
  const { data } = await api.post("/listings/", payload, { params });
  return data;
}

// Sincronizar apenas conta ativa
async sync(accountId?: string) {
  const params = accountId ? { ml_account_id: accountId } : {};
  const { data } = await api.post("/listings/sync", {}, { params });
  return data;
}
```

## Dicas de Debugging

1. **Verificar seleção persistida:**
   ```javascript
   localStorage.getItem('msm-active-account')
   ```

2. **Verificar store:**
   ```javascript
   useAccountStore.getState().activeAccountId
   ```

3. **Ver requests no Network:**
   - Com conta selecionada: `?ml_account_id=abc123`
   - Sem seleção: nenhum param (todos os dados)

## Próximas Features

- [ ] Filtro avançado por múltiplas contas ao mesmo tempo
- [ ] Comparação visual entre contas
- [ ] Atalho de teclado para trocar conta (Ctrl+Alt+A)
- [ ] Notificações por conta

## Referências

- Arquivo: `frontend/src/store/accountStore.ts`
- Arquivo: `frontend/src/components/AccountSelector.tsx`
- Arquivo: `frontend/src/hooks/useActiveAccount.ts`
- Exemplo: `frontend/src/pages/Dashboard/index.tsx` (já atualizado com queryKey de conta)

---

**Versão**: 1.0
**Data**: 2026-03-23
**Status**: Implementado
