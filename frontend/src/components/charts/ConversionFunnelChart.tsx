/**
 * ConversionFunnelChart — Funil de conversao com Recharts FunnelChart.
 *
 * Substitui o funil CSS atual do Dashboard por um grafico interativo
 * com tooltip, animacao e proporcao visual real.
 *
 * Uso:
 *   <ConversionFunnelChart
 *     visitas={1200}
 *     vendas={36}
 *     receita={4320}
 *   />
 */
import {
  FunnelChart,
  Funnel,
  Tooltip,
  LabelList,
  ResponsiveContainer,
} from "recharts";
import { formatCurrency } from "@/lib/utils";

interface ConversionFunnelChartProps {
  visitas: number;
  vendas: number;
  receita: number;
  height?: number;
}

interface FunnelTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      name: string;
      value: number;
      pct: string;
      formatted: string;
    };
  }>;
}

function FunnelTooltip({ active, payload }: FunnelTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-popover border rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-foreground mb-1">{d.name}</p>
      <p className="text-foreground font-bold">{d.formatted}</p>
      {d.pct && (
        <p className="text-muted-foreground mt-0.5">Taxa: {d.pct}</p>
      )}
    </div>
  );
}

export function ConversionFunnelChart({
  visitas,
  vendas,
  receita,
  height = 220,
}: ConversionFunnelChartProps) {
  const conversaoStr = visitas > 0 ? `${((vendas / visitas) * 100).toFixed(2)}%` : "0%";

  const data = [
    {
      name: "Visitas",
      value: visitas,
      fill: "#3b82f6",
      pct: "",
      formatted: visitas.toLocaleString("pt-BR"),
    },
    {
      name: "Vendas",
      value: vendas,
      fill: "#22c55e",
      pct: conversaoStr,
      formatted: vendas.toLocaleString("pt-BR") + " und",
    },
    {
      name: "Receita",
      value: Math.round(receita / 10), // escala proporcional ao funil (nao em R$)
      fill: "#10b981",
      pct: "",
      formatted: formatCurrency(receita),
    },
  ];

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <FunnelChart>
          <Tooltip content={<FunnelTooltip />} />
          <Funnel
            dataKey="value"
            data={data}
            isAnimationActive
            animationDuration={600}
          >
            <LabelList
              position="right"
              content={({ value, index }) => {
                const item = data[index as number];
                return (
                  <text
                    x={(value as unknown as { x: number }).x}
                    y={(value as unknown as { y: number }).y}
                    fill="hsl(var(--foreground))"
                    fontSize={11}
                    dominantBaseline="middle"
                  >
                    {item?.name}: {item?.formatted}
                  </text>
                );
              }}
            />
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
      {/* Taxa de conversao destacada */}
      <div className="flex items-center justify-center gap-2 mt-2 text-sm">
        <span className="text-muted-foreground">Conversao:</span>
        <span className="font-bold text-foreground text-base">{conversaoStr}</span>
      </div>
    </div>
  );
}
