import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAccountStore } from "./accountStore";

// Mock authService to prevent real API calls
vi.mock("@/services/authService", () => ({
  default: {
    updatePreferences: vi.fn().mockResolvedValue({}),
  },
}));

describe("accountStore", () => {
  beforeEach(() => {
    useAccountStore.setState({ activeAccountId: null });
  });

  it("starts with null activeAccountId (all accounts)", () => {
    const state = useAccountStore.getState();
    expect(state.activeAccountId).toBeNull();
  });

  it("setActiveAccount updates the active account", () => {
    const store = useAccountStore.getState();
    store.setActiveAccount("account-123", false);
    expect(useAccountStore.getState().activeAccountId).toBe("account-123");
  });

  it("setActiveAccount with null clears selection", () => {
    const store = useAccountStore.getState();
    store.setActiveAccount("account-123", false);
    store.setActiveAccount(null, false);
    expect(useAccountStore.getState().activeAccountId).toBeNull();
  });

  it("clearActiveAccount resets to null", () => {
    const store = useAccountStore.getState();
    store.setActiveAccount("account-456", false);
    store.clearActiveAccount(false);
    expect(useAccountStore.getState().activeAccountId).toBeNull();
  });

  it("setActiveAccount syncs with backend by default", async () => {
    const authService = (await import("@/services/authService")).default;
    const store = useAccountStore.getState();
    store.setActiveAccount("account-789");
    expect(authService.updatePreferences).toHaveBeenCalledWith("account-789");
  });

  it("setActiveAccount skips sync when sync=false", async () => {
    const authService = (await import("@/services/authService")).default;
    vi.mocked(authService.updatePreferences).mockClear();
    const store = useAccountStore.getState();
    store.setActiveAccount("account-no-sync", false);
    expect(authService.updatePreferences).not.toHaveBeenCalled();
  });
});
