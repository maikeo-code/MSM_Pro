import api from "./api";

// ─── Tipos alinhados com o backend ────────────────────────────────────────────

// ─── Cash Flow Projetado D+8 ──────────────────────────────────────────────────

export interface CashFlowDay {
  date: string;
  amount: number;
  orders_count: number;
}

export interface CashFlow {
  proximos_7d: number;
  proximos_14d: number;
  proximos_30d: number;
  total_pendente: number;
  timeline: CashFlowDay[];
}

export interface FinanceiroResumo {
  periodo: string;
  data_inicio: string;
  data_fim: string;
  // Valores financeiros
  vendas_brutas: number;
  taxas_ml_total: number;
  frete_total: number;
  receita_liquida: number;
  custo_total: number;
  margem_bruta: number;
  margem_pct: number;
  // Volumes
  total_pedidos: number;
  total_cancelamentos: number;
  total_devolucoes: number;
  // Variações (podem ser null)
  variacao_vendas_pct: number | null;
  variacao_receita_pct: number | null;
}

export interface FinanceiroTimelinePoint {
  date: string;
  vendas_brutas: number;
  receita_liquida: number;
  taxas: number;
  frete: number;
  pedidos: number;
}

// Backend retorna FinanceiroTimeSeriesOut = { periodo, data_inicio, data_fim, points: [...] }
interface FinanceiroTimeSeriesOut {
  periodo: string;
  data_inicio: string;
  data_fim: string;
  points: FinanceiroTimelinePoint[];
}

export interface FinanceiroDetalhado {
  mlb_id: string;
  title: string;
  listing_type: string;
  thumbnail: string | null;
  // Financeiro — nomes EXATOS do backend
  vendas_brutas: number;
  taxa_ml_pct: number;
  taxa_ml_valor: number;
  frete: number;              // backend usa "frete", não "frete_valor"
  receita_liquida: number;
  custo_unitario: number | null;
  custo_total: number | null;
  margem: number | null;
  margem_pct: number | null;
  // Volumes
  unidades: number;
  cancelamentos: number;
  devolucoes: number;
}

// Backend retorna FinanceiroDetalhadoOut = { periodo, data_inicio, data_fim, items: [...] }
interface FinanceiroDetalhadoOut {
  periodo: string;
  data_inicio: string;
  data_fim: string;
  items: FinanceiroDetalhado[];
}

const financeiroService = {
  async getResumo(period: string = "30d", mlAccountId?: string | null): Promise<FinanceiroResumo> {
    const params: any = { period };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<FinanceiroResumo>("/financeiro/resumo", {
      params,
    });
    return data;
  },

  // Backend retorna { periodo, data_inicio, data_fim, points: [...] }
  // Extraímos o array .points para o consumidor
  async getTimeline(period: string = "30d", mlAccountId?: string | null): Promise<FinanceiroTimelinePoint[]> {
    const params: any = { period };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<FinanceiroTimeSeriesOut>("/financeiro/timeline", {
      params,
    });
    return data.points ?? [];
  },

  // Backend retorna { periodo, data_inicio, data_fim, items: [...] }
  // Extraímos o array .items para o consumidor
  async getDetalhado(period: string = "30d", mlAccountId?: string | null): Promise<FinanceiroDetalhado[]> {
    const params: any = { period };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<FinanceiroDetalhadoOut>("/financeiro/detalhado", {
      params,
    });
    return data.items ?? [];
  },

  async getCashflow(mlAccountId?: string | null): Promise<CashFlow> {
    const params: any = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<CashFlow>("/financeiro/cashflow", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },
};

export default financeiroService;
