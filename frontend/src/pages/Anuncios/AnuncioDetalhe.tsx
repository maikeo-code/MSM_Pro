import React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertCircle,
  TrendingUp,
  Zap,
  Package,
  Target,
  Star,
  Link2,
  Link2Off,
  Calculator,
  BarChart2,
  DollarSign,
  Activity,
  Layers,
} from "lucide-react";
import {
  ComposedChart,
  AreaChart,
  Area,
  Bar,
  Line,
  LineChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import listingsService from "@/services/listingsService";
import productsService from "@/services/productsService";
import { formatCurrency, formatDate, formatPercent, cn } from "@/lib/utils";

// ─── Tipos ───────────────────────────────────────────────────────────────────
type ChartView = "vendas" | "preco" | "conversao" | "completo";

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
  receita: number;
  precoMedio: number;
  pedidos: number;
}

// ─── Toggle de grafico ────────────────────────────────────────────────────────
const chartToggleOptions: { key: ChartView; label: string; icon: React.ReactNode }[] = [
  { key: "vendas", label: "Vendas/dia", icon: <BarChart2 className="h-3.5 w-3.5" /> },
  { key: "preco", label: "Preco Medio", icon: <DollarSign className="h-3.5 w-3.5" /> },
  { key: "conversao", label: "Conversao", icon: <Activity className="h-3.5 w-3.5" /> },
  { key: "completo", label: "Visao Completa", icon: <Layers className="h-3.5 w-3.5" /> },
];

// ─── Tooltip customizado ──────────────────────────────────────────────────────
function CustomTooltipVendas({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const data = payload[0];
  return (
    <div className="rounded-lg border bg-card p-3 shadow-md text-xs space-y-1 min-w-[140px]">
      <p className="font-semibold text-foreground border-b pb-1 mb-1">{label}</p>
      <p className="text-muted-foreground">Unidades: <span className="font-medium text-foreground">{data?.value ?? 0}</span></p>
    </div>
  );
}

function CustomTooltipPreco({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card p-3 shadow-md text-xs space-y-1 min-w-[160px]">
      <p className="font-semibold text-foreground border-b pb-1 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-muted-foreground">
          {p.name}: <span className="font-medium text-foreground">{formatCurrency(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export default function AnuncioDetalhe() {
  const { mlbId } = useParams<{ mlbId: string }>();
  const queryClient = useQueryClient();
  const [days, setDays] = React.useState(30);
  const [simPreco, setSimPreco] = React.useState<string>("");
  const [selectedProductId, setSelectedProductId] = React.useState<string>("");
  const [chartView, setChartView] = React.useState<ChartView>("vendas");

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

  const { data: products = [] } = useQuery({
    queryKey: ["products"],
    queryFn: () => productsService.list(),
  });

  const precoSim = simPreco !== "" ? parseFloat(simPreco) : (analysis?.listing.price ?? 0);

  const { data: margem, isLoading: margemLoading } = useQuery({
    queryKey: ["margem", mlbId, precoSim],
    queryFn: () => listingsService.getMargem(mlbId!, precoSim),
    enabled: !!mlbId && precoSim > 0,
  });

  const linkSkuMutation = useMutation({
    mutationFn: ({ productId }: { productId: string | null }) =>
      listingsService.linkSku(mlbId!, productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listing-analysis", mlbId] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
  });

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar analise. Verifique sua conexao.
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-center py-12 text-muted-foreground">
          Carregando analise completa...
        </div>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  // ─── Preparar dados do grafico ──────────────────────────────────────────────
  const chartData: ChartDataPoint[] = analysis.snapshots.map((snap) => {
    const units = snap.sales_today;
    const revenue = snap.revenue ?? 0;
    const avgPrice = snap.avg_selling_price ?? (units > 0 ? revenue / units : parseFloat(snap.price.toString()));
    return {
      date: formatDate(snap.captured_at),
      vendas: units,
      conversao: snap.conversion_rate ? parseFloat(snap.conversion_rate.toString()) : 0,
      visitas: snap.visits,
      preco: parseFloat(snap.price.toString()),
      receita: revenue,
      precoMedio: avgPrice,
      pedidos: snap.orders_count ?? units,
    };
  });

  // Marcar mudancas de preco para ReferenceLine
  const priceChanges = chartData.reduce((acc: string[], point, index) => {
    if (index > 0 && point.preco !== chartData[index - 1].preco) {
      acc.push(point.date);
    }
    return acc;
  }, []);

  // ─── KPIs calculados ────────────────────────────────────────────────────────
  const totalSales = analysis.snapshots.reduce((sum, s) => sum + s.sales_today, 0);
  const totalReceita = analysis.snapshots.reduce((sum, s) => sum + (s.revenue ?? 0), 0);
  const totalVisitas = analysis.snapshots.reduce((sum, s) => sum + s.visits, 0);
  const avgConversion = analysis.snapshots.length
    ? analysis.snapshots.reduce((sum, s) => sum + (Number(s.conversion_rate) || 0), 0) /
      analysis.snapshots.length
    : 0;
  const currentPrice = analysis.listing.price;
  const lastSnapshot = analysis.snapshots[analysis.snapshots.length - 1];
  const lastStock = lastSnapshot ? lastSnapshot.stock : 0;

  // ─── Metricas extras (TAREFA 5) ─────────────────────────────────────────────
  const rpv = totalVisitas > 0 ? totalReceita / totalVisitas : null;
  const totalCancelled = analysis.snapshots.reduce((sum, s) => sum + (s.cancelled_orders ?? 0), 0);
  const totalOrders = analysis.snapshots.reduce((sum, s) => sum + (s.orders_count ?? s.sales_today), 0);
  const taxaCancelamento = totalOrders > 0 ? (totalCancelled / totalOrders) * 100 : null;

  // Dias para zerar (usa full_stock do backend)
  const diasParaZerar = analysis.full_stock.days_until_stockout_7d;

  return (
    <div className="p-8 space-y-6">
      {/* ─── Header ──────────────────────────────────────────────────────────── */}
      <div className="mb-8">
        <Link
          to="/anuncios"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para Anuncios
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
              <span className={cn(
                "inline-flex items-center rounded-full px-3 py-1 text-sm font-medium",
                analysis.listing.listing_type === "full"
                  ? "bg-purple-100 text-purple-700"
                  : analysis.listing.listing_type === "premium"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-700",
              )}>
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

      {/* ─── KPI Cards ──────────────────────────────────────────────────────── */}
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
              <p className="text-sm text-muted-foreground">Conversao Media</p>
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
              <p className="text-sm text-muted-foreground">Preco Atual</p>
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

      {/* ─── TAREFA 5: Card de metricas extras ─────────────────────────────── */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">Metricas Avancadas</h2>
        </div>
        <div className="grid grid-cols-3 gap-6">
          {/* RPV */}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">RPV (Receita por Visita)</p>
            <p className="text-2xl font-bold text-foreground">
              {rpv != null ? formatCurrency(rpv) : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {totalVisitas > 0 ? `${totalVisitas.toLocaleString("pt-BR")} visitas no periodo` : "Sem visitas no periodo"}
            </p>
          </div>

          {/* Taxa de cancelamento */}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Taxa de Cancelamento</p>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold text-foreground">
                {taxaCancelamento != null ? formatPercent(taxaCancelamento) : "—"}
              </p>
              {taxaCancelamento != null && taxaCancelamento > 3 && (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">
                  Alta
                </span>
              )}
              {taxaCancelamento != null && taxaCancelamento <= 3 && taxaCancelamento > 0 && (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">
                  Normal
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {totalCancelled > 0 ? `${totalCancelled} cancelados de ${totalOrders} pedidos` : "Sem cancelamentos no periodo"}
            </p>
          </div>

          {/* Velocidade de venda / Dias para zerar */}
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Velocidade de Venda</p>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold text-foreground">
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
              para zerar estoque (base: velocidade 7d: {analysis.full_stock.velocity_7d.toFixed(1)} und/dia)
            </p>
          </div>
        </div>
      </div>

      {/* ─── SKU Vinculado ─────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold">SKU Vinculado</h2>
          </div>
          {analysis.sku?.id && (
            <button
              onClick={() => {
                setSelectedProductId("");
                linkSkuMutation.mutate({ productId: null });
              }}
              disabled={linkSkuMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
            >
              <Link2Off className="h-3.5 w-3.5" />
              Desvincular
            </button>
          )}
        </div>

        {analysis.sku?.id ? (
          <div className="flex items-center gap-6">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Codigo SKU</p>
              <span className="inline-flex items-center rounded-md bg-primary/10 px-3 py-1 text-sm font-mono font-semibold text-primary">
                {analysis.sku.sku}
              </span>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Custo de Aquisicao</p>
              <p className="text-xl font-bold text-foreground">
                {formatCurrency(analysis.sku.cost)}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Nenhum SKU vinculado. Vincule um produto para calcular margens reais.
            </p>
            <div className="flex items-end gap-3">
              <div className="flex flex-col gap-1 flex-1 max-w-xs">
                <label className="text-xs font-medium text-muted-foreground">Selecionar SKU</label>
                <select
                  value={selectedProductId}
                  onChange={(e) => setSelectedProductId(e.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">-- Escolha um produto --</option>
                  {products
                    .filter((p) => p.is_active)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name} ({formatCurrency(parseFloat(p.cost))})
                      </option>
                    ))}
                </select>
              </div>
              <button
                onClick={() => {
                  if (selectedProductId) {
                    linkSkuMutation.mutate({ productId: selectedProductId });
                  }
                }}
                disabled={!selectedProductId || linkSkuMutation.isPending}
                className="inline-flex items-center gap-1.5 h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                <Link2 className="h-4 w-4" />
                Vincular
              </button>
            </div>
            {linkSkuMutation.isError && (
              <p className="text-sm text-destructive">Erro ao vincular SKU. Tente novamente.</p>
            )}
          </div>
        )}
      </div>

      {/* ─── Calculadora de Margem ─────────────────────────────────────────── */}
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
                  placeholder={String(analysis.listing.price)}
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
                Deixe vazio para usar o preco atual ({formatCurrency(analysis.listing.price)})
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
                {!analysis.sku?.id
                  ? "Vincule um SKU para calcular a margem real."
                  : "Informe um preco para simular."}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ─── Health Card ─────────────────────────────────────────────────────── */}
      {health && (
        <div className="rounded-lg border bg-card">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Saude do Anuncio</h2>
              <p className="text-sm text-muted-foreground">Score baseado em estoque, conversao e dados do anuncio</p>
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

      {/* ─── TAREFA 4: Graficos com toggle ──────────────────────────────────── */}
      <div className="rounded-lg border bg-card p-6">
        {/* Toggle buttons */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">Historico de Performance</h2>
          <div className="flex items-center gap-1 rounded-lg border bg-muted/30 p-1">
            {chartToggleOptions.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setChartView(opt.key)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  chartView === opt.key
                    ? "bg-background shadow-sm text-foreground border"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {opt.icon}
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Grafico: Vendas/dia ── */}
        {chartView === "vendas" && (
          <>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mb-4">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-3 rounded-sm bg-blue-500 opacity-80" />
                Unidades vendidas/dia
              </span>
            </div>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
                <defs>
                  <linearGradient id="colorVendas" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="opacity-40" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} angle={-45} height={80} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomTooltipVendas />} />
                <Area
                  type="monotone"
                  dataKey="vendas"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fill="url(#colorVendas)"
                  name="Unidades/dia"
                />
              </AreaChart>
            </ResponsiveContainer>
          </>
        )}

        {/* ── Grafico: Preco Medio ── */}
        {chartView === "preco" && (
          <>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mb-4">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 bg-blue-500" />
                Preco medio de venda (R$)
              </span>
            </div>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
                <defs>
                  <linearGradient id="colorPreco" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="opacity-40" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} angle={-45} height={80} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `R$${v.toFixed(0)}`} />
                <Tooltip content={<CustomTooltipPreco />} />
                <Area
                  type="monotone"
                  dataKey="precoMedio"
                  stroke="#3B82F6"
                  strokeWidth={2}
                  fill="url(#colorPreco)"
                  name="Preco Medio"
                />
              </AreaChart>
            </ResponsiveContainer>
          </>
        )}

        {/* ── Grafico: Conversao ── */}
        {chartView === "conversao" && (
          <>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mb-4">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 bg-green-500" />
                Conversao diaria (%)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-orange-400" />
                Benchmark 3%
              </span>
            </div>
            <ResponsiveContainer width="100%" height={350}>
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-40" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} angle={-45} height={80} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                <Tooltip
                  formatter={(value) => [`${Number(value).toFixed(2)}%`, "Conversao"]}
                  labelFormatter={(label) => `Data: ${label}`}
                />
                <ReferenceLine y={3} stroke="#f97316" strokeDasharray="4 4" label={{ value: "3% benchmark", position: "right", fill: "#f97316", fontSize: 10 }} />
                <Line
                  type="monotone"
                  dataKey="conversao"
                  stroke="#10B981"
                  strokeWidth={2}
                  dot={false}
                  name="Conversao %"
                />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}

        {/* ── Grafico: Visao Completa (original) ── */}
        {chartView === "completo" && (
          <>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mb-4">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 bg-blue-500" style={{ borderTop: "2px dashed #3b82f6" }} />
                Preco
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 bg-green-500" />
                Conversao
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-3 rounded-sm bg-orange-400 opacity-70" />
                Vendas/dia
              </span>
            </div>
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
                  label={{ value: "Preco (R$)", angle: -90, position: "insideLeft", offset: 10, style: { fontSize: 11 } }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tickFormatter={(v) => `${v.toFixed(0)}`}
                  label={{ value: "Conversao % / Visitas", angle: 90, position: "insideRight", offset: 10, style: { fontSize: 11 } }}
                />
                <YAxis
                  yAxisId="vendas"
                  orientation="left"
                  hide={true}
                  domain={[0, (dataMax: number) => Math.ceil(dataMax * 2)]}
                />
                <Tooltip
                  formatter={(value, name) => {
                    if (name === "Preco Base") return [formatCurrency(Number(value)), "Preco"];
                    if (name === "Conversao %") return [formatPercent(Number(value)), "Conversao"];
                    if (name === "Visitas") return [value, "Visitas"];
                    if (name === "Vendas/dia") return [`${value} und`, "Vendas/dia"];
                    return [value, name];
                  }}
                  labelFormatter={(label) => `Data: ${label}`}
                />
                <Legend />

                {priceChanges.map((date) => (
                  <ReferenceLine
                    key={date}
                    x={date}
                    stroke="#fbbf24"
                    strokeDasharray="3 3"
                    label={{ value: "Mudanca", position: "top", fill: "#f59e0b" }}
                  />
                ))}

                <Bar
                  yAxisId="vendas"
                  dataKey="vendas"
                  fill="#f97316"
                  opacity={0.7}
                  name="Vendas/dia"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="conversao"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                  name="Conversao %"
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
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray="5 5"
                  name="Preco Base"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* ─── Price Bands ─────────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">
          Histograma de Faixas de Preco
        </h2>
        {analysis.price_bands.length === 0 ? (
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
                {analysis.price_bands.map((band, idx) => (
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

      {/* ─── Stock Projection ────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-4">Projecao de Estoque</h2>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <p className="text-3xl font-bold text-foreground">
              {analysis.full_stock.available}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              unidades disponiveis
            </p>
          </div>

          <div>
            <div className={cn(
              "h-2 rounded-full mb-2",
              analysis.full_stock.status === "critical"
                ? "bg-red-500"
                : analysis.full_stock.status === "warning"
                  ? "bg-yellow-500"
                  : analysis.full_stock.status === "excess"
                    ? "bg-blue-500"
                    : "bg-green-500"
            )} />
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
            <p className="text-sm font-medium mb-2">Projecao 30 dias:</p>
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

      {/* ─── Promotions ──────────────────────────────────────────────────────── */}
      {analysis.promotions.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Promocoes</h2>
          <div className="space-y-4">
            {analysis.promotions.map((promo) => (
              <div key={promo.id} className="border rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">{promo.type}</span>
                      <span className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                        promo.status === "active"
                          ? "bg-green-100 text-green-700"
                          : promo.status === "programada"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700"
                      )}>
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
                      {promo.start_date} ate {promo.end_date}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Alerts ──────────────────────────────────────────────────────────── */}
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
                {AlertIconMap[alert.severity as keyof typeof AlertIconMap]}
                <div className="flex-1">
                  <p className="font-medium text-sm">{alert.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Competitor ──────────────────────────────────────────────────────── */}
      {analysis.competitor && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="text-lg font-semibold mb-4">Concorrente Vinculado</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{analysis.competitor.mlb_id}</p>
              <p className="text-sm text-muted-foreground">
                Preco: {formatCurrency(analysis.competitor.price)}
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
