import api from './api';

export interface AccountDiagnostic {
  id: string;
  nickname: string;
  token_status: 'healthy' | 'expiring_soon' | 'expired';
  token_expires_at: string | null;
  remaining_hours: number;
  has_refresh_token: boolean;
  last_successful_sync: string | null;
  last_refresh_attempt: string | null;
  last_refresh_success: boolean;
  days_since_last_sync: number;
  data_gap_warning: string | null;
  needs_reauth: boolean;
}

export interface TokenDiagnostics {
  celery_status: string;
  last_token_refresh_task: string | null;
  accounts: AccountDiagnostic[];
  recommendations: string[];
}

const tokenDiagnosticsService = {
  /**
   * Busca diagnósticos de tokens para todas as contas ML do usuário
   */
  async getDiagnostics(): Promise<TokenDiagnostics> {
    const { data } = await api.get<TokenDiagnostics>('/auth/ml/diagnostics');
    return data;
  },
};

export default tokenDiagnosticsService;
