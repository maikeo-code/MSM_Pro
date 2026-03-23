import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Check, X, Package, Link, Unlink, ChevronRight } from "lucide-react";
import productsService, {
  ProductOut,
  ProductCreate,
  ProductUpdate,
} from "@/services/productsService";
import listingsService from "@/services/listingsService";
import { formatCurrency, cn } from "@/lib/utils";

interface FormState {
  sku: string;
  name: string;
  cost: string;
  unit: string;
  notes: string;
}

const EMPTY_FORM: FormState = { sku: "", name: "", cost: "", unit: "un", notes: "" };

function ProductForm({
  initial,
  onSave,
  onCancel,
  loading,
}: {
  initial: FormState;
  onSave: (data: FormState) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [form, setForm] = React.useState<FormState>(initial);

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave(form);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border">
      <div className="flex flex-col gap-1 min-w-[120px]">
        <label className="text-xs font-medium text-muted-foreground">SKU (codigo)</label>
        <input
          required
          value={form.sku}
          onChange={(e) => set("sku", e.target.value)}
          placeholder="EX-001"
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="flex flex-col gap-1 flex-1 min-w-[180px]">
        <label className="text-xs font-medium text-muted-foreground">Nome do produto</label>
        <input
          required
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Nome do produto"
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="flex flex-col gap-1 min-w-[120px]">
        <label className="text-xs font-medium text-muted-foreground">Custo (R$)</label>
        <input
          required
          type="number"
          min="0"
          step="0.01"
          value={form.cost}
          onChange={(e) => set("cost", e.target.value)}
          placeholder="0,00"
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="flex flex-col gap-1 min-w-[80px]">
        <label className="text-xs font-medium text-muted-foreground">Unidade</label>
        <select
          value={form.unit}
          onChange={(e) => set("unit", e.target.value)}
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="un">un</option>
          <option value="kg">kg</option>
          <option value="g">g</option>
          <option value="cx">cx</option>
          <option value="par">par</option>
          <option value="kit">kit</option>
        </select>
      </div>
      <div className="flex flex-col gap-1 flex-1 min-w-[160px]">
        <label className="text-xs font-medium text-muted-foreground">Observacoes (opcional)</label>
        <input
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
          placeholder="Opcional"
          className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-1.5 h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Check className="h-4 w-4" />
          Salvar
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

export default function Produtos() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = React.useState(false);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [drawerOpenProductId, setDrawerOpenProductId] = React.useState<string | null>(null);
  const [showLinkForm, setShowLinkForm] = React.useState(false);
  const [selectedMlbId, setSelectedMlbId] = React.useState("");

  const { data: products = [], isLoading, error } = useQuery({
    queryKey: ["products"],
    queryFn: () => productsService.list(),
  });

  // Buscar listings do produto aberto no drawer
  const { data: listings = [] } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list("today"),
  });

  const drawerProduct = products.find((p) => p.id === drawerOpenProductId);
  const linkedListings = listings.filter((l) => l.product_id === drawerOpenProductId);
  const unlinkedListings = listings.filter((l) => !l.product_id);

  const createMutation = useMutation({
    mutationFn: (payload: ProductCreate) => productsService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setShowCreate(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProductUpdate }) =>
      productsService.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const linkSkuMutation = useMutation({
    mutationFn: ({ mlbId, productId }: { mlbId: string; productId: string | null }) =>
      listingsService.linkSku(mlbId, productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      setShowLinkForm(false);
      setSelectedMlbId("");
    },
  });

  function handleCreate(form: FormState) {
    createMutation.mutate({
      sku: form.sku,
      name: form.name,
      cost: parseFloat(form.cost),
      unit: form.unit,
      notes: form.notes || undefined,
    });
  }

  function handleUpdate(product: ProductOut, form: FormState) {
    updateMutation.mutate({
      id: product.id,
      payload: {
        name: form.name,
        cost: parseFloat(form.cost),
        unit: form.unit,
        notes: form.notes || undefined,
      },
    });
  }

  function handleDelete(product: ProductOut) {
    if (!window.confirm(`Desativar o produto "${product.name}" (${product.sku})?`)) return;
    deleteMutation.mutate(product.id);
  }

  const activeProducts = products.filter((p) => p.is_active);
  const inactiveProducts = products.filter((p) => !p.is_active);

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Produtos / SKUs</h1>
          <p className="text-muted-foreground mt-1">
            Gerencie seus produtos internos com custo de aquisicao
          </p>
        </div>
        {!showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Novo SKU
          </button>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar produtos. Verifique sua conexao.
        </div>
      )}

      {/* Formulario de criacao */}
      {showCreate && (
        <div className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-semibold mb-3">Novo Produto / SKU</h2>
          <ProductForm
            initial={EMPTY_FORM}
            onSave={handleCreate}
            onCancel={() => setShowCreate(false)}
            loading={createMutation.isPending}
          />
          {createMutation.isError && (
            <p className="mt-2 text-sm text-destructive">
              Erro ao criar produto. Verifique os dados e tente novamente.
            </p>
          )}
        </div>
      )}

      {/* Tabela de produtos ativos */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Produtos Ativos ({activeProducts.length})
          </h2>
        </div>

        {isLoading ? (
          <div className="px-6 py-12 text-center text-muted-foreground">
            Carregando produtos...
          </div>
        ) : activeProducts.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <Package className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="font-medium text-foreground">Nenhum produto cadastrado</p>
            <p className="text-sm text-muted-foreground mt-1">
              Crie seu primeiro SKU para comecar a calcular margens.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">SKU</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Nome</th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">Custo</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Unidade</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Observacoes</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Acoes</th>
                </tr>
              </thead>
              <tbody>
                {activeProducts.map((product) =>
                  editingId === product.id ? (
                    <tr key={product.id} className="border-b">
                      <td colSpan={6} className="px-4 py-3">
                        <ProductForm
                          initial={{
                            sku: product.sku,
                            name: product.name,
                            cost: product.cost,
                            unit: product.unit,
                            notes: product.notes ?? "",
                          }}
                          onSave={(form) => handleUpdate(product, form)}
                          onCancel={() => setEditingId(null)}
                          loading={updateMutation.isPending}
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr
                      key={product.id}
                      className="border-b hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 text-xs font-mono font-medium text-primary">
                          {product.sku}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-medium text-foreground">
                        {product.name}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-foreground">
                        {formatCurrency(parseFloat(product.cost))}
                      </td>
                      <td className="px-6 py-4 text-center text-muted-foreground">
                        {product.unit}
                      </td>
                      <td className="px-6 py-4 text-muted-foreground text-xs">
                        {product.notes ?? "—"}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => setDrawerOpenProductId(product.id)}
                            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            <Link className="h-3 w-3" />
                            MLBs
                          </button>
                          <button
                            onClick={() => setEditingId(product.id)}
                            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            <Pencil className="h-3 w-3" />
                            Editar
                          </button>
                          <button
                            onClick={() => handleDelete(product)}
                            disabled={deleteMutation.isPending}
                            className="inline-flex items-center gap-1 rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                          >
                            <Trash2 className="h-3 w-3" />
                            Desativar
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Produtos inativos */}
      {inactiveProducts.length > 0 && (
        <div className="rounded-lg border bg-card shadow-sm opacity-60">
          <div className="px-6 py-4 border-b">
            <h2 className="text-sm font-semibold text-muted-foreground">
              Inativos ({inactiveProducts.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">SKU</th>
                  <th className="px-6 py-3 text-left font-medium text-muted-foreground">Nome</th>
                  <th className="px-6 py-3 text-right font-medium text-muted-foreground">Custo</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Unidade</th>
                  <th className="px-6 py-3 text-center font-medium text-muted-foreground">Reativar</th>
                </tr>
              </thead>
              <tbody>
                {inactiveProducts.map((product) => (
                  <tr key={product.id} className="border-b">
                    <td className="px-6 py-4 text-muted-foreground font-mono text-xs">
                      {product.sku}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground line-through">
                      {product.name}
                    </td>
                    <td className="px-6 py-4 text-right text-muted-foreground">
                      {formatCurrency(parseFloat(product.cost))}
                    </td>
                    <td className="px-6 py-4 text-center text-muted-foreground">
                      {product.unit}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={() =>
                          updateMutation.mutate({
                            id: product.id,
                            payload: { is_active: true },
                          })
                        }
                        className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                      >
                        Reativar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Drawer de vinculacao de MLBs */}
      {drawerProduct && (
        <div className={cn(
          "fixed inset-y-0 right-0 w-full max-w-2xl bg-background border-l shadow-lg z-50 transition-transform duration-200",
          drawerOpenProductId ? "translate-x-0" : "translate-x-full"
        )}>
          {/* Header */}
          <div className="border-b p-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">Vincular Anuncios (MLBs)</h2>
              <p className="text-sm text-muted-foreground mt-1">
                {drawerProduct.sku} — {drawerProduct.name}
              </p>
            </div>
            <button
              onClick={() => {
                setDrawerOpenProductId(null);
                setShowLinkForm(false);
                setSelectedMlbId("");
              }}
              className="text-muted-foreground hover:text-foreground text-2xl font-light"
            >
              ×
            </button>
          </div>

          {/* Content */}
          <div className="overflow-y-auto h-[calc(100vh-120px)] p-6 space-y-6">
            {/* Anuncios vinculados */}
            <div className="space-y-3">
              <h3 className="font-semibold">
                Anuncios Vinculados ({linkedListings.length})
              </h3>
              {linkedListings.length === 0 ? (
                <div className="rounded-md bg-muted px-4 py-6 text-center text-sm text-muted-foreground">
                  Nenhum anuncio vinculado a este SKU.
                </div>
              ) : (
                <div className="space-y-2">
                  {linkedListings.map((listing) => (
                    <div
                      key={listing.id}
                      className="flex items-center justify-between rounded-md border bg-card p-4 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-mono text-sm font-semibold text-primary">
                          {listing.mlb_id}
                        </p>
                        <p className="text-sm text-foreground line-clamp-1">
                          {listing.title}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <div>
                            <span className="font-mono font-semibold text-foreground">
                              {formatCurrency(listing.price)}
                            </span>
                          </div>
                          {listing.last_snapshot && (
                            <>
                              <div>
                                Estoque: <span className="font-semibold text-foreground">
                                  {listing.last_snapshot.stock}
                                </span>
                              </div>
                              <div>
                                Vendas 7d: <span className="font-semibold text-foreground">
                                  {listing.last_snapshot.sales_today}
                                </span>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          linkSkuMutation.mutate({
                            mlbId: listing.mlb_id,
                            productId: null,
                          });
                        }}
                        disabled={linkSkuMutation.isPending}
                        className="ml-4 inline-flex items-center gap-1 rounded-md border border-destructive/30 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50 shrink-0"
                      >
                        <Unlink className="h-3 w-3" />
                        Desvincular
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Formulario para vincular novo MLB */}
            {!showLinkForm ? (
              <button
                onClick={() => setShowLinkForm(true)}
                className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Vincular Novo Anuncio
              </button>
            ) : (
              <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">
                    Selecionar MLB sem SKU
                  </label>
                  <select
                    value={selectedMlbId}
                    onChange={(e) => setSelectedMlbId(e.target.value)}
                    className="w-full h-10 mt-1 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">-- Escolha um anuncio --</option>
                    {unlinkedListings.map((listing) => (
                      <option key={listing.id} value={listing.mlb_id}>
                        {listing.mlb_id} — {listing.title.substring(0, 50)}...
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      if (selectedMlbId) {
                        linkSkuMutation.mutate({
                          mlbId: selectedMlbId,
                          productId: drawerProduct.id,
                        });
                      }
                    }}
                    disabled={!selectedMlbId || linkSkuMutation.isPending}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                  >
                    <Check className="h-4 w-4" />
                    Confirmar
                  </button>
                  <button
                    onClick={() => {
                      setShowLinkForm(false);
                      setSelectedMlbId("");
                    }}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent transition-colors"
                  >
                    <X className="h-4 w-4" />
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {/* Info sobre MLBs sem SKU */}
            {unlinkedListings.length > 0 && (
              <div className="rounded-md bg-blue-50 border border-blue-200 p-4 text-sm text-blue-900">
                <p className="font-semibold mb-1">Anuncios disponiveis</p>
                <p className="text-xs">
                  Existem {unlinkedListings.length} anuncio(s) sem SKU vinculado que podem ser
                  associados a este produto.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Overlay do drawer */}
      {drawerOpenProductId && (
        <div
          className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-200"
          onClick={() => {
            setDrawerOpenProductId(null);
            setShowLinkForm(false);
            setSelectedMlbId("");
          }}
        />
      )}
    </div>
  );
}
