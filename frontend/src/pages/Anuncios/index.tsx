import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ExternalLink, TrendingUp, Package, Download, Eye, Search } from "lucide-react";
import listingsService, { type ListingOut } from "@/services/listingsService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { DiasBadge } from "@/components/DiasBadge";
import { Variacao } from "@/components/Variacao";
import { exportCSV } from "@/utils/exportCSV";

// ─── Health badge (usa quality_score do backend) ─────────────────────────────
function HealthBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const color =
    score >= 80 ? "bg-green-100 text-green-700" :
    score >= 60 ? "bg-yellow-100 text-yellow-700" :
    score >= 40 ? "bg-orange-100 text-orange-700" :
    "bg-red-100 text-red-700";
  const label =
    score >= 80 ? "Otimo" :
    score >= 60 ? "Bom" :
    score >= 40 ? "Atencao" : "Critico";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {score} {label}
    </span>
  );
}

const PERIOD_OPTIONS = [
  { value: "today", label: "Hoje" },
  { value: "7d", label: "7 dias" },
  { value: "15d", label: "15 dias" },
  { value: "30d", label: "30 dias" },
  { value: "60d", label: "60 dias" },
] as const;

export default function Anuncios() {
  const [searchTerm, setSearchTerm] = useState("");
  const [tablePeriod, setTablePeriod] = useState<string>("today");

  const { data: listings, isLoading, error } = useQuery({
    queryKey: ["listings", tablePeriod],
    queryFn: () => listingsService.list(tablePeriod),
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary"],
    queryFn: () => listingsService.getKpiSummary(),
    retry: 2,
  });

  const displayListings = listings ?? [];

  // Ordenar por vendas do dia (unidades vendidas) — maior primeiro
  const sortedListings = [...displayListings].sort((a, b) => {
    const salesA = a.last_snapshot?.sales_today ?? 0;
    const salesB = b.last_snapshot?.sales_today ?? 0;
    return salesB - salesA;
  });

  // Filtro de busca client-side (titulo, mlb_id, seller_sku)
  const filteredListings = searchTerm.trim()
    ? sortedListings.filter((l) => {
        const term = searchTerm.toLowerCase();
        return (
          (l.title || "").toLowerCase().includes(term) ||
          (l.mlb_id || "").toLowerCase().includes(term) ||
          (l.seller_sku || "").toLowerCase().includes(term)
        );
      })
    : sortedListings;

  // Totais calculados (usam filteredListings para refletir busca)
  const totalPedidos = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.orders_count ?? l.last_snapshot?.sales_today ?? 0), 0);
  const totalUnidades = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.sales_today ?? 0), 0);
  const totalReceita = filteredListings.reduce((sum, l) => {
    const snap = l.last_snapshot;
    const effectivePrice = l.sale_price ?? l.price;
    return sum + (snap?.revenue ?? ((snap?.sales_today ?? 0) * effectivePrice));
  }, 0);
  const totalEstoque = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.stock ?? 0), 0);
  const totalVisitas = filteredListings.reduce((sum, l) => sum + (l.last_snapshot?.visits ?? 0), 0);
  const avgConversao = totalVisitas > 0 ? (totalUnidades / totalVisitas) * 100 : 0;
  const avgPrecoMedio = totalUnidades > 0 ? totalReceita / totalUnidades : 0;
  const avgPrecoMedioPorVenda = totalPedidos > 0 ? totalReceita / totalPedidos : 0;
  const totalEstoqueValor = filteredListings.reduce((sum, l) => {
    const preco = l.sale_price ?? l.price;
    const estoque = l.last_snapshot?.stock ?? 0;
    return sum + preco * estoque;
  }, 0);

  // colSpan: Produto + Tipo + Pedidos + Unidades + Receita + VoceRecebe + Preco/Un + Preco/Venda + Participacao + Visitas + Conversao + Estoque + DiasZerar + Acoes = 14
  const totalCols = 14;

  return (
    <div className="p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Anuncios</h1>
          <p className="text-muted-foreground mt-1">
            Gerencie seus anuncios do Mercado Livre
          </p>
        </div>
        {displayListings.length > 0 && (
          <button
            onClick={() => exportCSV(filteredListings, true)}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent transition-colors"
          >
            <Download className="h-4 w-4" />
            Baixar Relatorio
          </button>
        )}
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
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalEstoqueValor)}</p>
        </div>
      )}

      {/* ─── Filtro de periodo ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 mb-4 bg-muted/50 rounded-lg p-1 w-fit">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setTablePeriod(opt.value)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              tablePeriod === opt.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* ─── Tabela de anuncios com colunas completas ──────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-foreground shrink-0">Todos os Anuncios ({filteredListings.length})</h2>
          <div className="flex items-center gap-3 flex-1 justify-end">
            {/* Campo de busca */}
            <div className="relative max-w-xs w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Buscar por titulo, MLB ou SKU..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
            </div>
            {displayListings.length > 0 && (
              <button
                onClick={() => exportCSV(filteredListings, true)}
                className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors shrink-0"
              >
                <Download className="h-3.5 w-3.5" />
                CSV
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Produto</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Tipo</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Pedidos</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Unidades</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Receita (R$)</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Voce Recebe</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Unidade</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Venda</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Participacao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Visitas</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Conversao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Estoque</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Dias p/ Zerar</th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={totalCols} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : filteredListings.length === 0 ? (
                <tr>
                  <td colSpan={totalCols} className="px-6 py-12 text-center">
                    <TrendingUp className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                    <p className="font-medium text-foreground">
                      {searchTerm ? `Nenhum anuncio encontrado para "${searchTerm}"` : "Nenhum anuncio encontrado"}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {searchTerm ? "Tente outro termo de busca." : "Conecte sua conta do Mercado Livre para sincronizar seus anuncios."}
                    </p>
                  </td>
                </tr>
              ) : (
                <>
                  {filteredListings.map((listing) => {
                    const effectivePrice = listing.sale_price ?? listing.price;
                    const origPrice = listing.original_price ?? (listing.sale_price != null && listing.sale_price < listing.price ? listing.price : null);
                    const hasDiscount = origPrice != null && Number(origPrice) > Number(effectivePrice);
                    const snap = listing.last_snapshot;
                    const pedidos = snap?.orders_count ?? snap?.sales_today ?? 0;
                    const unidades = snap?.sales_today ?? 0;
                    const receita = snap?.revenue ?? (unidades * effectivePrice);
                    const precoMedio = snap?.avg_selling_price ?? (unidades > 0 ? receita / unidades : effectivePrice);
                    const precoMedioPorVenda = listing.avg_price_per_sale ?? (pedidos > 0 ? receita / pedidos : null);
                    const participacao = listing.participacao_pct;
                    const visitas = snap?.visits ?? 0;
                    const conversao = snap?.conversion_rate;
                    const estoque = snap?.stock;

                    return (
                      <tr
                        key={listing.id}
                        className="border-b hover:bg-muted/50 transition-colors"
                      >
                        {/* Produto: thumbnail + titulo + MLB ID + SKU + health badge */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            {listing.thumbnail ? (
                              <img
                                src={listing.thumbnail}
                                alt={listing.title}
                                className="h-10 w-10 rounded object-cover shrink-0 border"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-muted flex items-center justify-center shrink-0">
                                <Package className="h-4 w-4 text-muted-foreground/50" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <Link
                                  to={`/anuncios/${listing.mlb_id}`}
                                  className="font-medium text-primary hover:underline line-clamp-1 text-xs leading-tight"
                                >
                                  {listing.title}
                                </Link>
                                <HealthBadge score={listing.quality_score ?? null} />
                              </div>
                              <p className="text-xs text-muted-foreground font-mono">
                                {listing.mlb_id}
                                {listing.seller_sku && ` . SKU: ${listing.seller_sku}`}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {hasDiscount && (
                                  <span className="text-xs text-muted-foreground line-through">{formatCurrency(origPrice!)}</span>
                                )}
                                <span className={`text-xs font-medium ${hasDiscount ? "text-green-600" : ""}`}>
                                  {formatCurrency(effectivePrice)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </td>
                        {/* Tipo */}
                        <td className="px-4 py-3">
                          <span className={cn(
                            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                            listing.listing_type === "full"
                              ? "bg-purple-100 text-purple-700"
                              : listing.listing_type === "premium"
                              ? "bg-blue-100 text-blue-700"
                              : "bg-gray-100 text-gray-700",
                          )}>
                            {listing.listing_type}
                          </span>
                        </td>
                        {/* Pedidos */}
                        <td className="px-4 py-3 text-right font-medium">
                          {pedidos > 0 ? pedidos : "-"}
                        </td>
                        {/* Unidades + variacao */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex flex-col items-end gap-0.5">
                            <span className="font-medium">{unidades > 0 ? unidades : "-"}</span>
                            <Variacao value={listing.vendas_variacao} />
                          </div>
                        </td>
                        {/* Receita + variacao */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex flex-col items-end gap-0.5">
                            <span className="font-medium text-green-600">{receita > 0 ? formatCurrency(receita) : "-"}</span>
                            <Variacao value={listing.receita_variacao} />
                          </div>
                        </td>
                        {/* Voce Recebe */}
                        <td className="px-4 py-3 text-right font-semibold text-green-600">
                          {listing.voce_recebe != null ? formatCurrency(listing.voce_recebe) : "-"}
                        </td>
                        {/* Preco/Unidade */}
                        <td className="px-4 py-3 text-right">
                          {formatCurrency(precoMedio)}
                        </td>
                        {/* Preco/Venda */}
                        <td className="px-4 py-3 text-right">
                          {precoMedioPorVenda != null ? (
                            <span className="text-blue-700 font-medium">{formatCurrency(precoMedioPorVenda)}</span>
                          ) : "-"}
                        </td>
                        {/* Participacao % */}
                        <td className="px-4 py-3 text-right">
                          {participacao != null ? (
                            <div className="flex flex-col items-end gap-0.5">
                              <span className={cn(
                                "text-xs font-semibold",
                                participacao >= 30 ? "text-green-700" : participacao >= 10 ? "text-yellow-700" : "text-muted-foreground"
                              )}>
                                {participacao.toFixed(1)}%
                              </span>
                              <div className="w-12 h-1 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={cn(
                                    "h-full rounded-full",
                                    participacao >= 30 ? "bg-green-500" : participacao >= 10 ? "bg-yellow-500" : "bg-gray-400"
                                  )}
                                  style={{ width: `${Math.min(100, participacao)}%` }}
                                />
                              </div>
                            </div>
                          ) : "-"}
                        </td>
                        {/* Visitas */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Eye className="h-3 w-3 text-muted-foreground/50" />
                            <span>{visitas > 0 ? visitas.toLocaleString("pt-BR") : "-"}</span>
                          </div>
                        </td>
                        {/* Conversao */}
                        <td className="px-4 py-3 text-right">
                          {conversao != null ? (
                            <span className={cn(
                              "font-medium",
                              Number(conversao) >= 3 ? "text-green-600" : Number(conversao) >= 1 ? "text-yellow-600" : "text-red-500"
                            )}>
                              {formatPercent(Number(conversao))}
                            </span>
                          ) : "-"}
                        </td>
                        {/* Estoque */}
                        <td className="px-4 py-3 text-right">
                          <span className={cn(
                            (estoque ?? 0) < 10 ? "text-red-600 font-medium" : "",
                          )}>
                            {estoque ?? "-"}
                          </span>
                        </td>
                        {/* Dias p/ Zerar */}
                        <td className="px-4 py-3 text-right">
                          <DiasBadge dias={listing.dias_para_zerar} />
                        </td>
                        {/* Acoes */}
                        <td className="px-4 py-3 text-center">
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
                    );
                  })}

                  {/* ── Linha de totais ── */}
                  <tr className="bg-muted/30 font-bold border-t-2">
                    <td className="px-4 py-3 text-xs text-muted-foreground font-bold uppercase tracking-wide">
                      TOTAL ({filteredListings.length})
                    </td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3 text-right">{totalPedidos > 0 ? totalPedidos : "-"}</td>
                    <td className="px-4 py-3 text-right">{totalUnidades > 0 ? totalUnidades : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">{totalReceita > 0 ? formatCurrency(totalReceita) : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">--</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(avgPrecoMedio > 0 ? avgPrecoMedio : 0)}</td>
                    <td className="px-4 py-3 text-right text-blue-700">{avgPrecoMedioPorVenda > 0 ? formatCurrency(avgPrecoMedioPorVenda) : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">100%</td>
                    <td className="px-4 py-3 text-right">{totalVisitas > 0 ? totalVisitas.toLocaleString("pt-BR") : "-"}</td>
                    <td className="px-4 py-3 text-right">{formatPercent(avgConversao)}</td>
                    <td className="px-4 py-3 text-right">{totalEstoque > 0 ? totalEstoque : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">--</td>
                    <td className="px-4 py-3"></td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
