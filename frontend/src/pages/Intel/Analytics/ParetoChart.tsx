import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Line,
  ComposedChart,
  ReferenceLine,
} from "recharts";
import {
  BarChart2,
  TrendingUp,
  Package,
  AlertTriangle,
  CheckCircle2,
  Info,
} from "lucide-react";
import { analyticsService, type ParetoItem } from "@/services/intel/analyticsService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

// ─── Period selector ──────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { value: 7, label: "7 dias" },
  { value: 15, label: "15 dias" },
  { value: 30, label: "30 dias" },
  { value: 60, label: "60 dias" },
] as const;

type PeriodValue = (typeof PERIOD_OPTIONS)[number]["value"];

// ─── Helpers de cor por classificacao ─────────────────────────────────────────
function classificationColor(c: ParetoItem["classification"]): string {
  switch (c) {
    case "core":
      return "#22c55e";
    case "productive":
      return "#eab308";
    case "long_tail":
      return "#94a3b8";
  }
}

function classificationLabel(c: ParetoItem["classification"]): string {
  switch (c) {
    case "core":
      return "Core";
    case "productive":
      return "Produtivo";
    case "long_tail":
      return "Cauda Longa";
  }
}

function classificationBadge(c: ParetoItem["classification"]) {
  const base = "text-xs font-semibold px-2 py-0.5 rounded-full";
  switch (c) {
    case "core":
      return cn(base, "bg-green-100 text-green-700");
    case "productive":
      return cn(base, "bg-yellow-100 text-yellow-700");
    case "long_tail":
      return cn(base, "bg-slate-100 text-slate-600");
  }
}

function riskBadge(risk: "high" | "medium" | "low") {
  const base = "inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full";
  switch (risk) {
    case "high":
      return (
        <span className={cn(base, "bg-red-100 text-red-700")}>
          <AlertTriangle className="h-3 w-3" />
          Risco Alto
        </span>
      );
    case "medium":
      return (
        <span className={cn(base, "bg-yellow-100 text-yellow-700")}>
          <Info className="h-3 w-3" />
          Risco Medio
        </span>
      );
    case "low":
      return (
        <span className={cn(base, "bg-green-100 text-green-700")}>
          <CheckCircle2 className="h-3 w-3" />
          Risco Baixo
        </span>
      );
  }
}

// ─── Tooltip customizado do grafico Pareto ────────────────────────────────────
function ParetoTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: {
    name: string;
    value: number;
    payload: ParetoItem & { label: string };
  }[];
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs max-w-xs">
      <p className="font-semibold text-gray-800 mb-2 leading-snug">{item.title}</p>
      <p className="text-gray-500 font-mono mb-2">{item.mlb_id}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Receita:</span>
          <span className="font-semibold text-gray-900">
            {formatCurrency(item.revenue_30d)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">% do total:</span>
          <span className="font-semibold text-gray-900">
            {formatPercent(item.revenue_pct)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">% acumulado:</span>
          <span className="font-semibold text-gray-900">
            {formatPercent(item.cumulative_pct)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Pagina ParetoChart ───────────────────────────────────────────────────────
export default function ParetoChart() {
  const [period, setPeriod] = useState<PeriodValue>(30);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["intel-pareto", period],
    queryFn: () => analyticsService.getPareto(period),
    staleTime: 10 * 60 * 1000,
    retry: 2,
  });

  // Prepara dados para o grafico (limitar a 30 itens para legibilidade)
  const chartData = (data?.items ?? []).slice(0, 30).map((item) => ({
    ...item,
    label: item.mlb_id,
    barColor: classificationColor(item.classification),
  }));

  const coreCount = data?.core_count ?? 0;
  const totalItems = data?.items.length ?? 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart2 className="h-6 w-6 text-violet-600" />
            <h1 className="text-3xl font-bold text-foreground">Pareto 80/20</h1>
          </div>
          <p className="text-muted-foreground">
            Identifique quais anuncios geram 80% da sua receita
          </p>
        </div>

        {/* Period selector */}
        <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPeriod(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                period === opt.value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Erro ao carregar dados do Pareto. Verifique se o backend esta online e tente novamente.
        </div>
      )}

      {/* ─── KPI Cards ──────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {/* Receita Total */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground font-medium">Receita Total</p>
            <TrendingUp className="h-4 w-4 text-muted-foreground/40" />
          </div>
          <p className="text-2xl font-bold text-foreground">
            {isLoading ? "..." : formatCurrency(data?.total_revenue ?? 0)}
          </p>
          <p className="text-xs text-muted-foreground">Ultimos {period} dias</p>
        </div>

        {/* Anuncios Core */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground font-medium">Anuncios Core</p>
            <Package className="h-4 w-4 text-muted-foreground/40" />
          </div>
          <p className="text-2xl font-bold text-green-600">
            {isLoading ? "..." : coreCount}
          </p>
          <p className="text-xs text-muted-foreground">
            de {totalItems} anuncios ({totalItems > 0 ? ((coreCount / totalItems) * 100).toFixed(0) : 0}% do portfolio)
          </p>
        </div>

        {/* Receita dos Core */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground font-medium">Receita Core</p>
            <BarChart2 className="h-4 w-4 text-muted-foreground/40" />
          </div>
          <p className="text-2xl font-bold text-violet-600">
            {isLoading ? "..." : formatPercent(data?.core_revenue_pct ?? 0)}
          </p>
          <p className="text-xs text-muted-foreground">Da receita total gerada pelos core</p>
        </div>

        {/* Risco de Concentracao */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground font-medium">Concentracao</p>
            <AlertTriangle className="h-4 w-4 text-muted-foreground/40" />
          </div>
          <div className="mt-1">
            {isLoading ? (
              <span className="text-sm text-muted-foreground">...</span>
            ) : (
              riskBadge(data?.concentration_risk ?? "low")
            )}
          </div>
          <p className="text-xs text-muted-foreground">Risco de dependencia de poucos anuncios</p>
        </div>
      </div>

      {/* ─── Grafico Pareto ──────────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">
              Curva Pareto — Receita por Anuncio
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Barras = receita individual | Linha = % acumulada | Linha vermelha = limite 80%
            </p>
          </div>
          {/* Legenda de cores */}
          <div className="hidden md:flex items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-green-500 inline-block" />
              Core
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-yellow-400 inline-block" />
              Produtivo
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm bg-slate-400 inline-block" />
              Cauda Longa
            </span>
          </div>
        </div>

        <div className="p-6">
          {isLoading ? (
            <div className="h-80 flex items-center justify-center text-muted-foreground text-sm">
              Carregando dados do Pareto...
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-80 flex items-center justify-center text-muted-foreground text-sm">
              Nenhum dado disponivel. Sincronize seus anuncios para gerar o Pareto.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={360}>
              <ComposedChart
                data={chartData}
                margin={{ top: 5, right: 30, left: 20, bottom: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 9, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                  angle={-45}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) =>
                    v >= 1000 ? `R$${(v / 1000).toFixed(0)}k` : `R$${v}`
                  }
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip content={<ParetoTooltip />} />
                <ReferenceLine
                  yAxisId="right"
                  y={80}
                  stroke="#ef4444"
                  strokeDasharray="6 3"
                  strokeWidth={1.5}
                />
                <Bar
                  yAxisId="left"
                  dataKey="revenue_30d"
                  name="Receita"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={32}
                  fill="#22c55e"
                >
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.mlb_id}
                      fill={classificationColor(entry.classification)}
                    />
                  ))}
                </Bar>
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="cumulative_pct"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                  name="% Acumulado"
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ─── Tabela detalhada ─────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-foreground">
            Classificacao Completa dos Anuncios
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Ordenado por receita (maior primeiro)
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">#</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Anuncio</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Receita</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">% do Total</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">% Acumulado</th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">Classificacao</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : (data?.items ?? []).length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-muted-foreground">
                    Nenhum dado encontrado para o periodo selecionado.
                  </td>
                </tr>
              ) : (
                (data?.items ?? []).map((item, idx) => (
                  <tr
                    key={item.mlb_id}
                    className="border-b hover:bg-muted/50 transition-colors"
                  >
                    <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                      {idx + 1}
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground text-xs leading-snug line-clamp-1 max-w-xs">
                        {item.title}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">
                        {item.mlb_id}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-green-600">
                      {formatCurrency(item.revenue_30d)}
                    </td>
                    <td className="px-4 py-3 text-right text-foreground">
                      {formatPercent(item.revenue_pct)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={cn(
                          "font-medium",
                          item.cumulative_pct <= 80
                            ? "text-violet-600"
                            : "text-muted-foreground"
                        )}
                      >
                        {formatPercent(item.cumulative_pct)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={classificationBadge(item.classification)}>
                        {classificationLabel(item.classification)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
