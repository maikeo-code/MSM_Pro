import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  DollarSign,
  TrendingUp,
  Package,
  Truck,
  PiggyBank,
  ArrowUp,
  ArrowDown,
  CalendarClock,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import financeiroService, { type FinanceiroDetalhado, type FinanceiroResumo, type CashFlow } from "@/services/financeiroService";
import { cn } from "@/lib/utils";

// ─── Formatadores ─────────────────────────────────────────────────────────────
const fmtBRL = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

const fmtPct = (v: number) =>
  `${v.toFixed(1)}%`;

// ─── Period selector ──────────────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { value: "30d", label: "30 dias" },
  { value: "60d", label: "60 dias" },
  { value: "90d", label: "90 dias" },
] as const;

type Period = (typeof PERIOD_OPTIONS)[number]["value"];

// ─── Variacao ─────────────────────────────────────────────────────────────────
function Variacao({ value }: { value?: number | null }) {
  if (value == null) return null;
  const isPos = value >= 0;
  const Icon = isPos ? ArrowUp : ArrowDown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium",
        isPos ? "text-green-600" : "text-red-600"
      )}
    >
      <Icon className="h-3 w-3" />
      {Math.abs(value).toFixed(1)}%
    </span>
  );
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────
interface KpiCardProps {
  label: string;
  value: string;
  sub?: string;
  variacao?: number | null;
  icon: React.ReactNode;
  iconBg?: string;
}

function KpiCard({ label, value, sub, variacao, icon, iconBg = "bg-blue-50 text-blue-600" }: KpiCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-6 flex flex-col gap-2 border border-gray-100">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 font-medium">{label}</p>
        <span className={cn("p-2 rounded-lg", iconBg)}>{icon}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
      <Variacao value={variacao} />
    </div>
  );
}

// ─── Tooltip customizado ──────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 mb-1">
          <span className="h-2 w-2 rounded-full inline-block" style={{ background: p.color }} />
          <span className="text-gray-600">{p.name}:</span>
          <span className="font-medium text-gray-900">{fmtBRL(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Linha de tabela ──────────────────────────────────────────────────────────
function TabelaRow({ item, idx }: { item: FinanceiroDetalhado; idx: number }) {
  return (
    <tr className={cn("border-b hover:bg-gray-50 transition-colors", idx % 2 === 0 ? "" : "bg-gray-50/50")}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          {item.thumbnail ? (
            <img
              src={item.thumbnail}
              alt={item.title}
              className="h-9 w-9 rounded object-cover shrink-0 border border-gray-100"
            />
          ) : (
            <div className="h-9 w-9 rounded bg-gray-100 flex items-center justify-center shrink-0">
              <Package className="h-4 w-4 text-gray-400" />
            </div>
          )}
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-800 line-clamp-1">{item.title}</p>
            <p className="text-xs text-gray-400 font-mono mt-0.5">{item.mlb_id}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-right font-medium text-gray-900">{fmtBRL(item.vendas_brutas)}</td>
      <td className="px-4 py-3 text-right text-red-600 font-medium">{fmtBRL(item.taxa_ml_valor)}</td>
      <td className="px-4 py-3 text-right text-orange-600">{fmtBRL(item.frete)}</td>
      <td className="px-4 py-3 text-right font-bold text-green-600">{fmtBRL(item.receita_liquida)}</td>
      <td className="px-4 py-3 text-right">
        {item.margem_pct != null ? (
          <span
            className={cn(
              "text-xs font-semibold px-2 py-0.5 rounded-full",
              item.margem_pct >= 20
                ? "bg-green-100 text-green-700"
                : item.margem_pct >= 10
                ? "bg-yellow-100 text-yellow-700"
                : "bg-red-100 text-red-600"
            )}
          >
            {fmtPct(item.margem_pct)}
          </span>
        ) : (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
            N/A
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right text-gray-700">{item.unidades}</td>
    </tr>
  );
}

// ─── Helper: calcula percentual de taxas ML sobre vendas brutas ───────────────
function calcTaxasMlPct(resumo: FinanceiroResumo | undefined): number {
  if (!resumo || resumo.vendas_brutas === 0) return 0;
  return (resumo.taxas_ml_total / resumo.vendas_brutas) * 100;
}

// ─── Tooltip do Cash Flow ─────────────────────────────────────────────────────
function CashFlowTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; payload: { orders_count: number } }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      <p className="text-green-700 font-medium">{fmtBRL(payload[0].value)}</p>
      <p className="text-gray-500 mt-0.5">{payload[0].payload.orders_count} pedido(s)</p>
    </div>
  );
}

// ─── Secao Cash Flow ──────────────────────────────────────────────────────────
function CashFlowSection({ cashflow, loading }: { cashflow: CashFlow | undefined; loading: boolean }) {
  const buckets = [
    {
      label: "Proximos 7 dias",
      value: cashflow?.proximos_7d ?? 0,
      sub: "Liberacao imediata",
      color: "text-green-700",
      bg: "bg-green-50",
      border: "border-green-200",
    },
    {
      label: "8-14 dias",
      value: cashflow?.proximos_14d ?? 0,
      sub: "Liberacao em breve",
      color: "text-emerald-700",
      bg: "bg-emerald-50",
      border: "border-emerald-200",
    },
    {
      label: "15-30 dias",
      value: cashflow?.proximos_30d ?? 0,
      sub: "Liberacao futura",
      color: "text-teal-700",
      bg: "bg-teal-50",
      border: "border-teal-200",
    },
  ];

  // Formata data YYYY-MM-DD => DD/MM para exibir no grafico
  const chartData = (cashflow?.timeline ?? []).map((d) => ({
    ...d,
    dateLabel: d.date.slice(5).replace("-", "/"), // "MM/DD"
    amount: Number(d.amount),
  }));

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 mb-6">
      {/* Cabecalho */}
      <div className="flex items-center gap-2 mb-4">
        <CalendarClock className="h-5 w-5 text-green-600" />
        <h2 className="text-base font-semibold text-gray-900">Fluxo de Caixa Projetado</h2>
        <span className="ml-auto text-xs text-gray-400">Logica D+8 apos entrega</span>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center text-gray-400 text-sm">
          Carregando fluxo de caixa...
        </div>
      ) : (
        <>
          {/* 3 Cards de buckets */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {buckets.map((b) => (
              <div
                key={b.label}
                className={cn(
                  "rounded-lg border p-4 flex flex-col gap-1",
                  b.bg,
                  b.border
                )}
              >
                <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium">
                  <CalendarClock className={cn("h-3.5 w-3.5", b.color)} />
                  {b.label}
                </div>
                <p className={cn("text-2xl font-bold", b.color)}>
                  {fmtBRL(b.value)}
                </p>
                <p className="text-xs text-gray-500">{b.sub}</p>
              </div>
            ))}
          </div>

          {/* Total pendente */}
          {(cashflow?.total_pendente ?? 0) > 0 && (
            <p className="text-xs text-gray-500 mb-4">
              Total pendente de liberacao:{" "}
              <span className="font-semibold text-gray-700">
                {fmtBRL(cashflow!.total_pendente)}
              </span>
            </p>
          )}

          {/* Mini BarChart — R$ por dia */}
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart
                data={chartData}
                margin={{ top: 4, right: 12, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="dateLabel"
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#9ca3af" }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) =>
                    v >= 1000 ? `R$${(v / 1000).toFixed(0)}k` : `R$${v}`
                  }
                />
                <Tooltip content={<CashFlowTooltip />} />
                <Bar
                  dataKey="amount"
                  name="Liberacao"
                  fill="#22c55e"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-32 flex items-center justify-center text-gray-400 text-sm">
              Nenhum pagamento projetado para os proximos 30 dias.
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Pagina Principal ─────────────────────────────────────────────────────────
export default function Financeiro() {
  const [period, setPeriod] = useState<Period>("30d");

  const { data: resumo, isLoading: loadingResumo, isError: errorResumo } = useQuery({
    queryKey: ["financeiro-resumo", period],
    queryFn: () => financeiroService.getResumo(period),
    retry: 2,
  });

  const { data: timeline, isLoading: loadingTimeline, isError: errorTimeline } = useQuery({
    queryKey: ["financeiro-timeline", period],
    queryFn: () => financeiroService.getTimeline(period),
    retry: 2,
  });

  const { data: detalhado, isLoading: loadingDetalhado, isError: errorDetalhado } = useQuery({
    queryKey: ["financeiro-detalhado", period],
    queryFn: () => financeiroService.getDetalhado(period),
    retry: 2,
  });

  const { data: cashflow, isLoading: loadingCashflow, isError: errorCashflow } = useQuery({
    queryKey: ["financeiro-cashflow"],
    queryFn: () => financeiroService.getCashflow(),
    retry: 2,
  });

  const sortedDetalhado = [...(detalhado ?? [])].sort(
    (a, b) => b.receita_liquida - a.receita_liquida
  );

  if (errorResumo || errorTimeline || errorDetalhado || errorCashflow) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-lg font-semibold text-red-600">Erro ao carregar dados financeiros</p>
          <p className="text-sm text-gray-500 mt-2">Tente novamente em alguns segundos.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Financeiro</h1>
          <p className="text-gray-500 mt-1">
            Analise de receitas, taxas e margens dos seus anuncios
          </p>
        </div>

        {/* Period selector */}
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPeriod(opt.value)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                period === opt.value
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Secao 1 — Cards de resumo ─────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KpiCard
          label="Vendas Brutas"
          value={loadingResumo ? "..." : fmtBRL(resumo?.vendas_brutas ?? 0)}
          variacao={resumo?.variacao_vendas_pct}
          icon={<TrendingUp className="h-5 w-5" />}
          iconBg="bg-blue-50 text-blue-600"
        />
        <KpiCard
          label="Taxas ML Total"
          value={loadingResumo ? "..." : fmtBRL(resumo?.taxas_ml_total ?? 0)}
          sub={resumo ? fmtPct(calcTaxasMlPct(resumo)) + " das vendas" : undefined}
          icon={<DollarSign className="h-5 w-5" />}
          iconBg="bg-red-50 text-red-500"
        />
        <KpiCard
          label="Frete Total"
          value={loadingResumo ? "..." : fmtBRL(resumo?.frete_total ?? 0)}
          icon={<Truck className="h-5 w-5" />}
          iconBg="bg-orange-50 text-orange-500"
        />
        <KpiCard
          label="Receita Liquida"
          value={loadingResumo ? "..." : fmtBRL(resumo?.receita_liquida ?? 0)}
          sub={resumo ? "Margem: " + fmtPct(resumo.margem_pct) : undefined}
          variacao={resumo?.variacao_receita_pct}
          icon={<PiggyBank className="h-5 w-5" />}
          iconBg="bg-green-50 text-green-600"
        />
      </div>

      {/* ─── Secao 1.5 — Cash Flow Projetado D+8 ───────────────────────────────── */}
      <CashFlowSection cashflow={cashflow} loading={loadingCashflow} />

      {/* ─── Secao 2 — Grafico de timeline ─────────────────────────────────────── */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">Evolucao Financeira</h2>
          <p className="text-xs text-gray-400">Ultimos {period}</p>
        </div>

        {loadingTimeline ? (
          <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
            Carregando grafico...
          </div>
        ) : !timeline?.length ? (
          <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
            Sem dados de timeline para o periodo selecionado.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={timeline} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <defs>
                <linearGradient id="gradVendas" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradReceita" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradTaxas" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#9ca3af" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 16 }}
                formatter={(v) =>
                  v === "vendas_brutas"
                    ? "Vendas Brutas"
                    : v === "receita_liquida"
                    ? "Receita Liquida"
                    : "Taxas ML"
                }
              />
              <Area
                type="monotone"
                dataKey="vendas_brutas"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#gradVendas)"
              />
              <Area
                type="monotone"
                dataKey="receita_liquida"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#gradReceita)"
              />
              <Area
                type="monotone"
                dataKey="taxas"
                stroke="#ef4444"
                strokeWidth={2}
                fill="url(#gradTaxas)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ─── Secao 3 — Tabela detalhada por anuncio ────────────────────────────── */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Detalhamento por Anuncio</h2>
          <p className="text-xs text-gray-400 mt-0.5">Ordenado por receita liquida (maior primeiro)</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="px-4 py-3 text-left font-medium text-gray-500">Produto</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Vendas Brutas</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Taxa ML (R$)</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Frete (R$)</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Receita Liquida</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Margem %</th>
                <th className="px-4 py-3 text-right font-medium text-gray-500">Unidades</th>
              </tr>
            </thead>
            <tbody>
              {loadingDetalhado ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-gray-400">
                    Carregando...
                  </td>
                </tr>
              ) : sortedDetalhado.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-10 text-center text-gray-400">
                    Nenhum dado financeiro encontrado para este periodo. Sincronize os anuncios para gerar dados.
                  </td>
                </tr>
              ) : (
                <>
                  {sortedDetalhado.map((item, idx) => (
                    <TabelaRow key={item.mlb_id} item={item} idx={idx} />
                  ))}
                  {/* Linha de totais */}
                  <tr className="bg-gray-50 font-bold border-t-2 border-gray-200">
                    <td className="px-4 py-3 text-xs text-gray-500 uppercase tracking-wide font-bold">
                      TOTAL ({sortedDetalhado.length} anuncios)
                    </td>
                    <td className="px-4 py-3 text-right text-gray-900">
                      {fmtBRL(sortedDetalhado.reduce((s, i) => s + i.vendas_brutas, 0))}
                    </td>
                    <td className="px-4 py-3 text-right text-red-600">
                      {fmtBRL(sortedDetalhado.reduce((s, i) => s + i.taxa_ml_valor, 0))}
                    </td>
                    <td className="px-4 py-3 text-right text-orange-600">
                      {fmtBRL(sortedDetalhado.reduce((s, i) => s + i.frete, 0))}
                    </td>
                    <td className="px-4 py-3 text-right text-green-600">
                      {fmtBRL(sortedDetalhado.reduce((s, i) => s + i.receita_liquida, 0))}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {(() => {
                        const totalBruto = sortedDetalhado.reduce((s, i) => s + i.vendas_brutas, 0);
                        const totalLiq = sortedDetalhado.reduce((s, i) => s + i.receita_liquida, 0);
                        const pct = totalBruto > 0 ? (totalLiq / totalBruto) * 100 : 0;
                        return (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                            {fmtPct(pct)}
                          </span>
                        );
                      })()}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {sortedDetalhado.reduce((s, i) => s + i.unidades, 0)}
                    </td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
