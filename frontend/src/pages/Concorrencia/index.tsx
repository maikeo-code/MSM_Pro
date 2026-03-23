import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Users, ExternalLink } from "lucide-react";
import competitorsService, { CompetitorCreate } from "@/services/competitorsService";
import listingsService from "@/services/listingsService";
import { formatDate, cn } from "@/lib/utils";
import { EmptyState } from "@/components/EmptyState";

interface AddFormState {
  listing_id: string;
  competitor_mlb_id: string;
}

const EMPTY_FORM: AddFormState = { listing_id: "", competitor_mlb_id: "" };

export default function Concorrencia() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = React.useState(false);
  const [form, setForm] = React.useState<AddFormState>(EMPTY_FORM);
  const [formError, setFormError] = React.useState<string | null>(null);

  const { data: competitors = [], isLoading, error } = useQuery({
    queryKey: ["competitors"],
    queryFn: () => competitorsService.list(),
  });

  const { data: listings = [] } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
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
    return Object.fromEntries(listings.map((l) => [l.id, l.title]));
  }, [listings]);

  const activeCompetitors = competitors.filter((c) => c.is_active);

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
          <div className="px-6 py-8">
            <EmptyState
              icon={<Users className="h-6 w-6" />}
              title="Nenhum concorrente monitorado"
              description="Adicione o MLB ID de um concorrente para começar a monitorar os preços."
              action={!showForm && (
                <button
                  onClick={() => setShowForm(true)}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  Adicionar Primeiro Concorrente
                </button>
              )}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    MLB Concorrente
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Titulo
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Vinculado ao Anuncio
                  </th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                    Data de Adicao
                  </th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                    Acoes
                  </th>
                </tr>
              </thead>
              <tbody>
                {activeCompetitors.map((competitor) => (
                  <tr
                    key={competitor.id}
                    className="border-b hover:bg-muted/50 transition-colors"
                  >
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
                      {competitor.title ? (
                        <span className="line-clamp-1 text-foreground">{competitor.title}</span>
                      ) : (
                        <span className="text-muted-foreground italic text-xs">Sem titulo</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-foreground text-xs line-clamp-1">
                        {listingMap[competitor.listing_id] ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-xs">
                      {formatDate(competitor.created_at)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center">
                        <button
                          onClick={() => handleRemove(competitor.id, competitor.mlb_id)}
                          disabled={removeMutation.isPending}
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
    </div>
  );
}
