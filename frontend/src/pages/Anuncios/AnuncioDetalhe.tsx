import React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertCircle,
  TrendingUp,
  Zap,
  Package,
  Target,
  Star,
} from "lucide-react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import listingsService, { ListingHealth } from "@/services/listingsService";
import { formatCurrency, formatDate, formatPercent, cn } from "@/lib/utils";

const AlertSeverityColors = {
  critical: "bg-red-50 border-red-200 text-red-900",
  warning: "bg-yellow-50 border-yellow-200 text-yellow-900",
  info: "bg-blue-50 border-blue-200 text-blue-900",
};

const AlertIconMap = {
  critical: <AlertCircle className="h-4 w-4" />,
  warning: <Zap className="h-4 w-4" />,
  info: <TrendingUp className="h-4 w-4" />,
};

interface ChartDataPoint {
  date: string;
  vendas: number;
  conversao: number;
  visitas: number;
  preco: number;
}

export default function AnuncioDetalhe() {
  const { mlbId } = useParams<{ mlbId: string }>();
  const [days, setDays] = React.useState(30);

  const { data: analysis, isLoading, error } = useQuery({
    queryKey: ["listing-analysis", mlbId, days],
    queryFn: () => listingsService.getAnalysis(mlbId!, days),
    enabled: !!mlbId,
  });

  const { data: health } = useQuery({
    queryKey: ["listing-health", mlbId],
    queryFn: () => listingsService.getListingHealth(mlbId!),
    enabled: !!mlbId,
  });

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar análise. Verifique sua conexão.
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-center py-12 text-muted-foreground">
          Carregando análise completa...
        </div>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  // Preparar dados do gráfico
  const chartData: ChartDataPoint[] = analysis.snapshots.map((snap) => {
    return {
      date: formatDate(snap.captured_at),
      vendas: snap.sales_today,
      conversao: snap.conversion_rate ? parseFloat(snap.conversion_rate.toString()) : 0,
      visitas: snap.visits,
      preco: parseFloat(snap.price.toString()),
    };
  });

  // Detectar mudanças de preço para ReferenceLine
  const priceChanges = chartData.reduce((acc: string[], point, index) => {
    if (index > 0 && point.preco !== chartData[index - 1].preco) {
      acc.push(point.date);
    }
    return acc;
  }, []);

  // Cálculos de KPI
  const totalSales = analysis.snapshots.reduce((sum, s) => sum + s.sales_today, 0);
  const avgConversion = analysis.snapshots.length
    ? analysis.snapshots.reduce((sum, s) => sum + (Number(s.conversion_rate) || 0), 0) /
      analysis.snapshots.length
    : 0;
  const currentPrice = analysis.listing.price;
  const lastSnapshot = analysis.snapshots[analysis.snapshots.length - 1];
  const lastStock = lastSnapshot ? lastSnapshot.stock : 0;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="mb-8">
        <Link
          to="/anuncios"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para Anúncios
        </Link>

        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              {analysis.listing.thumbnail && (
                <img
                  src={analysis.listing.thumbnail}
                  alt={analysis.listing.title}
                  className="h-12 w-12 rounded object-cover"
                />
              )}
              <div>
                <h1 className="text-3xl font-bold text-foreground">
                  {analysis.listing.title}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {analysis.listing.mlb_id}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 mt-4">
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-3 py-1 text-sm font-medium",
                  analysis.listing.listing_type === "full"
                    ? "bg-purple-100 text-purple-700"
                    : analysis.listing.listing_type === "premium"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-700",
                )}
              >
                {analysis.listing.listing_type}
              </span>

              <span className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-green-100 text-green-700">
                {analysis.listing.status}
              </span>

              {analysis.sku && (
                <span className="text-sm text-muted-foreground">
                  SKU: <strong>{analysis.sku.sku}</strong>
                </span>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            {[7, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={cn(
                  "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "border bg-background hover:bg-accent",
                )}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Vendas Total</p>
              <p className="text-2xl font-bold text-foreground mt-2">
                {totalSales}
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-primary/50" />
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Conversão Média</p>
              <p className="text-2xl font-bold text-foreground mt-2">
                {formatPercent(avgConversion)}
              </p>
            </div>
            <Target className="h-8 w-8 text-primary/50" />
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Preço Atual</p>
              <p className="text-2xl font-bold text-foreground mt-2">
                {formatCurrency(currentPrice)}
              </p>
            </div>
            <Zap className="h-8 w-8 text-primary/50" />
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Estoque</p>
              <p className="text-2xl font-bold text-foreground mt-2">
                {lastStock}
              </p>
            </div>
            <Package className="h-8 w-8 text-primary/50" />
          </div>
        </div>
      </div>

      {/* Health Card */}
      {health && (
        <div className="rounded-lg border bg-card">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Saúde do Anúncio</h2>
              <p className="text-sm text-muted-foreground">Score baseado em estoque, conversão e dados do anúncio</p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`text-3xl font-bold ${
                health.color === "green" ? "text-green-600" :
                health.color === "yellow" ? "text-yellow-600" :
                health.color === "orange" ? "text-orange-600" :
                "text-red-600"
              }`}>
                {health.score}
              </div>
              <div className="text-sm text-muted-foreground">/100</div>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
                health.color === "green" ? "bg-green-100 text-green-700" :
                health.color === "yellow" ? "bg-yellow-100 text-yellow-700" :
                health.color === "orange" ? "bg-orange-100 text-orange-700" :
                "bg-red-100 text-red-700"
              }`}>
                {health.label}
              </span>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              {health.checks.map((check, i) => (
                <div key={i} className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2 flex-1">
                    <span className={check.ok ? "text-green-500" : "text-red-400"}>
                      {check.ok ? "✓" : "✗"}
                    </span>
                    <div>
                      <span className="text-sm font-medium">{check.item}</span>
                      {check.detail && <span className="ml-2 text-xs text-muted-foreground">{check.detail}</span>}
                      {!check.ok && check.action && (
                        <p className="text-xs text-muted-foreground mt-0.5">{check.action}</p>
                      )}
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0">{check.points}/{check.max} pts</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main Chart */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">
          Preço vs Conversão vs Visitas vs Vendas
        </h2>
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              angle={-45}
              height={80}
            />
            <YAxis
              yAxisId="left"
              orientation="left"
              tickFormatter={(v) => `R$${v.toFixed(0)}`}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tickFormatter={(v) => `${v.toFixed(0)}`}
            />
            <Tooltip
              formatter={(value, name) => {
                if (name === "preco") return [formatCurrency(Number(value)), "Preço"];
                if (name === "conversao") return [formatPercent(Number(value)), "Conversão"];
                if (name === "visitas") return [value, "Visitas"];
                if (name === "vendas") return [value, "Vendas"];
                return [value, name];
              }}
              labelFormatter={(label) => `Data: ${label}`}
            />
            <Legend />

            {/* Marcar mudanças de preço */}
            {priceChanges.map((date) => (
              <ReferenceLine
                key={date}
                x={date}
                stroke="#fbbf24"
                strokeDasharray="3 3"
                label={{ value: "Mudança", position: "top", fill: "#f59e0b" }}
              />
            ))}

            <Bar
              yAxisId="left"
              dataKey="vendas"
              fill="#3b82f6"
              opacity={0.6}
              name="Vendas/dia"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="conversao"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              name="Conversão %"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="visitas"
              stroke="#ec4899"
              strokeWidth={2}
              dot={false}
              name="Visitas"
            />
            <Line
              yAxisId="left"
              type="stepAfter"
              dataKey="preco"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              strokeDasharray="5 5"
              name="Preço Base"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Price Bands */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">
          Histograma de Faixas de Preço
        </h2>
        {analysis.price_bands.length === 0 ? (
          <p className="text-muted-foreground">Sem dados para exibir.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                    Faixa de Preço
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Dias
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Vendas/dia
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Conversão
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Receita
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Margem Unit.
                  </th>
                </tr>
              </thead>
              <tbody>
                {analysis.price_bands.map((band, idx) => (
                  <tr
                    key={idx}
                    className={cn(
                      "border-b",
                      band.is_optimal ? "bg-green-50" : ""
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {band.is_optimal && (
                          <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                        )}
                        <span>{band.price_range_label}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">{band.days_count}</td>
                    <td className="px-4 py-3 text-right">
                      {band.avg_sales_per_day.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatPercent(band.avg_conversion)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(band.total_revenue)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(band.avg_margin)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Stock Projection */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Projeção de Estoque</h2>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <p className="text-3xl font-bold text-foreground">
              {analysis.full_stock.available}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              unidades disponíveis
            </p>
          </div>

          <div>
            <div
              className={cn(
                "h-2 rounded-full mb-2",
                analysis.full_stock.status === "critical"
                  ? "bg-red-500"
                  : analysis.full_stock.status === "warning"
                    ? "bg-yellow-500"
                    : analysis.full_stock.status === "excess"
                      ? "bg-blue-500"
                      : "bg-green-500"
              )}
            />
            <p className="text-sm font-medium mb-1">
              {analysis.full_stock.days_until_stockout_7d
                ? `Ruptura em ~${analysis.full_stock.days_until_stockout_7d} dias`
                : "Dados insuficientes"}
            </p>
            <p className="text-xs text-muted-foreground">
              Baseado em velocidade de 7 dias:{" "}
              {analysis.full_stock.velocity_7d.toFixed(1)} und/dia
            </p>
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Projeção 30 dias:</p>
            <p className="text-lg font-semibold text-foreground">
              {analysis.full_stock.days_until_stockout_30d
                ? `~${analysis.full_stock.days_until_stockout_30d} dias`
                : "N/A"}
            </p>
            <p className="text-xs text-muted-foreground">
              Velocidade 30d: {analysis.full_stock.velocity_30d.toFixed(1)} und/dia
            </p>
          </div>
        </div>
      </div>

      {/* Promotions */}
      {analysis.promotions.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Promoções</h2>
          <div className="space-y-4">
            {analysis.promotions.map((promo) => (
              <div key={promo.id} className="border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">{promo.type}</span>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          promo.status === "active"
                            ? "bg-green-100 text-green-700"
                            : promo.status === "programada"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-gray-100 text-gray-700"
                        )}
                      >
                        {promo.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">
                      {promo.discount_pct}% de desconto
                    </p>
                    <p className="text-sm">
                      {formatCurrency(promo.original_price)} →{" "}
                      <span className="font-bold text-green-600">
                        {formatCurrency(promo.final_price)}
                      </span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {promo.start_date} até {promo.end_date}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {analysis.alerts.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Alertas Inteligentes</h2>
          <div className="space-y-3">
            {analysis.alerts.map((alert, idx) => (
              <div
                key={idx}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3",
                  AlertSeverityColors[alert.severity as keyof typeof AlertSeverityColors]
                )}
              >
                {
                  AlertIconMap[
                    alert.severity as keyof typeof AlertIconMap
                  ]
                }
                <div className="flex-1">
                  <p className="font-medium text-sm">{alert.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Competitor */}
      {analysis.competitor && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Concorrente Vinculado</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{analysis.competitor.mlb_id}</p>
              <p className="text-sm text-muted-foreground">
                Preço: {formatCurrency(analysis.competitor.price)}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Atualizado em:{" "}
                {new Date(analysis.competitor.last_updated).toLocaleDateString()}
              </p>
            </div>
            <div className="text-right">
              {analysis.listing.price > analysis.competitor.price ? (
                <div>
                  <p className="text-sm font-medium text-red-600">
                    {(
                      ((analysis.listing.price - analysis.competitor.price) /
                        analysis.listing.price) *
                      100
                    ).toFixed(1)}
                    % mais caro
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium text-green-600">
                    {(
                      ((analysis.competitor.price - analysis.listing.price) /
                        analysis.competitor.price) *
                      100
                    ).toFixed(1)}
                    % mais barato
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
