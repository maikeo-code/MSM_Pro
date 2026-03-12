import api from "./api";

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
}

export interface ListingCreate {
  product_id: string;
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
  id: string;
  sku: string;
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

const listingsService = {
  async list(): Promise<ListingOut[]> {
    const { data } = await api.get<ListingOut[]>("/listings/");
    return data;
  },

  async create(payload: ListingCreate): Promise<ListingOut> {
    const { data } = await api.post<ListingOut>("/listings/", payload);
    return data;
  },

  async getSnapshots(mlbId: string, dias = 30): Promise<SnapshotOut[]> {
    const { data } = await api.get<SnapshotOut[]>(`/listings/${mlbId}/snapshots`, {
      params: { dias },
    });
    return data;
  },

  async getAnalysis(mlbId: string, days = 30): Promise<ListingAnalysis> {
    const { data } = await api.get<ListingAnalysis>(`/listings/${mlbId}/analysis`, {
      params: { days },
    });
    return data;
  },

  async getMargem(mlbId: string, preco: number): Promise<MargemResult> {
    const { data } = await api.get<MargemResult>(`/listings/${mlbId}/margem`, {
      params: { preco },
    });
    return data;
  },

  async updatePrice(
    mlbId: string,
    payload: UpdatePricePayload
  ): Promise<{ mlb_id: string; new_price: number; updated_at: string }> {
    const { data } = await api.patch(`/listings/${mlbId}/price`, payload);
    return data;
  },

  async createPromotion(
    mlbId: string,
    payload: CreatePromotionPayload
  ): Promise<Promotion> {
    const { data } = await api.post<Promotion>(
      `/listings/${mlbId}/promotions`,
      payload
    );
    return data;
  },

  async getListingHealth(mlbId: string): Promise<ListingHealth> {
    const { data } = await api.get<ListingHealth>(`/listings/${mlbId}/health`);
    return data;
  },

  async sync(): Promise<{ message: string; created: number; updated: number; total: number }> {
    const { data } = await api.post("/listings/sync");
    return data;
  },
};

export default listingsService;
