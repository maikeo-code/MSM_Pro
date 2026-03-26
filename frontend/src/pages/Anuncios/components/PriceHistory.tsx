import { useQuery } from "@tanstack/react-query";
import { History, TrendingUp, TrendingDown } from "lucide-react";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatDate, cn } from "@/lib/utils";

interface PriceHistoryProps {
  mlbId: string;
}

export function PriceHistory({ mlbId }: PriceHistoryProps) {
  const { data: history = [], isLoading, error } = useQuery({
    queryKey: ["price-history", mlbId],
    queryFn: () => listingsService.getPriceHistory(mlbId, 50),
    enabled: !!mlbId,
    retry: 1,
  });

  if (error) {
    return (
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <History className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Historico de Precos</h2>
        </div>
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar historico de precos.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <History className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Historico de Precos</h2>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Carregando historico de precos...
        </div>
      ) : history.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          Nenhuma mudanca de preco registrada.
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((item) => {
            const oldPrice = item.old_price ?? 0;
            const newPrice = item.new_price ?? 0;
            const variation = newPrice - oldPrice;
            const variationPct = oldPrice > 0 ? (variation / oldPrice) * 100 : 0;
            const isIncrease = variation >= 0;

            return (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 rounded-md border bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 flex-1">
                  <div className={cn(
                    "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
                    isIncrease ? "bg-red-100" : "bg-green-100"
                  )}>
                    {isIncrease ? (
                      <TrendingUp className="h-4 w-4 text-red-600" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-green-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-mono font-medium text-muted-foreground">
                        {formatCurrency(oldPrice)}
                      </span>
                      <span className="text-muted-foreground">→</span>
                      <span className={cn(
                        "text-sm font-mono font-semibold",
                        isIncrease ? "text-red-600" : "text-green-600"
                      )}>
                        {formatCurrency(newPrice)}
                      </span>
                      <span className={cn(
                        "text-xs font-medium px-1.5 py-0.5 rounded",
                        isIncrease
                          ? "bg-red-100 text-red-700"
                          : "bg-green-100 text-green-700"
                      )}>
                        {isIncrease ? "+" : ""}{formatCurrency(variation)} ({isIncrease ? "+" : ""}{variationPct.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        {formatDate(item.changed_at)} — {new Date(item.changed_at).toLocaleTimeString("pt-BR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium">
                        {item.source}
                      </span>
                    </div>
                    {item.justification && (
                      <p className="text-xs text-muted-foreground mt-1">{item.justification}</p>
                    )}
                    {!item.success && item.error_message && (
                      <p className="text-xs text-destructive mt-1">Erro: {item.error_message}</p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
