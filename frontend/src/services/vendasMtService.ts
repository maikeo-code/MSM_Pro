import api from "./api";
import type { Venda } from "@/pages/VendasMT/types";

export interface VendasMTResponse {
  fonte: string;
  conta: string;
  total: number;
  vendas: Venda[];
}

// Aba Vendas (MT) — cadeia de endpoints do Mercado Turbo sobre a API do ML.
// Backend: GET /api/v1/vendas-mt/ (ver app/vendas_mt/).
export async function listVendasMT(
  period: string = "30d",
  mlAccountId?: string | null
): Promise<VendasMTResponse> {
  const params: Record<string, unknown> = { period };
  if (mlAccountId) params.ml_account_id = mlAccountId;
  const { data } = await api.get<VendasMTResponse>("/vendas-mt/", { params });
  return data;
}
