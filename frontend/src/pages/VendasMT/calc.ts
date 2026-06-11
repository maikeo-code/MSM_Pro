// Fórmula do "que sobra da venda" — extraída e validada no Mercado Turbo.
// Ver mercadoturbo_research/03-MECANISMO-ENDPOINTS.md.
import type { Venda } from "./types";

export const brl = (n: number | null | undefined): string =>
  n == null
    ? "—"
    : (n < 0 ? "-" : "") +
      "R$ " +
      Math.abs(n).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const pct = (n: number | null | undefined): string =>
  n == null ? "—" : `${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

export function calcular(
  v: Pick<Venda, "produtos" | "tarifaML" | "imposto" | "custoProduto" | "frete" | "total">
) {
  const receitaLiquida = v.produtos + (v.tarifaML ?? 0) + (v.imposto ?? 0);
  const lucro = receitaLiquida + (v.custoProduto ?? 0) + (v.frete ?? 0);
  const margem = v.total ? (lucro / v.total) * 100 : 0;
  return { receitaLiquida, lucro, margem };
}

// Cor da margem (faixas do Turbo): <5% vermelho, <15% amarelo, senão verde.
export function corMargem(margem: number | null): string {
  if (margem == null) return "text-[#33313B]";
  if (margem < 5) return "text-[#D43B4F]";
  if (margem < 15) return "text-[#FFC107]";
  return "text-[#329F69]";
}
