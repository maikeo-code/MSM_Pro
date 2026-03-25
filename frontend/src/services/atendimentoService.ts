import api from './api';

export interface AtendimentoItem {
  id: string;
  type: 'pergunta' | 'reclamacao' | 'mensagem' | 'devolucao';
  status: string;
  date_created: string;
  text: string;
  from_user?: { id: number; nickname: string } | null;
  item_id?: string;
  item_title?: string;
  order_id?: string;
  last_message?: string;
  requires_action: boolean;
  ai_suggested_response?: string;
  account_id?: string;
  account_nickname?: string;
}

export interface AtendimentoListResponse {
  total: number;
  items: AtendimentoItem[];
  by_type: Record<string, number>;
}

/** Schema real retornado pelo backend AtendimentoStatsOut */
export interface AtendimentoStatsRaw {
  total: number;
  requires_action: number;
  by_type: Record<string, number>; // perguntas, reclamacoes, mensagens, devolucoes
  by_status: Record<string, number>;
}

/** Shape derivado que o frontend usa nos KPI cards */
export interface AtendimentoStats {
  perguntas_pendentes: number;
  reclamacoes_abertas: number;
  mensagens_nao_lidas: number;
  devolucoes_pendentes: number;
  total_pendentes: number;
}

function mapStats(raw: AtendimentoStatsRaw): AtendimentoStats {
  return {
    perguntas_pendentes: raw.by_type?.perguntas ?? 0,
    reclamacoes_abertas: raw.by_type?.reclamacoes ?? 0,
    mensagens_nao_lidas: raw.by_type?.mensagens ?? 0,
    devolucoes_pendentes: raw.by_type?.devolucoes ?? 0,
    total_pendentes: raw.requires_action ?? raw.total ?? 0,
  };
}

export interface AISuggestionResponse {
  suggestion: string;
  confidence: number;
  based_on: string[];
}

export const atendimentoService = {
  getAll: (
    params?: {
      type?: string;
      status?: string;
      offset?: number;
      limit?: number;
    },
    mlAccountId?: string | null,
  ) => {
    const queryParams: any = { ...params };
    if (mlAccountId) {
      queryParams.ml_account_id = mlAccountId;
    }
    return api
      .get<AtendimentoListResponse>('/atendimento/', {
        params: Object.keys(queryParams).length > 0 ? queryParams : undefined,
      })
      .then((r) => r.data);
  },

  getStats: (mlAccountId?: string | null) => {
    const params: any = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    return api
      .get<AtendimentoStatsRaw>('/atendimento/stats', {
        params: Object.keys(params).length > 0 ? params : undefined,
      })
      .then((r) => mapStats(r.data));
  },

  respond: (
    itemType: string,
    itemId: string,
    body: { text: string; account_id: string },
  ) =>
    api
      .post(`/atendimento/${itemType}/${itemId}/respond`, body)
      .then((r) => r.data),

  getAiSuggestion: (itemType: string, itemId: string, accountId?: string) =>
    api
      .get<AISuggestionResponse>(
        `/atendimento/${itemType}/${itemId}/ai-suggestion`,
        { params: accountId ? { account_id: accountId } : {} },
      )
      .then((r) => r.data),
};
