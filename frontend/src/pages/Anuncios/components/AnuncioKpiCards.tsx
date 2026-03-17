import { TrendingUp, Target, Zap, Package, DollarSign, Star } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface AnuncioKpiCardsProps {
  totalSales: number;
  totalOrders: number;
  avgConversion: number;
  totalVisitas: number;
  currentPrice: number;
  precoMedioPorVenda: number | null;
  lastStock: number;
  diasParaZerar: number | null;
  totalReceita: number;
  vendasConcluidas: number;
}

export function AnuncioKpiCards({
  totalSales,
  totalOrders,
  avgConversion,
  totalVisitas,
  currentPrice,
  precoMedioPorVenda,
  lastStock,
  diasParaZerar,
  totalReceita,
  vendasConcluidas,
}: AnuncioKpiCardsProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Vendas Total</p>
          <TrendingUp className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-foreground">{totalSales}</p>
        <p className="text-xs text-muted-foreground mt-1">{totalOrders} pedidos</p>
      </div>

      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Conversao Media</p>
          <Target className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-foreground">{formatPercent(avgConversion)}</p>
        <p className="text-xs text-muted-foreground mt-1">{totalVisitas.toLocaleString("pt-BR")} visitas</p>
      </div>

      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Preco Atual</p>
          <Zap className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-foreground">{formatCurrency(currentPrice)}</p>
        {/* ITEM 1: preco medio por venda */}
        {precoMedioPorVenda != null && (
          <p className="text-xs text-blue-600 mt-1">{formatCurrency(precoMedioPorVenda)}/venda</p>
        )}
      </div>

      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Estoque</p>
          <Package className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-foreground">{lastStock}</p>
        <p className="text-xs text-muted-foreground mt-1">{diasParaZerar != null ? `${diasParaZerar}d para zerar` : "—"}</p>
      </div>

      {/* ITEM 5: Vendas Brutas vs Concluidas */}
      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Receita Bruta</p>
          <DollarSign className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-green-600">{formatCurrency(totalReceita)}</p>
        <p className="text-xs text-muted-foreground mt-1">no periodo</p>
      </div>

      <div className="rounded-lg border bg-card p-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs text-muted-foreground font-medium">Vendas Concluidas</p>
          <Star className="h-4 w-4 text-primary/50" />
        </div>
        <p className="text-2xl font-bold text-emerald-700">{formatCurrency(vendasConcluidas)}</p>
        <p className="text-xs text-muted-foreground mt-1">apos deducoes</p>
      </div>
    </div>
  );
}
