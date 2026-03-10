import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, RefreshCw, Settings } from "lucide-react";
import authService from "@/services/authService";
import { formatDateTime } from "@/lib/utils";

export default function Configuracoes() {
  const queryClient = useQueryClient();

  const { data: mlAccounts, isLoading } = useQuery({
    queryKey: ["ml-accounts"],
    queryFn: () => authService.listMLAccounts(),
  });

  const { data: connectURL, refetch: fetchConnectURL } = useQuery({
    queryKey: ["ml-connect-url"],
    queryFn: () => authService.getMLConnectURL(),
    enabled: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (accountId: string) => authService.deleteMLAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-accounts"] });
    },
  });

  const handleConnect = async () => {
    const result = await fetchConnectURL();
    if (result.data?.auth_url) {
      window.open(result.data.auth_url, "_blank");
    }
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Configuracoes</h1>
        <p className="text-muted-foreground mt-1">
          Gerencie suas contas do Mercado Livre e SKUs
        </p>
      </div>

      {/* Contas ML */}
      <div className="rounded-lg border bg-card mb-6">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Contas Mercado Livre</h2>
            <p className="text-sm text-muted-foreground">
              Conecte suas contas ML para sincronizar anuncios
            </p>
          </div>
          <button
            onClick={handleConnect}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Conectar conta
          </button>
        </div>

        <div className="p-6">
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Carregando contas...</p>
          ) : !mlAccounts || mlAccounts.length === 0 ? (
            <div className="text-center py-8">
              <Settings className="h-10 w-10 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                Nenhuma conta conectada ainda.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {mlAccounts.map((account) => (
                <div
                  key={account.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div>
                    <p className="font-medium">{account.nickname}</p>
                    <p className="text-sm text-muted-foreground">
                      {account.email ?? account.ml_user_id}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Token expira:{" "}
                      {account.token_expires_at
                        ? formatDateTime(account.token_expires_at)
                        : "N/A"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        account.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {account.is_active ? "Ativa" : "Inativa"}
                    </span>
                    <button
                      onClick={() => deleteMutation.mutate(account.id)}
                      disabled={deleteMutation.isPending}
                      className="rounded-md border p-2 text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Link para gerenciar SKUs */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-2">Produtos (SKUs)</h2>
        <p className="text-sm text-muted-foreground">
          Gerencie seu catalogo de produtos com custos para calcular margens.
          Disponivel em breve nesta pagina.
        </p>
      </div>
    </div>
  );
}
