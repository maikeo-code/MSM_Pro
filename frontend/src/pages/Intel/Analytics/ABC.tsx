import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AlertCircle, Package } from "lucide-react";
import { analyticsService } from "@/services/intel/analyticsService";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/hooks/useActiveAccount";

const classificationColors = {
  A: "bg-emerald-100 text-emerald-800 border-emerald-300",
  B: "bg-blue-100 text-blue-800 border-blue-300",
  C: "bg-amber-100 text-amber-800 border-amber-300",
};

export default function ABC() {
  const accountId = useActiveAccount();
  const [searchParams, setSearchParams] = useSearchParams();
  const period = (searchParams.get("period") || "30d") as "7d" | "15d" | "30d";
  const metric = (searchParams.get("metric") || "revenue") as "revenue" | "units" | "margin";

  const { data, isLoading, error } = useQuery({
    queryKey: ["abc", period, metric, accountId],
    queryFn: () => analyticsService.getABC(period, metric, accountId),
  });

  const handlePeriodChange = (newPeriod: "7d" | "15d" | "30d") => {
    setSearchParams({ period: newPeriod, metric });
  };

  const handleMetricChange = (newMetric: "revenue" | "units" | "margin") => {
    setSearchParams({ period, metric: newMetric });
  };

  const getMetricLabel = (m: string) => {
    return m === "revenue" ? "Receita" : m === "units" ? "Unidades" : "Margem";
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Classificação ABC</h1>
        <p className="text-muted-foreground mt-1">
          Análise de giro de estoque e classificação por contribuição (A=80%, B=15%, C=5%)
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 space-y-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Período</p>
          <div className="flex gap-2">
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
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Métrica</p>
          <div className="flex gap-2">
            {(["revenue", "units", "margin"] as const).map((m) => (
              <Button
                key={m}
                variant={metric === m ? "default" : "outline"}
                size="sm"
                onClick={() => handleMetricChange(m)}
              >
                {getMetricLabel(m)}
              </Button>
            ))}
          </div>
        </div>
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="p-4">
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Total Receita
              </div>
              <div className="text-2xl font-bold">
                R$ {data.total_revenue.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}
              </div>
            </Card>
            <Card className="p-4 border-emerald-200 bg-emerald-50">
              <div className="text-xs font-medium text-emerald-700 mb-1">
                Classe A (80%)
              </div>
              <div className="text-2xl font-bold text-emerald-900">
                {data.class_a_revenue_pct.toFixed(1)}%
              </div>
            </Card>
            <Card className="p-4 border-blue-200 bg-blue-50">
              <div className="text-xs font-medium text-blue-700 mb-1">
                Classe B (15%)
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {data.class_b_revenue_pct.toFixed(1)}%
              </div>
            </Card>
            <Card className="p-4 border-amber-200 bg-amber-50">
              <div className="text-xs font-medium text-amber-700 mb-1">
                Classe C (5%)
              </div>
              <div className="text-2xl font-bold text-amber-900">
                {data.class_c_revenue_pct.toFixed(1)}%
              </div>
            </Card>
          </div>

          {/* Products Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold">Anúncio</th>
                    <th className="px-4 py-3 text-center font-semibold">Classe</th>
                    <th className="px-4 py-3 text-right font-semibold">Receita</th>
                    <th className="px-4 py-3 text-right font-semibold">% Total</th>
                    <th className="px-4 py-3 text-right font-semibold">Vendidas</th>
                    <th className="px-4 py-3 text-right font-semibold">Estoque</th>
                    <th className="px-4 py-3 text-right font-semibold">Giro</th>
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
                      <td className="px-4 py-3 text-center">
                        <Badge className={cn("font-bold border", classificationColors[item.classification])}>
                          {item.classification}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        R$ {item.revenue_30d.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right text-muted-foreground">
                        {item.revenue_pct.toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-right">
                        {item.units_sold}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {item.current_stock}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <span>{item.turnover_rate.toFixed(2)}</span>
                          {item.current_stock > 0 && item.turnover_rate < 0.1 && (
                            <div title="Estoque parado">
                              <Package className="h-4 w-4 text-amber-600" />
                            </div>
                          )}
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

          {/* Legend */}
          <div className="mt-6 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-4">
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">Legenda de Giro:</span> Razão entre unidades vendidas e estoque atual.
              Valores baixos (&lt;0.1) indicam capital parado. Classe A deve ter alta rotatividade.
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}
