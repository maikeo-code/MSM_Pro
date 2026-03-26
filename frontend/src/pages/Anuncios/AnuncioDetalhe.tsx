import React from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  TrendingUp,
  Zap,
  Link2,
  Link2Off,
  RefreshCw,
  ArrowLeft,
} from "lucide-react";
import listingsService from "@/services/listingsService";
import productsService from "@/services/productsService";
import competitorsService from "@/services/competitorsService";
import { formatCurrency, formatDate, cn } from "@/lib/utils";
import { ConsultorDrawer } from "@/components/ConsultorDrawer";

// ─── Componentes extraídos ────────────────────────────────────────────────────
import { AnuncioHeader } from "./components/AnuncioHeader";
import { AnuncioKpiCards } from "./components/AnuncioKpiCards";
import { MetricasAvancadas } from "./components/MetricasAvancadas";
import { CalculadoraMargem } from "./components/CalculadoraMargem";
import { PerformanceCharts } from "./components/PerformanceCharts";
import { PriceBandsTable } from "./components/PriceBandsTable";
import { ConcorrenteCard } from "./components/ConcorrenteCard";
import { SearchPosition } from "./components/SearchPosition";
import { PriceHistory } from "./components/PriceHistory";
import type { ChartView, ChartDataPoint } from "./components/types";

// ─── Tipos locais (apenas o que o componente principal ainda usa) ─────────────
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

export default function AnuncioDetalhe() {
  const { mlbId } = useParams<{ mlbId: string }>();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [days, setDays] = React.useState(30);
  const initialSimPreco = searchParams.get("simPreco") ?? "";
  const [simPreco, setSimPreco] = React.useState<string>(initialSimPreco);
  const [selectedProductId, setSelectedProductId] = React.useState<string>("");
  const [chartView, setChartView] = React.useState<ChartView>("vendas");

  // ─── Consultor IA ──────────────────────────────────────────────────────────
  const [consultorAberto, setConsultorAberto] = React.useState(false);
  // States antigos removidos — chatbot agora é auto-gerenciado

  const { data: analysis, isLoading, error, refetch } = useQuery({
    queryKey: ["listing-analysis", mlbId, days],
    queryFn: () => listingsService.getAnalysis(mlbId!, days),
    enabled: !!mlbId,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
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

  // Debounce simPreco para evitar queries excessivas
  const [debouncedPreco, setDebouncedPreco] = React.useState<number>(analysis?.listing.price ?? 0);
  React.useEffect(() => {
    const timer = setTimeout(() => {
      const precoNum = simPreco !== "" ? parseFloat(simPreco) : (analysis?.listing.price ?? 0);
      setDebouncedPreco(isNaN(precoNum) ? 0 : precoNum);
    }, 500);
    return () => clearTimeout(timer);
  }, [simPreco, analysis?.listing.price]);

  const { data: margem, isLoading: margemLoading } = useQuery({
    queryKey: ["margem", mlbId, debouncedPreco],
    queryFn: () => listingsService.getMargem(mlbId!, debouncedPreco),
    enabled: !!mlbId && debouncedPreco > 0,
  });

  const linkSkuMutation = useMutation({
    mutationFn: ({ productId }: { productId: string | null }) =>
      listingsService.linkSku(mlbId!, productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listing-analysis", mlbId] });
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    },
  });

  // Buscar listing_id interno para poder consultar competitors
  const listingIdInterno = analysis?.snapshots?.[0]?.listing_id ?? null;

  const { data: competitorsList } = useQuery({
    queryKey: ["competitors-by-listing", listingIdInterno],
    queryFn: () => competitorsService.listByListing(listingIdInterno!),
    enabled: !!listingIdInterno && !!analysis?.competitor,
  });

  // Encontrar o competitor_id interno pelo mlb_id do competitor
  const competitorId = React.useMemo(() => {
    if (!competitorsList || !analysis?.competitor) return null;
    const found = competitorsList.find(
      (c) => c.mlb_id === analysis.competitor?.mlb_id
    );
    return found?.id ?? null;
  }, [competitorsList, analysis?.competitor]);

  const { data: competitorHistory } = useQuery({
    queryKey: ["competitor-history", competitorId, days],
    queryFn: () => competitorsService.getHistory(competitorId!, days),
    enabled: !!competitorId,
  });

  if (error) {
    const statusCode = (error as any)?.response?.status;
    const detail = (error as any)?.response?.data?.detail;
    const errorMsg = detail
      ? String(detail)
      : statusCode === 404
        ? `Anuncio ${mlbId} nao encontrado.`
        : statusCode === 401
          ? "Sessao expirada. Faca login novamente."
          : "Erro ao carregar analise. Verifique sua conexao.";

    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-4 text-sm text-destructive">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
            <div className="flex-1">
              <p className="font-semibold mb-1">Erro ao carregar analise</p>
              <p>{errorMsg}</p>
              {statusCode && <p className="text-xs mt-1 opacity-70">Codigo: {statusCode}</p>}
              <div className="mt-3 flex items-center gap-3">
                <button
                  onClick={() => refetch()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-destructive/20 px-3 py-1.5 text-xs font-medium hover:bg-destructive/30 transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Tentar novamente
                </button>
                <button
                  onClick={() => navigate(-1)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-destructive/20 px-3 py-1.5 text-xs font-medium hover:bg-destructive/10 transition-colors"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Voltar
                </button>
              </div>
            </div>
          </div>
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
  // Conversão calculada como (total vendas / total visitas) * 100 — não como média de %
  const avgConversion = totalVisitas > 0 ? (totalSales / totalVisitas) * 100 : 0;
  const currentPrice = analysis.listing.price;
  const lastSnapshot = analysis.snapshots[analysis.snapshots.length - 1];
  const lastStock = lastSnapshot ? lastSnapshot.stock : 0;

  // ─── Metricas extras ─────────────────────────────────────────────────────────
  const rpv = totalVisitas > 0 ? totalReceita / totalVisitas : null;
  const totalCancelled = analysis.snapshots.reduce((sum, s) => sum + (s.cancelled_orders ?? 0), 0);
  const totalOrders = analysis.snapshots.reduce((sum, s) => sum + (s.orders_count ?? s.sales_today), 0);
  const taxaCancelamento = totalOrders > 0 ? (totalCancelled / totalOrders) * 100 : null;

  // ITEM 1: Preco medio por VENDA (receita / pedidos)
  const precoMedioPorVenda = totalOrders > 0 ? totalReceita / totalOrders : null;

  // ITEMS 3 e 4: Cancelamentos e devoluções com valor em R$
  const totalCancelledRevenue = analysis.snapshots.reduce((sum, s) => sum + (s.cancelled_revenue ?? 0), 0);
  const totalReturnsCount = analysis.snapshots.reduce((sum, s) => sum + (s.returns_count ?? 0), 0);
  const totalReturnsRevenue = analysis.snapshots.reduce((sum, s) => sum + (s.returns_revenue ?? 0), 0);

  // ITEM 5: Vendas concluidas = receita bruta - cancelamentos - devoluções
  const vendasConcluidas = totalReceita - totalCancelledRevenue - totalReturnsRevenue;

  // Dias para zerar (usa full_stock do backend)
  const diasParaZerar = analysis.full_stock.days_until_stockout_7d;

  return (
    <div className="p-8 space-y-6">
      {/* Drawer do Consultor IA */}
      <ConsultorDrawer
        aberto={consultorAberto}
        onFechar={() => setConsultorAberto(false)}
      />

      {/* ─── Header ──────────────────────────────────────────────────────────── */}
      <AnuncioHeader
        analysis={analysis}
        days={days}
        setDays={setDays}
        onConsultor={() => setConsultorAberto(true)}
      />

      {/* ─── KPI Cards ──────────────────────────────────────────────────────── */}
      <AnuncioKpiCards
        totalSales={totalSales}
        totalOrders={totalOrders}
        avgConversion={avgConversion}
        totalVisitas={totalVisitas}
        currentPrice={currentPrice}
        precoMedioPorVenda={precoMedioPorVenda}
        lastStock={lastStock}
        diasParaZerar={diasParaZerar}
        totalReceita={totalReceita}
        vendasConcluidas={vendasConcluidas}
      />

      {/* ─── Card de metricas avancadas ──────────────────────────────────────── */}
      <MetricasAvancadas
        rpv={rpv}
        totalVisitas={totalVisitas}
        taxaCancelamento={taxaCancelamento}
        totalCancelled={totalCancelled}
        totalCancelledRevenue={totalCancelledRevenue}
        totalReturnsCount={totalReturnsCount}
        totalReturnsRevenue={totalReturnsRevenue}
        diasParaZerar={diasParaZerar}
        velocity7d={analysis.full_stock.velocity_7d}
      />

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
      <CalculadoraMargem
        simPreco={simPreco}
        setSimPreco={setSimPreco}
        currentPrice={currentPrice}
        margem={margem}
        margemLoading={margemLoading}
        hasSku={!!analysis.sku?.id}
        mlbId={mlbId}
      />

      {/* ─── Posicao na Busca ──────────────────────────────────────────────────── */}
      <SearchPosition mlbId={mlbId!} />

      {/* ─── Historico de Precos ───────────────────────────────────────────────── */}
      <PriceHistory mlbId={mlbId!} />

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

      {/* ─── Graficos com toggle ──────────────────────────────────────────────── */}
      <PerformanceCharts
        chartData={chartData}
        chartView={chartView}
        setChartView={setChartView}
        priceChanges={priceChanges}
      />

      {/* ─── Price Bands ─────────────────────────────────────────────────────── */}
      <PriceBandsTable priceBands={analysis.price_bands} />

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
        <ConcorrenteCard
          competitor={analysis.competitor}
          listing={analysis.listing}
          competitorId={competitorId}
          competitorHistory={competitorHistory}
          mySnapshots={analysis.snapshots}
        />
      )}
    </div>
  );
}
