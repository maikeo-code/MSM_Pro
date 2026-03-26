import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "./authStore";
import * as apiModule from "@/services/api";

vi.mock("@/services/api", () => ({
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));

describe("authStore (useAuthStore)", () => {
  beforeEach(() => {
    // Reset Zustand state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
    vi.clearAllMocks();
  });

  describe("initial state", () => {
    it("should have null user, token, and isAuthenticated false initially", () => {
      const state = useAuthStore.getState();

      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("setAuth", () => {
    it("should set user and token, and mark as authenticated", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };
      const mockToken = "test-token-abc123";

      useAuthStore.getState().setAuth(mockUser, mockToken);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.token).toBe(mockToken);
      expect(state.isAuthenticated).toBe(true);
    });

    it("should call setStoredToken when setting auth", () => {
      const mockUser = {
        id: "user-456",
        email: "another@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };
      const mockToken = "another-token-xyz789";

      useAuthStore.getState().setAuth(mockUser, mockToken);

      expect(apiModule.setStoredToken).toHaveBeenCalledWith(mockToken);
    });

    it("should update user and token when called multiple times", () => {
      const user1 = {
        id: "user-1",
        email: "user1@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };
      const user2 = {
        id: "user-2",
        email: "user2@example.com",
        is_active: true,
        created_at: "2026-01-02T00:00:00Z",
      };

      useAuthStore.getState().setAuth(user1, "token-1");
      expect(useAuthStore.getState().user).toEqual(user1);

      useAuthStore.getState().setAuth(user2, "token-2");
      expect(useAuthStore.getState().user).toEqual(user2);
      expect(useAuthStore.getState().token).toBe("token-2");
    });
  });

  describe("clearAuth", () => {
    it("should clear user, token, and mark as not authenticated", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "test-token");
      expect(useAuthStore.getState().isAuthenticated).toBe(true);

      useAuthStore.getState().clearAuth();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it("should call removeStoredToken when clearing auth", () => {
      const mockUser = {
        id: "user-789",
        email: "user@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "test-token-789");
      vi.clearAllMocks();

      useAuthStore.getState().clearAuth();

      expect(apiModule.removeStoredToken).toHaveBeenCalled();
    });

    it("should be safe to call clearAuth when already cleared", () => {
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);

      // Calling again should not cause errors
      useAuthStore.getState().clearAuth();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  describe("isAuthenticated", () => {
    it("should be false initially", () => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it("should be true after setAuth is called", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "token-123");

      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it("should be false after clearAuth is called", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "token-123");
      useAuthStore.getState().clearAuth();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  describe("user", () => {
    it("should store user data correctly", () => {
      const mockUser = {
        id: "user-abc",
        email: "abc@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "token");

      const state = useAuthStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.user?.id).toBe("user-abc");
      expect(state.user?.email).toBe("abc@example.com");
      expect(state.user?.is_active).toBe(true);
    });

    it("should handle inactive users", () => {
      const inactiveUser = {
        id: "user-inactive",
        email: "inactive@example.com",
        is_active: false,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(inactiveUser, "token");

      expect(useAuthStore.getState().user?.is_active).toBe(false);
    });
  });

  describe("token", () => {
    it("should store token correctly", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };
      const testToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

      useAuthStore.getState().setAuth(mockUser, testToken);

      expect(useAuthStore.getState().token).toBe(testToken);
    });

    it("should be null after clearAuth", () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "token-123");
      useAuthStore.getState().clearAuth();

      expect(useAuthStore.getState().token).toBeNull();
    });
  });

  describe("store persistence", () => {
    it("should have localStorage key 'msm-auth-storage'", () => {
      const mockUser = {
        id: "user-persist",
        email: "persist@example.com",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      };

      useAuthStore.getState().setAuth(mockUser, "persist-token");

      // The Zustand persist middleware should save to localStorage
      // Check that localStorage is being used (name is msm-auth-storage)
      const stored = localStorage.getItem("msm-auth-storage");
      expect(stored).toBeTruthy();
    });
  });
});
