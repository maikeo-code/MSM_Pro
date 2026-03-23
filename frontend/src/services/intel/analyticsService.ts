import api from "../api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ParetoItem {
  mlb_id: string;
  title: string;
  revenue_30d: number;
  revenue_pct: number;
  cumulative_pct: number;
  classification: "core" | "productive" | "long_tail";
}

export interface ParetoResponse {
  items: ParetoItem[];
  total_revenue: number;
  core_count: number;
  core_revenue_pct: number;
  concentration_risk: "high" | "medium" | "low";
}

export interface ForecastPoint {
  date: string;
  predicted_sales: number;
  lower_bound: number;
  upper_bound: number;
}

export interface ForecastResponse {
  listing_mlb_id: string;
  forecast_7d: ForecastPoint[];
  forecast_30d: ForecastPoint[];
  trend: "up" | "down" | "stable";
  confidence: number;
}

export interface DistributionItem {
  mlb_id: string;
  title: string;
  revenue_30d: number;
  sales_count: number;
  pct_of_total: number;
}

export interface DistributionResponse {
  items: DistributionItem[];
  total_revenue: number;
  total_sales: number;
  gini_coefficient: number;
}

export interface InsightItem {
  id: string;
  type: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  created_at: string;
}

export interface InsightsResponse {
  insights: InsightItem[];
  generated_at: string;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const analyticsService = {
  async getPareto(days = 30): Promise<ParetoResponse> {
    const { data } = await api.get<ParetoResponse>(
      `/intel/analytics/pareto?days=${days}`
    );
    return data;
  },

  async getForecast(
    mlbId: string,
    daysHistory = 60
  ): Promise<ForecastResponse> {
    const { data } = await api.get<ForecastResponse>(
      `/intel/analytics/forecast/${mlbId}?days_history=${daysHistory}`
    );
    return data;
  },

  async getDistribution(days = 30): Promise<DistributionResponse> {
    const { data } = await api.get<DistributionResponse>(
      `/intel/analytics/distribution?days=${days}`
    );
    return data;
  },

  async getInsights(): Promise<InsightsResponse> {
    const { data } = await api.get<InsightsResponse>(
      `/intel/analytics/insights`
    );
    return data;
  },
};
