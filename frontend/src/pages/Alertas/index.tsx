import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Bell, Check, X, ToggleLeft, ToggleRight } from "lucide-react";
import alertasService, {
  AlertConfigCreate,
  AlertType,
  AlertChannel,
  Severity,
} from "@/services/alertasService";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatDateTime, cn } from "@/lib/utils";
import { EmptyState } from "@/components/EmptyState";

// -------------------------------------------------------
// Helpers de display
// -------------------------------------------------------

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  conversion_below: "Conversao Baixa",
  stock_below: "Estoque Baixo",
  competitor_price_change: "Concorrente Mudou Preco",
  no_sales_days: "Sem Vendas",
  competitor_price_below: "Concorrente Abaixo de R$",
  visits_spike: "Pico de Visitas",
  conversion_improved: "Conversao Melhorou",
  stockout_forecast: "Previsao de Estoque",
};

const ALERT_TYPE_COLORS: Record<AlertType, string> = {
  conversion_below: "bg-yellow-100 text-yellow-700",
  stock_below: "bg-red-100 text-red-700",
  competitor_price_change: "bg-blue-100 text-blue-700",
  no_sales_days: "bg-orange-100 text-orange-700",
  competitor_price_below: "bg-purple-100 text-purple-700",
  visits_spike: "bg-green-100 text-green-700",
  conversion_improved: "bg-emerald-100 text-emerald-700",
  stockout_forecast: "bg-amber-100 text-amber-700",
};

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  warning: "bg-yellow-100 text-yellow-700 border-yellow-200",
  info: "bg-blue-100 text-blue-700 border-blue-200",
};

const THRESHOLD_LABELS: Record<AlertType, string | null> = {
  conversion_below: "Conversao minima (%)",
  stock_below: "Estoque minimo (un)",
  competitor_price_change: null,
  no_sales_days: "Dias sem venda",
  competitor_price_below: "Preco maximo (R$)",
  visits_spike: null,
  conversion_improved: null,
  stockout_forecast: "Dias ate stockout",
};

function formatThreshold(type: AlertType, value: number | null): string {
  if (value == null) return "—";
  if (type === "conversion_below") return `${value}%`;
  if (type === "stock_below") return `${value} un`;
  if (type === "no_sales_days") return `${value} dias`;
  if (type === "competitor_price_below") return formatCurrency(value);
  return String(value);
}

function AlertTypeBadge({ type }: { type: AlertType }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        ALERT_TYPE_COLORS[type] ?? "bg-gray-100 text-gray-700"
      )}
    >
      {ALERT_TYPE_LABELS[type] ?? type}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: Severity }) {
  const labels: Record<Severity, string> = {
    critical: "Crítico",
    warning: "Aviso",
    info: "Info",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border",
        SEVERITY_COLORS[severity]
      )}
    >
      {labels[severity]}
    </span>
  );
}

// -------------------------------------------------------
// Formulario de criar alerta
// -------------------------------------------------------

interface AlertFormState {
  alert_type: AlertType;
  listing_id: string;
  threshold: string;
  channel: AlertChannel;
}

const EMPTY_ALERT_FORM: AlertFormState = {
  alert_type: "conversion_below",
  listing_id: "",
  threshold: "",
  channel: "email",
};

function AlertForm({
  listings,
  onSave,
  onCancel,
  loading,
  error,
}: {
  listings: { id: string; title: string; mlb_id: string }[];
  onSave: (data: AlertFormState) => void;
  onCancel: () => void;
  loading: boolean;
  error: string | null;
}) {
  const [form, setForm] = React.useState<AlertFormState>(EMPTY_ALERT_FORM);

  function set<K extends keyof AlertFormState>(field: K, value: AlertFormState[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave(form);
  }

  const thresholdLabel = THRESHOLD_LABELS[form.alert_type];
  const needsThreshold = thresholdLabel !== null;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap gap-4">
        {/* Tipo de alerta */}
        <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
          <label className="text-xs font-medium text-muted-foreground">Tipo de Alerta</label>
          <select
            required
            value={form.alert_type}
            onChange={(e) => set("alert_type", e.target.value as AlertType)}
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {(Object.keys(ALERT_TYPE_LABELS) as AlertType[]).map((type) => (
              <option key={type} value={type}>
                {ALERT_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>

        {/* Anuncio (obrigatorio) */}
        <div className="flex flex-col gap-1 flex-1 min-w-[240px]">
          <label className="text-xs font-medium text-muted-foreground">
            Anuncio <span className="text-destructive">*</span>
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

        {/* Threshold */}
        {needsThreshold && (
          <div className="flex flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-muted-foreground">
              {thresholdLabel}
            </label>
            <input
              required
              type="number"
              min="0"
              step="0.01"
              value={form.threshold}
              onChange={(e) => set("threshold", e.target.value)}
              placeholder="0"
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        )}

        {/* Canal */}
        <div className="flex flex-col gap-1 min-w-[130px]">
          <label className="text-xs font-medium text-muted-foreground">Canal</label>
          <select
            value={form.channel}
            onChange={(e) => set("channel", e.target.value as AlertChannel)}
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="email">Email</option>
            <option value="webhook">Webhook</option>
          </select>
        </div>
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-1.5 h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Check className="h-4 w-4" />
          {loading ? "Salvando..." : "Salvar Alerta"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 h-9 rounded-md border px-4 text-sm font-medium hover:bg-accent transition-colors"
        >
          <X className="h-4 w-4" />
          Cancelar
        </button>
      </div>
    </form>
  );
}

// -------------------------------------------------------
// Pagina principal
// -------------------------------------------------------

export default function Alertas() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = React.useState<Severity | "all">("all");

  const { data: alertas = [], isLoading, error } = useQuery({
    queryKey: ["alertas"],
    queryFn: () => alertasService.list(),
  });

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["alerta-events"],
    queryFn: () => alertasService.listEvents(30),
  });

  const { data: listings = [] } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
  });

  const createMutation = useMutation({
    mutationFn: (payload: AlertConfigCreate) => alertasService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alertas"] });
      setShowCreate(false);
      setFormError(null);
    },
    onError: () => {
      setFormError("Erro ao criar alerta. Verifique os dados informados.");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      alertasService.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alertas"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => alertasService.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alertas"] });
    },
  });

  function handleCreate(form: {
    alert_type: AlertType;
    listing_id: string;
    threshold: string;
    channel: AlertChannel;
  }) {
    const needsThreshold = THRESHOLD_LABELS[form.alert_type] !== null;

    if (needsThreshold && !form.threshold) {
      setFormError("Informe o valor limite para este tipo de alerta.");
      return;
    }

    // Backend exige listing_id OU product_id obrigatoriamente
    if (!form.listing_id) {
      setFormError("Selecione um anuncio para criar o alerta.");
      return;
    }

    const payload: AlertConfigCreate = {
      alert_type: form.alert_type,
      channel: form.channel,
      threshold: needsThreshold && form.threshold ? parseFloat(form.threshold) : null,
      listing_id: form.listing_id || undefined,
    };

    createMutation.mutate(payload);
  }

  function handleDelete(id: string) {
    if (!window.confirm("Remover este alerta?")) return;
    deleteMutation.mutate(id);
  }

  // Mapear listing_id -> titulo para exibicao
  const listingMap = React.useMemo(() => {
    return Object.fromEntries(listings.map((l) => [l.id, l.title]));
  }, [listings]);

  const activeCount = alertas.filter((a) => a.is_active).length;

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Alertas</h1>
          <p className="text-muted-foreground mt-1">
            {activeCount > 0
              ? `${activeCount} alerta${activeCount !== 1 ? "s" : ""} ativo${activeCount !== 1 ? "s" : ""}`
              : "Configure alertas para seus anuncios"}
          </p>
        </div>
        {!showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Novo Alerta
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar alertas. Verifique sua conexao.
        </div>
      )}

      {/* Formulario de criar alerta */}
      {showCreate && (
        <div className="rounded-lg border bg-card shadow-sm">
          <div className="px-6 py-4 border-b">
            <h2 className="text-sm font-semibold">Novo Alerta</h2>
          </div>
          <div className="p-6">
            <AlertForm
              listings={listings}
              onSave={handleCreate}
              onCancel={() => {
                setShowCreate(false);
                setFormError(null);
              }}
              loading={createMutation.isPending}
              error={formError}
            />
          </div>
        </div>
      )}

      {/* Tabela de alertas */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b space-y-4">
          <h2 className="text-lg font-semibold">
            Alertas Configurados ({alertas.length})
          </h2>

          {alertas.length > 0 && (
            <div className="flex gap-2 items-center flex-wrap">
              <span className="text-xs font-medium text-muted-foreground">Filtrar por severidade:</span>
              <button
                onClick={() => setFilterSeverity("all")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  filterSeverity === "all"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                Todos
              </button>
              <button
                onClick={() => setFilterSeverity("critical")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  filterSeverity === "critical"
                    ? "bg-red-600 text-white"
                    : "bg-red-100 text-red-700 hover:bg-red-200"
                )}
              >
                Críticos
              </button>
              <button
                onClick={() => setFilterSeverity("warning")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  filterSeverity === "warning"
                    ? "bg-yellow-600 text-white"
                    : "bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                )}
              >
                Avisos
              </button>
              <button
                onClick={() => setFilterSeverity("info")}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  filterSeverity === "info"
                    ? "bg-blue-600 text-white"
                    : "bg-blue-100 text-blue-700 hover:bg-blue-200"
                )}
              >
                Info
              </button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            Carregando alertas...
          </div>
        ) : alertas.length === 0 ? (
          <div className="px-6 py-8">
            <EmptyState
              icon={<Bell className="h-6 w-6" />}
              title="Nenhum alerta configurado"
              description="Configure alertas para conversão baixa, estoque crítico e mudanças de preço."
              action={!showCreate && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  Criar Primeiro Alerta
                </button>
              )}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Tipo</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Anuncio</th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">Limite</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Severidade</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Canal</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Status</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Acoes</th>
                </tr>
              </thead>
              <tbody>
                {alertas
                  .filter((alerta) => filterSeverity === "all" || alerta.severity === filterSeverity)
                  .map((alerta) => (
                  <tr
                    key={alerta.id}
                    className={cn(
                      "border-b transition-colors",
                      alerta.is_active ? "hover:bg-muted/50" : "opacity-50 hover:bg-muted/30"
                    )}
                  >
                    <td className="px-6 py-4">
                      <AlertTypeBadge type={alerta.alert_type as AlertType} />
                    </td>
                    <td className="px-6 py-4 text-xs text-foreground">
                      {alerta.listing_id && listingMap[alerta.listing_id] ? (
                        <span className="line-clamp-1">{listingMap[alerta.listing_id]}</span>
                      ) : (
                        <span className="text-muted-foreground">Todos os anuncios</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right font-medium">
                      {formatThreshold(alerta.alert_type as AlertType, alerta.threshold)}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <SeverityBadge severity={alerta.severity as Severity} />
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium capitalize">
                        {alerta.channel}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() =>
                          toggleMutation.mutate({
                            id: alerta.id,
                            is_active: !alerta.is_active,
                          })
                        }
                        disabled={toggleMutation.isPending}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
                          alerta.is_active
                            ? "bg-green-100 text-green-700 hover:bg-green-200"
                            : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                        )}
                        title={alerta.is_active ? "Clique para desativar" : "Clique para ativar"}
                      >
                        {alerta.is_active ? (
                          <>
                            <ToggleRight className="h-3.5 w-3.5" />
                            Ativo
                          </>
                        ) : (
                          <>
                            <ToggleLeft className="h-3.5 w-3.5" />
                            Inativo
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center">
                        <button
                          onClick={() => handleDelete(alerta.id)}
                          disabled={deleteMutation.isPending}
                          className="inline-flex items-center gap-1 rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="h-3 w-3" />
                          Remover
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Historico de eventos */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">Historico de Eventos</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Ultimos 30 dias</p>
        </div>

        {eventsLoading ? (
          <div className="px-6 py-8 text-center text-muted-foreground text-sm">
            Carregando historico...
          </div>
        ) : events.length === 0 ? (
          <div className="px-6 py-10 text-center">
            <Bell className="h-8 w-8 text-muted-foreground/20 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Nenhum alerta disparado ainda.</p>
            <p className="text-xs text-muted-foreground mt-1">
              Os alertas aparecem aqui quando as condicoes configuradas forem atingidas.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Data</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Mensagem</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Enviado</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id} className="border-b hover:bg-muted/50 transition-colors">
                    <td className="px-6 py-4 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDateTime(event.triggered_at)}
                    </td>
                    <td className="px-6 py-4 text-foreground">{event.message}</td>
                    <td className="px-6 py-4 text-center">
                      {event.sent_at ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                          <Check className="h-3 w-3" />
                          Sim
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
                          Pendente
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
