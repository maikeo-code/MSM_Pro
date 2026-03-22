/**
 * WaterfallChart — Grafico de cachoeira para P&L.
 *
 * Ideal para mostrar: Receita Bruta → (-Taxas ML) → (-Frete) → (=Receita Liquida)
 *
 * Uso:
 *   const data = [
 *     { name: "Receita Bruta", value: 10000, type: "positive" },
 *     { name: "Taxas ML",      value: -1600, type: "negative" },
 *     { name: "Frete",         value: -400,  type: "negative" },
 *     { name: "Receita Liq.",  value: 8000,  type: "total" },
 *   ];
 *   <WaterfallChart data={data} />
 */
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface WaterfallItem {
  name: string;
  value: number;
  /** "positive" = entrada, "negative" = saida, "total" = barra completa (resultado) */
  type: "positive" | "negative" | "total";
}

interface WaterfallChartProps {
  data: WaterfallItem[];
  height?: number;
}

const COLOR_MAP = {
  positive: "#22c55e",
  negative: "#ef4444",
  total: "#3b82f6",
};

const fmtBRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(Math.abs(v));

interface WaterfallTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: WaterfallItem & { base: number; displayValue: number };
  }>;
}

function WaterfallTooltip({ active, payload }: WaterfallTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-foreground mb-1">{d.name}</p>
      <p
        style={{ color: COLOR_MAP[d.type] }}
        className="font-bold"
      >
        {d.type === "negative" ? "-" : ""}{fmtBRL(d.value)}
      </p>
    </div>
  );
}

export function WaterfallChart({ data, height = 300 }: WaterfallChartProps) {
  // Calcula o "base" (ponto de partida invisible) e displayValue para cada barra
  let running = 0;
  const chartData = data.map((item) => {
    if (item.type === "total") {
      return {
        ...item,
        base: 0,
        displayValue: Math.abs(item.value),
      };
    }
    const base = running;
    const displayValue = Math.abs(item.value);
    if (item.type === "positive") {
      running += item.value;
    } else {
      running += item.value; // value is already negative
    }
    return { ...item, base, displayValue };
  });

  const allValues = chartData.flatMap((d) => [d.base, d.base + d.displayValue]);
  const yMin = Math.min(0, ...allValues) * 1.05;
  const yMax = Math.max(...allValues) * 1.1;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={chartData}
        margin={{ top: 10, right: 20, left: 10, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground) / 0.15)" />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={[yMin, yMax]}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => v >= 1000 ? `R$${(v / 1000).toFixed(0)}k` : `R$${v}`}
        />
        <Tooltip content={<WaterfallTooltip />} />
        <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1} />

        {/* Barra invisivel de base (spacer) — sem tooltip */}
        <Bar dataKey="base" stackId="stack" fill="transparent" legendType="none" />

        {/* Barra visivel com cor por tipo */}
        <Bar dataKey="displayValue" stackId="stack" radius={[4, 4, 0, 0]} maxBarSize={56} legendType="none">
          {chartData.map((entry, idx) => (
            <Cell
              key={idx}
              fill={COLOR_MAP[entry.type]}
              fillOpacity={entry.type === "total" ? 1 : 0.85}
            />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}
