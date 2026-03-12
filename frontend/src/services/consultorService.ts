import api from './api';

export interface ConsultorRequest {
  mlb_id?: string;
}

export interface ConsultorResponse {
  analise: string;
  anuncios_analisados: number;
  gerado_em: string;
}

export const consultorService = {
  analisar: async (request?: ConsultorRequest): Promise<ConsultorResponse> => {
    const { data } = await api.post<ConsultorResponse>('/consultor/analisar', request || {});
    return data;
  },
};
