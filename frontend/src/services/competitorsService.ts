import api from "./api";

export interface CompetitorOut {
  id: string;
  listing_id: string;
  mlb_id: string;
  title: string | null;
  seller_nickname: string | null;
  thumbnail: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CompetitorCreate {
  listing_id: string;
  competitor_mlb_id: string;
}

export interface CompetitorHistoryItem {
  date: string;
  price: number;
  sold_quantity: number | null;
  sales_delta: number;
}

export interface CompetitorHistory {
  competitor_id: string;
  mlb_id: string;
  title: string | null;
  days: number;
  history: CompetitorHistoryItem[];
}

const competitorsService = {
  async list(mlAccountId?: string | null): Promise<CompetitorOut[]> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<CompetitorOut[]>("/competitors/", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async listByListing(listingId: string, mlAccountId?: string | null): Promise<CompetitorOut[]> {
    const params: Record<string, unknown> = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<CompetitorOut[]>(`/competitors/listing/${listingId}`, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return data;
  },

  async add(payload: CompetitorCreate): Promise<CompetitorOut> {
    const { data } = await api.post<CompetitorOut>("/competitors/", payload);
    return data;
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/competitors/${id}`);
  },

  async getHistory(competitorId: string, days = 30): Promise<CompetitorHistory> {
    const { data } = await api.get<CompetitorHistory>(`/competitors/${competitorId}/history`, {
      params: { days },
    });
    return data;
  },
};

export default competitorsService;
