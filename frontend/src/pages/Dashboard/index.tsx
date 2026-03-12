import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, TrendingUp, Tag, AlertCircle, RefreshCw, WifiOff } from "lucide-react";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color?: string;
}

function KpiCard({ title, value, subtitle, icon, color = "text-primary" }: KpiCardProps) {
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{value}</p>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <div className={cn("rounded-full p-2 bg-accent", color)}>{icon}</div>
      </div>
    </div>
  );
}

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

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const result = await listingsService.sync();
      setSyncMsg(result.message);
      queryClient.invalidateQueries({ queryKey: ["listings"] });
    } catch {
      setSyncMsg("Erro ao sincronizar. Verifique se a conta ML está conectada.");
    } finally {
      setSyncing(false);
    }
  };

  const displayListings = listings ?? [];

  const totalListings = displayListings.length;
  const totalSalesToday = displayListings.reduce(
    (acc, l) => acc + (l.last_snapshot?.sales_today ?? 0),
    0,
  );
  const totalVisits = displayListings.reduce(
    (acc, l) => acc + (l.last_snapshot?.visits ?? 0),
    0,
  );

  // MLB com melhor conversão
  const bestConverting = [...displayListings].sort((a, b) => {
    const convA = Number(a.last_snapshot?.conversion_rate ?? "0");
    const convB = Number(b.last_snapshot?.conversion_rate ?? "0");
    return convB - convA;
  })[0];

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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <KpiCard
          title="Total de Anuncios"
          value={isLoading ? "..." : totalListings}
          subtitle="Anuncios ativos"
          icon={<Tag className="h-5 w-5" />}
        />
        <KpiCard
          title="Vendas Hoje"
          value={isLoading ? "..." : totalSalesToday}
          subtitle="Unidades vendidas"
          icon={<Package className="h-5 w-5" />}
          color="text-green-600"
        />
        <KpiCard
          title="Visitas Hoje"
          value={isLoading ? "..." : totalVisits.toLocaleString("pt-BR")}
          subtitle="Visitas nos anuncios"
          icon={<TrendingUp className="h-5 w-5" />}
          color="text-blue-600"
        />
        <KpiCard
          title="Melhor Conversao"
          value={
            isLoading
              ? "..."
              : bestConverting?.last_snapshot?.conversion_rate
              ? formatPercent(bestConverting.last_snapshot.conversion_rate)
              : "N/A"
          }
          subtitle={bestConverting?.title?.slice(0, 24) ? bestConverting.title.slice(0, 24) + "..." : "—"}
          icon={<TrendingUp className="h-5 w-5" />}
          color="text-purple-600"
        />
      </div>

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
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : displayListings.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
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
                    <td className="px-6 py-4 text-right font-medium">
                      {formatCurrency(listing.price)}
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
