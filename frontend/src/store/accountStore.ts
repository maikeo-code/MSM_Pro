import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AccountState {
  activeAccountId: string | null; // null = todas as contas
  setActiveAccount: (id: string | null) => void;
  clearActiveAccount: () => void;
}

export const useAccountStore = create<AccountState>()(
  persist(
    (set) => ({
      activeAccountId: null,
      setActiveAccount: (id) => {
        set({ activeAccountId: id });
      },
      clearActiveAccount: () => {
        set({ activeAccountId: null });
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
