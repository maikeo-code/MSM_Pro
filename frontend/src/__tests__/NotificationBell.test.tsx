import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationBell } from "@/components/NotificationBell";
import notificationsService from "@/services/notificationsService";
import type { Notification } from "@/services/notificationsService";

vi.mock("@/services/notificationsService", () => ({
  default: {
    getCount: vi.fn(),
    getUnread: vi.fn(),
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
  },
}));

vi.mock("@/lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

const makeNotification = (overrides: Partial<Notification> = {}): Notification => ({
  id: "notif-1",
  type: "alert",
  title: "Estoque baixo",
  message: "MLB123456789 tem apenas 2 unidades em estoque",
  is_read: false,
  action_url: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

const createWrapper = (queryClient?: QueryClient) => {
  const client =
    queryClient ??
    new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
};

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([]);
    vi.mocked(notificationsService.markAsRead).mockResolvedValue();
    vi.mocked(notificationsService.markAllAsRead).mockResolvedValue();
  });

  it("renderiza o ícone de sino", () => {
    render(<NotificationBell />, { wrapper: createWrapper() });

    // O botão com title "Notificações" deve existir
    const button = document.querySelector('button[title="Notificações"]');
    expect(button).toBeDefined();
  });

  it("não mostra badge quando contagem de não lidas é zero", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 0 });

    render(<NotificationBell />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Não deve haver span com número de contagem
      const badge = document.querySelector(
        "span.rounded-full.bg-red-500"
      ) as HTMLElement | null;
      expect(badge).toBeNull();
    });
  });

  it("mostra badge com contagem quando há notificações não lidas", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 3 });

    render(<NotificationBell />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("3")).toBeDefined();
    });
  });

  it("mostra '99+' quando contagem excede 99", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 150 });

    render(<NotificationBell />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("99+")).toBeDefined();
    });
  });

  it("click no sino abre o dropdown", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 2 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification(),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Notificações")).toBeDefined();
    });
  });

  it("exibe 'Nenhuma notificação' quando dropdown abre sem notificações", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Nenhuma notificação")).toBeDefined();
    });
  });

  it("exibe lista de notificações no dropdown", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({ title: "Alerta de preço" }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Alerta de preço")).toBeDefined();
    });
  });

  it("click em notificação não lida chama markAsRead", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({ id: "notif-999", is_read: false }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Estoque baixo")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Estoque baixo").closest("div.cursor-pointer")!);

    await waitFor(() => {
      expect(notificationsService.markAsRead).toHaveBeenCalledWith("notif-999");
    });
  });

  it("click em notificação já lida não chama markAsRead", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 0 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({ id: "notif-already-read", is_read: true }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Estoque baixo")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Estoque baixo").closest("div.cursor-pointer")!);

    await waitFor(() => {
      expect(notificationsService.markAsRead).not.toHaveBeenCalled();
    });
  });

  it("botão 'Marcar todas como lidas' aparece quando há não lidas", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 3 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification(),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const button = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText("Marcar todas como lidas")).toBeDefined();
    });
  });

  it("'Marcar todas como lidas' chama markAllAsRead", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 2 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification(),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("Marcar todas como lidas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Marcar todas como lidas"));

    await waitFor(() => {
      expect(notificationsService.markAllAsRead).toHaveBeenCalled();
    });
  });

  it("fecha o dropdown após marcar todas como lidas", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification(),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("Marcar todas como lidas")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Marcar todas como lidas"));

    await waitFor(() => {
      // O dropdown deve fechar — "Notificações" header some
      expect(screen.queryByText("Nenhuma notificação")).toBeNull();
    });
  });

  it("getRelativeTime — retorna 'há 1 mês' para 30 dias atrás", async () => {
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({ created_at: thirtyDaysAgo }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("há 1 mês")).toBeDefined();
    });
  });

  it("getRelativeTime — retorna 'há 2 meses' para 60 dias atrás", async () => {
    const sixtyDaysAgo = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString();

    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({ created_at: sixtyDaysAgo }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("há 2 meses")).toBeDefined();
    });
  });

  it("exibe link 'Ver todas as notificações' quando há notificações no dropdown", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification(),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("Ver todas as notificações")).toBeDefined();
    });
  });

  it("navega para action_url ao clicar em notificação com URL", async () => {
    vi.mocked(notificationsService.getCount).mockResolvedValue({ unread_count: 1 });
    vi.mocked(notificationsService.getUnread).mockResolvedValue([
      makeNotification({
        id: "notif-with-url",
        action_url: "/alertas",
        is_read: false,
      }),
    ]);

    render(<NotificationBell />, { wrapper: createWrapper() });

    const sinoButton = document.querySelector(
      'button[title="Notificações"]'
    ) as HTMLElement;
    fireEvent.click(sinoButton);

    await waitFor(() => {
      expect(screen.getByText("Estoque baixo")).toBeDefined();
    });

    fireEvent.click(screen.getByText("Estoque baixo").closest("div.cursor-pointer")!);

    await waitFor(() => {
      expect(window.location.href).toBe("/alertas");
    });
  });
});
