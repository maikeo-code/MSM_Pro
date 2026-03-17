import { Star } from "lucide-react";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

interface PriceBand {
  price_range_label: string;
  days_count: number;
  avg_sales_per_day: number;
  avg_conversion: number;
  total_revenue: number;
  avg_margin: number;
  is_optimal: boolean;
}

interface PriceBandsTableProps {
  priceBands: PriceBand[];
}

export function PriceBandsTable({ priceBands }: PriceBandsTableProps) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <h2 className="text-lg font-semibold mb-4">
        Histograma de Faixas de Preco
      </h2>
      {priceBands.length === 0 ? (
        <p className="text-muted-foreground">Sem dados para exibir.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Faixa de Preco</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Dias</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Vendas/dia</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Conversao</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Receita</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Margem Unit.</th>
              </tr>
            </thead>
            <tbody>
              {priceBands.map((band, idx) => (
                <tr
                  key={idx}
                  className={cn(
                    "border-b transition-colors",
                    band.is_optimal
                      ? "bg-green-50 dark:bg-green-950/30"
                      : "hover:bg-muted/50"
                  )}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {band.is_optimal && (
                        <Star className="h-4 w-4 text-yellow-500 fill-yellow-500 shrink-0" />
                      )}
                      <span className={band.is_optimal ? "font-semibold" : ""}>
                        {band.price_range_label}
                      </span>
                      {band.is_optimal && (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                          Otimo
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">{band.days_count}</td>
                  <td className="px-4 py-3 text-right font-medium">
                    {band.avg_sales_per_day.toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatPercent(band.avg_conversion)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-green-600">
                    {formatCurrency(band.total_revenue)}
                  </td>
                  <td className={cn(
                    "px-4 py-3 text-right font-medium",
                    band.avg_margin > 0 ? "text-green-600" : band.avg_margin < 0 ? "text-red-600" : "text-muted-foreground"
                  )}>
                    {formatCurrency(band.avg_margin)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
