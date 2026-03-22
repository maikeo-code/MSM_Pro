/**
 * PriceGapChart — Grafico de preco meu vs concorrente com area sombreada
 * representando o gap de preco ao longo do tempo.
 *
 * Substitui o LineChart simples do ConcorrenteCard por uma visualizacao
 * que deixa o gap visualmente evidente.
 *
 * Uso:
 *   <PriceGapChart
 *     data={mergedData}  // [{ date, my_price, competitor_price }]
 *     myLabel="Meu Preco"
 *     competitorLabel="MLB-XXX"
 *   />
 */
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import { formatCurrency } from "@/lib/utils";

interface PricePoint {
  date: string;
  my_price: number | null;
  competitor_price: number | null;
}

interface PriceGapChartProps {
  data: PricePoint[];
  myLabel?: string;
  competitorLabel?: string;
  height?: number;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number | null; color: string }>;
  label?: string;
}

function PriceGapTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const my = payload.find((p) => p.name === "Meu Preco");
  const comp = payload.find((p) => p.name === "Concorrente");
  const gap =
    my?.value != null && comp?.value != null
      ? my.value - comp.value
      : null;

  return (
    <div className="bg-popover border rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-foreground mb-2">{label}</p>
      {my?.value != null && (
        <p style={{ color: my.color }}>Meu Preco: <span className="font-bold">{formatCurrency(my.value)}</span></p>
      )}
      {comp?.value != null && (
        <p style={{ color: comp.color }}>Concorrente: <span className="font-bold">{formatCurrency(comp.value)}</span></p>
      )}
      {gap != null && (
        <p className={`mt-1.5 font-semibold border-t pt-1.5 ${gap > 0 ? "text-red-500" : "text-green-600"}`}>
          {gap > 0 ? `${formatCurrency(gap)} mais caro` : `${formatCurrency(Math.abs(gap))} mais barato`}
        </p>
      )}
    </div>
  );
}

export function PriceGapChart({
  data,
  myLabel = "Meu Preco",
  competitorLabel = "Concorrente",
  height = 280,
}: PriceGapChartProps) {
  // Ponto mais recente com ambos precos disponiveis
  const latestWithBoth = [...data].reverse().find(
    (d) => d.my_price != null && d.competitor_price != null
  );

  const fmtDate = (v: string) => {
    const d = new Date(v + "T00:00:00");
    return isNaN(d.getTime())
      ? v
      : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={data}
        margin={{ top: 10, right: 20, left: 0, bottom: 60 }}
      >
        <defs>
          <linearGradient id="gapColorAbove" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gapColorBelow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
          </linearGradient>
        </defs>

        <CartesianGrid
          strokeDasharray="3 3"
          stroke="hsl(var(--muted-foreground) / 0.15)"
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11 }}
          angle={-45}
          height={80}
          tickFormatter={fmtDate}
        />
        <YAxis
          tick={{ fontSize: 11 }}
          tickFormatter={(v: number) =>
            new Intl.NumberFormat("pt-BR", {
              style: "currency",
              currency: "BRL",
              maximumFractionDigits: 0,
            }).format(v)
          }
        />
        <Tooltip content={<PriceGapTooltip />} />
        <Legend />

        {/* Area de gap (simplificada — area do preco concorrente como fundo) */}
        <Area
          type="stepAfter"
          dataKey="competitor_price"
          stroke="none"
          fill="url(#gapColorAbove)"
          legendType="none"
          connectNulls={false}
        />

        {/* Linha do concorrente */}
        <Line
          type="stepAfter"
          dataKey="competitor_price"
          stroke="#ef4444"
          strokeWidth={2}
          dot={false}
          name={competitorLabel}
          connectNulls={false}
        />

        {/* Linha do meu preco */}
        <Line
          type="stepAfter"
          dataKey="my_price"
          stroke="#3b82f6"
          strokeWidth={2.5}
          dot={false}
          name={myLabel}
          connectNulls={false}
        />

        {/* Ponto destacado com delta atual */}
        {latestWithBoth && latestWithBoth.my_price != null && (
          <ReferenceDot
            x={latestWithBoth.date}
            y={latestWithBoth.my_price}
            r={5}
            fill="#3b82f6"
            stroke="#fff"
            strokeWidth={2}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
