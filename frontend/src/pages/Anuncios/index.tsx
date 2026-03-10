import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ExternalLink, TrendingUp } from "lucide-react";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatPercent } from "@/lib/utils";

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}

export default function Anuncios() {
  const { data: listings, isLoading, error } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
  });

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

      <div className="rounded-lg border bg-card shadow-sm">
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
                  Preco atual
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Visitas
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Conversao
                </th>
                <th className="px-6 py-3 text-right font-medium text-muted-foreground">
                  Estoque
                </th>
                <th className="px-6 py-3 text-center font-medium text-muted-foreground">
                  Acoes
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : !listings || listings.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <TrendingUp className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                    <p className="font-medium text-foreground">Nenhum anuncio encontrado</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Conecte sua conta do Mercado Livre para sincronizar seus anuncios.
                    </p>
                  </td>
                </tr>
              ) : (
                listings.map((listing) => (
                  <tr
                    key={listing.id}
                    className="border-b hover:bg-muted/50 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <Link
                          to={`/anuncios/${listing.mlb_id}`}
                          className="font-medium text-primary hover:underline line-clamp-1"
                        >
                          {listing.title}
                        </Link>
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
                    <td className="px-6 py-4 text-right font-medium">
                      {formatCurrency(listing.price)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {listing.last_snapshot?.visits?.toLocaleString("pt-BR") ?? "-"}
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
