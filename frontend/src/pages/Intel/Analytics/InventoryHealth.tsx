import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { AlertCircle, AlertTriangle, CheckCircle } from "lucide-react";
import { analyticsService } from "@/services/intel/analyticsService";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/hooks/useActiveAccount";

const healthColors = {
  healthy: { bg: "bg-emerald-50", border: "border-emerald-200", icon: CheckCircle, color: "text-emerald-600" },
  overstocked: { bg: "bg-yellow-50", border: "border-yellow-200", icon: AlertTriangle, color: "text-yellow-600" },
  critical_low: { bg: "bg-red-50", border: "border-red-200", icon: AlertCircle, color: "text-red-600" },
};

export default function InventoryHealth() {
  const accountId = useActiveAccount();
  const [searchParams, setSearchParams] = useSearchParams();
  const period = (searchParams.get("period") || "30d") as "7d" | "15d" | "30d";

  const { data, isLoading, error } = useQuery({
    queryKey: ["inventory-health", period, accountId],
    queryFn: () => analyticsService.getInventoryHealth(period, accountId),
  });

  const handlePeriodChange = (newPeriod: "7d" | "15d" | "30d") => {
    setSearchParams({ period: newPeriod });
  };

  const getStatusBadge = (status: "healthy" | "overstocked" | "critical_low") => {
    const config = healthColors[status];
    const Icon = config.icon;
    const labels = {
      healthy: "Saudável",
      overstocked: "Overstockado",
      critical_low: "Crítico",
    };
    return (
      <Badge className={cn("gap-1", config.bg, config.border, "border")}>
        <Icon className="h-3 w-3" />
        {labels[status]}
      </Badge>
    );
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Saúde do Estoque</h1>
        <p className="text-muted-foreground mt-1">
          Análise de dias de estoque, taxa de sell-through e alertas de desabastecimento
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
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="p-4">
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Total de Anúncios
              </div>
              <div className="text-2xl font-bold">{data.total_items}</div>
            </Card>
            <Card className="p-4 border-emerald-200 bg-emerald-50">
              <div className="text-xs font-medium text-emerald-700 mb-1">
                Saudável
              </div>
              <div className="text-2xl font-bold text-emerald-900">
                {data.healthy_count}
              </div>
              <p className="text-xs text-emerald-700 mt-1">
                {data.total_items > 0 ? ((data.healthy_count / data.total_items) * 100).toFixed(0) : 0}%
              </p>
            </Card>
            <Card className="p-4 border-yellow-200 bg-yellow-50">
              <div className="text-xs font-medium text-yellow-700 mb-1">
                Overstockado
              </div>
              <div className="text-2xl font-bold text-yellow-900">
                {data.overstocked_count}
              </div>
              <p className="text-xs text-yellow-700 mt-1">
                Capital parado
              </p>
            </Card>
            <Card className="p-4 border-red-200 bg-red-50">
              <div className="text-xs font-medium text-red-700 mb-1">
                Crítico
              </div>
              <div className="text-2xl font-bold text-red-900">
                {data.critical_low_count}
              </div>
              <p className="text-xs text-red-700 mt-1">
                Risco de falta
              </p>
            </Card>
          </div>

          {/* Average Days of Stock */}
          <Card className="mb-8 p-6 border-blue-200 bg-blue-50">
            <h3 className="text-lg font-semibold text-blue-900 mb-2">Média de Dias de Estoque</h3>
            <div className="text-4xl font-bold text-blue-900">{data.avg_days_of_stock.toFixed(1)} dias</div>
            <p className="text-sm text-blue-700 mt-2">
              {data.avg_days_of_stock < 7
                ? "⚠️ Estoque crítico - Risco de desabastecimento"
                : data.avg_days_of_stock < 30
                ? "✓ Estoque baixo - Monitor regularmente"
                : data.avg_days_of_stock > 90
                ? "⚠️ Estoque alto - Considere promoções"
                : "✓ Estoque equilibrado"}
            </p>
          </Card>

          {/* Products Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold">Anúncio</th>
                    <th className="px-4 py-3 text-center font-semibold">Status</th>
                    <th className="px-4 py-3 text-right font-semibold">Estoque</th>
                    <th className="px-4 py-3 text-right font-semibold">Vendas/dia</th>
                    <th className="px-4 py-3 text-right font-semibold">Dias Estoque</th>
                    <th className="px-4 py-3 text-right font-semibold">Taxa Sell-Through</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.items
                    .sort((a, b) => {
                      // Sort by status priority: critical_low -> overstocked -> healthy
                      const priority: Record<string, number> = {
                        critical_low: 0,
                        overstocked: 1,
                        healthy: 2,
                      };
                      return priority[a.health_status] - priority[b.health_status];
                    })
                    .map((item) => {
                      const config = healthColors[item.health_status];
                      const Icon = config.icon;

                      return (
                        <tr key={item.mlb_id} className={cn("hover:bg-muted/30 transition-colors", config.bg)}>
                          <td className="px-4 py-3">
                            <div className="font-medium text-foreground truncate max-w-xs">
                              {item.title}
                            </div>
                            <div className="text-xs text-muted-foreground">{item.mlb_id}</div>
                          </td>
                          <td className="px-4 py-3 text-center">
                            {getStatusBadge(item.health_status)}
                          </td>
                          <td className="px-4 py-3 text-right font-medium">
                            {item.current_stock}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {item.avg_daily_sales.toFixed(2)}
                          </td>
                          <td className={cn(
                            "px-4 py-3 text-right font-bold",
                            item.days_of_stock < 7 ? "text-red-600" : item.days_of_stock > 90 ? "text-yellow-600" : "text-emerald-600"
                          )}>
                            {item.days_of_stock === 999.0 ? "∞" : item.days_of_stock.toFixed(1)}
                          </td>
                          <td className="px-4 py-3 text-right text-muted-foreground">
                            {(item.sell_through_rate * 100).toFixed(1)}%
                          </td>
                        </tr>
                      );
                    })}
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
          <div className="mt-6 space-y-3">
            <div className="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-4">
              <p className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Saúde:</span>
                <span className="ml-1">
                  ✓ Saudável (30-90 dias) | ⚠️ Overstockado (&gt;90 dias) | 🚨 Crítico (&lt;7 dias)
                </span>
              </p>
            </div>
            <div className="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-4">
              <p className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Taxa Sell-Through:</span>
                <span className="ml-1">
                  Proporção de vendas sobre (vendas + estoque). Valores próximos a 100% indicam alta rotatividade.
                </span>
              </p>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
