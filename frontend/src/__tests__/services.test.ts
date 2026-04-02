import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import notificationsService from "@/services/notificationsService";
import tokenDiagnosticsService from "@/services/tokenDiagnosticsService";
import listingsService from "@/services/listingsService";
import * as apiModule from "@/services/api";

vi.mock("@/services/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));

describe("notificationsService", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = vi.mocked(apiModule).default;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("getUnread", () => {
    it("chama GET /notifications com params unread_only=true", async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            id: "notif-1",
            type: "alert",
            title: "Estoque baixo",
            message: "MLB123 tem 2 unidades",
            is_read: false,
            action_url: null,
            created_at: "2026-04-01T10:00:00Z",
          },
        ],
      });

      const result = await notificationsService.getUnread();

      expect(mockApi.get).toHaveBeenCalledWith("/notifications", {
        params: { unread_only: true },
      });
      expect(result).toHaveLength(1);
      expect(result[0].title).toBe("Estoque baixo");
      expect(result[0].is_read).toBe(false);
    });

    it("retorna array vazio quando não há notificações", async () => {
      mockApi.get.mockResolvedValue({ data: [] });

      const result = await notificationsService.getUnread();

      expect(result).toHaveLength(0);
    });
  });

  describe("getCount", () => {
    it("chama GET /notifications/count e retorna contagem", async () => {
      mockApi.get.mockResolvedValue({ data: { unread_count: 5 } });

      const result = await notificationsService.getCount();

      expect(mockApi.get).toHaveBeenCalledWith("/notifications/count");
      expect(result.unread_count).toBe(5);
    });

    it("retorna unread_count zero quando não há notificações", async () => {
      mockApi.get.mockResolvedValue({ data: { unread_count: 0 } });

      const result = await notificationsService.getCount();

      expect(result.unread_count).toBe(0);
    });
  });

  describe("markAsRead", () => {
    it("chama POST /notifications/{id}/read para marcar como lida", async () => {
      mockApi.post.mockResolvedValue({});

      await notificationsService.markAsRead("notif-abc-123");

      expect(mockApi.post).toHaveBeenCalledWith("/notifications/notif-abc-123/read");
    });
  });

  describe("markAllAsRead", () => {
    it("chama POST /notifications/read-all para marcar todas como lidas", async () => {
      mockApi.post.mockResolvedValue({});

      await notificationsService.markAllAsRead();

      expect(mockApi.post).toHaveBeenCalledWith("/notifications/read-all");
    });

    it("não recebe parâmetros — apenas POST no endpoint correto", async () => {
      mockApi.post.mockResolvedValue({});

      await notificationsService.markAllAsRead();

      expect(mockApi.post).toHaveBeenCalledTimes(1);
      expect(mockApi.post).toHaveBeenCalledWith("/notifications/read-all");
    });
  });

  describe("getAll", () => {
    it("chama GET /notifications com limit padrão de 50", async () => {
      mockApi.get.mockResolvedValue({ data: [] });

      await notificationsService.getAll();

      expect(mockApi.get).toHaveBeenCalledWith("/notifications", {
        params: { limit: 50 },
      });
    });

    it("chama GET /notifications com limit customizado", async () => {
      mockApi.get.mockResolvedValue({ data: [] });

      await notificationsService.getAll(100);

      expect(mockApi.get).toHaveBeenCalledWith("/notifications", {
        params: { limit: 100 },
      });
    });
  });

  describe("deleteNotification", () => {
    it("chama DELETE /notifications/{id} para deletar notificação", async () => {
      mockApi.delete.mockResolvedValue({});

      await notificationsService.deleteNotification("notif-del-456");

      expect(mockApi.delete).toHaveBeenCalledWith("/notifications/notif-del-456");
    });
  });
});

describe("tokenDiagnosticsService", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = vi.mocked(apiModule).default;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("getDiagnostics", () => {
    it("chama GET /auth/ml/diagnostics e retorna dados de saúde", async () => {
      const mockDiagnostics = {
        celery_status: "ok",
        last_token_refresh_task: "2026-04-01T06:00:00Z",
        accounts: [
          {
            id: "acc-1",
            nickname: "MSM_PRIME",
            token_status: "healthy",
            token_expires_at: "2026-12-01T00:00:00Z",
            remaining_hours: 720,
            has_refresh_token: true,
            last_successful_sync: "2026-04-01T06:00:00Z",
            last_refresh_attempt: null,
            last_refresh_success: true,
            days_since_last_sync: 1,
            data_gap_warning: null,
            needs_reauth: false,
          },
        ],
        recommendations: [],
      };

      mockApi.get.mockResolvedValue({ data: mockDiagnostics });

      const result = await tokenDiagnosticsService.getDiagnostics();

      expect(mockApi.get).toHaveBeenCalledWith("/auth/ml/diagnostics");
      expect(result.celery_status).toBe("ok");
      expect(result.accounts).toHaveLength(1);
      expect(result.accounts[0].nickname).toBe("MSM_PRIME");
      expect(result.accounts[0].token_status).toBe("healthy");
    });

    it("retorna accounts vazio quando usuário não tem contas ML", async () => {
      const mockDiagnostics = {
        celery_status: "ok",
        last_token_refresh_task: null,
        accounts: [],
        recommendations: ["Conecte uma conta ML para começar"],
      };

      mockApi.get.mockResolvedValue({ data: mockDiagnostics });

      const result = await tokenDiagnosticsService.getDiagnostics();

      expect(result.accounts).toHaveLength(0);
      expect(result.recommendations).toHaveLength(1);
    });

    it("retorna conta com needs_reauth=true quando token inválido", async () => {
      const mockDiagnostics = {
        celery_status: "degraded",
        last_token_refresh_task: null,
        accounts: [
          {
            id: "acc-exp",
            nickname: "Conta Expirada",
            token_status: "expired",
            token_expires_at: null,
            remaining_hours: 0,
            has_refresh_token: false,
            last_successful_sync: null,
            last_refresh_attempt: "2026-03-30T06:00:00Z",
            last_refresh_success: false,
            days_since_last_sync: 15,
            data_gap_warning: "15 dias sem dados",
            needs_reauth: true,
          },
        ],
        recommendations: ["Reconecte a conta Conta Expirada"],
      };

      mockApi.get.mockResolvedValue({ data: mockDiagnostics });

      const result = await tokenDiagnosticsService.getDiagnostics();

      expect(result.accounts[0].needs_reauth).toBe(true);
      expect(result.accounts[0].token_status).toBe("expired");
      expect(result.accounts[0].data_gap_warning).toBe("15 dias sem dados");
    });
  });
});

describe("listingsService — endpoints adicionais", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = vi.mocked(apiModule).default;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("sync", () => {
    it("chama POST /listings/sync sem mlAccountId", async () => {
      mockApi.post.mockResolvedValue({
        data: { message: "Sync ok", created: 2, updated: 5, total: 7 },
      });

      const result = await listingsService.sync();

      expect(mockApi.post).toHaveBeenCalledWith("/listings/sync", {}, {
        params: undefined,
      });
      expect(result.total).toBe(7);
    });

    it("chama POST /listings/sync com mlAccountId correto", async () => {
      mockApi.post.mockResolvedValue({
        data: { message: "Sync ok", created: 1, updated: 3, total: 4 },
      });

      const result = await listingsService.sync("account-xyz");

      expect(mockApi.post).toHaveBeenCalledWith("/listings/sync", {}, {
        params: { ml_account_id: "account-xyz" },
      });
      expect(result.total).toBe(4);
    });
  });

  describe("getKpiSummary", () => {
    it("chama GET /listings/kpi/summary sem mlAccountId", async () => {
      const mockKpi = {
        hoje: { vendas: 10, visitas: 200, conversao: 5, anuncios: 16, valor_estoque: 8000, receita: 999.9 },
        ontem: { vendas: 8, visitas: 180, conversao: 4.44, anuncios: 16, valor_estoque: 8000, receita: 799.92 },
        anteontem: { vendas: 12, visitas: 220, conversao: 5.45, anuncios: 16, valor_estoque: 8000, receita: 1199.88 },
        "7dias": { vendas: 70, visitas: 1400, conversao: 5, anuncios: 16, valor_estoque: 8000, receita: 6999.3 },
        "30dias": { vendas: 300, visitas: 6000, conversao: 5, anuncios: 16, valor_estoque: 8000, receita: 29997 },
      };

      mockApi.get.mockResolvedValue({ data: mockKpi });

      const result = await listingsService.getKpiSummary();

      expect(mockApi.get).toHaveBeenCalledWith("/listings/kpi/summary", {
        params: undefined,
      });
      expect(result.hoje.vendas).toBe(10);
      expect(result.hoje.anuncios).toBe(16);
    });

    it("chama GET /listings/kpi/summary com mlAccountId", async () => {
      const mockKpi = {
        hoje: { vendas: 3, visitas: 60, conversao: 5, anuncios: 5, valor_estoque: 2500, receita: 299.97 },
        ontem: { vendas: 2, visitas: 50, conversao: 4, anuncios: 5, valor_estoque: 2500, receita: 199.98 },
        anteontem: { vendas: 4, visitas: 70, conversao: 5.71, anuncios: 5, valor_estoque: 2500, receita: 399.96 },
        "7dias": { vendas: 21, visitas: 420, conversao: 5, anuncios: 5, valor_estoque: 2500, receita: 2099.79 },
        "30dias": { vendas: 90, visitas: 1800, conversao: 5, anuncios: 5, valor_estoque: 2500, receita: 8999.1 },
      };

      mockApi.get.mockResolvedValue({ data: mockKpi });

      const result = await listingsService.getKpiSummary("account-specific");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/kpi/summary", {
        params: { ml_account_id: "account-specific" },
      });
      expect(result.hoje.vendas).toBe(3);
    });
  });
});
