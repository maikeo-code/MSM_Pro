import api from "./api";

export interface KpiPeriod {
  vendas: number;
  visitas: number;
  conversao: number;
  anuncios: number;
  valor_estoque: number;
  receita: number;
  // Campos analytics
  pedidos?: number;
  receita_total?: number;
  preco_medio?: number;
  taxa_cancelamento?: number;
  // Novos campos (itens 1, 3, 4, 5)
  preco_medio_por_venda?: number;
  vendas_concluidas?: number;
  cancelamentos_valor?: number;
  devolucoes_valor?: number;
  devolucoes_qtd?: number;
  // Variacoes
  vendas_variacao?: number | null;
  receita_variacao?: number | null;
  visitas_variacao?: number | null;
  conversao_variacao?: number | null;
  // Medias diarias (Tema 2) — usadas para comparar periodos > 1 dia com dias individuais
  dias_no_periodo?: number;
  vendas_media_dia?: number;
  visitas_media_dia?: number;
  pedidos_media_dia?: number;
  receita_media_dia?: number;
}

export interface KpiSummary {
  hoje: KpiPeriod;
  ontem: KpiPeriod;
  anteontem: KpiPeriod;
  "7dias": KpiPeriod;
  "30dias": KpiPeriod;
}

export interface SnapshotOut {
  id: string;
  listing_id: string;
  price: number;
  visits: number;
  sales_today: number;
  questions: number;
  stock: number;
  conversion_rate: number | null;
  captured_at: string;
  // Campos analytics existentes
  orders_count?: number;
  revenue?: number;
  avg_selling_price?: number;
  cancelled_orders?: number;
  // Novos campos (migration 0005)
  cancelled_revenue?: number;
  returns_count?: number;
  returns_revenue?: number;
}

export interface ListingOut {
  id: string;
  user_id: string;
  product_id: string | null;
  ml_account_id: string;
  mlb_id: string;
  title: string;
  listing_type: "classico" | "premium" | "full";
  price: number;
  original_price: number | null;
  sale_price: number | null;
  status: string;
  permalink: string | null;
  thumbnail: string | null;
  created_at: string;
  updated_at: string;
  last_snapshot: SnapshotOut | null;
  // Campos calculados existentes
  dias_para_zerar?: number | null;
  rpv?: number | null;
  taxa_cancelamento?: number | null;
  // Novos campos calculados (itens 1, 2, 5)
  avg_price_per_sale?: number | null;
  participacao_pct?: number | null;
  vendas_concluidas?: number | null;
  // Novos campos para UI (SKU e voce_recebe)
  seller_sku?: string | null;
  category_id?: string | null;
  voce_recebe?: number | null;
  // Quality score (0-100) calculado no backend
  quality_score?: number | null;
  // Variacao por anuncio (hoje vs ontem)
  vendas_variacao?: number | null;
  receita_variacao?: number | null;
  // Media de visitas por dia (para periodos > 1 dia)
  avg_visits_per_day?: number | null;
}

export interface FunnelData {
  visitas: number;
  vendas: number;
  conversao: number;
  receita: number;
}

export interface HeatmapCell {
  day_of_week: number; // 0=seg, 6=dom
  hour: number;        // 0-23 (0 quando fallback por dia)
  day_name: string;
  count: number;
  avg_per_week: number;
}

export interface HeatmapData {
  data: HeatmapCell[];
  peak_day: string;
  peak_day_index: number;
  peak_hour: string;       // ex: "14:00-15:00" (vazio no fallback)
  avg_daily: number;
  total_sales: number;
  period_days: number;
  has_hourly_data: boolean; // true = Orders (dia+hora), false = fallback snapshots
}

// Alias para compatibilidade com imports antigos
export type HeatmapDay = HeatmapCell;

export interface ListingCreate {
  product_id?: string | null;
  ml_account_id: string;
  mlb_id: string;
  title: string;
  listing_type?: "classico" | "premium" | "full";
  price: number;
  permalink?: string;
  thumbnail?: string;
}

export interface MargemResult {
  preco: number;
  custo_sku: number;
  taxa_ml_pct: number;
  taxa_ml_valor: number;
  frete: number;
  margem_bruta: number;
  margem_pct: number;
  lucro: number;
  listing_type: string;
}

export interface PriceBand {
  price_range_label: string;
  avg_sales_per_day: number;
  avg_conversion: number;
  total_revenue: number;
  avg_margin: number;
  days_count: number;
  is_optimal: boolean;
}

export interface SKUInfo {
  id: string | null;
  sku: string | null;
  cost: number;
}

export interface FullStock {
  available: number;
  in_transit: number;
  days_until_stockout_7d: number | null;
  days_until_stockout_30d: number | null;
  velocity_7d: number;
  velocity_30d: number;
  status: "critical" | "warning" | "excess" | "ok";
}

export interface Promotion {
  id: string;
  type: string;
  discount_pct: number;
  original_price: number;
  final_price: number;
  start_date: string;
  end_date: string;
  status: string;
}

export interface Ads {
  roas: number;
  impressions: number;
  clicks: number;
  cpc: number;
  ctr: number;
  spend: number;
  attributed_sales: number;
}

export interface CompetitorPrice {
  mlb_id: string;
  price: number;
  last_updated: string;
}

export interface Alert {
  type: string;
  message: string;
  severity: "critical" | "warning" | "info";
}

export interface HealthCheck {
  item: string;
  ok: boolean;
  points: number;
  max: number;
  action?: string;
  detail?: string;
}

export interface ListingHealth {
  score: number;
  status: "excellent" | "good" | "warning" | "critical";
  label: string;
  color: string;
  checks: HealthCheck[];
}

export interface ListingAnalysis {
  is_mock: boolean;
  listing: {
    mlb_id: string;
    title: string;
    price: number;
    listing_type: string;
    status: string;
    thumbnail: string | null;
    permalink: string | null;
  };
  sku: SKUInfo;
  snapshots: SnapshotOut[];
  price_bands: PriceBand[];
  full_stock: FullStock;
  promotions: Promotion[];
  ads: Partial<Ads>;
  competitor: CompetitorPrice | null;
  alerts: Alert[];
}

export interface UpdatePricePayload {
  price: number;
}

export interface CreatePromotionPayload {
  discount_pct: number;
  start_date: string;
  end_date: string;
  promotion_id?: string;
}

export interface SearchPositionResult {
  found: boolean;
  position?: number;
  page?: number;
  total_results: number;
  keyword: string;
  mlb_id: string;
}

export interface PriceHistoryItem {
  id: string;
  mlb_id: string;
  old_price: number | null;
  new_price: number | null;
  source: string;
  justification: string | null;
  success: boolean;
  error_message: string | null;
  changed_at: string;
}

export interface SimulatePriceResult {
  target_price: number;
  estimated_sales_per_day: number;
  estimated_revenue_per_day: number;
  estimated_margin: number;
  is_estimated: boolean;
  elasticity: number | null;
}

const listingsService = {
  async list(period: string = "today", mlAccountId?: string | null): Promise<ListingOut[]> {
    const params: Record<string, unknown> = period !== "today" ? { period } : {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<ListingOut[]>("/listings/", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async create(payload: ListingCreate): Promise<ListingOut> {
    const { data } = await api.post<ListingOut>("/listings/", payload);
    return data;
  },

  async getSnapshots(mlbId: string, dias = 30, mlAccountId?: string | null): Promise<SnapshotOut[]> {
    const params: Record<string, unknown> = { dias };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<SnapshotOut[]>(`/listings/${mlbId}/snapshots`, {
      params,
    });
    return data;
  },

  async getAnalysis(mlbId: string, days = 30, mlAccountId?: string | null): Promise<ListingAnalysis> {
    const params: Record<string, unknown> = { days };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<ListingAnalysis>(`/listings/${mlbId}/analysis`, {
      params,
    });
    return data;
  },

  async getMargem(mlbId: string, preco: number, mlAccountId?: string | null): Promise<MargemResult> {
    const params: Record<string, unknown> = { preco };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<MargemResult>(`/listings/${mlbId}/margem`, {
      params,
    });
    return data;
  },

  async updatePrice(
    mlbId: string,
    payload: UpdatePricePayload,
    mlAccountId?: string | null
  ): Promise<{ mlb_id: string; new_price: number; updated_at: string }> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.patch(`/listings/${mlbId}/price`, payload, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async createPromotion(
    mlbId: string,
    payload: CreatePromotionPayload,
    mlAccountId?: string | null
  ): Promise<Promotion> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.post<Promotion>(
      `/listings/${mlbId}/promotions`,
      payload,
      {
        params: Object.keys(params).length > 0 ? params : undefined,
      }
    );
    return data;
  },

  async getListingHealth(mlbId: string, mlAccountId?: string | null): Promise<ListingHealth> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<ListingHealth>(`/listings/${mlbId}/health`, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async sync(mlAccountId?: string | null): Promise<{ message: string; created: number; updated: number; total: number }> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.post("/listings/sync", {}, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async getKpiSummary(mlAccountId?: string | null): Promise<KpiSummary> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<KpiSummary>("/listings/kpi/summary", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async getFunnel(period: string = "7d", mlAccountId?: string | null): Promise<FunnelData> {
    const params: Record<string, unknown> = { period };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<FunnelData>("/listings/analytics/funnel", {
      params,
    });
    return data;
  },

  async linkSku(mlbId: string, productId: string | null, mlAccountId?: string | null): Promise<ListingOut> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.patch<ListingOut>(`/listings/${mlbId}/sku`, {
      product_id: productId,
    }, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async getHeatmap(period = "30d", mlAccountId?: string | null): Promise<HeatmapData> {
    const params: Record<string, unknown> = { period };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<HeatmapData>("/listings/analytics/heatmap", {
      params,
    });
    return data;
  },

  async getSearchPosition(mlbId: string, keyword: string, mlAccountId?: string | null): Promise<SearchPositionResult> {
    const params: Record<string, unknown> = { keyword };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<SearchPositionResult>(`/listings/${mlbId}/search-position`, {
      params,
    });
    return data;
  },

  async getPriceHistory(mlbId: string, limit = 50, mlAccountId?: string | null): Promise<PriceHistoryItem[]> {
    const params: Record<string, unknown> = { limit };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<PriceHistoryItem[]>(`/listings/${mlbId}/price-history`, {
      params,
    });
    return data;
  },

  async simulatePrice(mlbId: string, targetPrice: number, mlAccountId?: string | null): Promise<SimulatePriceResult> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.post<SimulatePriceResult>(`/listings/${mlbId}/simulate-price`, {
      target_price: targetPrice,
    }, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },
};

export default listingsService;
