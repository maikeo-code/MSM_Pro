import api from "./api";

export interface SnapshotOut {
  id: string;
  listing_id: string;
  price: string;
  visits: number;
  sales_today: number;
  questions: number;
  stock: number;
  conversion_rate: string | null;
  captured_at: string;
}

export interface ListingOut {
  id: string;
  user_id: string;
  product_id: string;
  ml_account_id: string;
  mlb_id: string;
  title: string;
  listing_type: "classico" | "premium" | "full";
  price: string;
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
  preco: string;
  custo_sku: string;
  taxa_ml_pct: string;
  taxa_ml_valor: string;
  frete: string;
  margem_bruta: string;
  margem_pct: string;
  lucro: string;
  listing_type: string;
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

  async getMargem(mlbId: string, preco: number): Promise<MargemResult> {
    const { data } = await api.get<MargemResult>(`/listings/${mlbId}/margem`, {
      params: { preco },
    });
    return data;
  },
};

export default listingsService;
