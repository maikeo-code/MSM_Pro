import api from "./api";

export interface CompetitorOut {
  id: string;
  listing_id: string;
  mlb_id: string;
  title: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CompetitorCreate {
  listing_id: string;
  competitor_mlb_id: string;
}

const competitorsService = {
  async list(): Promise<CompetitorOut[]> {
    const { data } = await api.get<CompetitorOut[]>("/competitors/");
    return data;
  },

  async listByListing(listingId: string): Promise<CompetitorOut[]> {
    const { data } = await api.get<CompetitorOut[]>(`/competitors/listing/${listingId}`);
    return data;
  },

  async add(payload: CompetitorCreate): Promise<CompetitorOut> {
    const { data } = await api.post<CompetitorOut>("/competitors/", payload);
    return data;
  },

  async remove(id: string): Promise<void> {
    await api.delete(`/competitors/${id}`);
  },
};

export default competitorsService;
