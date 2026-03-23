import api from "./api";

// ─── Simulador de Risco ───────────────────────────────────────────────────────

export interface RiskItem {
  kpi: string;
  label: string;
  current_rate: number;
  threshold: number;
  current_count: number;
  max_allowed: number;
  buffer: number;
  risk_level: "critical" | "warning" | "safe";
}

export interface ReputationRisk {
  ml_account_id: string;
  total_sales_60d: number;
  items: RiskItem[];
}

export interface HealthDimensionItem {
  dimension: string; // claims, mediations, cancellations, late_shipments
  rate: number;
  status: "good" | "warning" | "critical";
  threshold_good: number;
  threshold_warning: number;
}

export interface ReputationThresholds {
  claims: number;
  mediations: number;
  cancellations: number;
  late_shipments: number;
}

export interface ReputationCurrent {
  ml_account_id: string;
  nickname: string | null;
  seller_level: string | null;
  power_seller_status: string | null;
  claims_rate: number;
  mediations_rate: number;
  cancellations_rate: number;
  late_shipments_rate: number;
  claims_value: number;
  mediations_value: number;
  cancellations_value: number;
  late_shipments_value: number;
  total_sales_60d: number;
  completed_sales_60d: number;
  total_revenue_60d: number;
  captured_at: string | null;
  // Thresholds dinâmicos retornados pelo backend
  thresholds?: ReputationThresholds;
  // Health score por dimensão
  health_by_dimension?: HealthDimensionItem[];
}

export interface ReputationSnapshot {
  id: string;
  ml_account_id: string;
  seller_level: string | null;
  power_seller_status: string | null;
  claims_rate: number | null;
  mediations_rate: number | null;
  cancellations_rate: number | null;
  late_shipments_rate: number | null;
  total_sales_60d: number | null;
  completed_sales_60d: number | null;
  total_revenue_60d: number | null;
  claims_value: number | null;
  mediations_value: number | null;
  cancellations_value: number | null;
  late_shipments_value: number | null;
  captured_at: string;
}

const reputacaoService = {
  async getCurrent(mlAccountId?: string): Promise<ReputationCurrent> {
    const params: Record<string, string> = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ReputationCurrent>("/reputation/current", { params });
    return data;
  },

  async getHistory(days = 60, mlAccountId?: string): Promise<ReputationSnapshot[]> {
    const params: Record<string, string | number> = { days };
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ReputationSnapshot[]>("/reputation/history", { params });
    return data;
  },

  async sync(mlAccountId?: string): Promise<{ success: boolean; synced: number }> {
    const params: Record<string, string> = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.post("/reputation/sync", null, { params });
    return data;
  },

  async getRiskSimulator(mlAccountId?: string): Promise<ReputationRisk> {
    const params: Record<string, string> = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    const { data } = await api.get<ReputationRisk>("/reputation/risk-simulator", { params });
    return data;
  },
};

export default reputacaoService;
