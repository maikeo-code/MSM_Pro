import React from "react";
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
import {
  BarChart2,
  DollarSign,
  Activity,
  Layers,
} from "lucide-react";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import type { ChartView, ChartDataPoint } from "./types";

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

interface PerformanceChartsProps {
  chartData: ChartDataPoint[];
  chartView: ChartView;
  setChartView: (view: ChartView) => void;
  priceChanges: string[];
}

export function PerformanceCharts({
  chartData,
  chartView,
  setChartView,
  priceChanges,
}: PerformanceChartsProps) {
  return (
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
  );
}
