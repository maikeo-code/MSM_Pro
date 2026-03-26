import { useEffect, useState } from "react";
import { Shield, RefreshCw, Award, TrendingUp, AlertTriangle, AlertCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import reputacaoService, {
  type ReputationCurrent,
  type ReputationSnapshot,
  type ReputationRisk,
  type RiskItem,
} from "@/services/reputacaoService";
import { useActiveAccount } from "@/hooks/useActiveAccount";

// --- Helpers ---

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

/** Mapeamento do level_id do ML para nome legivel */
function getLevelLabel(level: string | null): string {
  if (!level) return "Sem nivel";
  const map: Record<string, string> = {
    "5_green": "MercadoLider",
    "4_light_green": "Bom",
    "3_yellow": "Regular",
    "2_orange": "Abaixo",
    "1_red": "Critico",
  };
  return map[level] || level;
}

/** Power seller status para label */
function getPowerSellerLabel(status: string | null): string {
  if (!status) return "";
  const map: Record<string, string> = {
    gold: "MercadoLider Gold",
    platinum: "MercadoLider Platinum",
    silver: "MercadoLider",
  };
  return map[status] || status;
}

/** Cor do badge conforme power seller status */
function getPowerSellerColor(status: string | null): string {
  if (!status) return "bg-gray-100 text-gray-600";
  const map: Record<string, string> = {
    platinum: "bg-gradient-to-r from-slate-200 to-slate-400 text-slate-800",
    gold: "bg-gradient-to-r from-yellow-300 to-amber-500 text-amber-900",
    silver: "bg-gradient-to-r from-gray-200 to-gray-400 text-gray-700",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}

/** Cor do termometro conforme level_id */
function getLevelColor(level: string | null): string {
  if (!level) return "bg-gray-300";
  const map: Record<string, string> = {
    "5_green": "bg-green-600",
    "4_light_green": "bg-green-400",
    "3_yellow": "bg-yellow-400",
    "2_orange": "bg-orange-500",
    "1_red": "bg-red-500",
  };
  return map[level] || "bg-gray-300";
}

/** Largura do termometro (0-100%) */
function getLevelWidth(level: string | null): number {
  if (!level) return 10;
  const map: Record<string, number> = {
    "5_green": 100,
    "4_light_green": 80,
    "3_yellow": 60,
    "2_orange": 40,
    "1_red": 20,
  };
  return map[level] || 10;
}

// --- Tipos para KPI cards ---

interface MetricConfig {
  key: "claims" | "mediations" | "cancellations" | "late_shipments";
  label: string;
  limit: number;
  rateField: keyof ReputationCurrent;
  valueField: keyof ReputationCurrent;
}

// Thresholds padrão (serão sobrescritos pelo backend se disponível)
const DEFAULT_THRESHOLDS = {
  claims: 3.0,
  mediations: 2.0,
  cancellations: 2.0,
  late_shipments: 15.0,
};

function getMetricsWithThresholds(reputation: ReputationCurrent | null): MetricConfig[] {
  const thresholds = reputation?.thresholds || DEFAULT_THRESHOLDS;
  return [
    { key: "claims", label: "Reclamacoes", limit: thresholds.claims, rateField: "claims_rate", valueField: "claims_value" },
    { key: "mediations", label: "Mediacoes", limit: thresholds.mediations, rateField: "mediations_rate", valueField: "mediations_value" },
    { key: "cancellations", label: "Cancelamentos", limit: thresholds.cancellations, rateField: "cancellations_rate", valueField: "cancellations_value" },
    { key: "late_shipments", label: "Atrasos no envio", limit: thresholds.late_shipments, rateField: "late_shipments_rate", valueField: "late_shipments_value" },
  ];
}

function getMetricStatus(
  value: number,
  limit: number
): { status: string; color: string; barColor: string } {
  const ratio = value / limit;
  if (ratio < 0.5) {
    return { status: "OK", color: "text-green-600", barColor: "bg-green-500" };
  }
  if (ratio < 0.8) {
    return { status: "Atencao", color: "text-yellow-600", barColor: "bg-yellow-500" };
  }
  if (value < limit) {
    return { status: "Atencao", color: "text-yellow-600", barColor: "bg-yellow-500" };
  }
  return { status: "Critico", color: "text-red-600", barColor: "bg-red-500" };
}

// --- Componentes ---

function MetricCard({ metric, reputation }: { metric: MetricConfig; reputation: ReputationCurrent }) {
  const rate = reputation[metric.rateField] as number;
  const value = reputation[metric.valueField] as number;
  const { status, color, barColor } = getMetricStatus(rate, metric.limit);

  // Barra: preenche proporcionalmente ao limite
  const fillPct = Math.min((rate / metric.limit) * 100, 100);

  return (
    <div className="rounded-lg border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-muted-foreground">{metric.label}</h3>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
          status === "OK"
            ? "bg-green-100 text-green-700"
            : status === "Atencao"
            ? "bg-yellow-100 text-yellow-700"
            : "bg-red-100 text-red-700"
        }`}>
          {status}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className={`text-2xl font-bold ${color}`}>{formatPercent(rate)}</span>
        {value > 0 && (
          <span className="text-xs text-muted-foreground">({value} {value === 1 ? "caso" : "casos"})</span>
        )}
      </div>

      {/* Barra de progresso */}
      <div className="w-full h-2.5 bg-gray-200 rounded-full mt-2 mb-1.5">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${fillPct}%` }}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Limite: &lt;{metric.limit}%
      </p>
    </div>
  );
}

// --- Simulador de Risco ---

function riskBadge(level: RiskItem["risk_level"]) {
  if (level === "safe") return { label: "Seguro", cls: "bg-green-100 text-green-700 border-green-200" };
  if (level === "warning") return { label: "Atencao", cls: "bg-yellow-100 text-yellow-700 border-yellow-200" };
  return { label: "Critico", cls: "bg-red-100 text-red-700 border-red-200" };
}

function RiskCard({ item }: { item: RiskItem }) {
  const { label, cls } = riskBadge(item.risk_level);
  const isCritical = item.risk_level === "critical";

  return (
    <div
      className={[
        "rounded-lg border p-5 shadow-sm relative overflow-hidden transition-all",
        isCritical
          ? "border-red-400 animate-pulse ring-2 ring-red-300"
          : "border-border bg-card",
      ].join(" ")}
    >
      {/* Cabecalho */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-muted-foreground">{item.label}</h3>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
          {label}
        </span>
      </div>

      {/* Taxa atual e limite */}
      <div className="flex items-baseline gap-2 mb-1">
        <span
          className={`text-2xl font-bold ${
            isCritical
              ? "text-red-600"
              : item.risk_level === "warning"
              ? "text-yellow-600"
              : "text-green-600"
          }`}
        >
          {item.current_rate.toFixed(2)}%
        </span>
        <span className="text-xs text-muted-foreground">de {item.threshold}% max</span>
      </div>

      {/* Barra de uso */}
      <div className="w-full h-2 bg-gray-200 rounded-full mt-2 mb-3">
        <div
          className={`h-full rounded-full transition-all ${
            isCritical ? "bg-red-500" : item.risk_level === "warning" ? "bg-yellow-400" : "bg-green-500"
          }`}
          style={{ width: `${Math.min((item.current_rate / item.threshold) * 100, 100)}%` }}
        />
      </div>

      {/* Folga */}
      <p className="text-xs text-muted-foreground">
        {item.buffer > 0 ? (
          <>
            Folga:{" "}
            <span className="font-semibold text-foreground">
              {item.buffer} {item.buffer === 1 ? "ocorrencia" : "ocorrencias"}
            </span>{" "}
            antes de ultrapassar o limite
          </>
        ) : (
          <span className="text-red-600 font-semibold">Limite atingido ou ultrapassado</span>
        )}
      </p>

      <p className="text-xs text-muted-foreground mt-1">
        {item.current_count} ocorrencias atuais / max {item.max_allowed} permitidas
      </p>
    </div>
  );
}

function RiskSimulatorSection({ risk, loading, error }: { risk: ReputationRisk | null; loading: boolean; error: boolean }) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="h-5 w-5 text-orange-500" />
          <h2 className="text-lg font-semibold text-foreground">Simulador de Risco</h2>
        </div>
        <div className="h-24 flex items-center justify-center text-muted-foreground text-sm">
          Carregando simulador...
        </div>
      </div>
    );
  }

  if (error || !risk) {
    return (
      <div className="rounded-lg border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="h-5 w-5 text-orange-500" />
          <h2 className="text-lg font-semibold text-foreground">Simulador de Risco</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Nao foi possivel calcular o risco. Sincronize a reputacao primeiro.
        </p>
      </div>
    );
  }

  const overallLevel = risk.items.some((i) => i.risk_level === "critical")
    ? "critical"
    : risk.items.some((i) => i.risk_level === "warning")
    ? "warning"
    : "safe";

  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertCircle className={`h-5 w-5 ${overallLevel === "critical" ? "text-red-500" : overallLevel === "warning" ? "text-yellow-500" : "text-green-500"}`} />
          <h2 className="text-lg font-semibold text-foreground">Simulador de Risco</h2>
        </div>
        <span className="text-xs text-muted-foreground">
          Base: {risk.total_sales_60d} vendas nos ultimos 60 dias
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {risk.items.map((item) => (
          <RiskCard key={item.kpi} item={item} />
        ))}
      </div>
    </div>
  );
}

// --- Pagina principal ---

export default function Reputacao() {
  const accountId = useActiveAccount();
  const [reputation, setReputation] = useState<ReputationCurrent | null>(null);
  const [history, setHistory] = useState<ReputationSnapshot[]>([]);
  const [risk, setRisk] = useState<ReputationRisk | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingRisk, setLoadingRisk] = useState(true);
  const [errorRisk, setErrorRisk] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const fetchRisk = async (mlAccountId?: string | null) => {
    setLoadingRisk(true);
    setErrorRisk(false);
    try {
      const data = await reputacaoService.getRiskSimulator(mlAccountId ?? undefined);
      setRisk(data);
    } catch {
      setErrorRisk(true);
    } finally {
      setLoadingRisk(false);
    }
  };

  const fetchData = async (mlAccountId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      const [current, hist] = await Promise.all([
        reputacaoService.getCurrent(mlAccountId ?? undefined),
        reputacaoService.getHistory(60, mlAccountId ?? undefined),
      ]);
      setReputation(current);
      setHistory(hist);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao carregar reputacao";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(accountId);
    fetchRisk(accountId);
  }, [accountId]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncError(null);
    try {
      await reputacaoService.sync(accountId ?? undefined);
      await fetchData(accountId);
    } catch {
      setSyncError("Erro ao sincronizar reputacao. Tente novamente.");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-2" />
          <p className="text-red-700">{error}</p>
          <button
            onClick={() => fetchData(accountId)}
            className="mt-3 text-sm text-red-600 underline hover:text-red-800"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  if (!reputation) return null;

  // Prepara dados do grafico
  const chartData = history.map((snap) => ({
    date: new Date(snap.captured_at).toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
    }),
    reclamacoes: snap.claims_rate != null ? Number(snap.claims_rate) : 0,
    mediacoes: snap.mediations_rate != null ? Number(snap.mediations_rate) : 0,
    cancelamentos: snap.cancellations_rate != null ? Number(snap.cancellations_rate) : 0,
    atrasos: snap.late_shipments_rate != null ? Number(snap.late_shipments_rate) : 0,
  }));

  const powerLabel = getPowerSellerLabel(reputation.power_seller_status);
  const levelLabel = getLevelLabel(reputation.seller_level);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold text-foreground">Reputacao</h1>
            <p className="text-sm text-muted-foreground">
              Metricas de qualidade da sua conta no Mercado Livre
            </p>
          </div>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Sincronizando..." : "Atualizar"}
        </button>
      </div>

      {syncError && (
        <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {syncError}
        </div>
      )}

      {/* Badge + Resumo */}
      <div className="rounded-lg border bg-card p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          {/* Badge medalha */}
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold shadow-sm ${getPowerSellerColor(reputation.power_seller_status)}`}>
            <Award className="h-5 w-5" />
            {powerLabel || levelLabel}
          </div>

          {/* Resumo 60 dias */}
          <div className="flex flex-wrap gap-6 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <TrendingUp className="h-4 w-4 text-green-500" />
              <span className="font-semibold text-foreground">{formatNumber(reputation.total_sales_60d)}</span> vendas
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-foreground">{formatNumber(reputation.completed_sales_60d)}</span> concluidas
            </div>
            {reputation.total_revenue_60d > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-foreground">{formatCurrency(reputation.total_revenue_60d)}</span> faturado
              </div>
            )}
            <div className="text-xs text-muted-foreground self-center">
              Ultimos 60 dias
            </div>
          </div>
        </div>

        {/* Termometro */}
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-muted-foreground">Nivel da conta</span>
            <span className="text-xs font-medium text-foreground">{levelLabel}</span>
          </div>
          <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${getLevelColor(reputation.seller_level)}`}
              style={{ width: `${getLevelWidth(reputation.seller_level)}%` }}
            />
          </div>
          <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
            <span>Critico</span>
            <span>Abaixo</span>
            <span>Regular</span>
            <span>Bom</span>
            <span>MercadoLider</span>
          </div>
        </div>

        {reputation.captured_at && (
          <p className="text-[11px] text-muted-foreground mt-3">
            Atualizado em: {new Date(reputation.captured_at).toLocaleString("pt-BR")}
          </p>
        )}
      </div>

      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {getMetricsWithThresholds(reputation).map((metric) => (
          <MetricCard key={metric.key} metric={metric} reputation={reputation} />
        ))}
      </div>

      {/* Simulador de Risco */}
      <RiskSimulatorSection risk={risk} loading={loadingRisk} error={errorRisk} />

      {/* Grafico historico */}
      {chartData.length > 1 && (
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Historico de Metricas
          </h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v: number) => `${v.toFixed(2)}%`}
                />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(2)}%`]}
                  labelStyle={{ fontWeight: 600 }}
                />
                <Legend />
                {/* Linhas de limite critico por metrica */}
                <ReferenceLine y={reputation?.thresholds?.claims || 3.0} stroke="#ef4444" strokeDasharray="4 3" strokeWidth={1.5}
                  label={{ value: `Limite Recl. ${reputation?.thresholds?.claims?.toFixed(1) || 3.0}%`, position: "right", fill: "#ef4444", fontSize: 9 }} />
                <ReferenceLine y={reputation?.thresholds?.mediations || 2.0} stroke="#f97316" strokeDasharray="4 3" strokeWidth={1.5}
                  label={{ value: `Limite Med. ${reputation?.thresholds?.mediations?.toFixed(1) || 2.0}%`, position: "right", fill: "#f97316", fontSize: 9 }} />
                <ReferenceLine y={reputation?.thresholds?.cancellations || 2.0} stroke="#fbbf24" strokeDasharray="4 3" strokeWidth={1.5}
                  label={{ value: `Limite Canc. ${reputation?.thresholds?.cancellations?.toFixed(1) || 2.0}%`, position: "right", fill: "#fbbf24", fontSize: 9 }} />
                <ReferenceLine y={reputation?.thresholds?.late_shipments || 15.0} stroke="#3b82f6" strokeDasharray="4 3" strokeWidth={1.5}
                  label={{ value: `Limite Atrasos ${reputation?.thresholds?.late_shipments?.toFixed(1) || 15.0}%`, position: "right", fill: "#3b82f6", fontSize: 9 }} />
                <Line
                  type="monotone"
                  dataKey="reclamacoes"
                  name="Reclamacoes"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="mediacoes"
                  name="Mediacoes"
                  stroke="#f97316"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="cancelamentos"
                  name="Cancelamentos"
                  stroke="#eab308"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="atrasos"
                  name="Atrasos"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
