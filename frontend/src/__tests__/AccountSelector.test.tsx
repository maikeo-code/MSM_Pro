import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AccountSelector } from "@/components/AccountSelector";
import authService from "@/services/authService";
import tokenDiagnosticsService from "@/services/tokenDiagnosticsService";
import { useAccountStore } from "@/store/accountStore";
import type { MLAccountOut } from "@/services/authService";
import type { TokenDiagnostics } from "@/services/tokenDiagnosticsService";

vi.mock("@/services/authService", () => ({
  default: {
    listMLAccounts: vi.fn(),
    updatePreferences: vi.fn(),
  },
}));

vi.mock("@/services/tokenDiagnosticsService", () => ({
  default: {
    getDiagnostics: vi.fn(),
  },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

const makeAccount = (overrides: Partial<MLAccountOut> = {}): MLAccountOut => ({
  id: "acc-1",
  ml_user_id: "2050442871",
  nickname: "MSM_PRIME",
  email: "seller@example.com",
  token_expires_at: "2026-12-01T00:00:00Z",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  needs_reauth: false,
  last_sync_at: "2026-04-01T06:00:00Z",
  ...overrides,
});

const makeHealthyDiagnostics = (): TokenDiagnostics => ({
  celery_status: "ok",
  last_token_refresh_task: null,
  accounts: [],
  recommendations: [],
});

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("AccountSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAccountStore.setState({ activeAccountId: null });
    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(
      makeHealthyDiagnostics()
    );
  });

  it("não renderiza quando há apenas uma conta", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([makeAccount()]);

    const { container } = render(<AccountSelector />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      // Com apenas 1 conta, retorna null
      expect(container.firstChild).toBeNull();
    });
  });

  it("não renderiza quando não há contas", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([]);

    const { container } = render(<AccountSelector />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renderiza dropdown quando há múltiplas contas", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta 1" }),
      makeAccount({ id: "acc-2", nickname: "Conta 2" }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Deve mostrar o botão do seletor (com texto "Todas as contas")
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });
  });

  it("clique no botão abre o dropdown com opções de contas", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta Alpha" }),
      makeAccount({ id: "acc-2", nickname: "Conta Beta" }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    // Clicar no botão para abrir
    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Conta Alpha")).toBeDefined();
      expect(screen.getByText("Conta Beta")).toBeDefined();
    });
  });

  it("exibe opção 'Todas as contas' no dropdown", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta 1" }),
      makeAccount({ id: "acc-2", nickname: "Conta 2" }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      // Deve haver pelo menos duas ocorrências de "Todas as contas" (botão + dropdown)
      const items = screen.getAllByText("Todas as contas");
      expect(items.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("selecionar uma conta atualiza o store", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta Alpha" }),
      makeAccount({ id: "acc-2", nickname: "Conta Beta" }),
    ]);
    vi.mocked(authService.updatePreferences).mockResolvedValue();

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Conta Alpha")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Conta Alpha").closest("button")!);

    await waitFor(() => {
      expect(useAccountStore.getState().activeAccountId).toBe("acc-1");
    });
  });

  it("selecionar 'Todas as contas' limpa a conta ativa", async () => {
    // Começar com uma conta ativa
    useAccountStore.setState({ activeAccountId: "acc-1" });

    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta Alpha" }),
      makeAccount({ id: "acc-2", nickname: "Conta Beta" }),
    ]);
    vi.mocked(authService.updatePreferences).mockResolvedValue();

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Conta Alpha")).toBeDefined();
    });

    // Abrir o dropdown
    fireEvent.click(screen.getByText("Conta Alpha").closest("button")!);

    await waitFor(() => {
      // No dropdown deve haver a opção "Todas as contas"
      const allAccountsOptions = screen.getAllByText("Todas as contas");
      expect(allAccountsOptions.length).toBeGreaterThan(0);
    });

    // Clicar em "Todas as contas" no dropdown
    const dropdownAllButton = screen.getAllByText("Todas as contas")[0].closest("button")!;
    fireEvent.click(dropdownAllButton);

    await waitFor(() => {
      expect(useAccountStore.getState().activeAccountId).toBeNull();
    });
  });

  it("selecionar conta chama updatePreferences via store", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta X" }),
      makeAccount({ id: "acc-2", nickname: "Conta Y" }),
    ]);
    vi.mocked(authService.updatePreferences).mockResolvedValue();

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Conta X")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Conta X").closest("button")!);

    await waitFor(() => {
      expect(authService.updatePreferences).toHaveBeenCalledWith("acc-1");
    });
  });

  it("fecha dropdown após selecionar uma conta", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta Alpha" }),
      makeAccount({ id: "acc-2", nickname: "Conta Beta" }),
    ]);
    vi.mocked(authService.updatePreferences).mockResolvedValue();

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Conta Alpha")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Conta Alpha").closest("button")!);

    await waitFor(() => {
      // Dropdown fechou — só a instância do botão principal permanece
      const alphaItems = screen.queryAllByText("Conta Alpha");
      // Depois de selecionar, o botão principal mostra "Conta Alpha"
      // mas o dropdown fechou, então não há duplicata de dropdown
      expect(alphaItems.length).toBe(1);
    });
  });

  it("exibe indicador de problema em conta com token expirado", async () => {
    const expiredDiagnostics: TokenDiagnostics = {
      celery_status: "ok",
      last_token_refresh_task: null,
      accounts: [
        {
          id: "acc-2",
          nickname: "Conta Com Problema",
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
    };

    vi.mocked(tokenDiagnosticsService.getDiagnostics).mockResolvedValue(expiredDiagnostics);
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta OK" }),
      makeAccount({ id: "acc-2", nickname: "Conta Com Problema", token_expires_at: null }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    // Abrir dropdown para verificar indicadores
    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Conta Com Problema")).toBeDefined();
    });
  });

  it("exibe badge 'Expirado' para conta sem token_expires_at", async () => {
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta OK" }),
      makeAccount({ id: "acc-2", nickname: "Conta Expirada", token_expires_at: null }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      expect(screen.getByText("Expirado")).toBeDefined();
    });
  });

  it("exibe badge 'Ativo' para conta com token válido por mais de 7 dias", async () => {
    const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
    vi.mocked(authService.listMLAccounts).mockResolvedValue([
      makeAccount({ id: "acc-1", nickname: "Conta OK 1", token_expires_at: futureDate }),
      makeAccount({ id: "acc-2", nickname: "Conta OK 2", token_expires_at: futureDate }),
    ]);

    render(<AccountSelector />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Todas as contas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Todas as contas").closest("button")!);

    await waitFor(() => {
      const activeBadges = screen.getAllByText("Ativo");
      expect(activeBadges.length).toBeGreaterThanOrEqual(2);
    });
  });
});
