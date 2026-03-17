import { Activity } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface MetricasAvancadasProps {
  rpv: number | null;
  totalVisitas: number;
  taxaCancelamento: number | null;
  totalCancelled: number;
  totalCancelledRevenue: number;
  totalReturnsCount: number;
  totalReturnsRevenue: number;
  diasParaZerar: number | null;
  velocity7d: number;
}

export function MetricasAvancadas({
  rpv,
  totalVisitas,
  taxaCancelamento,
  totalCancelled,
  totalCancelledRevenue,
  totalReturnsCount,
  totalReturnsRevenue,
  diasParaZerar,
  velocity7d,
}: MetricasAvancadasProps) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Metricas Avancadas</h2>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {/* RPV */}
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">RPV (Receita/Visita)</p>
          <p className="text-xl font-bold text-foreground">
            {rpv != null ? formatCurrency(rpv) : "—"}
          </p>
          <p className="text-xs text-muted-foreground">
            {totalVisitas > 0 ? `${totalVisitas.toLocaleString("pt-BR")} visitas` : "Sem visitas"}
          </p>
        </div>

        {/* Taxa de cancelamento */}
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Taxa de Cancelamento</p>
          <div className="flex items-center gap-2">
            <p className="text-xl font-bold text-foreground">
              {taxaCancelamento != null ? formatPercent(taxaCancelamento) : "—"}
            </p>
            {taxaCancelamento != null && taxaCancelamento > 3 && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">Alta</span>
            )}
            {taxaCancelamento != null && taxaCancelamento <= 3 && taxaCancelamento > 0 && (
              <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">Normal</span>
            )}
          </div>
          {/* ITEM 3: valor dos cancelamentos */}
          <p className="text-xs text-muted-foreground">
            {totalCancelled > 0
              ? `${totalCancelled} cancelados • ${formatCurrency(totalCancelledRevenue)}`
              : "Sem cancelamentos"}
          </p>
        </div>

        {/* ITEM 4: Devoluções */}
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Devolucoes</p>
          <p className="text-xl font-bold text-foreground">
            {totalReturnsCount > 0 ? totalReturnsCount : "—"}
          </p>
          <p className="text-xs text-muted-foreground">
            {totalReturnsCount > 0
              ? `${totalReturnsCount} ${totalReturnsCount === 1 ? "pedido" : "pedidos"} • ${formatCurrency(totalReturnsRevenue)}`
              : "Sem devolucoes"}
          </p>
        </div>

        {/* Velocidade de venda */}
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Velocidade de Venda</p>
          <div className="flex items-center gap-2">
            <p className="text-xl font-bold text-foreground">
              {diasParaZerar != null ? `${diasParaZerar}d` : "—"}
            </p>
            {diasParaZerar != null && (
              diasParaZerar > 30
                ? <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">OK</span>
                : diasParaZerar >= 7
                ? <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800">Atencao</span>
                : <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">Critico</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {velocity7d.toFixed(1)} und/dia (7d)
          </p>
        </div>
      </div>
    </div>
  );
}
