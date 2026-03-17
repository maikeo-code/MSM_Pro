import { Calculator } from "lucide-react";
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
}

export function CalculadoraMargem({
  simPreco,
  setSimPreco,
  currentPrice,
  margem,
  margemLoading,
  hasSku,
}: CalculadoraMargemProps) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Calculator className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Calculadora de Margem</h2>
      </div>

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
    </div>
  );
}
