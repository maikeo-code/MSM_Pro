import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Megaphone,
  RefreshCw,
  DollarSign,
  TrendingUp,
  MousePointerClick,
  ShoppingCart,
  ArrowUp,
  ArrowDown,
  BarChart2,
  Target,
  Info,
} from "lucide-react";
import { useActiveAccount } from "@/hooks/useActiveAccount";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import adsService, { type AdsCampanha } from "@/services/adsService";
import { cn } from "@/lib/utils";
import { KpiCard } from "@/components/KpiCard";

// ─── Formatadores ─────────────────────────────────────────────────────────────
const fmtBRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const fmtPct = (v: number) => `${v.toFixed(1)}%`;

const fmtNum = (v: number) =>
  new Intl.NumberFormat("pt-BR").format(v);

// ─── Period selector ──────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { value: "7d", label: "7 dias" },
  { value: "30d", label: "30 dias" },
  { value: "60d", label: "60 dias" },
] as const;

type Period = (typeof PERIOD_OPTIONS)[number]["value"];

// ─── Delta com seta colorida ──────────────────────────────────────────────────
function Delta({ value, unit = "x" }: { value?: number | null; unit?: string }) {
  if (value == null) return <span className="text-gray-300 text-xs">—</span>;
  const isPos = value >= 0;
  const Icon = isPos ? ArrowUp : ArrowDown;
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium", isPos ? "text-green-600" : "text-red-600")}>
      <Icon className="h-3 w-3" />
      {Math.abs(value).toFixed(1)}{unit}
    </span>
  );
}

// ─── Badge de diagnostico ─────────────────────────────────────────────────────
function DiagnosticoBadge({ value }: { value: AdsCampanha["diagnostico"] }) {
  const map = {
    excellent: { label: "Excelente", cls: "bg-green-100 text-green-700 border-green-200" },
    good: { label: "Bom", cls: "bg-blue-100 text-blue-700 border-blue-200" },
    needs_improvement: { label: "Pode Melhorar", cls: "bg-orange-100 text-orange-700 border-orange-200" },
  };
  const { label, cls } = map[value] ?? map.needs_improvement;
  return (
    <span className={cn("text-xs font-semibold px-2 py-0.5 rounded-full border", cls)}>
      {label}
    </span>
  );
}

// ─── Tooltip customizado ──────────────────────────────────────────────────────
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; dataKey: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border border-border rounded-lg shadow-lg p-3 text-xs text-popover-foreground">
      <p className="font-semibold mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center gap-2 mb-1">
          <span className="h-2 w-2 rounded-full inline-block" style={{ background: p.color }} />
          <span>{p.name}:</span>
          <span className="font-medium">
            {p.dataKey === "cliques" ? fmtNum(p.value) : fmtNum(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Pagina Principal ─────────────────────────────────────────────────────────
export default function Publicidade() {
  const queryClient = useQueryClient();
  const accountId = useActiveAccount();
  const [selectedCampanha, setSelectedCampanha] = useState<string | null>(null);
  const [chartPeriod, setChartPeriod] = useState<Period>("30d");
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ads", accountId],
    queryFn: () => adsService.list(accountId),
    retry: 2,
  });

  const { data: campanhaDetalhe, isLoading: loadingDetalhe } = useQuery({
    queryKey: ["ads-campanha", selectedCampanha, chartPeriod, accountId],
    queryFn: () => adsService.getCampanha(selectedCampanha!, chartPeriod, accountId),
    enabled: !!selectedCampanha,
    retry: 2,
  });

  const syncMutation = useMutation({
    mutationFn: () => adsService.sync(),
    onSuccess: (res) => {
      setSyncMsg(`Sincronizado: ${res.synced} campanhas atualizadas.`);
      queryClient.invalidateQueries({ queryKey: ["ads"] });
    },
    onError: () => setSyncMsg("Erro ao sincronizar campanhas."),
  });

  const resumo = data?.resumo;
  const campanhas = data?.campanhas ?? [];

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Publicidade</h1>
          <p className="text-gray-500 mt-1">
            Gerenciamento e analise de campanhas de anuncios no Mercado Livre
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setSyncMsg(null); syncMutation.mutate(); }}
            disabled={syncMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
            {syncMutation.isPending ? "Sincronizando..." : "Sincronizar Ads"}
          </button>
          {syncMsg && (
            <span className="text-sm text-gray-500">{syncMsg}</span>
          )}
        </div>
      </div>

      {/* Erro de carregamento */}
      {isError && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Nao foi possivel carregar os dados de publicidade. O modulo de Ads pode nao estar disponivel ainda.
        </div>
      )}

      {/* ─── Secao 1 — KPI Cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <KpiCard
          label="Total Investimento"
          value={isLoading ? "..." : fmtBRL(resumo?.total_investimento ?? 0)}
          icon={<DollarSign className="h-4 w-4" />}
          iconBg="bg-red-50 text-red-500"
        />
        <KpiCard
          label="Receita Ads"
          value={isLoading ? "..." : fmtBRL(resumo?.receita_ads ?? 0)}
          icon={<TrendingUp className="h-4 w-4" />}
          iconBg="bg-green-50 text-green-600"
        />
        <KpiCard
          label="ROAS Geral"
          value={isLoading ? "..." : `${(resumo?.roas_geral ?? 0).toFixed(1)}x`}
          icon={<BarChart2 className="h-4 w-4" />}
          iconBg="bg-blue-50 text-blue-600"
        />
        <KpiCard
          label="ACOS Geral"
          value={isLoading ? "..." : fmtPct(resumo?.acos_geral ?? 0)}
          icon={<Target className="h-4 w-4" />}
          iconBg="bg-purple-50 text-purple-600"
        />
        <KpiCard
          label="Total Cliques"
          value={isLoading ? "..." : fmtNum(resumo?.total_cliques ?? 0)}
          icon={<MousePointerClick className="h-4 w-4" />}
          iconBg="bg-orange-50 text-orange-500"
        />
        <KpiCard
          label="Vendas por Ads"
          value={isLoading ? "..." : String(resumo?.vendas_por_ads ?? 0)}
          icon={<ShoppingCart className="h-4 w-4" />}
          iconBg="bg-emerald-50 text-emerald-600"
        />
      </div>

      {/* ─── Secao 2 — Tabela de Campanhas ─────────────────────────────────────── */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-100 mb-6">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Campanhas</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Clique em uma campanha para ver o grafico de desempenho detalhado
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="px-4 py-3 text-left font-medium text-gray-500">Nome</th>
                <th className="px-4 py-3 text-center font-medium text-gray-500">Diagnostico</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Orcamento Diario</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">ROAS Objetivo</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Vendas Ads</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">ROAS</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">ACOS</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Investimento</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-10 text-center text-gray-400">
                    Carregando campanhas...
                  </td>
                </tr>
              ) : campanhas.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-2 py-6">
                    <div className="mx-auto max-w-lg rounded-lg border border-blue-200 bg-blue-50 p-6 flex flex-col items-center gap-3 text-center">
                      <div className="flex items-center justify-center h-12 w-12 rounded-full bg-blue-100">
                        <Info className="h-6 w-6 text-blue-600" />
                      </div>
                      <h3 className="text-base font-semibold text-blue-800">
                        Integracao com Product Ads
                      </h3>
                      <p className="text-sm text-blue-700 leading-relaxed">
                        Os dados de publicidade do Mercado Livre nao estao disponiveis via API publica no momento.
                        Quando o ML liberar acesso, o MSM_Pro ja esta preparado para importar automaticamente suas campanhas, ROAS e ACOS.
                      </p>
                      <button
                        onClick={() => { setSyncMsg(null); syncMutation.mutate(); }}
                        disabled={syncMutation.isPending}
                        className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-60"
                      >
                        <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
                        {syncMutation.isPending ? "Verificando..." : "Tentar Sincronizar"}
                      </button>
                      {syncMsg && (
                        <p className="text-xs text-blue-600">{syncMsg}</p>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                campanhas.map((c, idx) => (
                  <tr
                    key={c.id}
                    onClick={() => setSelectedCampanha(selectedCampanha === c.id ? null : c.id)}
                    className={cn(
                      "border-b cursor-pointer transition-colors",
                      idx % 2 === 1 ? "bg-gray-50/50" : "",
                      selectedCampanha === c.id
                        ? "bg-blue-50 hover:bg-blue-50"
                        : "hover:bg-gray-50"
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "h-2 w-2 rounded-full shrink-0",
                            c.status === "active" ? "bg-green-500" : "bg-gray-300"
                          )}
                        />
                        <span className="font-medium text-gray-800 text-xs line-clamp-1">{c.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <DiagnosticoBadge value={c.diagnostico} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">{fmtBRL(c.orcamento_diario)}</td>
                    <td className="px-4 py-3 text-right text-gray-500">{c.roas_objetivo.toFixed(1)}x</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="font-medium text-gray-900">{c.vendas_ads}</span>
                        <Delta value={c.delta_vendas} unit="%" />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span
                          className={cn(
                            "font-semibold",
                            c.roas >= c.roas_objetivo ? "text-green-600" : "text-red-500"
                          )}
                        >
                          {c.roas.toFixed(1)}x
                        </span>
                        <Delta value={c.delta_roas} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={cn(
                          "text-xs font-semibold px-2 py-0.5 rounded-full",
                          c.acos <= 15
                            ? "bg-green-100 text-green-700"
                            : c.acos <= 30
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-red-100 text-red-600"
                        )}
                      >
                        {fmtPct(c.acos)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">{fmtBRL(c.investimento)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ─── Secao 3 — Grafico combo da campanha selecionada ───────────────────── */}
      {selectedCampanha && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
            <div>
              <h2 className="text-base font-semibold text-gray-900">
                Desempenho da Campanha
              </h2>
              {campanhaDetalhe && (
                <p className="text-xs text-gray-400 mt-0.5">{campanhaDetalhe.name}</p>
              )}
            </div>
            {/* Period selector */}
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={(e) => { e.stopPropagation(); setChartPeriod(opt.value); }}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                    chartPeriod === opt.value
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {loadingDetalhe ? (
            <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
              Carregando grafico...
            </div>
          ) : !campanhaDetalhe?.timeline?.length ? (
            <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
              Sem dados de timeline para esta campanha.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart
                data={campanhaDetalhe.timeline}
                margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                />
                {/* Y-axis esquerdo: vendas */}
                <YAxis
                  yAxisId="vendas"
                  orientation="left"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                />
                {/* Y-axis direito: cliques */}
                <YAxis
                  yAxisId="cliques"
                  orientation="right"
                  tick={{ fontSize: 11, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 12, paddingTop: 16 }}
                  formatter={(v) =>
                    v === "vendas_ads"
                      ? "Vendas Ads"
                      : v === "vendas_organicas"
                      ? "Vendas Organicas"
                      : "Cliques"
                  }
                />
                {/* Barra vendas ads (azul) */}
                <Bar
                  yAxisId="vendas"
                  dataKey="vendas_ads"
                  name="Vendas Ads"
                  fill="#3b82f6"
                  radius={[2, 2, 0, 0]}
                  barSize={10}
                />
                {/* Barra vendas organicas (azul claro) */}
                <Bar
                  yAxisId="vendas"
                  dataKey="vendas_organicas"
                  name="Vendas Organicas"
                  fill="#93c5fd"
                  radius={[2, 2, 0, 0]}
                  barSize={10}
                />
                {/* Linha cliques (roxo) */}
                <Line
                  yAxisId="cliques"
                  type="monotone"
                  dataKey="cliques"
                  name="Cliques"
                  stroke="#7c3aed"
                  strokeWidth={2}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  );
}
