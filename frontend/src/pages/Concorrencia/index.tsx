import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Users, ExternalLink, LineChart as LineChartIcon, TrendingUp, TrendingDown } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import competitorsService, { CompetitorCreate, CompetitorOut } from "@/services/competitorsService";
import listingsService from "@/services/listingsService";
import { cn } from "@/lib/utils";

interface AddFormState {
  listing_id: string;
  competitor_mlb_id: string;
}

interface CompetitorWithMetrics extends CompetitorOut {
  myPrice?: number;
  myVisits?: number;
  mySalesPerDay?: number;
  priceGapPct?: number;
  competitorSalesPerDay?: number;
  competitorTrend?: "up" | "down" | "stable";
}

const EMPTY_FORM: AddFormState = { listing_id: "", competitor_mlb_id: "" };

const PriceGapIndicator: React.FC<{ gapPct: number | undefined }> = ({ gapPct }) => {
  if (gapPct === undefined) return null;

  let bgColor = "bg-green-100 text-green-800"; // Você está mais barato
  let label = "Você é mais barato";

  if (gapPct > 5) {
    bgColor = "bg-red-100 text-red-800";
    label = "Concorrente mais barato";
  } else if (gapPct > 0) {
    bgColor = "bg-yellow-100 text-yellow-800";
    label = `Gap ${gapPct.toFixed(1)}%`;
  }

  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${bgColor}`}>
      {label}
    </span>
  );
};

export default function Concorrencia() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = React.useState(false);
  const [form, setForm] = React.useState<AddFormState>(EMPTY_FORM);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [expandedCompetitor, setExpandedCompetitor] = React.useState<string | null>(null);
  const [selectedChartDays, setSelectedChartDays] = React.useState(30);

  const { data: competitors = [], isLoading, error } = useQuery({
    queryKey: ["competitors"],
    queryFn: () => competitorsService.list(),
  });

  const { data: listings = [] } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
  });

  // Query para histórico do concorrente expandido
  const { data: competitorHistory } = useQuery({
    queryKey: ["competitorHistory", expandedCompetitor, selectedChartDays],
    queryFn: () =>
      expandedCompetitor
        ? competitorsService.getHistory(expandedCompetitor, selectedChartDays)
        : Promise.resolve(null),
    enabled: !!expandedCompetitor,
  });

  // Query para dados do meu listing (para comparação)
  const expandedListingId = React.useMemo(() => {
    if (!expandedCompetitor || !competitors.length) return null;
    const comp = competitors.find((c) => c.id === expandedCompetitor);
    return comp?.listing_id;
  }, [expandedCompetitor, competitors]);

  const { data: myListingAnalysis } = useQuery({
    queryKey: ["listingAnalysis", expandedListingId],
    queryFn: () =>
      expandedListingId
        ? listingsService.getAnalysis(expandedListingId, selectedChartDays)
        : Promise.resolve(null),
    enabled: !!expandedListingId,
  });

  const addMutation = useMutation({
    mutationFn: (payload: CompetitorCreate) => competitorsService.add(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["competitors"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
      setFormError(null);
    },
    onError: () => {
      setFormError("Erro ao adicionar concorrente. Verifique o MLB ID informado.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => competitorsService.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["competitors"] });
      if (expandedCompetitor === id) {
        setExpandedCompetitor(null);
      }
    },
  });

  function set(field: keyof AddFormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFormError(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.listing_id) {
      setFormError("Selecione um anuncio para vincular o concorrente.");
      return;
    }
    if (!form.competitor_mlb_id.trim()) {
      setFormError("Informe o MLB ID do concorrente.");
      return;
    }
    addMutation.mutate({
      listing_id: form.listing_id,
      competitor_mlb_id: form.competitor_mlb_id.trim(),
    });
  }

  function handleRemove(id: string, mlbId: string) {
    if (!window.confirm(`Remover o concorrente ${mlbId} do monitoramento?`)) return;
    removeMutation.mutate(id);
  }

  // Mapear listing_id -> titulo para exibicao na tabela
  const listingMap = React.useMemo(() => {
    return Object.fromEntries(listings.map((l) => [l.id, { title: l.title, price: l.price }]));
  }, [listings]);

  // Calcular métricas por concorrente
  const competitorsWithMetrics: CompetitorWithMetrics[] = React.useMemo(() => {
    return competitors.map((comp) => {
      const listing = listings.find((l) => l.id === comp.listing_id);
      const myPrice = listing?.price ?? 0;

      // Calcular gap de preço (percentual)
      let lastCompetitorPrice = 0;
      if (competitorHistory && competitorHistory.competitor_id === comp.id && competitorHistory.history.length > 0) {
        lastCompetitorPrice = parseFloat(competitorHistory.history[competitorHistory.history.length - 1].price.toString());
      }

      const priceGapPct = myPrice > 0 ? ((lastCompetitorPrice - myPrice) / myPrice) * 100 : 0;

      // Calcular sales/dia (média dos últimos snapshots)
      const recentSalesDeltas = competitorHistory?.history.slice(-7) ?? [];
      const competitorSalesPerDay =
        recentSalesDeltas.length > 0
          ? recentSalesDeltas.reduce((sum, h) => sum + (h.sales_delta ?? 0), 0) / recentSalesDeltas.length
          : 0;

      // Tendência: comparar 7d recentes vs 7d anteriores
      let competitorTrend: "up" | "down" | "stable" = "stable";
      if (competitorHistory && competitorHistory.history.length > 14) {
        const recent = competitorHistory.history.slice(-7).reduce((sum, h) => sum + (h.sales_delta ?? 0), 0);
        const previous = competitorHistory.history
          .slice(-14, -7)
          .reduce((sum, h) => sum + (h.sales_delta ?? 0), 0);
        if (recent > previous * 1.1) competitorTrend = "up";
        else if (recent < previous * 0.9) competitorTrend = "down";
      }

      return {
        ...comp,
        myPrice,
        priceGapPct,
        competitorSalesPerDay,
        competitorTrend,
      };
    });
  }, [competitors, listingMap, competitorHistory]);

  // Preparar dados para gráfico de comparação de preço
  const chartData = React.useMemo(() => {
    if (!competitorHistory || !myListingAnalysis) return [];

    const competitorPrices = new Map<string, number>();
    competitorHistory.history.forEach((h) => {
      competitorPrices.set(h.date.split("T")[0], parseFloat(h.price.toString()));
    });

    const myPrices = new Map<string, number>();
    myListingAnalysis.snapshots.forEach((snap) => {
      myPrices.set(snap.captured_at.split("T")[0], snap.price);
    });

    const allDates = Array.from(new Set([...competitorPrices.keys(), ...myPrices.keys()])).sort();

    return allDates.map((date) => ({
      date,
      "Preço Concorrente": competitorPrices.get(date) || null,
      "Meu Preço": myPrices.get(date) || null,
    }));
  }, [competitorHistory, myListingAnalysis]);

  const activeCompetitors = competitorsWithMetrics.filter((c) => c.is_active);

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Concorrencia</h1>
          <p className="text-muted-foreground mt-1">
            {activeCompetitors.length > 0
              ? `${activeCompetitors.length} concorrente${activeCompetitors.length !== 1 ? "s" : ""} monitorado${activeCompetitors.length !== 1 ? "s" : ""}`
              : "Monitore os precos dos seus concorrentes"}
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Adicionar Concorrente
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar concorrentes. Verifique sua conexao.
        </div>
      )}

      {/* Formulario de adicionar */}
      {showForm && (
        <div className="rounded-lg border bg-card shadow-sm">
          <div className="px-6 py-4 border-b">
            <h2 className="text-sm font-semibold">Adicionar Concorrente</h2>
          </div>
          <form onSubmit={handleSubmit} className="p-6">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1 flex-1 min-w-[240px]">
                <label className="text-xs font-medium text-muted-foreground">
                  Meu Anuncio (MLB)
                </label>
                <select
                  required
                  value={form.listing_id}
                  onChange={(e) => set("listing_id", e.target.value)}
                  className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Selecione um anuncio...</option>
                  {listings.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.title} ({l.mlb_id})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-muted-foreground">
                  MLB ID do Concorrente
                </label>
                <input
                  required
                  value={form.competitor_mlb_id}
                  onChange={(e) => set("competitor_mlb_id", e.target.value)}
                  placeholder="Ex: MLB-1234567890"
                  className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={addMutation.isPending}
                  className="inline-flex items-center gap-1.5 h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  {addMutation.isPending ? "Adicionando..." : "Adicionar"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setForm(EMPTY_FORM);
                    setFormError(null);
                  }}
                  className="inline-flex items-center h-9 rounded-md border px-4 text-sm font-medium hover:bg-accent transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
            {formError && (
              <p className="mt-3 text-sm text-destructive">{formError}</p>
            )}
            <p className="mt-3 text-xs text-muted-foreground">
              O MLB ID deve estar no formato MLB-XXXXXXXXX ou MLB1234567890.
            </p>
          </form>
        </div>
      )}

      {/* Tabela de concorrentes */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Concorrentes Monitorados ({activeCompetitors.length})
          </h2>
        </div>

        {isLoading ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            Carregando concorrentes...
          </div>
        ) : activeCompetitors.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Users className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="font-medium text-foreground">Nenhum concorrente monitorado</p>
            <p className="text-sm text-muted-foreground mt-1">
              Adicione o MLB ID de um concorrente para comecar a monitorar os precos.
            </p>
            {!showForm && (
              <button
                onClick={() => setShowForm(true)}
                className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Adicionar Primeiro Concorrente
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground w-32">
                      MLB Concorrente
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                      Vendedor
                    </th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                      Preço Concorrente
                    </th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                      Meu Preço
                    </th>
                    <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                      Gap (%)
                    </th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                      Vendas/Dia
                    </th>
                    <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                      Tendência
                    </th>
                    <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                      Acoes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {activeCompetitors.map((competitor) => (
                    <React.Fragment key={competitor.id}>
                      <tr className="border-b hover:bg-muted/50 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center rounded-md bg-orange-100 px-2 py-0.5 text-xs font-mono font-medium text-orange-700">
                              {competitor.mlb_id}
                            </span>
                            <a
                              href={`https://produto.mercadolivre.com.br/${competitor.mlb_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-muted-foreground hover:text-foreground transition-colors"
                              title="Ver no Mercado Livre"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex flex-col">
                            <span className="text-foreground font-medium">
                              {competitor.title ? competitor.title.substring(0, 40) + "..." : "—"}
                            </span>
                            {competitor.seller_nickname && (
                              <span className="text-xs text-muted-foreground">@{competitor.seller_nickname}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <span className="font-semibold">
                            {competitorHistory
                              ? `R$ ${competitorHistory.history.length > 0
                                ? parseFloat(
                                  competitorHistory.history[competitorHistory.history.length - 1].price.toString()
                                ).toFixed(2)
                                : "—"
                              }`
                              : "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <span className="font-semibold">
                            {competitor.myPrice ? `R$ ${competitor.myPrice.toFixed(2)}` : "—"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <PriceGapIndicator gapPct={competitor.priceGapPct} />
                        </td>
                        <td className="px-6 py-4 text-right">
                          <span className="text-foreground">
                            {competitor.competitorSalesPerDay.toFixed(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          {competitor.competitorTrend === "up" && (
                            <TrendingUp className="h-4 w-4 text-green-600 inline" />
                          )}
                          {competitor.competitorTrend === "down" && (
                            <TrendingDown className="h-4 w-4 text-red-600 inline" />
                          )}
                          {competitor.competitorTrend === "stable" && (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              onClick={() =>
                                setExpandedCompetitor(
                                  expandedCompetitor === competitor.id ? null : competitor.id
                                )
                              }
                              className="inline-flex items-center gap-1 rounded-md border px-2 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                            >
                              <LineChartIcon className="h-3 w-3" />
                              Gráfico
                            </button>
                            <button
                              onClick={() => handleRemove(competitor.id, competitor.mlb_id)}
                              disabled={removeMutation.isPending}
                              className="inline-flex items-center gap-1 rounded-md border border-destructive/30 px-2 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                            >
                              <Trash2 className="h-3 w-3" />
                              Remover
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Seção de gráfico expandida */}
                      {expandedCompetitor === competitor.id && chartData.length > 0 && (
                        <tr className="bg-muted/30">
                          <td colSpan={8} className="px-6 py-6">
                            <div className="space-y-4">
                              <div className="flex items-center justify-between">
                                <h3 className="font-semibold flex items-center gap-2">
                                  <LineChartIcon className="h-4 w-4" />
                                  Comparação de Preço - {competitor.mlb_id}
                                </h3>
                                <div className="flex gap-2">
                                  {[7, 15, 30].map((days) => (
                                    <button
                                      key={days}
                                      onClick={() => setSelectedChartDays(days)}
                                      className={cn(
                                        "px-3 py-1 text-xs font-medium rounded-md transition-colors",
                                        selectedChartDays === days
                                          ? "bg-primary text-primary-foreground"
                                          : "bg-muted text-muted-foreground hover:bg-muted/80"
                                      )}
                                    >
                                      {days}d
                                    </button>
                                  ))}
                                </div>
                              </div>
                              {chartData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={300}>
                                  <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--muted)" />
                                    <XAxis
                                      dataKey="date"
                                      stroke="var(--muted-foreground)"
                                      tick={{ fontSize: 12 }}
                                    />
                                    <YAxis
                                      stroke="var(--muted-foreground)"
                                      tick={{ fontSize: 12 }}
                                      label={{ value: "R$", angle: -90, position: "insideLeft" }}
                                    />
                                    <Tooltip
                                      formatter={(value) =>
                                        value ? `R$ ${parseFloat(value.toString()).toFixed(2)}` : "—"
                                      }
                                      contentStyle={{
                                        backgroundColor: "var(--card)",
                                        border: "1px solid var(--border)",
                                      }}
                                    />
                                    <Legend wrapperStyle={{ paddingTop: "10px" }} />
                                    <Line
                                      type="monotone"
                                      dataKey="Preço Concorrente"
                                      stroke="#f97316"
                                      connectNulls
                                      dot={false}
                                      strokeWidth={2}
                                    />
                                    <Line
                                      type="monotone"
                                      dataKey="Meu Preço"
                                      stroke="#3b82f6"
                                      connectNulls
                                      dot={false}
                                      strokeWidth={2}
                                    />
                                  </LineChart>
                                </ResponsiveContainer>
                              ) : (
                                <div className="h-64 flex items-center justify-center text-muted-foreground">
                                  Sem dados de preço disponíveis
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
