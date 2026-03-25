import { create } from "zustand";
import { persist } from "zustand/middleware";
import authService from "@/services/authService";

interface AccountState {
  activeAccountId: string | null; // null = todas as contas
  setActiveAccount: (id: string | null, sync?: boolean) => void;
  clearActiveAccount: (sync?: boolean) => void;
}

export const useAccountStore = create<AccountState>()(
  persist(
    (set) => ({
      activeAccountId: null,
      setActiveAccount: (id, sync = true) => {
        set({ activeAccountId: id });
        if (sync) {
          authService.updatePreferences(id).catch(() => {});
        }
      },
      clearActiveAccount: (sync = true) => {
        set({ activeAccountId: null });
        if (sync) {
          authService.updatePreferences(null).catch(() => {});
        }
      },
    }),
    {
      name: "msm-active-account",
      partialize: (state) => ({
        activeAccountId: state.activeAccountId,
      }),
    },
  ),
);
