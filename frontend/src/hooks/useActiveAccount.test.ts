import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useActiveAccount, useAccountQueryParams } from "./useActiveAccount";
import { useAccountStore } from "@/store/accountStore";

vi.mock("@/services/authService", () => ({
  default: {
    updatePreferences: vi.fn().mockResolvedValue({}),
  },
}));

describe("useActiveAccount", () => {
  beforeEach(() => {
    useAccountStore.setState({ activeAccountId: null });
  });

  it("returns null when no account is selected", () => {
    const { result } = renderHook(() => useActiveAccount());
    expect(result.current).toBeNull();
  });

  it("returns the active account id", () => {
    useAccountStore.setState({ activeAccountId: "acc-123" });
    const { result } = renderHook(() => useActiveAccount());
    expect(result.current).toBe("acc-123");
  });
});

describe("useAccountQueryParams", () => {
  beforeEach(() => {
    useAccountStore.setState({ activeAccountId: null });
  });

  it("returns empty object when no account selected", () => {
    const { result } = renderHook(() => useAccountQueryParams());
    expect(result.current).toEqual({});
  });

  it("returns ml_account_id param when account selected", () => {
    useAccountStore.setState({ activeAccountId: "acc-456" });
    const { result } = renderHook(() => useAccountQueryParams());
    expect(result.current).toEqual({ ml_account_id: "acc-456" });
  });
});
