import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { TokenHealthBanner } from "@/components/TokenHealthBanner";
import tokenDiagnosticsService from "@/services/tokenDiagnosticsService";
import type { TokenDiagnostics } from "@/services/tokenDiagnosticsService";

vi.mock("@/services/tokenDiagnosticsService", () => ({
  default: {
    getDiagnostics: vi.fn(),
  },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
};

const makeHealthyDiagnostics = (): TokenDiagnostics => ({
  celery_status: "ok",
  last_token_refresh_task: null,
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
});

const makeExpiredDiagnostics = (): TokenDiagnostics => ({
  celery_status: "ok",
  last_token_refresh_task: null,
  accounts: [
    {
      id: "acc-1",
      nickname: "MSM_PRIME",
      token_status: "expired",
      token_expires_at: "2026-03-01T00:00:00Z",
      remaining_hours: -48,
      has_refresh_token: false,
      last_successful_sync: "2026-03-25T06:00:00Z",
      last_refresh_attempt: "2026-03-26T06:00:00Z",
      last_refresh_success: false,
      days_since_last_sync: 7,
      data_gap_warning: "7 dias sem sincronização",
      needs_reauth: false,
    },
  ],
  recommendations: [],
});

const makeNeedsReauthDiagnostics = (): TokenDiagnostics => ({
  celery_status: "ok",
  last_token_refresh_task: null,
  accounts: [
    {
      id: "acc-1",
      nickname: "Conta Vendedor",
      token_status: "expired",
      token_expires_at: null,
      remaining_hours: 0,
      has_refresh_token: false,
      last_successful_sync: null,
      last_refresh_attempt: null,
      last_refresh_success: false,
      days_since_last_sync: 0,
      data_gap_warning: null,
      needs_reauth: true,
    },
  ],
  recommendations: [],
});

const makeMultipleProblemsDiagnostics = (): TokenDiagnostics => ({
  celery_status: "ok",
  last_token_refresh_task: null,
  accounts: [
    {
      id: "acc-1",
      nickname: "Conta A",
      token_status: "expired",
      token_expires_at: null,
      remaining_hours: 0,
      has_refresh_token: false,
      last_successful_sync: null,
      last_refresh_attempt: null,
      last_refresh_success: false,
      days_since_last_sync: 3,
      data_gap_warning: null,
      needs_reauth: true,
    },
    {
      id: "acc-2",
      nickname: "Conta B",
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
    {
      id: "acc-3",
      nickname: "Conta C",
      token_status: "expired",
      token_expires_at: "2026-03-01T00:00:00Z",
      remaining_hours: -100,
      has_refresh_token: false,
      last_successful_sync: "2026-03-20T06:00:00Z",
      last_refresh_attempt: null,
      last_refresh_success: false,
      days_since_last_sync: 12,
      data_gap_warning: "12 dias sem sincronização",
      needs_reauth: false,
    },
  ],
  recommendations: [],
});

describe("TokenHealthBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("não renderiza nada quando todos os tokens estão saudáveis", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeHealthyDiagnostics()
    );

    const { container } = render(<TokenHealthBanner />, {
      wrapper: createWrapper(),
    });

    // Aguardar resolução da query
    await vi.waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("não renderiza nada enquanto diagnostics está carregando (sem dados ainda)", () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockReturnValue(
      new Promise(() => {}) // promise que nunca resolve
    );

    const { container } = render(<TokenHealthBanner />, {
      wrapper: createWrapper(),
    });

    expect(container.firstChild).toBeNull();
  });

  it("renderiza banner quando conta tem token expirado", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      expect(screen.getByText(/MSM_PRIME/i)).toBeDefined();
    });
  });

  it("renderiza banner quando conta precisa de reautenticação", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeNeedsReauthDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      expect(screen.getByText(/Conta Vendedor/i)).toBeDefined();
    });
  });

  it("mostra botão de reconectar", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      expect(screen.getByText("Reconectar")).toBeDefined();
    });
  });

  it("botão de reconectar leva para /configuracoes", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      const link = screen.getByText("Reconectar").closest("a");
      expect(link?.getAttribute("href")).toBe("/configuracoes");
    });
  });

  it("exibe mensagem de autenticação expirada para needs_reauth=true", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeNeedsReauthDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      expect(
        screen.getByText(/Autenticação expirada — reconnecte para sincronizar dados\./i)
      ).toBeDefined();
    });
  });

  it("exibe mensagem de token expirado quando needs_reauth=false mas token_status=expired", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      expect(
        screen.getByText(/Token expirado — reconnecte para continuar\./i)
      ).toBeDefined();
    });
  });

  it("exibe aviso de dias sem sincronização quando days_since_last_sync > 0", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // O texto "7 dias sem sincronização" deve aparecer pelo menos uma vez
      const matches = screen.getAllByText(/7 dias? sem sincronização/i);
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("exibe aviso de data_gap_warning quando presente", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeExpiredDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // data_gap_warning é exibido em parágrafo itálico (italic)
      const matches = screen.getAllByText(/7 dias sem sincronização/i);
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("exibe múltiplos banners quando há múltiplas contas com problema", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeMultipleProblemsDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      // Deve mostrar Conta A e Conta C (com problemas), mas não Conta B (saudável)
      expect(screen.getByText(/Conta A/i)).toBeDefined();
      expect(screen.getByText(/Conta C/i)).toBeDefined();
      expect(screen.queryByText(/Conta B/i)).toBeNull();
    });
  });

  it("exibe dois botões de reconectar para duas contas com problema", async () => {
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeMultipleProblemsDiagnostics()
    );

    render(<TokenHealthBanner />, { wrapper: createWrapper() });

    await vi.waitFor(() => {
      const buttons = screen.getAllByText("Reconectar");
      expect(buttons).toHaveLength(2);
    });
  });
});
