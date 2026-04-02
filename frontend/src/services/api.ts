import axios, { type AxiosInstance, type AxiosError } from "axios";
import { useAuthStore } from "@/store/authStore";

const BASE_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

const TOKEN_KEY = "msm_access_token";
const TOKEN_REFRESHED_AT_KEY = "msm_token_refreshed_at";
const REFRESH_INTERVAL_MS = 12 * 60 * 60 * 1000; // 12 horas

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TOKEN_REFRESHED_AT_KEY, Date.now().toString());
}

export function removeStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_REFRESHED_AT_KEY);
}

function shouldRefreshJwt(): boolean {
  const lastRefresh = localStorage.getItem(TOKEN_REFRESHED_AT_KEY);
  if (!lastRefresh) return true;
  return Date.now() - parseInt(lastRefresh, 10) > REFRESH_INTERVAL_MS;
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshJwt(): Promise<boolean> {
  // Se já há um refresh em andamento, aguardar o resultado dele
  if (refreshPromise) return refreshPromise;

  const token = getStoredToken();
  if (!token) return false;

  // Criar promise de refresh e armazená-la para evitar race conditions
  refreshPromise = (async () => {
    try {
      const response = await axios.post(
        `${BASE_URL}/auth/refresh`,
        {},
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          timeout: 15000,
        },
      );
      const newToken = response.data.access_token;
      if (newToken) {
        // setAuth já chama setStoredToken internamente, não chamar 2x
        const store = useAuthStore.getState();
        if (store.user) {
          store.setAuth(store.user, newToken);
        } else {
          // Fallback: apenas user não está setado (caso raro)
          setStoredToken(newToken);
        }
        return true;
      }
      return false;
    } catch {
      // Token inválido — não fazer nada, o interceptor de 401 cuida
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    // Limpar promise para próximas tentativas
    refreshPromise = null;
  }
}

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000,
});

// Interceptor de request: adiciona JWT + auto-refresh se necessário
api.interceptors.request.use(
  async (config) => {
    let token = getStoredToken();
    if (token) {
      // Auto-refresh a cada 12h (silencioso, sem interromper)
      if (shouldRefreshJwt() && !config.url?.includes("/auth/refresh")) {
        // Aguardar refresh para pegar token atualizado
        await tryRefreshJwt();
        token = getStoredToken(); // Pegar token atualizado após refresh
      }
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Interceptor de response: tenta refresh em 401 antes de redirecionar
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Se não é a request de refresh, tenta renovar o token
      const originalRequest = error.config;
      if (originalRequest && !originalRequest.url?.includes("/auth/refresh")) {
        // Evitar loop infinito: se já foi feito retry uma vez, ir direto para logout
        if ((originalRequest as any)._retry) {
          removeStoredToken();
          useAuthStore.getState().clearAuth();
          if (!window.location.pathname.includes("/login")) {
            window.location.href = "/login";
          }
          return Promise.reject(error);
        }
        (originalRequest as any)._retry = true;
        const refreshed = await tryRefreshJwt();
        if (refreshed && originalRequest) {
          // Retry com novo token usando api (com interceptors)
          const newToken = getStoredToken();
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api.request(originalRequest);
        }
      }
      // Refresh falhou — logout
      removeStoredToken();
      useAuthStore.getState().clearAuth();
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

// Auto-refresh periódico: renova JWT a cada 12h enquanto a aba está aberta
setInterval(() => {
  if (getStoredToken() && shouldRefreshJwt()) {
    tryRefreshJwt();
  }
}, 60 * 60 * 1000); // Verifica a cada 1h

export default api;
