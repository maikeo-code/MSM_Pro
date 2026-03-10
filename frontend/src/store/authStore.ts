import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserOut } from "@/services/authService";

interface AuthState {
  user: UserOut | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: UserOut, token: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setAuth: (user, token) =>
        set({ user, token, isAuthenticated: true }),
      clearAuth: () =>
        set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: "msm-auth-storage",
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
