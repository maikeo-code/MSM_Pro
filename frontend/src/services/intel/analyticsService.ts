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

// ─── Temporal Comparison (MoM) ─────────────────────────────────────────────

export interface ComparisonItem {
  mlb_id: string;
  title: string;
  revenue_current: number;
  revenue_previous: number;
  revenue_delta_pct: number;
  sales_current: number;
  sales_previous: number;
  sales_delta_pct: number;
}

export interface ComparisonResponse {
  items: ComparisonItem[];
  period_days: number;
  total_revenue_current: number;
  total_revenue_previous: number;
  total_revenue_delta_pct: number;
  total_sales_current: number;
  total_sales_previous: number;
  total_sales_delta_pct: number;
}

// ─── ABC Classification ────────────────────────────────────────────────────

export interface ABCItem {
  mlb_id: string;
  title: string;
  classification: "A" | "B" | "C";
  revenue_30d: number;
  revenue_pct: number;
  cumulative_pct: number;
  units_sold: number;
  current_stock: number;
  turnover_rate: number;
  metric: string;
}

export interface ABCResponse {
  items: ABCItem[];
  period_days: number;
  metric_used: string;
  total_revenue: number;
  class_a_revenue_pct: number;
  class_b_revenue_pct: number;
  class_c_revenue_pct: number;
}

// ─── Inventory Health ──────────────────────────────────────────────────────

export interface InventoryHealthItem {
  mlb_id: string;
  title: string;
  current_stock: number;
  avg_daily_sales: number;
  sell_through_rate: number;
  days_of_stock: number;
  health_status: "healthy" | "overstocked" | "critical_low";
}

export interface InventoryHealthResponse {
  items: InventoryHealthItem[];
  period_days: number;
  total_items: number;
  healthy_count: number;
  overstocked_count: number;
  critical_low_count: number;
  avg_days_of_stock: number;
}

// ─── Service ──────────────────────────────────────────────────────────────────

export const analyticsService = {
  async getPareto(days = 30, mlAccountId?: string | null): Promise<ParetoResponse> {
    const params: any = { days };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ParetoResponse>("/intel/analytics/pareto", { params });
    return data;
  },

  async getForecast(
    mlbId: string,
    daysHistory = 60,
    mlAccountId?: string | null,
  ): Promise<ForecastResponse> {
    const params: any = { days_history: daysHistory };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ForecastResponse>(
      `/intel/analytics/forecast/${mlbId}`,
      { params },
    );
    return data;
  },

  async getDistribution(days = 30, mlAccountId?: string | null): Promise<DistributionResponse> {
    const params: any = { days };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<DistributionResponse>("/intel/analytics/distribution", { params });
    return data;
  },

  async getInsights(mlAccountId?: string | null): Promise<InsightsResponse> {
    const params: any = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<InsightsResponse>("/intel/analytics/insights", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async getComparison(period: "7d" | "15d" | "30d" = "30d", mlAccountId?: string | null): Promise<ComparisonResponse> {
    const params: any = { period };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ComparisonResponse>("/intel/analytics/comparison", { params });
    return data;
  },

  async getABC(
    period: "7d" | "15d" | "30d" = "30d",
    metric: "revenue" | "units" | "margin" = "revenue",
    mlAccountId?: string | null,
  ): Promise<ABCResponse> {
    const params: any = { period, metric };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ABCResponse>("/intel/analytics/abc", { params });
    return data;
  },

  async getInventoryHealth(period: "7d" | "15d" | "30d" = "30d", mlAccountId?: string | null): Promise<InventoryHealthResponse> {
    const params: any = { period };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<InventoryHealthResponse>("/intel/analytics/inventory-health", { params });
    return data;
  },
};
