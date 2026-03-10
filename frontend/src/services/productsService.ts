import api from "./api";

export interface ProductOut {
  id: string;
  user_id: string;
  sku: string;
  name: string;
  cost: string;
  unit: string;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  sku: string;
  name: string;
  cost: number;
  unit?: string;
  notes?: string;
}

export interface ProductUpdate {
  name?: string;
  cost?: number;
  unit?: string;
  notes?: string;
  is_active?: boolean;
}

const productsService = {
  async list(): Promise<ProductOut[]> {
    const { data } = await api.get<ProductOut[]>("/produtos/");
    return data;
  },

  async get(productId: string): Promise<ProductOut> {
    const { data } = await api.get<ProductOut>(`/produtos/${productId}`);
    return data;
  },

  async create(payload: ProductCreate): Promise<ProductOut> {
    const { data } = await api.post<ProductOut>("/produtos/", payload);
    return data;
  },

  async update(productId: string, payload: ProductUpdate): Promise<ProductOut> {
    const { data } = await api.put<ProductOut>(`/produtos/${productId}`, payload);
    return data;
  },

  async delete(productId: string): Promise<void> {
    await api.delete(`/produtos/${productId}`);
  },
};

export default productsService;
