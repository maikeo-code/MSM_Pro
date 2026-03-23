import { useAccountStore } from "@/store/accountStore";

/**
 * Hook customizado para acessar a conta ativa e incluir em query params
 * Retorna o ID da conta ativa ou null (todas as contas)
 */
export function useActiveAccount() {
  return useAccountStore((state) => state.activeAccountId);
}

/**
 * Hook customizado para obter parâmetros de query prontos para usar em chamadas API
 * Retorna um objeto que pode ser passado direto no params do axios
 */
export function useAccountQueryParams() {
  const activeAccountId = useAccountStore((state) => state.activeAccountId);
  return activeAccountId ? { ml_account_id: activeAccountId } : {};
}
