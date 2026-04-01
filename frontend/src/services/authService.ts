import api, { setStoredToken, removeStoredToken } from "./api";

export interface UserOut {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserOut;
}

export interface MLAccountOut {
  id: string;
  ml_user_id: string;
  nickname: string;
  email: string | null;
  token_expires_at: string | null;
  is_active: boolean;
  created_at: string;
  needs_reauth?: boolean;
  last_sync_at?: string | null;
}

export interface MLConnectURL {
  auth_url: string;
  message: string;
}

export interface UserPreferences {
  active_ml_account_id: string | null;
}

const authService = {
  async register(email: string, password: string): Promise<UserOut> {
    const { data } = await api.post<UserOut>("/auth/register", { email, password });
    return data;
  },

  async login(email: string, password: string): Promise<Token> {
    const { data } = await api.post<Token>("/auth/login", { email, password });
    setStoredToken(data.access_token);
    return data;
  },

  async refreshToken(): Promise<Token> {
    const { data } = await api.post<Token>("/auth/refresh");
    setStoredToken(data.access_token);
    return data;
  },

  async getMe(): Promise<UserOut> {
    const { data } = await api.get<UserOut>("/auth/me");
    return data;
  },

  logout(): void {
    removeStoredToken();
  },

  async getMLConnectURL(): Promise<MLConnectURL> {
    const { data } = await api.get<MLConnectURL>("/auth/ml/connect");
    return data;
  },

  async listMLAccounts(): Promise<MLAccountOut[]> {
    const { data } = await api.get<MLAccountOut[]>("/auth/ml/accounts");
    return data;
  },

  async deleteMLAccount(accountId: string): Promise<void> {
    await api.delete(`/auth/ml/accounts/${accountId}`);
  },

  async getPreferences(): Promise<UserPreferences> {
    const { data } = await api.get<UserPreferences>("/auth/preferences");
    return data;
  },

  async updatePreferences(activeMLAccountId: string | null): Promise<void> {
    await api.put("/auth/preferences", { active_ml_account_id: activeMLAccountId });
  },
};

export default authService;
