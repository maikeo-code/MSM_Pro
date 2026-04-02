import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "@/store/authStore";
import * as apiModule from "@/services/api";

vi.mock("@/services/api", () => ({
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));

const mockUser = {
  id: "user-new-1",
  email: "novo@example.com",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("authStore — testes adicionais", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    vi.clearAllMocks();
  });

  describe("isAuthenticated", () => {
    it("retorna false quando não há token", () => {
      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
    });

    it("retorna true após setAuth com token válido", () => {
      useAuthStore.getState().setAuth(mockUser, "valid-token-abc");
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it("retorna false após logout (clearAuth)", () => {
      useAuthStore.getState().setAuth(mockUser, "some-token");
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  describe("setAuth — sincronização com localStorage", () => {
    it("setAuth chama setStoredToken para sincronizar localStorage", () => {
      useAuthStore.getState().setAuth(mockUser, "sync-token-xyz");
      expect(apiModule.setStoredToken).toHaveBeenCalledWith("sync-token-xyz");
    });

    it("setAuth chama setStoredToken com o token correto na segunda chamada", () => {
      useAuthStore.getState().setAuth(mockUser, "first-token");
      useAuthStore.getState().setAuth(mockUser, "second-token");
      expect(apiModule.setStoredToken).toHaveBeenCalledTimes(2);
      expect(apiModule.setStoredToken).toHaveBeenLastCalledWith("second-token");
    });

    it("setAuth salva o token no Zustand state", () => {
      useAuthStore.getState().setAuth(mockUser, "zustand-token");
      expect(useAuthStore.getState().token).toBe("zustand-token");
    });

    it("setAuth salva os dados do usuário corretamente", () => {
      const user = {
        id: "user-detail",
        email: "detail@example.com",
        is_active: true,
        created_at: "2026-02-15T00:00:00Z",
      };
      useAuthStore.getState().setAuth(user, "detail-token");
      const state = useAuthStore.getState();
      expect(state.user?.id).toBe("user-detail");
      expect(state.user?.email).toBe("detail@example.com");
    });
  });

  describe("logout / clearAuth", () => {
    it("clearAuth remove o token do Zustand", () => {
      useAuthStore.getState().setAuth(mockUser, "token-to-remove");
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().token).toBeNull();
    });

    it("clearAuth remove o usuário do Zustand", () => {
      useAuthStore.getState().setAuth(mockUser, "token-to-remove");
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().user).toBeNull();
    });

    it("clearAuth chama removeStoredToken para limpar localStorage", () => {
      useAuthStore.getState().setAuth(mockUser, "logout-token");
      vi.clearAllMocks();
      useAuthStore.getState().clearAuth();
      expect(apiModule.removeStoredToken).toHaveBeenCalledTimes(1);
    });

    it("clearAuth não chama setStoredToken — apenas remove", () => {
      useAuthStore.getState().setAuth(mockUser, "token");
      vi.clearAllMocks();
      useAuthStore.getState().clearAuth();
      expect(apiModule.setStoredToken).not.toHaveBeenCalled();
      expect(apiModule.removeStoredToken).toHaveBeenCalled();
    });
  });

  describe("persistência no localStorage", () => {
    it("persiste dados no localStorage com chave msm-auth-storage", () => {
      useAuthStore.getState().setAuth(mockUser, "persist-token-extra");
      const stored = localStorage.getItem("msm-auth-storage");
      expect(stored).toBeTruthy();
      expect(stored).toContain("novo@example.com");
    });

    it("estado é limpo após clearAuth refletido no store", () => {
      useAuthStore.getState().setAuth(mockUser, "token-to-clear");
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().token).toBeNull();
    });
  });
});
