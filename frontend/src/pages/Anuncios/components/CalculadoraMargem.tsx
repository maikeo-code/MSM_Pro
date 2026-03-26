import { useQuery } from "@tanstack/react-query";
import { Calculator, TrendingUp } from "lucide-react";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

interface MargemData {
  preco: number | string;
  custo_sku: number | string;
  listing_type: string;
  taxa_ml_pct: number | string;
  taxa_ml_valor: number | string;
  frete: number | string;
  margem_bruta: number | string;
  margem_pct: number | string;
}

interface CalculadoraMargemProps {
  simPreco: string;
  setSimPreco: (v: string) => void;
  currentPrice: number;
  margem: MargemData | undefined;
  margemLoading: boolean;
  hasSku: boolean;
  mlbId?: string;
}

export function CalculadoraMargem({
  simPreco,
  setSimPreco,
  currentPrice,
  margem,
  margemLoading,
  hasSku,
  mlbId,
}: CalculadoraMargemProps) {
  const simPrecoNum = simPreco !== "" ? parseFloat(simPreco) : null;

  const { data: simulation, isLoading: simLoading } = useQuery({
    queryKey: ["simulate-price", mlbId, simPrecoNum],
    queryFn: () => listingsService.simulatePrice(mlbId!, simPrecoNum!),
    enabled: !!mlbId && simPrecoNum !== null && simPrecoNum > 0,
    retry: 1,
  });

  return (
    <div className="rounded-lg border bg-card p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Calculator className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Calculadora de Margem</h2>
      </div>

      {/* Seção de input e margem atual */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-muted-foreground">
              Simular com preco (R$)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0"
                step="0.01"
                value={simPreco}
                onChange={(e) => setSimPreco(e.target.value)}
                placeholder={String(currentPrice)}
                className="h-10 w-44 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              {simPreco && (
                <button
                  onClick={() => setSimPreco("")}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Limpar
                </button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Deixe vazio para usar o preco atual ({formatCurrency(currentPrice)})
            </p>
          </div>
        </div>

        <div>
          {margemLoading ? (
            <p className="text-sm text-muted-foreground">Calculando...</p>
          ) : margem ? (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Preco de venda</span>
                <span className="font-medium">{formatCurrency(Number(margem.preco))}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Custo SKU</span>
                <span className="font-medium text-red-600">- {formatCurrency(Number(margem.custo_sku))}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">
                  Taxa ML ({margem.listing_type}) — {formatPercent(Number(margem.taxa_ml_pct))}
                </span>
                <span className="font-medium text-red-600">- {formatCurrency(Number(margem.taxa_ml_valor))}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Frete estimado</span>
                <span className="font-medium text-red-600">- {formatCurrency(Number(margem.frete))}</span>
              </div>
              <div className="border-t pt-2 mt-2 flex justify-between">
                <span className="font-semibold">Margem Bruta</span>
                <span className={cn(
                  "font-bold text-lg",
                  Number(margem.margem_bruta) >= 0 ? "text-green-600" : "text-red-600"
                )}>
                  {formatCurrency(Number(margem.margem_bruta))}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Margem %</span>
                <span className={cn(
                  "text-sm font-semibold rounded-full px-2 py-0.5",
                  Number(margem.margem_pct) >= 20
                    ? "bg-green-100 text-green-700"
                    : Number(margem.margem_pct) >= 10
                    ? "bg-yellow-100 text-yellow-700"
                    : "bg-red-100 text-red-700"
                )}>
                  {formatPercent(Number(margem.margem_pct))}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              {!hasSku
                ? "Vincule um SKU para calcular a margem real."
                : "Informe um preco para simular."}
            </p>
          )}
        </div>
      </div>

      {/* Simulação de impacto de preço */}
      {simPrecoNum !== null && simPrecoNum > 0 && simulation && (
        <div className="border-t pt-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="h-4 w-4 text-primary" />
            <h3 className="font-semibold text-sm">Impacto da Mudanca de Preco</h3>
            {simulation.is_estimated && (
              <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded font-medium">
                Estimado
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-md bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground mb-1">Preco Simulado</p>
              <p className="font-bold text-lg text-foreground">
                {formatCurrency(simulation.target_price)}
              </p>
            </div>
            <div className="rounded-md bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground mb-1">Vendas Est./Dia</p>
              <p className="font-bold text-lg text-foreground">
                {simulation.estimated_sales_per_day.toFixed(1)}
              </p>
            </div>
            <div className="rounded-md bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground mb-1">Receita Est./Dia</p>
              <p className="font-bold text-lg text-green-600">
                {formatCurrency(simulation.estimated_revenue_per_day)}
              </p>
            </div>
            <div className="rounded-md bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground mb-1">Margem Estimada</p>
              <p className={cn(
                "font-bold text-lg",
                simulation.estimated_margin >= 0 ? "text-green-600" : "text-red-600"
              )}>
                {formatCurrency(simulation.estimated_margin)}
              </p>
            </div>
          </div>

          {simulation.elasticity !== null && (
            <p className="text-xs text-muted-foreground mt-3">
              Elasticidade calculada: {simulation.elasticity.toFixed(2)} (baseado em historico de 90 dias)
            </p>
          )}
        </div>
      )}

      {simLoading && (
        <div className="border-t pt-4 text-sm text-muted-foreground">
          Simulando impacto do novo preco...
        </div>
      )}
    </div>
  );
}
