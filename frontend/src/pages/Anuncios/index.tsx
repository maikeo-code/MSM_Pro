import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ExternalLink, TrendingUp } from "lucide-react";
import listingsService, { ListingOut } from "@/services/listingsService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

function HealthBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color =
    score >= 80 ? "bg-green-100 text-green-700" :
    score >= 60 ? "bg-yellow-100 text-yellow-700" :
    score >= 40 ? "bg-orange-100 text-orange-700" :
    "bg-red-100 text-red-700";
  const label =
    score >= 80 ? "Ótimo" :
    score >= 60 ? "Bom" :
    score >= 40 ? "Atenção" : "Crítico";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function quickHealthScore(listing: ListingOut): number {
  const snap = listing.last_snapshot;
  let score = 50;
  if (listing.thumbnail) score += 10;
  if (listing.status === "active") score += 10;
  if (snap) {
    const conversion = Number(snap.conversion_rate) || 0;
    if (conversion >= 3) score += 20;
    else if (conversion >= 1) score += 10;
    if (snap.stock > 30) score += 10;
  }
  return Math.min(100, score);
}

export default function Anuncios() {
  const { data: listings, isLoading, error } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary"],
    queryFn: () => listingsService.getKpiSummary(),
    retry: 2,
  });

  const displayListings = listings ?? [];

  const totalEstoqueAtual = displayListings.reduce((sum, l) => {
    const preco = l.sale_price ?? l.price;
    const estoque = l.last_snapshot?.stock ?? 0;
    return sum + preco * estoque;
  }, 0);

  return (
    <div className="p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Anuncios</h1>
          <p className="text-muted-foreground mt-1">
            Gerencie seus anuncios do Mercado Livre
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar anuncios. Verifique sua conexao.
        </div>
      )}

      {/* Resumo por Periodo */}
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
          </div>
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalEstoqueAtual)}</p>
        </div>
      )}

      {/* Tabela de anuncios */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-foreground">Todos os Anuncios ({displayListings.length})</h2>
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
                  Preco
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
                <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                  Acoes
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : displayListings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-12 text-center">
                    <TrendingUp className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                    <p className="font-medium text-foreground">Nenhum anuncio encontrado</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Conecte sua conta do Mercado Livre para sincronizar seus anuncios.
                    </p>
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
                        <div className="flex items-center gap-2 mb-1">
                          <Link
                            to={`/anuncios/${listing.mlb_id}`}
                            className="font-medium text-primary hover:underline line-clamp-1"
                          >
                            {listing.title}
                          </Link>
                          <HealthBadge score={quickHealthScore(listing)} />
                        </div>
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
                    <td className="px-6 py-4 text-right font-medium">
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
                            : "",
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
                    <td className="px-6 py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <Link
                          to={`/anuncios/${listing.mlb_id}`}
                          className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                        >
                          Detalhes
                        </Link>
                        {listing.permalink && (
                          <a
                            href={listing.permalink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
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
