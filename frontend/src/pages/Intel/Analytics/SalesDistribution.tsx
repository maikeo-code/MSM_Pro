import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Treemap,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { PieChart, Info } from "lucide-react";
import { analyticsService, type DistributionItem } from "@/services/intel/analyticsService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

// ─── Period selector ──────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { value: 7, label: "7 dias" },
  { value: 15, label: "15 dias" },
  { value: 30, label: "30 dias" },
] as const;

type PeriodValue = (typeof PERIOD_OPTIONS)[number]["value"];

// ─── Paleta de cores para o Treemap ──────────────────────────────────────────
const TREE_COLORS = [
  "#6366f1", // indigo
  "#3b82f6", // blue
  "#0ea5e9", // sky
  "#10b981", // emerald
  "#22c55e", // green
  "#84cc16", // lime
  "#eab308", // yellow
  "#f97316", // orange
  "#ef4444", // red
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#14b8a6", // teal
];

function getColor(index: number): string {
  return TREE_COLORS[index % TREE_COLORS.length];
}

// ─── Conteudo customizado das celulas do Treemap ──────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function TreemapCell(props: any) {
  const { x, y, width, height, name, value, pct_of_total, colorIndex } = props;
  const color = getColor(colorIndex);
  const showLabel = width > 60 && height > 40;
  const showValue = width > 80 && height > 60;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill: color, stroke: "#fff", strokeWidth: 2 }}
        rx={4}
      />
      {showLabel && (
        <text
          x={x + 8}
          y={y + 18}
          fill="#fff"
          fontSize={10}
          fontWeight={600}
          style={{ userSelect: "none", pointerEvents: "none" }}
        >
          {name.length > 18 ? name.slice(0, 15) + "..." : name}
        </text>
      )}
      {showValue && (
        <>
          <text
            x={x + 8}
            y={y + 34}
            fill="rgba(255,255,255,0.85)"
            fontSize={9}
            style={{ userSelect: "none", pointerEvents: "none" }}
          >
            {formatCurrency(value)}
          </text>
          <text
            x={x + 8}
            y={y + 48}
            fill="rgba(255,255,255,0.7)"
            fontSize={9}
            style={{ userSelect: "none", pointerEvents: "none" }}
          >
            {formatPercent(pct_of_total)}
          </text>
        </>
      )}
    </g>
  );
}

// ─── Tooltip do Treemap ───────────────────────────────────────────────────────
function TreemapTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: DistributionItem & { colorIndex: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs max-w-xs">
      <p className="font-semibold text-gray-800 mb-2 leading-snug">{item.title}</p>
      <p className="text-gray-400 font-mono mb-2">{item.mlb_id}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Receita:</span>
          <span className="font-semibold text-gray-900">
            {formatCurrency(item.revenue_30d)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Vendas:</span>
          <span className="font-semibold text-gray-900">
            {item.sales_count.toLocaleString("pt-BR")}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">% do total:</span>
          <span className="font-semibold text-gray-900">
            {formatPercent(item.pct_of_total)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Badge do coeficiente de Gini ────────────────────────────────────────────
function GiniBadge({ gini }: { gini: number }) {
  let label: string;
  let cls: string;

  if (gini >= 0.6) {
    label = "Muito Concentrada";
    cls = "bg-red-100 text-red-700";
  } else if (gini >= 0.4) {
    label = "Concentrada";
    cls = "bg-yellow-100 text-yellow-700";
  } else if (gini >= 0.2) {
    label = "Moderada";
    cls = "bg-blue-100 text-blue-700";
  } else {
    label = "Distribuida";
    cls = "bg-green-100 text-green-700";
  }

  return (
    <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full", cls)}>
      {label}
    </span>
  );
}

// ─── Pagina SalesDistribution ─────────────────────────────────────────────────
export default function SalesDistribution() {
  const [period, setPeriod] = useState<PeriodValue>(30);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["intel-distribution", period],
    queryFn: () => analyticsService.getDistribution(period),
    staleTime: 10 * 60 * 1000,
    retry: 2,
  });

  // Prepara dados para o Treemap
  const treemapData = (data?.items ?? []).map((item, idx) => ({
    ...item,
    name: item.mlb_id,
    value: item.revenue_30d,
    colorIndex: idx,
  }));

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <PieChart className="h-6 w-6 text-emerald-600" />
            <h1 className="text-3xl font-bold text-foreground">Distribuicao de Vendas</h1>
          </div>
          <p className="text-muted-foreground">
            Proporcao de receita por anuncio — mapa visual e tabela comparativa
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

      {isError && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Erro ao carregar dados de distribuicao. Tente novamente.
        </div>
      )}

      {/* ─── Cards KPI ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {/* Receita Total */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <p className="text-sm text-muted-foreground font-medium">Receita Total</p>
          <p className="text-2xl font-bold text-foreground">
            {isLoading ? "..." : formatCurrency(data?.total_revenue ?? 0)}
          </p>
          <p className="text-xs text-muted-foreground">Ultimos {period} dias</p>
        </div>

        {/* Total de Vendas */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
          <p className="text-sm text-muted-foreground font-medium">Total de Vendas</p>
          <p className="text-2xl font-bold text-foreground">
            {isLoading ? "..." : (data?.total_sales ?? 0).toLocaleString("pt-BR")}
          </p>
          <p className="text-xs text-muted-foreground">Unidades vendidas no periodo</p>
        </div>

        {/* Coeficiente de Gini */}
        <div className="rounded-lg border bg-card p-5 flex flex-col gap-3">
          <div className="flex items-center gap-1.5">
            <p className="text-sm text-muted-foreground font-medium">Coeficiente de Gini</p>
            <Info className="h-3.5 w-3.5 text-muted-foreground/50" />
          </div>
          <div className="flex items-center gap-3">
            <p className="text-2xl font-bold text-foreground">
              {isLoading ? "..." : (data?.gini_coefficient ?? 0).toFixed(3)}
            </p>
            {!isLoading && <GiniBadge gini={data?.gini_coefficient ?? 0} />}
          </div>
          <p className="text-xs text-muted-foreground">
            0 = igualmente distribuido | 1 = tudo em 1 anuncio
          </p>
        </div>
      </div>

      {/* ─── Treemap ──────────────────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
        <div className="px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-foreground">
            Mapa de Receita por Anuncio
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Area proporcional a receita — passe o cursor para ver detalhes
          </p>
        </div>
        <div className="p-6">
          {isLoading ? (
            <div className="h-96 flex items-center justify-center text-muted-foreground text-sm">
              Carregando mapa de distribuicao...
            </div>
          ) : treemapData.length === 0 ? (
            <div className="h-96 flex items-center justify-center text-muted-foreground text-sm">
              Nenhum dado disponivel. Sincronize seus anuncios.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={400}>
              <Treemap
                data={treemapData}
                dataKey="value"
                nameKey="name"
                aspectRatio={4 / 3}
                content={<TreemapCell />}
              >
                <Tooltip content={<TreemapTooltip />} />
              </Treemap>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ─── Tabela de distribuicao ────────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-foreground">
            Tabela de Distribuicao
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Todos os anuncios ordenados por receita
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">#</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Anuncio</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Receita</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Vendas</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">% do Total</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Participacao</th>
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
                      {item.sales_count.toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-foreground">
                      {formatPercent(item.pct_of_total)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="w-32 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, item.pct_of_total)}%`,
                            backgroundColor: getColor(idx),
                          }}
                        />
                      </div>
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
