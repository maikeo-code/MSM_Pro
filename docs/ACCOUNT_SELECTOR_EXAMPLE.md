# Exemplo Prático: Integrando Account Selector na Dashboard

## Antes e Depois

### Antes (sem filtro de conta)

```typescript
export default function Dashboard() {
  const [tablePeriod, setTablePeriod] = useState<string>("today");

  const { data: listings } = useQuery({
    queryKey: ["listings", tablePeriod],  // ❌ Não inclui conta
    queryFn: () => listingsService.list(tablePeriod),
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary"],  // ❌ Sem filtro de conta
    queryFn: () => listingsService.getKpiSummary(),
  });

  // ... resto
}
```

### Depois (com filtro de conta)

```typescript
import { useActiveAccount } from "@/hooks/useActiveAccount";

export default function Dashboard() {
  const [tablePeriod, setTablePeriod] = useState<string>("today");
  const accountId = useActiveAccount();  // ✅ Obtém conta ativa

  const { data: listings } = useQuery({
    queryKey: ["listings", tablePeriod, accountId],  // ✅ Inclui conta
    queryFn: () => listingsService.list(tablePeriod, accountId),  // ✅ Passa conta
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary", accountId],  // ✅ Inclui conta
    queryFn: () => listingsService.getKpiSummary(accountId),  // ✅ Passa conta
  });

  // ... resto — sem mudança no resto da lógica
}
```

## Checklist para Atualizar uma Página

### Passo 1: Importar o hook
```typescript
import { useActiveAccount } from "@/hooks/useActiveAccount";
```

### Passo 2: Chamar o hook
```typescript
const accountId = useActiveAccount();
```

### Passo 3: Adicionar accountId ao queryKey
```typescript
// ❌ ANTES
queryKey: ["dados"]

// ✅ DEPOIS
queryKey: ["dados", accountId]
```

### Passo 4: Passar accountId aos serviços
```typescript
// ❌ ANTES
queryFn: () => service.metodo()

// ✅ DEPOIS
queryFn: () => service.metodo(periodo, accountId)
```

## Exemplo Completo: Página de Financeiro

```typescript
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useActiveAccount } from "@/hooks/useActiveAccount";
import financeiroService from "@/services/financeiroService";

export default function FinanceiroPage() {
  const [period, setPeriod] = useState("30d");
  const accountId = useActiveAccount();  // ✅ Uma linha!

  // Query 1: Resumo
  const { data: resumo, isLoading: loadingResumo } = useQuery({
    queryKey: ["financeiro-resumo", period, accountId],  // ✅ accountId aqui
    queryFn: () => financeiroService.getResumo(period, accountId),  // ✅ e aqui
    retry: 2,
  });

  // Query 2: Timeline
  const { data: timeline, isLoading: loadingTimeline } = useQuery({
    queryKey: ["financeiro-timeline", period, accountId],
    queryFn: () => financeiroService.getTimeline(period, accountId),
    retry: 2,
  });

  // Query 3: Detalhado
  const { data: detalhado } = useQuery({
    queryKey: ["financeiro-detalhado", period, accountId],
    queryFn: () => financeiroService.getDetalhado(period, accountId),
    retry: 2,
  });

  return (
    <div className="p-8">
      <h1>Financeiro
        {accountId && <span className="ml-2 text-sm text-muted-foreground">(Conta: {accountId.slice(0, 8)}...)</span>}
      </h1>

      <select value={period} onChange={(e) => setPeriod(e.target.value)} className="mb-4">
        <option value="7d">7 dias</option>
        <option value="30d">30 dias</option>
        <option value="60d">60 dias</option>
      </select>

      {/* Cards de resumo */}
      {resumo && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          <Card>
            <div className="text-sm text-muted-foreground">Vendas Brutas</div>
            <div className="text-2xl font-bold">{formatCurrency(resumo.vendas_brutas)}</div>
          </Card>
          <Card>
            <div className="text-sm text-muted-foreground">Receita Líquida</div>
            <div className="text-2xl font-bold">{formatCurrency(resumo.receita_liquida)}</div>
          </Card>
          <Card>
            <div className="text-sm text-muted-foreground">Margem</div>
            <div className="text-2xl font-bold">{resumo.margem_pct.toFixed(1)}%</div>
          </Card>
          <Card>
            <div className="text-sm text-muted-foreground">Pedidos</div>
            <div className="text-2xl font-bold">{resumo.total_pedidos}</div>
          </Card>
        </div>
      )}

      {/* Gráfico de timeline */}
      {timeline && timeline.length > 0 && (
        <LineChart data={timeline} />
      )}

      {/* Tabela detalhada */}
      {detalhado && (
        <Table data={detalhado} />
      )}
    </div>
  );
}
```

## Exemplo: Componente com Múltiplas Queries

```typescript
import { useActiveAccount, useAccountQueryParams } from "@/hooks/useActiveAccount";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

export default function AdsPage() {
  const accountId = useActiveAccount();
  const queryClient = useQueryClient();

  // Query 1: Lista de campanhas
  const { data: ads } = useQuery({
    queryKey: ["ads-list", accountId],
    queryFn: () => adsService.list(accountId),
  });

  // Query 2: Detalhe de campanha selecionada
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);

  const { data: campaignDetail } = useQuery({
    queryKey: ["ads-detalhe", selectedCampaign, accountId],
    queryFn: () => selectedCampaign
      ? adsService.getCampanha(selectedCampaign, "30d", accountId)
      : null,
    enabled: !!selectedCampaign,
  });

  // Invalidar tudo ao trocar conta
  useEffect(() => {
    queryClient.invalidateQueries({
      predicate: (query) =>
        String(query.queryKey[0]).startsWith("ads"),
    });
  }, [accountId, queryClient]);

  return (
    <div>
      <h1>Campanhas de Publicidade</h1>
      {accountId && <p className="text-xs text-muted-foreground">Filtrando por: {accountId}</p>}

      {/* Lista */}
      {ads?.campanhas.map((c) => (
        <div
          key={c.id}
          onClick={() => setSelectedCampaign(c.id)}
          className="cursor-pointer p-4 border rounded hover:bg-accent"
        >
          <div className="font-semibold">{c.name}</div>
          <div className="text-sm text-muted-foreground">ROAS: {c.roas}</div>
        </div>
      ))}

      {/* Detalhe */}
      {campaignDetail && (
        <div className="mt-8 p-4 bg-accent rounded">
          <h2>{campaignDetail.name}</h2>
          <LineChart data={campaignDetail.timeline} />
        </div>
      )}
    </div>
  );
}
```

## Exemplo: Hook Customizado para Simplicidade

Se você quer simplificar ainda mais, crie um hook customizado:

```typescript
// frontend/src/hooks/useListingsByAccount.ts
import { useActiveAccount } from "./useActiveAccount";
import { useQuery } from "@tanstack/react-query";
import listingsService from "@/services/listingsService";

export function useListingsByAccount(period: string = "today") {
  const accountId = useActiveAccount();

  return useQuery({
    queryKey: ["listings", period, accountId],
    queryFn: () => listingsService.list(period, accountId),
  });
}

// Uso na página:
export default function Dashboard() {
  const { data: listings } = useListingsByAccount("today");  // ✅ Uma linha!
  // ... resto
}
```

## Comportamento Esperado

### Cenário 1: Usuário com 1 conta
- AccountSelector fica invisível (hidden)
- `accountId` é sempre null
- Endpoints retornam dados dessa conta automaticamente

### Cenário 2: Usuário com 2+ contas
- AccountSelector aparece na Topbar
- Usuário clica no seletor → dropdown com contas
- Seleciona uma conta → `accountId` muda no store
- React Query detecta mudança na queryKey
- Queries são refetchadas automaticamente
- Componentes renderizam dados da nova conta

### Cenário 3: Modo "Todas as Contas"
- Usuário clica em "Todas as contas" no dropdown
- `accountId` vira null no store
- localStorage atualiza para `{ activeAccountId: null }`
- Queries refetch sem parâmetro `ml_account_id`
- Endpoints retornam agregação de todas as contas

## Troubleshooting

### Problema: Dados não mudam ao trocar conta
**Solução**: Verifique se queryKey inclui `accountId`
```typescript
// ❌ ERRADO
queryKey: ["dados"]

// ✅ CORRETO
queryKey: ["dados", accountId]
```

### Problema: accountId é undefined
**Solução**: Verifique import
```typescript
// ❌ ERRADO
import { useAccountStore } from "@/store/accountStore";
const { activeAccountId } = useAccountStore();

// ✅ CORRETO
import { useActiveAccount } from "@/hooks/useActiveAccount";
const accountId = useActiveAccount();
```

### Problema: AccountSelector não aparece
**Verificar:**
1. Usuário tem 2+ contas? (se 1 only, fica invisível)
2. Está em tela médio (md:block)? (hidden em mobile)
3. Frontend está carregando as contas? (check Network)

---

**Pro Tip**: Use `useAccountQueryParams()` para query params automáticos em POST/PATCH:

```typescript
const params = useAccountQueryParams();  // { ml_account_id: "..." } ou {}

await api.post("/endpoint", data, { params });  // ✅ params já inclui conta se necessário
```
