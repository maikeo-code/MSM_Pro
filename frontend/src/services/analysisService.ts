import api from "./api";

export interface AnuncioAnalise {
  mlb_id: string;
  titulo: string;
  descricao: string | null;
  tipo: "classico" | "premium" | "full" | "fulfillment" | string;
  preco: number;
  preco_original: number | null;
  visitas_hoje: number;
  visitas_ontem: number;
  conversao_7d: number | null;
  conversao_15d: number | null;
  conversao_30d: number | null;
  vendas_hoje: number;
  vendas_ontem: number;
  vendas_anteontem: number;
  vendas_7d: number;
  dias_dados_7d: number;
  dias_dados_15d: number;
  dias_dados_30d: number;
  estoque: number;
  roas_7d: number | null;
  roas_15d: number | null;
  roas_30d: number | null;
  acos_7d: number | null;
  acos_15d: number | null;
  acos_30d: number | null;
  thumbnail: string | null;
  permalink: string | null;
  quality_score: number | null;
}

export interface AnalysisResponse {
  total: number;
  anuncios: AnuncioAnalise[];
}

const analysisService = {
  async getListingsAnalysis(mlAccountId?: string | null): Promise<AnalysisResponse> {
    const params: any = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<AnalysisResponse>("/analysis/listings", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },
};

export default analysisService;
