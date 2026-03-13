import type { ListingOut } from "@/services/listingsService";

/**
 * Gera e dispara o download de um CSV com os dados dos anuncios.
 *
 * @param listings - Lista de anuncios a exportar
 * @param includeType - Incluir coluna "Tipo" (padrao: false). Usar true na pagina Anuncios.
 */
export function exportCSV(listings: ListingOut[], includeType = false): void {
  const baseHeaders = ["MLB", "Titulo", "SKU"];
  const typeHeader = includeType ? ["Tipo"] : [];
  const restHeaders = ["Preco", "Estoque", "Visitas", "Vendas", "Conversao", "Receita", "Participacao", "Score"];
  const headers = [...baseHeaders, ...typeHeader, ...restHeaders];

  const rows = listings.map((l) => {
    const snap = l.last_snapshot;
    const effectivePrice = l.sale_price ?? l.price;
    const unidades = snap?.sales_today ?? 0;
    const receita = snap?.revenue ?? unidades * effectivePrice;

    const baseFields = [
      l.mlb_id,
      `"${(l.title || "").replace(/"/g, '""')}"`,
      l.seller_sku || "",
    ];
    const typeField = includeType ? [l.listing_type] : [];
    const restFields = [
      effectivePrice.toFixed(2),
      snap?.stock ?? 0,
      snap?.visits ?? 0,
      unidades,
      snap?.conversion_rate != null ? Number(snap.conversion_rate).toFixed(2) + "%" : "",
      receita > 0 ? receita.toFixed(2) : "0",
      l.participacao_pct != null ? l.participacao_pct.toFixed(1) + "%" : "",
      l.quality_score ?? "",
    ];

    return [...baseFields, ...typeField, ...restFields].join(",");
  });

  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `anuncios_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
