/**
 * SparklineCard — Mini grafico de linha embutido em card KPI.
 *
 * Uso:
 *   <SparklineCard
 *     label="Receita 30d"
 *     value="R$ 12.450"
 *     trend={+8.3}
 *     data={[1200, 980, 1450, 1100, 1600, 1350, 1800, 1400, 1700, 1550]}
 *     color="#22c55e"
 *   />
 */
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface SparklineCardProps {
  label: string;
  value: string;
  trend?: number | null;
  data: number[];
  color?: string;
  /** Sufixo do tooltip, ex: "unidades", "R$", "%" */
  unit?: string;
}

function SparklineTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: { value: number }[];
  unit?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border rounded-md shadow-md px-2 py-1 text-xs font-medium text-foreground">
      {payload[0].value.toLocaleString("pt-BR")}
      {unit ? ` ${unit}` : ""}
    </div>
  );
}

export function SparklineCard({
  label,
  value,
  trend,
  data,
  color = "#3b82f6",
  unit,
}: SparklineCardProps) {
  const chartData = data.map((v, i) => ({ i, v }));

  const TrendIcon =
    trend == null
      ? Minus
      : trend > 0
      ? TrendingUp
      : trend < 0
      ? TrendingDown
      : Minus;

  const trendColor =
    trend == null
      ? "text-muted-foreground"
      : trend > 0
      ? "text-green-600"
      : trend < 0
      ? "text-red-500"
      : "text-muted-foreground";

  return (
    <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
      <p className="text-sm text-muted-foreground font-medium">{label}</p>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          {trend != null && (
            <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium mt-1", trendColor)}>
              <TrendIcon className="h-3 w-3" />
              {Math.abs(trend).toFixed(1)}%
            </span>
          )}
        </div>
        {/* Sparkline inline */}
        <div className="w-24 h-12 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
              <Tooltip
                content={<SparklineTooltip unit={unit} />}
                cursor={{ stroke: color, strokeWidth: 1, strokeDasharray: "2 2" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
