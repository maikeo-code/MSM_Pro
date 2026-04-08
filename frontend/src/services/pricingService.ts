import api from "./api";

export interface ScoreBreakdown {
  conv_trend: number;
  visit_trend: number;
  comp_score: number;
  stock_score: number;
  margem_score: number;
  hist_score?: number;
}

export interface PeriodMetrics {
  visits: number;
  sales: number;
  conversion: number;
  avg_price: number;
}

export interface PeriodsData {
  today: PeriodMetrics | null;
  yesterday: PeriodMetrics | null;
  day_before: PeriodMetrics | null;
  d3: PeriodMetrics | null;
  d4: PeriodMetrics | null;
  d5: PeriodMetrics | null;
  d6: PeriodMetrics | null;
  last_7d: PeriodMetrics | null;
  last_15d: PeriodMetrics | null;
  last_30d: PeriodMetrics | null;
}

export interface ConversionIndex {
  value: number;
  short_trend: number;  // ontem vs anteontem
  medium_trend: number; // ontem vs 7d
  long_trend: number;   // 7d vs 30d
}

export interface PriceRecommendation {
  id: string;
  listing_id: string;
  mlb_id: string;
  sku: string | null;
  title: string;
  thumbnail: string | null;

  current_price: number;
  suggested_price: number;
  price_change_pct: number;

  action: "increase" | "decrease" | "hold";
  confidence: "high" | "medium" | "low";
  risk_level: "low" | "medium" | "high";
  urgency: "immediate" | "next_48h" | "monitor";
  reasoning: string;

  score: number | null;
  score_breakdown: ScoreBreakdown | null;
  conversion_index: ConversionIndex | null;

  conversion_today: number | null;
  conversion_7d: number | null;
  visits_today: number | null;
  visits_7d: number | null;
  sales_today: number | null;
  sales_7d: number | null;
  stock: number | null;
  stock_days_projection: number | null;
  estimated_daily_sales: number | null;
  estimated_daily_profit: number | null;
  health_score: number | null;

  competitor_avg_price: number | null;
  competitor_min_price: number | null;

  periods_data: PeriodsData | null;

  // Promocao ativa no ML
  has_active_promotion: boolean | null;

  status: string;
  applied_at: string | null;
  report_date: string;
  created_at: string;
}

export interface RecommendationSummary {
  total: number;
  increase_count: number;
  decrease_count: number;
  hold_count: number;
  avg_confidence: string; // Backend retorna percentual de "high" confidence (ex: "75%")
}

export interface RecommendationListResponse {
  items: PriceRecommendation[];
  total: number;
  date: string;
  summary: RecommendationSummary;
}

export interface ApplyResponse {
  recommendation_id: string;
  mlb_id: string;
  old_price: number;
  new_price: number;
  ml_api_success: boolean;
  message: string;
  has_active_promotion: boolean | null;
  promo_warning: string | null;
}

// API calls
export const getRecommendations = async (
  params?: {
    report_date?: string;
    action?: string;
    confidence?: string;
    sort?: string;
  },
  mlAccountId?: string | null,
): Promise<RecommendationListResponse> => {
  const queryParams: Record<string, unknown> = { ...params };
  if (mlAccountId) {
    queryParams.ml_account_id = mlAccountId;
  }
  const { data } = await api.get("/intel/pricing/recommendations", {
    params: Object.keys(queryParams).length > 0 ? queryParams : undefined,
  });
  return data;
};

export const applyRecommendation = async (id: string, mlAccountId?: string | null): Promise<ApplyResponse> => {
  const params: Record<string, unknown> = {};
  if (mlAccountId) {
    params.ml_account_id = mlAccountId;
  }
  const { data } = await api.post(
    `/intel/pricing/recommendations/${id}/apply`,
    {},
    { params: Object.keys(params).length > 0 ? params : undefined },
  );
  return data;
};

export const dismissRecommendation = async (
  id: string,
  reason?: string,
): Promise<void> => {
  await api.post(`/intel/pricing/recommendations/${id}/dismiss`, { reason });
};

export const getRecommendationHistory = async (
  mlbId: string,
  days?: number,
): Promise<{
  items: PriceRecommendation[];
  total: number;
}> => {
  const { data } = await api.get(
    `/intel/pricing/recommendations/history/${mlbId}`,
    {
      params: { days: days || 30 },
    },
  );
  return data;
};

export const generateRecommendations = async (mlAccountId?: string | null): Promise<{
  status: string;
  recommendations_count: number;
  processing_time_ms: number;
  message: string;
}> => {
  const params: Record<string, unknown> = {};
  if (mlAccountId) {
    params.ml_account_id = mlAccountId;
  }
  const { data } = await api.post(
    "/intel/pricing/recommendations/generate",
    {},
    { params: Object.keys(params).length > 0 ? params : undefined },
  );
  return data;
};
