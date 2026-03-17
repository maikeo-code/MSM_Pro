// ─── Tipos compartilhados dos componentes de AnuncioDetalhe ──────────────────

export type ChartView = "vendas" | "preco" | "conversao" | "completo";

export interface ChartDataPoint {
  date: string;
  vendas: number;
  conversao: number;
  visitas: number;
  preco: number;
  receita: number;
  precoMedio: number;
  pedidos: number;
}
