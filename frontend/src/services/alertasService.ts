import api from "./api";

export type AlertType =
  | "conversion_below"
  | "stock_below"
  | "competitor_price_change"
  | "no_sales_days"
  | "competitor_price_below";

export type AlertChannel = "email" | "webhook";

export interface AlertConfigOut {
  id: string;
  user_id: string;
  listing_id: string | null;
  product_id: string | null;
  alert_type: AlertType;
  threshold: number | null;
  channel: AlertChannel;
  is_active: boolean;
  created_at: string;
}

export interface AlertConfigCreate {
  alert_type: AlertType;
  listing_id?: string | null;
  product_id?: string | null;
  threshold?: number | null;
  channel?: AlertChannel;
}

export interface AlertConfigUpdate {
  threshold?: number | null;
  channel?: AlertChannel;
  is_active?: boolean;
}

export interface AlertEventOut {
  id: string;
  alert_config_id: string;
  message: string;
  triggered_at: string;
  sent_at: string | null;
}

const alertasService = {
  async list(params?: { listing_id?: string; is_active?: boolean }): Promise<AlertConfigOut[]> {
    const { data } = await api.get<AlertConfigOut[]>("/alertas/", { params });
    return data;
  },

  async create(payload: AlertConfigCreate): Promise<AlertConfigOut> {
    const { data } = await api.post<AlertConfigOut>("/alertas/", payload);
    return data;
  },

  async get(id: string): Promise<AlertConfigOut> {
    const { data } = await api.get<AlertConfigOut>(`/alertas/${id}`);
    return data;
  },

  async update(id: string, payload: AlertConfigUpdate): Promise<AlertConfigOut> {
    const { data } = await api.put<AlertConfigOut>(`/alertas/${id}`, payload);
    return data;
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/alertas/${id}`);
  },

  async listEvents(days = 30): Promise<AlertEventOut[]> {
    const { data } = await api.get<AlertEventOut[]>("/alertas/events/", { params: { days } });
    return data;
  },

  async listEventsByAlert(alertId: string, days = 30): Promise<AlertEventOut[]> {
    const { data } = await api.get<AlertEventOut[]>(`/alertas/events/${alertId}`, {
      params: { days },
    });
    return data;
  },
};

export default alertasService;
