/**
 * GaugeChart — Gauge semicircular para exibir metas e health scores.
 *
 * Implementado com SVG puro (sem dependencia extra) + RadialBar do Recharts
 * como alternativa.
 *
 * Uso:
 *   <GaugeChart value={72} max={100} label="Health Score" color="#22c55e" />
 *   <GaugeChart value={3500} max={5000} label="Meta de Receita" unit="R$" />
 */
import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

interface GaugeChartProps {
  /** Valor atual (0 a max) */
  value: number;
  /** Valor maximo para a escala */
  max?: number;
  /** Label exibido abaixo do valor */
  label: string;
  /** Unidade opcional exibida junto ao valor (ex: "%", "R$") */
  unit?: string;
  /** Tamanho do container — padrao "md" */
  size?: "sm" | "md" | "lg";
  /** Cor da barra de preenchimento */
  color?: string;
}

function getSemanticColor(pct: number): string {
  if (pct >= 80) return "#22c55e";
  if (pct >= 50) return "#eab308";
  return "#ef4444";
}

const SIZE_MAP = {
  sm: { h: 100, innerRadius: "55%", outerRadius: "80%", fontSize: "text-lg" },
  md: { h: 140, innerRadius: "55%", outerRadius: "80%", fontSize: "text-2xl" },
  lg: { h: 180, innerRadius: "55%", outerRadius: "80%", fontSize: "text-3xl" },
};

export function GaugeChart({
  value,
  max = 100,
  label,
  unit,
  size = "md",
  color,
}: GaugeChartProps) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  const resolvedColor = color ?? getSemanticColor(pct);
  const { h, innerRadius, outerRadius, fontSize } = SIZE_MAP[size];

  const data = [
    {
      value: pct,
      fill: resolvedColor,
    },
  ];

  return (
    <div className="flex flex-col items-center gap-1">
      <div style={{ width: "100%", height: h }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            data={data}
            cx="50%"
            cy="90%"
            startAngle={180}
            endAngle={0}
            innerRadius={innerRadius}
            outerRadius={outerRadius}
          >
            {/* Track de fundo */}
            <RadialBar
              dataKey="value"
              cornerRadius={6}
              background={{ fill: "hsl(var(--muted))" }}
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* Texto central sobreposto */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-2 pointer-events-none">
          <p className={cn("font-bold leading-none text-foreground", fontSize)}>
            {unit === "R$"
              ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(value)
              : `${value.toFixed(0)}${unit ?? ""}`}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
        </div>
      </div>

      {/* Escala min/max */}
      <div className="flex justify-between w-full text-[10px] text-muted-foreground px-4">
        <span>0</span>
        <span>
          {unit === "R$"
            ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(max)
            : `${max}${unit ?? ""}`}
        </span>
      </div>
    </div>
  );
}
