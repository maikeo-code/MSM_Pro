import api from './api';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface Claim {
  id: string;
  ml_claim_id: string;
  ml_account_id: string;
  claim_type: string;
  status: string;
  reason: string | null;
  description: string | null;
  ml_order_id: string | null;
  mlb_id: string | null;
  item_title: string | null;
  item_thumbnail: string | null;
  item_permalink: string | null;
  buyer_id: number | null;
  buyer_nickname: string | null;
  date_created: string;
  date_updated: string | null;
  resolved_at: string | null;
  resolution_type: string | null;
  resolution_notes: string | null;
  ml_suggestion: string | null;
  synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClaimListResponse {
  total: number;
  offset: number;
  limit: number;
  items: Claim[];
}

export interface ClaimStats {
  total: number;
  open: number;
  resolved: number;
  unresolved: number;
}

export interface SimilarClaim {
  ml_claim_id: string;
  reason: string | null;
  resolution_type: string | null;
  resolution_notes: string | null;
  ml_suggestion: string | null;
  resolved_at: string | null;
}

export interface SimilarClaimsResponse {
  mlb_id: string;
  count: number;
  items: SimilarClaim[];
}

export interface SyncResult {
  accounts_synced: number;
  synced: number;
  new: number;
  updated: number;
  errors: number;
}

export type ResolutionType =
  | 'refund'
  | 'replace'
  | 'partial_refund'
  | 'kept'
  | 'ml_suggested';

export const RESOLUTION_LABELS: Record<ResolutionType, string> = {
  refund: 'Reembolso total',
  replace: 'Troca do produto',
  partial_refund: 'Reembolso parcial',
  kept: 'Produto mantido',
  ml_suggested: 'Solucao sugerida pelo ML',
};

// ─── Service ───────────────────────────────────────────────────────────────────

export const claimsService = {
  list: (params?: {
    status?: string;
    mlb_id?: string;
    claim_type?: string;
    offset?: number;
    limit?: number;
    ml_account_id?: string | null;
  }) => {
    const query: Record<string, unknown> = {};
    if (params?.status) query.status = params.status;
    if (params?.mlb_id) query.mlb_id = params.mlb_id;
    if (params?.claim_type) query.claim_type = params.claim_type;
    if (params?.offset != null) query.offset = params.offset;
    if (params?.limit != null) query.limit = params.limit;
    if (params?.ml_account_id) query.ml_account_id = params.ml_account_id;
    return api
      .get<ClaimListResponse>('/atendimento/claims', { params: query })
      .then((r) => r.data);
  },

  getStats: (mlAccountId?: string | null) => {
    const params: Record<string, unknown> = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    return api
      .get<ClaimStats>('/atendimento/claims/stats', {
        params: Object.keys(params).length > 0 ? params : undefined,
      })
      .then((r) => r.data);
  },

  sync: (mlAccountId?: string | null) => {
    const params: Record<string, unknown> = {};
    if (mlAccountId) params.ml_account_id = mlAccountId;
    return api
      .post<SyncResult>('/atendimento/claims/sync', null, {
        params: Object.keys(params).length > 0 ? params : undefined,
      })
      .then((r) => r.data);
  },

  resolve: (
    claimId: string,
    body: { resolution_type: ResolutionType; notes?: string },
  ) =>
    api
      .post(`/atendimento/claims/${claimId}/resolve`, body)
      .then((r) => r.data),

  getSimilar: (mlbId: string, limit = 5) =>
    api
      .get<SimilarClaimsResponse>(`/atendimento/claims/similar/${mlbId}`, {
        params: { limit },
      })
      .then((r) => r.data),
};
