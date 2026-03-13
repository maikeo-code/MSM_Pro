// Re-exporta formatadores ja definidos em lib/utils para uso centralizado
export { formatCurrency, formatPercent, formatDate, formatDateTime } from "@/lib/utils";

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "0";
  return new Intl.NumberFormat("pt-BR").format(value);
}
