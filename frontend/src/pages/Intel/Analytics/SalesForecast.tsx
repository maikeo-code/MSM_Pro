import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Package,
} from "lucide-react";
import { analyticsService, type ForecastPoint } from "@/services/intel/analyticsService";
import listingsService from "@/services/listingsService";
import { formatPercent, cn } from "@/lib/utils";

// ─── Opcoes de historico ───────────────────────────────────────────────────────
const HISTORY_OPTIONS = [
  { value: 30, label: "30 dias" },
  { value: 60, label: "60 dias" },
  { value: 90, label: "90 dias" },
] as const;

type HistoryValue = (typeof HISTORY_OPTIONS)[number]["value"];

// ─── Badge de tendencia ───────────────────────────────────────────────────────
function TrendBadge({ trend }: { trend: "up" | "down" | "stable" }) {
  switch (trend) {
    case "up":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-green-100 text-green-700">
          <TrendingUp className="h-4 w-4" />
          Alta
        </span>
      );
    case "down":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-red-100 text-red-700">
          <TrendingDown className="h-4 w-4" />
          Queda
        </span>
      );
    case "stable":
      return (
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-1.5 rounded-full bg-slate-100 text-slate-700">
          <Minus className="h-4 w-4" />
          Estavel
        </span>
      );
  }
}

// ─── Tooltip customizado ──────────────────────────────────────────────────────
function ForecastTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 mb-1">
          <span
            className="h-2 w-2 rounded-full inline-block"
            style={{ background: p.color }}
          />
          <span className="text-gray-600">{p.name}:</span>
          <span className="font-medium text-gray-900">
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Prepara dados combinados para o grafico ──────────────────────────────────
function buildChartData(
  forecast7d: ForecastPoint[],
  forecast30d: ForecastPoint[]
) {
  // Usa o forecast 30d como base (inclui os 7d)
  return forecast30d.map((point) => {
    const f7 = forecast7d.find((p) => p.date === point.date);
    return {
      date: point.date.slice(8, 10) + "/" + point.date.slice(5, 7), // DD/MM
      previsao_30d: point.predicted_sales,
      limite_inf_30d: point.lower_bound,
      limite_sup_30d: point.upper_bound,
      previsao_7d: f7?.predicted_sales ?? null,
      limite_inf_7d: f7?.lower_bound ?? null,
      limite_sup_7d: f7?.upper_bound ?? null,
    };
  });
}

// ─── Pagina SalesForecast ─────────────────────────────────────────────────────
export default function SalesForecast() {
  const [selectedMlbId, setSelectedMlbId] = useState<string>("");
  const [history, setHistory] = useState<HistoryValue>(60);

  // Busca listagens para o dropdown
  const { data: listings } = useQuery({
    queryKey: ["listings", "today"],
    queryFn: () => listingsService.list("today"),
    staleTime: 60 * 1000,
    retry: 2,
  });

  const mlbOptions = listings ?? [];

  // Busca forecast quando um MLB esta selecionado
  const { data: forecast, isLoading, isError } = useQuery({
    queryKey: ["intel-forecast", selectedMlbId, history],
    queryFn: () => analyticsService.getForecast(selectedMlbId, history),
    staleTime: 10 * 60 * 1000,
    enabled: !!selectedMlbId,
    retry: 2,
  });

  const chartData =
    forecast
      ? buildChartData(forecast.forecast_7d, forecast.forecast_30d)
      : [];

  const selectedListing = mlbOptions.find((l) => l.mlb_id === selectedMlbId);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="h-6 w-6 text-blue-600" />
          <h1 className="text-3xl font-bold text-foreground">Projecao de Vendas</h1>
        </div>
        <p className="text-muted-foreground">
          Previsao de vendas com intervalo de confianca por anuncio
        </p>
      </div>

      {/* ─── Controles ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
        {/* Dropdown de anuncio */}
        <div className="flex flex-col gap-1 w-full sm:max-w-sm">
          <label className="text-xs font-medium text-muted-foreground">
            Selecionar Anuncio
          </label>
          <select
            value={selectedMlbId}
            onChange={(e) => setSelectedMlbId(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">-- Escolha um anuncio --</option>
            {mlbOptions.map((l) => (
              <option key={l.mlb_id} value={l.mlb_id}>
                {l.mlb_id} — {l.title.slice(0, 50)}{l.title.length > 50 ? "..." : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Selector de historico */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">
            Historico de Referencia
          </label>
          <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
            {HISTORY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setHistory(opt.value)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  history === opt.value
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Estado vazio: nenhum anuncio selecionado */}
      {!selectedMlbId && (
        <div className="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-12 text-center">
          <Package className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground font-medium">
            Selecione um anuncio acima para visualizar a projecao de vendas
          </p>
        </div>
      )}

      {/* Erro */}
      {isError && selectedMlbId && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Erro ao carregar previsao. O endpoint de forecast pode nao estar disponivel ainda.
        </div>
      )}

      {/* ─── Cards de resumo do forecast ──────────────────────────────────────── */}
      {forecast && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {/* Titulo do anuncio selecionado */}
            <div className="sm:col-span-2 rounded-lg border bg-card p-5 flex flex-col gap-2">
              <p className="text-xs font-medium text-muted-foreground">Anuncio Analisado</p>
              <p className="text-base font-semibold text-foreground leading-snug">
                {selectedListing?.title ?? forecast.listing_mlb_id}
              </p>
              <p className="text-xs text-muted-foreground font-mono">
                {forecast.listing_mlb_id}
              </p>
            </div>

            {/* Tendencia + Confianca */}
            <div className="rounded-lg border bg-card p-5 flex flex-col gap-3">
              <p className="text-xs font-medium text-muted-foreground">Tendencia</p>
              <TrendBadge trend={forecast.trend} />
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">Confianca do modelo</p>
                <p className="text-sm font-bold text-foreground">
                  {formatPercent(forecast.confidence * 100)}
                </p>
              </div>
              {/* Barra de confianca */}
              <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    forecast.confidence >= 0.7
                      ? "bg-green-500"
                      : forecast.confidence >= 0.5
                      ? "bg-yellow-400"
                      : "bg-red-400"
                  )}
                  style={{ width: `${(forecast.confidence * 100).toFixed(0)}%` }}
                />
              </div>
            </div>
          </div>

          {/* ─── Grafico de Previsao ───────────────────────────────────────────── */}
          <div className="rounded-lg border bg-card shadow-sm mb-6">
            <div className="px-6 py-4 border-b">
              <h2 className="text-base font-semibold text-foreground">
                Projecao de Vendas — Proximos 30 dias
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Area preenchida = intervalo de confianca | Linhas = previsao central | Linha verde = hoje
              </p>
            </div>
            <div className="p-6">
              {isLoading ? (
                <div className="h-80 flex items-center justify-center text-muted-foreground text-sm">
                  Carregando previsao...
                </div>
              ) : chartData.length === 0 ? (
                <div className="h-80 flex items-center justify-center text-muted-foreground text-sm">
                  Sem dados de previsao disponiveis para este anuncio.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={340}>
                  <AreaChart
                    data={chartData}
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <defs>
                      <linearGradient id="gradPrevisao7d" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradPrevisao30d" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "#9ca3af" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#9ca3af" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => v.toFixed(0)}
                    />
                    <Tooltip content={<ForecastTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 12, paddingTop: 16 }} />

                    {/* Linha "Hoje" — demarcacao entre historico e previsao */}
                    {(() => {
                      const today = new Date();
                      const todayLabel = String(today.getDate()).padStart(2, "0") + "/" + String(today.getMonth() + 1).padStart(2, "0");
                      return (
                        <ReferenceLine
                          x={todayLabel}
                          stroke="#10b981"
                          strokeWidth={2}
                          strokeDasharray="4 3"
                          label={{ value: "Hoje", position: "top", fill: "#10b981", fontSize: 10 }}
                        />
                      );
                    })()}

                    {/* Banda de confianca 30d */}
                    <Area
                      type="monotone"
                      dataKey="limite_sup_30d"
                      stroke="none"
                      fill="url(#gradPrevisao30d)"
                      fillOpacity={1}
                      name="Limite Sup. 30d"
                      legendType="none"
                    />
                    <Area
                      type="monotone"
                      dataKey="limite_inf_30d"
                      stroke="none"
                      fillOpacity={0}
                      name="Limite Inf. 30d"
                      legendType="none"
                    />

                    {/* Previsao 30d */}
                    <Area
                      type="monotone"
                      dataKey="previsao_30d"
                      stroke="#a78bfa"
                      strokeWidth={2}
                      strokeDasharray="6 3"
                      fill="none"
                      name="Previsao 30d"
                      dot={false}
                    />

                    {/* Banda de confianca 7d */}
                    <Area
                      type="monotone"
                      dataKey="limite_sup_7d"
                      stroke="none"
                      fill="url(#gradPrevisao7d)"
                      name="Limite Sup. 7d"
                      legendType="none"
                    />

                    {/* Previsao 7d (linha solida mais destacada) */}
                    <Area
                      type="monotone"
                      dataKey="previsao_7d"
                      stroke="#3b82f6"
                      strokeWidth={2.5}
                      fill="none"
                      name="Previsao 7d"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* ─── Tabela de pontos de previsao ─────────────────────────────────── */}
          <div className="rounded-lg border bg-card shadow-sm">
            <div className="px-6 py-4 border-b">
              <h2 className="text-base font-semibold text-foreground">
                Detalhes da Projecao — 7 dias
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium text-muted-foreground">Data</th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">Previsao</th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">Minimo</th>
                    <th className="px-4 py-3 text-right font-medium text-muted-foreground">Maximo</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.forecast_7d.map((point) => (
                    <tr
                      key={point.date}
                      className="border-b hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                        {new Date(point.date).toLocaleDateString("pt-BR", {
                          day: "2-digit",
                          month: "2-digit",
                          weekday: "short",
                        })}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-blue-600">
                        {point.predicted_sales.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right text-muted-foreground">
                        {point.lower_bound.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right text-muted-foreground">
                        {point.upper_bound.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
