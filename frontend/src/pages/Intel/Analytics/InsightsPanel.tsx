import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Lightbulb,
  RefreshCw,
  AlertTriangle,
  Info,
  CheckCircle2,
  TrendingUp,
  Package,
  DollarSign,
  BarChart2,
  Zap,
} from "lucide-react";
import { analyticsService, type InsightItem } from "@/services/intel/analyticsService";
import { cn } from "@/lib/utils";

// ─── Helpers de prioridade ────────────────────────────────────────────────────
function priorityBadge(priority: InsightItem["priority"]) {
  const base = "inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full";
  switch (priority) {
    case "high":
      return (
        <span className={cn(base, "bg-red-100 text-red-700")}>
          <AlertTriangle className="h-3 w-3" />
          Alta
        </span>
      );
    case "medium":
      return (
        <span className={cn(base, "bg-yellow-100 text-yellow-700")}>
          <Info className="h-3 w-3" />
          Media
        </span>
      );
    case "low":
      return (
        <span className={cn(base, "bg-blue-100 text-blue-700")}>
          <CheckCircle2 className="h-3 w-3" />
          Baixa
        </span>
      );
  }
}

function priorityOrder(p: InsightItem["priority"]): number {
  switch (p) {
    case "high":
      return 0;
    case "medium":
      return 1;
    case "low":
      return 2;
  }
}

// ─── Icone por tipo de insight ────────────────────────────────────────────────
function typeIcon(type: string) {
  const cls = "h-5 w-5";
  switch (type.toLowerCase()) {
    case "pricing":
    case "preco":
      return <DollarSign className={cn(cls, "text-green-600")} />;
    case "stock":
    case "estoque":
      return <Package className={cn(cls, "text-orange-500")} />;
    case "trend":
    case "tendencia":
      return <TrendingUp className={cn(cls, "text-blue-600")} />;
    case "performance":
    case "desempenho":
      return <BarChart2 className={cn(cls, "text-violet-600")} />;
    case "opportunity":
    case "oportunidade":
      return <Zap className={cn(cls, "text-amber-500")} />;
    default:
      return <Lightbulb className={cn(cls, "text-amber-500")} />;
  }
}

function typeIconBg(type: string): string {
  switch (type.toLowerCase()) {
    case "pricing":
    case "preco":
      return "bg-green-50";
    case "stock":
    case "estoque":
      return "bg-orange-50";
    case "trend":
    case "tendencia":
      return "bg-blue-50";
    case "performance":
    case "desempenho":
      return "bg-violet-50";
    case "opportunity":
    case "oportunidade":
      return "bg-amber-50";
    default:
      return "bg-amber-50";
  }
}

// ─── Card de insight ──────────────────────────────────────────────────────────
function InsightCard({ insight }: { insight: InsightItem }) {
  const borderColor: Record<InsightItem["priority"], string> = {
    high: "border-l-red-400",
    medium: "border-l-yellow-400",
    low: "border-l-blue-400",
  };

  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-5 flex gap-4 border-l-4 hover:shadow-sm transition-shadow",
        borderColor[insight.priority]
      )}
    >
      {/* Icone */}
      <div
        className={cn(
          "h-10 w-10 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
          typeIconBg(insight.type)
        )}
      >
        {typeIcon(insight.type)}
      </div>

      {/* Conteudo */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3 mb-1">
          <h3 className="text-sm font-semibold text-foreground leading-snug">
            {insight.title}
          </h3>
          {priorityBadge(insight.priority)}
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {insight.description}
        </p>
        <p className="text-xs text-muted-foreground/60 mt-2">
          {new Date(insight.created_at).toLocaleDateString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
          {" "}&mdash;{" "}
          <span className="capitalize">{insight.type}</span>
        </p>
      </div>
    </div>
  );
}

// ─── Tipo de ordenacao ────────────────────────────────────────────────────────
type SortOrder = "priority" | "date";

// ─── Pagina InsightsPanel ─────────────────────────────────────────────────────
export default function InsightsPanel() {
  const queryClient = useQueryClient();
  const [sortBy, setSortBy] = useState<SortOrder>("priority");
  const [refreshing, setRefreshing] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["intel-insights"],
    queryFn: () => analyticsService.getInsights(),
    staleTime: 10 * 60 * 1000,
    retry: 2,
  });

  const handleRefresh = async () => {
    setRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ["intel-insights"] });
    setRefreshing(false);
  };

  // Ordena insights por prioridade ou data
  const sortedInsights = [...(data?.insights ?? [])].sort((a, b) => {
    if (sortBy === "priority") {
      return priorityOrder(a.priority) - priorityOrder(b.priority);
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // Contagem por prioridade
  const highCount = data?.insights.filter((i) => i.priority === "high").length ?? 0;
  const mediumCount = data?.insights.filter((i) => i.priority === "medium").length ?? 0;
  const lowCount = data?.insights.filter((i) => i.priority === "low").length ?? 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Lightbulb className="h-6 w-6 text-amber-500" />
            <h1 className="text-3xl font-bold text-foreground">Insights com IA</h1>
          </div>
          <p className="text-muted-foreground">
            Recomendacoes automaticas geradas a partir dos seus dados de vendas
          </p>
        </div>

        {/* Controles de ordenacao e refresh */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
            <button
              onClick={() => setSortBy("priority")}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                sortBy === "priority"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Prioridade
            </button>
            <button
              onClick={() => setSortBy("date")}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                sortBy === "date"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              Mais Recentes
            </button>
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing || isLoading}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent transition-colors disabled:opacity-60"
          >
            <RefreshCw className={cn("h-4 w-4", (refreshing || isLoading) && "animate-spin")} />
            Atualizar
          </button>
        </div>
      </div>

      {isError && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Erro ao carregar insights. Verifique se o endpoint esta disponivel.
        </div>
      )}

      {/* ─── Resumo por prioridade ─────────────────────────────────────────────── */}
      {!isLoading && data && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="rounded-lg border bg-red-50 border-red-200 p-4 text-center">
            <p className="text-2xl font-bold text-red-700">{highCount}</p>
            <p className="text-xs font-medium text-red-600 mt-0.5">Prioridade Alta</p>
          </div>
          <div className="rounded-lg border bg-yellow-50 border-yellow-200 p-4 text-center">
            <p className="text-2xl font-bold text-yellow-700">{mediumCount}</p>
            <p className="text-xs font-medium text-yellow-600 mt-0.5">Prioridade Media</p>
          </div>
          <div className="rounded-lg border bg-blue-50 border-blue-200 p-4 text-center">
            <p className="text-2xl font-bold text-blue-700">{lowCount}</p>
            <p className="text-xs font-medium text-blue-600 mt-0.5">Prioridade Baixa</p>
          </div>
        </div>
      )}

      {/* Data de geracao */}
      {data?.generated_at && (
        <p className="text-xs text-muted-foreground mb-4">
          Gerado em:{" "}
          <span className="font-medium text-foreground">
            {new Date(data.generated_at).toLocaleDateString("pt-BR", {
              day: "2-digit",
              month: "2-digit",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </p>
      )}

      {/* ─── Lista de insights ─────────────────────────────────────────────────── */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="rounded-lg border bg-card p-5 h-24 animate-pulse bg-muted/50"
            />
          ))}
        </div>
      ) : sortedInsights.length === 0 ? (
        <div className="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-12 text-center">
          <Lightbulb className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground font-medium">
            Nenhum insight disponivel no momento
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Mantenha a sincronizacao ativa para que a IA gere recomendacoes com base nos seus dados
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedInsights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}
