import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCw, WifiOff, ShoppingCart, Package, DollarSign, Target, BarChart2, Sparkles, Download, Eye, Search } from "lucide-react";
import { Link } from "react-router-dom";
import listingsService, { type FunnelData, type HeatmapData } from "@/services/listingsService";
import { consultorService, type ConsultorResponse } from "@/services/consultorService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { ConsultorDrawer } from "@/components/ConsultorDrawer";
import { DiasBadge } from "@/components/DiasBadge";
import { Variacao } from "@/components/Variacao";
import { KpiCard } from "@/components/KpiCard";
import { exportCSV } from "@/utils/exportCSV";
import { useActiveAccount } from "@/hooks/useActiveAccount";

// ─── Funil de Conversao Visual ──────────────────────────────────────────────
function ConversionFunnel({ data }: { data: FunnelData | undefined }) {
  if (!data) return null;
  const { visitas, vendas, conversao, receita } = data;
  const maxVal = Math.max(visitas, 1);

  const steps = [
    { label: "Visitas", value: visitas, format: (v: number) => v.toLocaleString("pt-BR"), color: "bg-blue-500" },
    { label: "Vendas", value: vendas, format: (v: number) => v.toLocaleString("pt-BR"), color: "bg-green-500" },
    { label: "Receita", value: receita, format: (v: number) => formatCurrency(v), color: "bg-emerald-600" },
  ];

  return (
    <div className="space-y-3">
      {steps.map((step, i) => {
        const widthPct = i === 0 ? 100 : Math.max(5, (step.value / maxVal) * 100);
        return (
          <div key={step.label} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">{step.label}</span>
              <span className="font-semibold text-foreground">{step.format(step.value)}</span>
            </div>
            <div className="h-6 w-full rounded bg-muted overflow-hidden">
              <div
                className={cn("h-full rounded transition-all duration-700", step.color)}
                style={{ width: `${widthPct}%` }}
              />
            </div>
          </div>
        );
      })}
      <div className="pt-2 border-t text-sm flex items-center justify-between">
        <span className="text-muted-foreground">Conversao</span>
        <span className="font-bold text-foreground">{conversao.toFixed(2)}%</span>
      </div>
    </div>
  );
}

// ─── Heatmap de Concentracao de Vendas ───────────────────────────────────────

const DAY_ABBR = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"];
const DAY_NAMES_FULL = [
  "Segunda-feira", "Terca-feira", "Quarta-feira",
  "Quinta-feira", "Sexta-feira", "Sabado", "Domingo",
];

// Faixas horarias para o grid horario (4 blocos de 6h)
const HOUR_BANDS = [
  { label: "Manha", range: "06-12", hours: [6, 7, 8, 9, 10, 11] },
  { label: "Tarde", range: "12-18", hours: [12, 13, 14, 15, 16, 17] },
  { label: "Noite", range: "18-24", hours: [18, 19, 20, 21, 22, 23] },
  { label: "Madrugada", range: "00-06", hours: [0, 1, 2, 3, 4, 5] },
];

function getHeatColor(ratio: number): string {
  if (ratio === 0) return "bg-slate-50 text-slate-300 dark:bg-slate-900 dark:text-slate-600";
  if (ratio < 0.2) return "bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400";
  if (ratio < 0.4) return "bg-blue-200 text-blue-700 dark:bg-blue-900 dark:text-blue-300";
  if (ratio < 0.65) return "bg-blue-400 text-white dark:bg-blue-700";
  return "bg-blue-700 text-white dark:bg-blue-500";
}

// ── Grid 7×4 faixas horarias (modo Orders) ───────────────────────────────────
function HeatmapHourly({ data }: { data: HeatmapData }) {
  const [tooltip, setTooltip] = useState<string | null>(null);

  // Monta lookup (day, hour) → count
  const lookup = new Map<string, number>();
  for (const cell of data.data) {
    lookup.set(`${cell.day_of_week}-${cell.hour}`, cell.count);
  }

  // Max global para escala de cor
  const maxCount = Math.max(...data.data.map((c) => c.count), 1);

  // Detecta pico (day, hora) para destacar com borda dourada
  const peakCell = data.data.reduce(
    (best, c) => (c.count > best.count ? c : best),
    data.data[0] ?? { day_of_week: 0, hour: 0, count: 0 }
  );

  return (
    <div className="space-y-3">
      {/* Cabecalho: dias da semana */}
      <div className="grid" style={{ gridTemplateColumns: "80px repeat(7, 1fr)", gap: "4px" }}>
        <div />
        {DAY_ABBR.map((abbr, i) => (
          <div key={i} className={cn("text-center text-xs font-semibold", i === data.peak_day_index ? "text-blue-600" : "text-muted-foreground")}>
            {abbr}
          </div>
        ))}
      </div>

      {/* Linhas: uma por faixa horaria */}
      {HOUR_BANDS.map((band) => {
        // Soma as horas da faixa por dia
        return (
          <div key={band.label} className="grid items-center" style={{ gridTemplateColumns: "80px repeat(7, 1fr)", gap: "4px" }}>
            {/* Label da faixa */}
            <div className="text-right pr-2">
              <div className="text-[11px] font-medium text-muted-foreground leading-tight">{band.label}</div>
              <div className="text-[10px] text-muted-foreground/60">{band.range}h</div>
            </div>
            {/* Celulas: 7 dias */}
            {Array.from({ length: 7 }, (_, dayIdx) => {
              const bandCount = band.hours.reduce((sum, h) => sum + (lookup.get(`${dayIdx}-${h}`) ?? 0), 0);
              const ratio = bandCount / maxCount;
              const isPeak = peakCell.day_of_week === dayIdx && band.hours.includes(peakCell.hour);
              // Descobre qual hora da faixa tem mais vendas para o tooltip
              const peakHourInBand = band.hours.reduce(
                (best, h) => ((lookup.get(`${dayIdx}-${h}`) ?? 0) > (lookup.get(`${dayIdx}-${best}`) ?? 0) ? h : best),
                band.hours[0]
              );
              const tipText = `${DAY_NAMES_FULL[dayIdx]} ${peakHourInBand}h-${peakHourInBand + 1}h: ${bandCount} vendas`;

              return (
                <div
                  key={dayIdx}
                  className={cn(
                    "rounded-md flex flex-col items-center justify-center py-2 cursor-default transition-all relative",
                    getHeatColor(ratio),
                    isPeak && "ring-2 ring-offset-1 ring-yellow-400"
                  )}
                  title={tipText}
                  onMouseEnter={() => setTooltip(tipText)}
                  onMouseLeave={() => setTooltip(null)}
                >
                  {bandCount > 0 && (
                    <span className="text-xs font-bold leading-none">{bandCount}</span>
                  )}
                  {isPeak && (
                    <span className="text-[9px] font-bold leading-none mt-0.5 text-yellow-400">Pico</span>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}

      {/* Tooltip global (fallback para mobile) */}
      {tooltip && (
        <div className="text-xs text-center text-muted-foreground bg-muted rounded px-2 py-1">{tooltip}</div>
      )}

      {/* Rodape */}
      <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t">
        <span>
          Media diaria:{" "}
          <span className="font-semibold text-foreground">{data.avg_daily.toFixed(1)}</span>
        </span>
        <span>
          Pico:{" "}
          <span className="font-semibold text-foreground">{data.peak_day} {data.peak_hour}</span>
        </span>
        <span>
          Total {data.period_days}d:{" "}
          <span className="font-semibold text-foreground">{data.total_sales}</span>
        </span>
      </div>
    </div>
  );
}

// ── Grid 7 colunas (modo fallback snapshots) ──────────────────────────────────
function HeatmapDaily({ data }: { data: HeatmapData }) {
  const maxCount = Math.max(...data.data.map((d) => d.count), 1);

  // Garantir 7 dias na ordem certa (Seg a Dom)
  const days = Array.from({ length: 7 }, (_, i) => {
    const found = data.data.find((d) => d.day_of_week === i);
    return found ?? { day_of_week: i, hour: 0, day_name: DAY_NAMES_FULL[i], count: 0, avg_per_week: 0 };
  });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-7 gap-2">
        {days.map((day) => {
          const isPeak = day.day_of_week === data.peak_day_index;
          const ratio = day.count / maxCount;
          return (
            <div key={day.day_of_week} className="flex flex-col items-center gap-1">
              <span className={cn("text-xs font-medium", isPeak ? "text-blue-600" : "text-muted-foreground")}>
                {DAY_ABBR[day.day_of_week]}
              </span>
              <div
                className={cn(
                  "w-full rounded-lg flex flex-col items-center justify-center py-3 px-1 transition-all",
                  getHeatColor(ratio),
                  isPeak && "ring-2 ring-offset-1 ring-blue-500"
                )}
                title={`${day.day_name}: ${day.count} vendas`}
              >
                <span className="text-sm font-bold leading-tight">{day.count}</span>
                {isPeak && (
                  <span className="text-[10px] font-semibold mt-0.5 leading-tight">Pico</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground/70 text-center italic">
        Dados por hora estarao disponiveis quando houver pedidos sincronizados
      </p>
      <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t">
        <span>
          Media diaria:{" "}
          <span className="font-semibold text-foreground">{data.avg_daily.toFixed(1)} unidades</span>
        </span>
        <span>
          Dia mais forte:{" "}
          <span className="font-semibold text-foreground">{data.peak_day}</span>
        </span>
        <span>
          Total {data.period_days}d:{" "}
          <span className="font-semibold text-foreground">{data.total_sales}</span>
        </span>
      </div>
    </div>
  );
}

function SalesHeatmap({ data }: { data: HeatmapData | undefined }) {
  if (!data) return null;
  if (data.has_hourly_data) return <HeatmapHourly data={data} />;
  return <HeatmapDaily data={data} />;
}

const PERIOD_OPTIONS = [
  { value: "today", label: "Hoje" },
  { value: "7d", label: "7 dias" },
  { value: "15d", label: "15 dias" },
  { value: "30d", label: "30 dias" },
  { value: "60d", label: "60 dias" },
] as const;

export default function Dashboard() {
  const queryClient = useQueryClient();
  const accountId = useActiveAccount();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [funnelPeriod, setFunnelPeriod] = useState<string>("7d");
  const [searchTerm, setSearchTerm] = useState("");
  const [tablePeriod, setTablePeriod] = useState<string>("today");

  // ─── Consultor IA ────────────────────────────────────────────────────────────
  const [consultorAberto, setConsultorAberto] = useState(false);
  const [consultorLoading, setConsultorLoading] = useState(false);
  const [consultorResultado, setConsultorResultado] = useState<ConsultorResponse | null>(null);
  const [consultorErro, setConsultorErro] = useState<string | null>(null);

  const handleConsultor = async () => {
    setConsultorAberto(true);
    if (consultorResultado) return; // ja tem resultado, so abre
    setConsultorLoading(true);
    setConsultorErro(null);
    try {
      const res = await consultorService.analisar();
      setConsultorResultado(res);
    } catch {
      setConsultorErro("Nao foi possivel gerar a analise. Verifique se o backend esta online.");
    } finally {
      setConsultorLoading(false);
    }
  };

  const { data: listings, isLoading, isError, error } = useQuery({
    queryKey: ["listings", tablePeriod, accountId],
    queryFn: () => listingsService.list(tablePeriod, accountId),
    retry: 2,
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary", accountId],
    queryFn: () => listingsService.getKpiSummary(accountId),
    retry: 2,
  });

  const { data: funnelData } = useQuery({
    queryKey: ["funnel", funnelPeriod, accountId],
    queryFn: () => listingsService.getFunnel(funnelPeriod, accountId),
    retry: 2,
  });

  const [heatmapPeriod, setHeatmapPeriod] = useState("30d");

  const { data: heatmapData } = useQuery({
    queryKey: ["heatmap", heatmapPeriod, accountId],
    queryFn: () => listingsService.getHeatmap(heatmapPeriod, accountId),
    retry: 2,
  });

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const result = await listingsService.sync(accountId);
      setSyncMsg(result.message);
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["kpi-summary"] });
      queryClient.invalidateQueries({ queryKey: ["funnel"] });
    } catch {
      setSyncMsg("Erro ao sincronizar. Verifique se a conta ML esta conectada.");
    } finally {
      setSyncing(false);
    }
  };

  const displayListings = listings ?? [];

  // Ordenar por vendas do dia (unidades vendidas) — maior primeiro
  const sortedListings = [...displayListings].sort((a, b) => {
    const salesA = a.last_snapshot?.sales_today ?? 0;
    const salesB = b.last_snapshot?.sales_today ?? 0;
    return salesB - salesA;
  });

  // Filtro de busca client-side (titulo, mlb_id, seller_sku)
  const filteredListings = searchTerm.trim()
    ? sortedListings.filter((l) => {
        const term = searchTerm.toLowerCase();
        return (
          (l.title || "").toLowerCase().includes(term) ||
          (l.mlb_id || "").toLowerCase().includes(term) ||
          (l.seller_sku || "").toLowerCase().includes(term)
        );
      })
    : sortedListings;

  // Totais calculados da tabela (usam filteredListings para refletir busca)
  const totalPedidos = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.orders_count ?? l.last_snapshot?.sales_today ?? 0), 0);
  const totalUnidades = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.sales_today ?? 0), 0);
  const totalReceita = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.revenue ?? 0), 0);
  const totalEstoque = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.stock ?? 0), 0);
  const totalEstoqueValor = filteredListings.reduce((sum, l) => {
    const preco = l.price;
    const estoque = l.last_snapshot?.stock ?? 0;
    return sum + preco * estoque;
  }, 0);

  const totalVisitas = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.visits ?? 0), 0);
  const avgConversao = totalVisitas > 0 ? (totalUnidades / totalVisitas) * 100 : 0;
  const avgPrecoMedio = totalUnidades > 0 ? totalReceita / totalUnidades : 0;
  // Preco medio por venda (receita / pedidos)
  const avgPrecoMedioPorVenda = totalPedidos > 0 ? totalReceita / totalPedidos : 0;

  // Dados KPI para cards (usa periodo "hoje" ou soma dos listings)
  const kpiHoje = kpi?.hoje;

  // colSpan count: Produto + Pedidos + Unidades + Receita + VoceRecebe + Preco/Un + Preco/Venda + Participacao + Visitas + Conversao + Estoque + DiasZerar + Acoes = 13
  const totalCols = 13;

  return (
    <div className="p-8">
      {/* Drawer do Consultor IA */}
      <ConsultorDrawer
        aberto={consultorAberto}
        onFechar={() => setConsultorAberto(false)}
        loading={consultorLoading}
        resultado={consultorResultado}
        erro={consultorErro}
      />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Visao geral dos seus anuncios no Mercado Livre
        </p>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Sincronizando..." : "Sincronizar ML"}
          </button>

          <button
            onClick={handleConsultor}
            className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-blue-700 hover:to-violet-700 transition-all"
          >
            <Sparkles className="h-4 w-4" />
            Consultor IA
          </button>

          {displayListings.length > 0 && (
            <button
              onClick={() => exportCSV(sortedListings)}
              className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent transition-colors"
            >
              <Download className="h-4 w-4" />
              Baixar Relatorio
            </button>
          )}

          {consultorResultado && (
            <button
              onClick={() => { setConsultorResultado(null); setConsultorErro(null); handleConsultor(); }}
              className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
            >
              Atualizar analise
            </button>
          )}

          {syncMsg && (
            <span className="text-sm text-muted-foreground">{syncMsg}</span>
          )}
        </div>
      </div>

      {/* Erro da API */}
      {isError && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <WifiOff className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Erro ao carregar anuncios</p>
            <p className="mt-1">
              {(error as Error)?.message ?? "Nao foi possivel conectar a API."}
              {" "}Verifique se a conta ML esta conectada em{" "}
              <a href="/configuracoes" className="underline font-medium">Configuracoes</a>.
            </p>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["listings"] })}
              className="mt-2 inline-flex items-center gap-1 text-red-800 underline text-xs font-medium"
            >
              <RefreshCw className="h-3 w-3" /> Tentar novamente
            </button>
          </div>
        </div>
      )}

      {/* Nenhum anuncio */}
      {!isLoading && !isError && displayListings.length === 0 && !searchTerm && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Nenhum anuncio encontrado</p>
            <p className="mt-1">
              Clique em <strong>"Sincronizar ML"</strong> acima para importar seus anuncios do Mercado Livre,
              ou conecte uma conta ML em{" "}
              <a href="/configuracoes" className="underline font-medium">Configuracoes</a>.
            </p>
          </div>
        </div>
      )}

      {/* ─── KPI Cards com variacao (estilo UpSeller) ─────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <KpiCard
          label="Pedidos Validos"
          value={String(kpiHoje?.pedidos ?? totalPedidos)}
          variacao={kpiHoje?.vendas_variacao}
          icon={<ShoppingCart className="h-5 w-5" />}
        />
        <KpiCard
          label="Unidades Vendidas"
          value={String(kpiHoje?.vendas ?? totalUnidades)}
          variacao={kpiHoje?.vendas_variacao}
          icon={<Package className="h-5 w-5" />}
        />
        <KpiCard
          label="Receita Total"
          value={formatCurrency(kpiHoje?.receita_total ?? kpiHoje?.receita ?? totalReceita)}
          variacao={kpiHoje?.receita_variacao}
          icon={<DollarSign className="h-5 w-5" />}
        />
        <KpiCard
          label="Preco Medio"
          value={formatCurrency(kpiHoje?.preco_medio ?? avgPrecoMedio)}
          variacao={null}
          icon={<BarChart2 className="h-5 w-5" />}
        />
        <KpiCard
          label="Conversao"
          value={formatPercent(kpiHoje?.conversao ?? avgConversao)}
          variacao={kpiHoje?.conversao_variacao}
          icon={<Target className="h-5 w-5" />}
        />
      </div>

      {/* ─── Funil de Conversao + Tabela KPI por periodo (lado a lado) ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Funil de Conversao */}
        <div className="rounded-lg border bg-card shadow-sm">
          <div className="px-4 py-2 border-b flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Funil de Conversao</h2>
            <div className="flex gap-1">
              {(["7d", "15d", "30d", "60d"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setFunnelPeriod(p)}
                  className={cn(
                    "px-2 py-0.5 rounded text-xs font-medium transition-colors",
                    funnelPeriod === p
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted"
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="p-4">
            <ConversionFunnel data={funnelData} />
          </div>
        </div>

        {/* Tabela KPI por periodo */}
        <div className="rounded-lg border bg-card shadow-sm lg:col-span-2">
          <div className="px-4 py-2 border-b">
            <h2 className="text-sm font-semibold text-foreground">Resumo por Periodo</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">Periodo</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Anuncios</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Vendas</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Visitas</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Conversao</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Receita</th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">Valor Estoque</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "Hoje", data: kpi?.hoje },
                  { label: "Ontem", data: kpi?.ontem },
                  { label: "Anteontem", data: kpi?.anteontem },
                  { label: "7 dias", data: kpi?.["7dias"] },
                  { label: "30 dias", data: kpi?.["30dias"] },
                ].map(({ label, data }) => (
                  <tr key={label} className="border-b hover:bg-muted/50">
                    <td className="px-4 py-2 font-medium text-foreground">{label}</td>
                    <td className="px-4 py-2 text-right text-foreground">{data?.anuncios ?? "-"}</td>
                    <td className="px-4 py-2 text-right font-medium text-foreground">{data?.vendas ?? "-"}</td>
                    <td className="px-4 py-2 text-right text-foreground">{data?.visitas?.toLocaleString("pt-BR") ?? "-"}</td>
                    <td className="px-4 py-2 text-right text-foreground">
                      {data?.conversao != null ? `${data.conversao.toFixed(2)}%` : "-"}
                    </td>
                    <td className="px-4 py-2 text-right font-medium text-green-600">
                      {data?.receita != null && data.receita > 0 ? formatCurrency(data.receita) : "-"}
                    </td>
                    <td className="px-4 py-2 text-right font-medium text-foreground">
                      {data?.valor_estoque != null ? formatCurrency(data.valor_estoque) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ─── Heatmap de Concentracao de Vendas ─────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
        <div className="px-4 py-2 border-b flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">
            Concentracao de Vendas{heatmapData?.has_hourly_data ? " por Dia e Hora" : " por Dia da Semana"}
          </h2>
          <div className="flex gap-1">
            {(["7d", "15d", "30d", "60d"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setHeatmapPeriod(p)}
                className={cn(
                  "px-2 py-0.5 rounded text-xs font-medium transition-colors",
                  heatmapPeriod === p
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                )}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className="p-4">
          {!heatmapData ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              Carregando dados de concentracao de vendas...
            </p>
          ) : (
            <SalesHeatmap data={heatmapData} />
          )}
        </div>
      </div>

      {/* Card total estoque atual */}
      {displayListings.length > 0 && (
        <div className="rounded-lg border bg-card shadow-sm mb-6 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Valor Total em Estoque (atual)</p>
            <p className="text-xs text-muted-foreground mt-0.5">Soma de todos os anuncios ativos x estoque x preco com desconto</p>
          </div>
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalEstoqueValor)}</p>
        </div>
      )}

      {/* ─── Filtro de periodo ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 mb-4 bg-muted/50 rounded-lg p-1 w-fit">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setTablePeriod(opt.value)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              tablePeriod === opt.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* ─── Tabela de anuncios estilo UpSeller ──────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-foreground shrink-0">Anuncios Ativos</h2>
          <div className="flex items-center gap-3 flex-1 justify-end">
            {/* Campo de busca */}
            <div className="relative max-w-xs w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Buscar por titulo, MLB ou SKU..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
            </div>
            {displayListings.length > 0 && (
              <button
                onClick={() => exportCSV(filteredListings)}
                className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors shrink-0"
              >
                <Download className="h-3.5 w-3.5" />
                CSV
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Produto</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Pedidos</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Unidades</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Receita (R$)</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Voce Recebe</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Unidade</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Venda</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Participacao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Visitas</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Conversao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Estoque</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Dias p/ Zerar</th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={totalCols} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : filteredListings.length === 0 ? (
                <tr>
                  <td colSpan={totalCols} className="px-6 py-8 text-center text-muted-foreground">
                    {searchTerm ? `Nenhum anuncio encontrado para "${searchTerm}".` : "Nenhum anuncio encontrado. Sincronize para importar do Mercado Livre."}
                  </td>
                </tr>
              ) : (
                <>
                  {filteredListings.map((listing) => {
                    const effectivePrice = listing.price;
                    const snap = listing.last_snapshot;
                    const pedidos = snap?.orders_count ?? snap?.sales_today ?? 0;
                    const unidades = snap?.sales_today ?? 0;
                    const receita = snap?.revenue ?? (unidades * effectivePrice);
                    const precoMedio = snap?.avg_selling_price ?? (unidades > 0 ? receita / unidades : effectivePrice);
                    const precoMedioPorVenda = listing.avg_price_per_sale ?? (pedidos > 0 ? receita / pedidos : null);
                    const participacao = listing.participacao_pct;
                    const visitas = snap?.visits ?? 0;
                    const conversao = snap?.conversion_rate;
                    const estoque = snap?.stock;
                    const diasParaZerar = listing.dias_para_zerar;

                    return (
                      <tr
                        key={listing.id}
                        className="border-b hover:bg-muted/50 transition-colors"
                      >
                        {/* Produto: thumbnail + titulo + MLB ID + SKU */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            {listing.thumbnail ? (
                              <img
                                src={listing.thumbnail}
                                alt={listing.title}
                                className="h-10 w-10 rounded object-cover shrink-0 border"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-muted flex items-center justify-center shrink-0">
                                <Package className="h-4 w-4 text-muted-foreground/50" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <p className="font-medium text-foreground line-clamp-1 text-xs leading-tight">
                                {listing.title}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                                {listing.mlb_id}
                                {listing.seller_sku && ` . SKU: ${listing.seller_sku}`}
                              </p>
                            </div>
                          </div>
                        </td>
                        {/* Pedidos */}
                        <td className="px-4 py-3 text-right font-medium">
                          {pedidos > 0 ? pedidos : "-"}
                        </td>
                        {/* Unidades + variacao */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex flex-col items-end gap-0.5">
                            <span className="font-medium">{unidades > 0 ? unidades : "-"}</span>
                            <Variacao value={listing.vendas_variacao} />
                          </div>
                        </td>
                        {/* Receita + variacao */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex flex-col items-end gap-0.5">
                            <span className="font-medium text-green-600">{receita > 0 ? formatCurrency(receita) : "-"}</span>
                            <Variacao value={listing.receita_variacao} />
                          </div>
                        </td>
                        {/* Voce Recebe */}
                        <td className="px-4 py-3 text-right font-semibold text-green-600">
                          {listing.voce_recebe != null ? formatCurrency(listing.voce_recebe) : "-"}
                        </td>
                        {/* Preco/Unidade */}
                        <td className="px-4 py-3 text-right">
                          {formatCurrency(precoMedio)}
                        </td>
                        {/* Preco/Venda */}
                        <td className="px-4 py-3 text-right">
                          {precoMedioPorVenda != null ? (
                            <span className="text-blue-700 font-medium">{formatCurrency(precoMedioPorVenda)}</span>
                          ) : "-"}
                        </td>
                        {/* Participacao % */}
                        <td className="px-4 py-3 text-right">
                          {participacao != null ? (
                            <div className="flex flex-col items-end gap-0.5">
                              <span className={cn(
                                "text-xs font-semibold",
                                participacao >= 30 ? "text-green-700" : participacao >= 10 ? "text-yellow-700" : "text-muted-foreground"
                              )}>
                                {participacao.toFixed(1)}%
                              </span>
                              <div className="w-12 h-1 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={cn(
                                    "h-full rounded-full",
                                    participacao >= 30 ? "bg-green-500" : participacao >= 10 ? "bg-yellow-500" : "bg-gray-400"
                                  )}
                                  style={{ width: `${Math.min(100, participacao)}%` }}
                                />
                              </div>
                            </div>
                          ) : "-"}
                        </td>
                        {/* Visitas */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Eye className="h-3 w-3 text-muted-foreground/50" />
                            <span>{visitas > 0 ? visitas.toLocaleString("pt-BR") : "-"}</span>
                          </div>
                        </td>
                        {/* Conversao */}
                        <td className="px-4 py-3 text-right">
                          {conversao != null ? (
                            <span className={cn(
                              "font-medium",
                              Number(conversao) >= 3 ? "text-green-600" : Number(conversao) >= 1 ? "text-yellow-600" : "text-red-500"
                            )}>
                              {formatPercent(Number(conversao))}
                            </span>
                          ) : "-"}
                        </td>
                        {/* Estoque */}
                        <td className="px-4 py-3 text-right">
                          <span className={cn(
                            (estoque ?? 0) < 10 ? "text-red-600 font-medium" : "text-foreground"
                          )}>
                            {estoque ?? "-"}
                          </span>
                        </td>
                        {/* Dias p/ Zerar */}
                        <td className="px-4 py-3 text-right">
                          <DiasBadge dias={diasParaZerar} />
                        </td>
                        {/* Acoes */}
                        <td className="px-4 py-3 text-center">
                          <Link
                            to={`/anuncios/${listing.mlb_id}`}
                            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            Detalhes
                          </Link>
                        </td>
                      </tr>
                    );
                  })}

                  {/* ── Linha de totais ── */}
                  <tr className="bg-muted/30 font-bold border-t-2">
                    <td className="px-4 py-3 text-xs text-muted-foreground font-bold uppercase tracking-wide">
                      TOTAL ({filteredListings.length} anuncios)
                    </td>
                    <td className="px-4 py-3 text-right">{totalPedidos > 0 ? totalPedidos : "-"}</td>
                    <td className="px-4 py-3 text-right">{totalUnidades > 0 ? totalUnidades : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">{totalReceita > 0 ? formatCurrency(totalReceita) : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">--</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(avgPrecoMedio > 0 ? avgPrecoMedio : 0)}</td>
                    <td className="px-4 py-3 text-right text-blue-700">{avgPrecoMedioPorVenda > 0 ? formatCurrency(avgPrecoMedioPorVenda) : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">100%</td>
                    <td className="px-4 py-3 text-right">{totalVisitas > 0 ? totalVisitas.toLocaleString("pt-BR") : "-"}</td>
                    <td className="px-4 py-3 text-right">{formatPercent(avgConversao)}</td>
                    <td className="px-4 py-3 text-right">{totalEstoque > 0 ? totalEstoque : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">--</td>
                    <td className="px-4 py-3"></td>
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
