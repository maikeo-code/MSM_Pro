import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import authService from "./authService";
import * as apiModule from "./api";

vi.mock("./api", () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));

describe("authService", () => {
  let mockApi: any;
  let setStoredTokenMock: any;
  let removeStoredTokenMock: any;

  beforeEach(() => {
    mockApi = vi.mocked(apiModule).default;
    setStoredTokenMock = vi.mocked(apiModule).setStoredToken;
    removeStoredTokenMock = vi.mocked(apiModule).removeStoredToken;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("login", () => {
    it("should call POST /auth/login with email and password", async () => {
      const mockResponse = {
        data: {
          access_token: "test-token-123",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "user-123",
            email: "test@example.com",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await authService.login("test@example.com", "password123");

      expect(mockApi.post).toHaveBeenCalledWith("/auth/login", {
        email: "test@example.com",
        password: "password123",
      });
      expect(setStoredTokenMock).toHaveBeenCalledWith("test-token-123");
      expect(result.access_token).toBe("test-token-123");
      expect(result.user.email).toBe("test@example.com");
    });

    it("should handle login errors", async () => {
      const mockError = new Error("Invalid credentials");
      mockApi.post.mockRejectedValue(mockError);

      await expect(authService.login("test@example.com", "wrong-password")).rejects.toThrow(
        "Invalid credentials"
      );
    });
  });

  describe("logout", () => {
    it("should call removeStoredToken on logout", () => {
      authService.logout();

      expect(removeStoredTokenMock).toHaveBeenCalled();
    });
  });

  describe("getMe", () => {
    it("should call GET /auth/me and return user data", async () => {
      const mockResponse = {
        data: {
          id: "user-123",
          email: "test@example.com",
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await authService.getMe();

      expect(mockApi.get).toHaveBeenCalledWith("/auth/me");
      expect(result.id).toBe("user-123");
      expect(result.email).toBe("test@example.com");
    });
  });

  describe("register", () => {
    it("should call POST /auth/register with email and password", async () => {
      const mockResponse = {
        data: {
          id: "user-456",
          email: "newuser@example.com",
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await authService.register("newuser@example.com", "password123");

      expect(mockApi.post).toHaveBeenCalledWith("/auth/register", {
        email: "newuser@example.com",
        password: "password123",
      });
      expect(result.email).toBe("newuser@example.com");
    });
  });

  describe("refreshToken", () => {
    it("should call POST /auth/refresh and update stored token", async () => {
      const mockResponse = {
        data: {
          access_token: "new-token-456",
          token_type: "bearer",
          expires_in: 3600,
          user: {
            id: "user-123",
            email: "test@example.com",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await authService.refreshToken();

      expect(mockApi.post).toHaveBeenCalledWith("/auth/refresh");
      expect(setStoredTokenMock).toHaveBeenCalledWith("new-token-456");
      expect(result.access_token).toBe("new-token-456");
    });
  });

  describe("getMLConnectURL", () => {
    it("should call GET /auth/ml/connect and return auth URL", async () => {
      const mockResponse = {
        data: {
          auth_url: "https://auth.mercadolibre.com.br/authorization?...",
          message: "Click to connect your Mercado Libre account",
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await authService.getMLConnectURL();

      expect(mockApi.get).toHaveBeenCalledWith("/auth/ml/connect");
      expect(result.auth_url).toContain("https://auth.mercadolibre.com.br");
    });
  });

  describe("listMLAccounts", () => {
    it("should call GET /auth/ml/accounts and return list of accounts", async () => {
      const mockResponse = {
        data: [
          {
            id: "account-1",
            ml_user_id: "2050442871",
            nickname: "MSM_PRIME",
            email: "seller@example.com",
            token_expires_at: "2026-03-26T10:00:00Z",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await authService.listMLAccounts();

      expect(mockApi.get).toHaveBeenCalledWith("/auth/ml/accounts");
      expect(result).toHaveLength(1);
      expect(result[0].nickname).toBe("MSM_PRIME");
    });
  });

  describe("deleteMLAccount", () => {
    it("should call DELETE /auth/ml/accounts/{accountId}", async () => {
      mockApi.delete.mockResolvedValue({});

      await authService.deleteMLAccount("account-1");

      expect(mockApi.delete).toHaveBeenCalledWith("/auth/ml/accounts/account-1");
    });
  });

  describe("getPreferences", () => {
    it("should call GET /auth/preferences and return user preferences", async () => {
      const mockResponse = {
        data: {
          active_ml_account_id: "account-1",
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await authService.getPreferences();

      expect(mockApi.get).toHaveBeenCalledWith("/auth/preferences");
      expect(result.active_ml_account_id).toBe("account-1");
    });
  });

  describe("updatePreferences", () => {
    it("should call PUT /auth/preferences with active account ID", async () => {
      mockApi.put.mockResolvedValue({});

      await authService.updatePreferences("account-1");

      expect(mockApi.put).toHaveBeenCalledWith("/auth/preferences", {
        active_ml_account_id: "account-1",
      });
    });

    it("should allow null value to clear active account", async () => {
      mockApi.put.mockResolvedValue({});

      await authService.updatePreferences(null);

      expect(mockApi.put).toHaveBeenCalledWith("/auth/preferences", {
        active_ml_account_id: null,
      });
    });
  });
});
