import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCw, WifiOff } from "lucide-react";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatPercent } from "@/lib/utils";

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const { data: listings, isLoading, isError, error } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
    retry: 2,
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary"],
    queryFn: () => listingsService.getKpiSummary(),
    retry: 2,
  });

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const result = await listingsService.sync();
      setSyncMsg(result.message);
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["kpi-summary"] });
    } catch {
      setSyncMsg("Erro ao sincronizar. Verifique se a conta ML está conectada.");
    } finally {
      setSyncing(false);
    }
  };

  const displayListings = listings ?? [];

  const totalEstoqueAtual = displayListings.reduce((sum, l) => {
    const preco = l.sale_price ?? l.price;
    const estoque = l.last_snapshot?.stock ?? 0;
    return sum + preco * estoque;
  }, 0);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
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
            <p className="font-semibold">Erro ao carregar anúncios</p>
            <p className="mt-1">
              {(error as Error)?.message ?? "Não foi possível conectar à API."}
              {" "}Verifique se a conta ML está conectada em{" "}
              <a href="/configuracoes" className="underline font-medium">Configurações</a>.
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

      {/* Nenhum anúncio — convite para sincronizar */}
      {!isLoading && !isError && displayListings.length === 0 && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Nenhum anúncio encontrado</p>
            <p className="mt-1">
              Clique em <strong>"Sincronizar ML"</strong> acima para importar seus anúncios do Mercado Livre,
              ou conecte uma conta ML em{" "}
              <a href="/configuracoes" className="underline font-medium">Configurações</a>.
            </p>
          </div>
        </div>
      )}

      {/* KPI Comparison Table */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
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

      {/* Card total estoque atual */}
      {displayListings.length > 0 && (
        <div className="rounded-lg border bg-card shadow-sm mb-6 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Valor Total em Estoque (atual)</p>
            <p className="text-xs text-muted-foreground mt-0.5">Soma de todos os anúncios ativos × estoque × preço com desconto</p>
          </div>
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalEstoqueAtual)}</p>
        </div>
      )}

      {/* Tabela de anuncios */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-foreground">Anuncios Ativos</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                  Anuncio
                </th>
                <th className="px-6 py-3 text-left font-medium text-muted-foreground">
                  Tipo
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Preço
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Visitas
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Vendas hoje
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Conversao
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Estoque
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Valor Estoque
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : displayListings.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-muted-foreground">
                    Nenhum anuncio encontrado. Sincronize para importar do Mercado Livre.
                  </td>
                </tr>
              ) : (
                displayListings.map((listing) => (
                  <tr
                    key={listing.id}
                    className="border-b hover:bg-muted/50 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-foreground line-clamp-1">
                          {listing.title}
                        </p>
                        <p className="text-xs text-muted-foreground">{listing.mlb_id}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          listing.listing_type === "full"
                            ? "bg-purple-100 text-purple-700"
                            : listing.listing_type === "premium"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-gray-100 text-gray-700",
                        )}
                      >
                        {listing.listing_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      {(() => {
                        const effectivePrice = listing.sale_price ?? listing.price;
                        const origPrice = listing.original_price ?? (listing.sale_price != null && listing.sale_price < listing.price ? listing.price : null);
                        const hasDiscount = origPrice != null && Number(origPrice) > Number(effectivePrice);
                        return (
                          <div>
                            {hasDiscount && (
                              <p className="text-xs text-muted-foreground line-through">
                                {formatCurrency(origPrice!)}
                              </p>
                            )}
                            <p className={`font-medium ${hasDiscount ? "text-green-600" : ""}`}>
                              {formatCurrency(effectivePrice)}
                            </p>
                          </div>
                        );
                      })()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {listing.last_snapshot?.visits?.toLocaleString("pt-BR") ?? "-"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {listing.last_snapshot?.sales_today ?? "-"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {listing.last_snapshot?.conversion_rate
                        ? formatPercent(listing.last_snapshot.conversion_rate)
                        : "-"}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span
                        className={cn(
                          (listing.last_snapshot?.stock ?? 0) < 10
                            ? "text-red-600 font-medium"
                            : "text-foreground",
                        )}
                      >
                        {listing.last_snapshot?.stock ?? "-"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-medium text-foreground">
                      {listing.last_snapshot?.stock != null
                        ? formatCurrency((listing.sale_price ?? listing.price) * listing.last_snapshot.stock)
                        : "-"}
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
