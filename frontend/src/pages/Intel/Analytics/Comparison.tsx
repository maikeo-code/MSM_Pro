import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { TrendingUp, TrendingDown, AlertCircle } from "lucide-react";
import { analyticsService } from "@/services/intel/analyticsService";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/hooks/useActiveAccount";

export default function Comparison() {
  const accountId = useActiveAccount();
  const [searchParams, setSearchParams] = useSearchParams();
  const period = (searchParams.get("period") || "30d") as "7d" | "15d" | "30d";

  const { data, isLoading, error } = useQuery({
    queryKey: ["comparison", period, accountId],
    queryFn: () => analyticsService.getComparison(period, accountId),
  });

  const handlePeriodChange = (newPeriod: "7d" | "15d" | "30d") => {
    setSearchParams({ period: newPeriod });
  };

  const getDeltaColor = (delta: number) => {
    if (delta > 0) return "text-green-600";
    if (delta < 0) return "text-red-600";
    return "text-muted-foreground";
  };

  const getDeltaIcon = (delta: number) => {
    if (delta > 0) return <TrendingUp className="h-4 w-4" />;
    if (delta < 0) return <TrendingDown className="h-4 w-4" />;
    return null;
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Comparação Temporal (MoM)</h1>
        <p className="text-muted-foreground mt-1">
          Compare receita e vendas entre período atual e anterior
        </p>
      </div>

      {/* Period selector */}
      <div className="mb-6 flex gap-2">
        {(["7d", "15d", "30d"] as const).map((p) => (
          <Button
            key={p}
            variant={period === p ? "default" : "outline"}
            size="sm"
            onClick={() => handlePeriodChange(p)}
          >
            {p === "7d" ? "7 dias" : p === "15d" ? "15 dias" : "30 dias"}
          </Button>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 flex gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-900">Erro ao carregar dados</p>
            <p className="text-xs text-red-700 mt-1">
              Verifique sua conexão e tente novamente
            </p>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : data ? (
        <>
          {/* KPI Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <Card className="p-4">
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Receita Atual
              </div>
              <div className="text-2xl font-bold">
                R$ {data.total_revenue_current.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Receita Anterior
              </div>
              <div className="text-2xl font-bold">
                R$ {data.total_revenue_previous.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
              </div>
            </Card>
            <Card className={cn("p-4", getDeltaColor(data.total_revenue_delta_pct))}>
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Variação Receita
              </div>
              <div className="flex items-center gap-2">
                <div className="text-2xl font-bold">
                  {Math.abs(data.total_revenue_delta_pct).toFixed(1)}%
                </div>
                {getDeltaIcon(data.total_revenue_delta_pct)}
              </div>
            </Card>
            <Card className={cn("p-4", getDeltaColor(data.total_sales_delta_pct))}>
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Variação Vendas
              </div>
              <div className="flex items-center gap-2">
                <div className="text-2xl font-bold">
                  {Math.abs(data.total_sales_delta_pct).toFixed(1)}%
                </div>
                {getDeltaIcon(data.total_sales_delta_pct)}
              </div>
            </Card>
          </div>

          {/* Listings Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold">Anúncio</th>
                    <th className="px-4 py-3 text-right font-semibold">Receita Atual</th>
                    <th className="px-4 py-3 text-right font-semibold">Receita Anterior</th>
                    <th className="px-4 py-3 text-right font-semibold">Δ Receita</th>
                    <th className="px-4 py-3 text-right font-semibold">Vendas Atual</th>
                    <th className="px-4 py-3 text-right font-semibold">Vendas Anterior</th>
                    <th className="px-4 py-3 text-right font-semibold">Δ Vendas</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.items.map((item) => (
                    <tr key={item.mlb_id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground truncate max-w-xs">
                          {item.title}
                        </div>
                        <div className="text-xs text-muted-foreground">{item.mlb_id}</div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        R$ {item.revenue_current.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        R$ {item.revenue_previous.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
                      </td>
                      <td className={cn(
                        "px-4 py-3 text-right font-medium",
                        getDeltaColor(item.revenue_delta_pct)
                      )}>
                        <div className="flex items-center justify-end gap-1">
                          {item.revenue_delta_pct > 0 ? "+" : ""}{item.revenue_delta_pct.toFixed(1)}%
                          {getDeltaIcon(item.revenue_delta_pct)}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {item.sales_current}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {item.sales_previous}
                      </td>
                      <td className={cn(
                        "px-4 py-3 text-right font-medium",
                        getDeltaColor(item.sales_delta_pct)
                      )}>
                        <div className="flex items-center justify-end gap-1">
                          {item.sales_delta_pct > 0 ? "+" : ""}{item.sales_delta_pct.toFixed(1)}%
                          {getDeltaIcon(item.sales_delta_pct)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.items.length === 0 && (
              <div className="p-8 text-center">
                <p className="text-muted-foreground">Nenhum anúncio encontrado</p>
              </div>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
}
