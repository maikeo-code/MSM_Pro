import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import listingsService from "./listingsService";
import * as apiModule from "./api";

vi.mock("./api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
  setStoredToken: vi.fn(),
  removeStoredToken: vi.fn(),
}));

describe("listingsService", () => {
  let mockApi: any;

  beforeEach(() => {
    mockApi = vi.mocked(apiModule).default;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("list", () => {
    it("should call GET /listings/ without parameters when period is today", async () => {
      const mockResponse = {
        data: [
          {
            id: "listing-1",
            user_id: "user-1",
            product_id: null,
            ml_account_id: "account-1",
            mlb_id: "MLB123456789",
            title: "Test Product",
            listing_type: "classico",
            price: 99.99,
            original_price: 149.99,
            sale_price: null,
            status: "active",
            permalink: "https://example.com",
            thumbnail: "https://example.com/thumb.jpg",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-03-26T00:00:00Z",
            last_snapshot: null,
          },
        ],
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.list("today");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/", {
        params: undefined,
      });
      expect(result).toHaveLength(1);
      expect(result[0].mlb_id).toBe("MLB123456789");
    });

    it("should include period parameter when period is not today", async () => {
      const mockResponse = { data: [] };
      mockApi.get.mockResolvedValue(mockResponse);

      await listingsService.list("7d");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/", {
        params: { period: "7d" },
      });
    });

    it("should include mlAccountId parameter when provided", async () => {
      const mockResponse = { data: [] };
      mockApi.get.mockResolvedValue(mockResponse);

      await listingsService.list("today", "account-1");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/", {
        params: { ml_account_id: "account-1" },
      });
    });
  });

  describe("sync", () => {
    it("should call POST /listings/sync without mlAccountId", async () => {
      const mockResponse = {
        data: {
          message: "Sync completed",
          created: 5,
          updated: 10,
          total: 15,
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await listingsService.sync();

      expect(mockApi.post).toHaveBeenCalledWith("/listings/sync", {}, {
        params: undefined,
      });
      expect(result.created).toBe(5);
      expect(result.updated).toBe(10);
      expect(result.total).toBe(15);
    });

    it("should call POST /listings/sync with mlAccountId", async () => {
      const mockResponse = {
        data: {
          message: "Sync completed",
          created: 3,
          updated: 7,
          total: 10,
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await listingsService.sync("account-1");

      expect(mockApi.post).toHaveBeenCalledWith("/listings/sync", {}, {
        params: { ml_account_id: "account-1" },
      });
      expect(result.total).toBe(10);
    });
  });

  describe("getKpiSummary", () => {
    it("should call GET /listings/kpi/summary without mlAccountId", async () => {
      const mockResponse = {
        data: {
          hoje: {
            vendas: 5,
            visitas: 100,
            conversao: 5,
            anuncios: 10,
            valor_estoque: 5000,
            receita: 499.95,
          },
          ontem: {
            vendas: 3,
            visitas: 80,
            conversao: 3.75,
            anuncios: 10,
            valor_estoque: 5000,
            receita: 299.97,
          },
          anteontem: {
            vendas: 4,
            visitas: 90,
            conversao: 4.44,
            anuncios: 10,
            valor_estoque: 5000,
            receita: 399.96,
          },
          "7dias": {
            vendas: 30,
            visitas: 600,
            conversao: 5,
            anuncios: 10,
            valor_estoque: 5000,
            receita: 2999.7,
          },
          "30dias": {
            vendas: 120,
            visitas: 2400,
            conversao: 5,
            anuncios: 10,
            valor_estoque: 5000,
            receita: 11998.8,
          },
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getKpiSummary();

      expect(mockApi.get).toHaveBeenCalledWith("/listings/kpi/summary", {
        params: undefined,
      });
      expect(result.hoje.vendas).toBe(5);
      expect(result.ontem.vendas).toBe(3);
    });

    it("should call GET /listings/kpi/summary with mlAccountId", async () => {
      const mockResponse = {
        data: {
          hoje: { vendas: 2, visitas: 50, conversao: 4, anuncios: 5, valor_estoque: 2500, receita: 199.98 },
          ontem: { vendas: 1, visitas: 40, conversao: 2.5, anuncios: 5, valor_estoque: 2500, receita: 99.99 },
          anteontem: { vendas: 2, visitas: 45, conversao: 4.44, anuncios: 5, valor_estoque: 2500, receita: 199.98 },
          "7dias": { vendas: 15, visitas: 300, conversao: 5, anuncios: 5, valor_estoque: 2500, receita: 1499.85 },
          "30dias": { vendas: 60, visitas: 1200, conversao: 5, anuncios: 5, valor_estoque: 2500, receita: 5999.4 },
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getKpiSummary("account-1");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/kpi/summary", {
        params: { ml_account_id: "account-1" },
      });
      expect(result.hoje.vendas).toBe(2);
    });
  });

  describe("getSnapshots", () => {
    it("should call GET /listings/{mlbId}/snapshots with dias parameter", async () => {
      const mockResponse = {
        data: [
          {
            id: "snapshot-1",
            listing_id: "MLB123456789",
            price: 99.99,
            visits: 10,
            sales_today: 2,
            questions: 1,
            stock: 50,
            conversion_rate: 20,
            captured_at: "2026-03-26T00:00:00Z",
          },
        ],
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getSnapshots("MLB123456789", 30);

      expect(mockApi.get).toHaveBeenCalledWith("/listings/MLB123456789/snapshots", {
        params: { dias: 30 },
      });
      expect(result).toHaveLength(1);
      expect(result[0].price).toBe(99.99);
    });
  });

  describe("updatePrice", () => {
    it("should call PATCH /listings/{mlbId}/price with new price", async () => {
      const mockResponse = {
        data: {
          mlb_id: "MLB123456789",
          new_price: 89.99,
          updated_at: "2026-03-26T10:00:00Z",
        },
      };
      mockApi.patch.mockResolvedValue(mockResponse);

      const result = await listingsService.updatePrice("MLB123456789", { price: 89.99 });

      expect(mockApi.patch).toHaveBeenCalledWith("/listings/MLB123456789/price", { price: 89.99 }, {
        params: undefined,
      });
      expect(result.new_price).toBe(89.99);
    });
  });

  describe("getListingHealth", () => {
    it("should call GET /listings/{mlbId}/health", async () => {
      const mockResponse = {
        data: {
          score: 85,
          status: "good",
          label: "Bom",
          color: "#22c55e",
          checks: [
            {
              item: "Conversao",
              ok: true,
              points: 25,
              max: 35,
            },
          ],
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getListingHealth("MLB123456789");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/MLB123456789/health", {
        params: undefined,
      });
      expect(result.score).toBe(85);
      expect(result.status).toBe("good");
    });
  });

  describe("getFunnel", () => {
    it("should call GET /listings/analytics/funnel with period parameter", async () => {
      const mockResponse = {
        data: {
          visitas: 600,
          vendas: 30,
          conversao: 5,
          receita: 2999.7,
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getFunnel("7d");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/analytics/funnel", {
        params: { period: "7d" },
      });
      expect(result.visitas).toBe(600);
      expect(result.vendas).toBe(30);
      expect(result.conversao).toBe(5);
    });
  });

  describe("getHeatmap", () => {
    it("should call GET /listings/analytics/heatmap with period parameter", async () => {
      const mockResponse = {
        data: {
          data: [
            {
              day_of_week: 0,
              hour: 14,
              day_name: "segunda",
              count: 5,
              avg_per_week: 4.3,
            },
          ],
          peak_day: "segunda",
          peak_day_index: 0,
          peak_hour: "14:00-15:00",
          avg_daily: 4.3,
          total_sales: 30,
          period_days: 7,
          has_hourly_data: true,
        },
      };
      mockApi.get.mockResolvedValue(mockResponse);

      const result = await listingsService.getHeatmap("7d");

      expect(mockApi.get).toHaveBeenCalledWith("/listings/analytics/heatmap", {
        params: { period: "7d" },
      });
      expect(result.peak_day).toBe("segunda");
      expect(result.total_sales).toBe(30);
    });
  });

  describe("simulatePrice", () => {
    it("should call POST /listings/{mlbId}/simulate-price with target price", async () => {
      const mockResponse = {
        data: {
          target_price: 79.99,
          estimated_sales_per_day: 8,
          estimated_revenue_per_day: 639.92,
          estimated_margin: 29.99,
          is_estimated: true,
          elasticity: -1.5,
        },
      };
      mockApi.post.mockResolvedValue(mockResponse);

      const result = await listingsService.simulatePrice("MLB123456789", 79.99);

      expect(mockApi.post).toHaveBeenCalledWith(
        "/listings/MLB123456789/simulate-price",
        { target_price: 79.99 },
        { params: undefined }
      );
      expect(result.target_price).toBe(79.99);
      expect(result.estimated_sales_per_day).toBe(8);
    });
  });
});
