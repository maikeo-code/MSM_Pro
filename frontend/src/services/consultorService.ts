import api from './api';

export interface ConsultorRequest {
  mlb_id?: string;
}

export interface ConsultorResponse {
  analise: string;
  anuncios_analisados: number;
  gerado_em: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  reply: string;
  tokens_used: number;
}

export const consultorService = {
  analisar: async (request?: ConsultorRequest): Promise<ConsultorResponse> => {
    const { data } = await api.post<ConsultorResponse>('/consultor/analisar', request || {});
    return data;
  },

  chat: async (message: string, history: ChatMessage[]): Promise<ChatResponse> => {
    const { data } = await api.post<ChatResponse>('/consultor/chat', { message, history });
    return data;
  },
};
