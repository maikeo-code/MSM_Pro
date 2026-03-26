import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Settings, User, Lock, AlertCircle, Loader2, RefreshCw, CheckCircle2, Clock } from "lucide-react";
import authService from "@/services/authService";
// formatDateTime removido — UX agora mostra status em texto, não data de expiração

export default function Configuracoes() {
  const queryClient = useQueryClient();
  const [connectLoading, setConnectLoading] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  const { data: currentUser, isLoading: userLoading } = useQuery({
    queryKey: ["current-user"],
    queryFn: () => authService.getMe(),
  });

  const { data: mlAccounts, isLoading, isError: mlError } = useQuery({
    queryKey: ["ml-accounts"],
    queryFn: () => authService.listMLAccounts(),
  });

  const deleteMutation = useMutation({
    mutationFn: (accountId: string) => authService.deleteMLAccount(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ml-accounts"] });
    },
  });

  const handleConnect = async () => {
    setConnectLoading(true);
    setConnectError(null);
    try {
      const result = await authService.getMLConnectURL();
      if (result.auth_url) {
        // Redireciona no mesmo tab — padrão OAuth (não é bloqueado como popup)
        window.location.href = result.auth_url;
      } else {
        setConnectError("URL de autorização não retornada pela API.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao conectar conta ML.";
      setConnectError(msg);
    } finally {
      setConnectLoading(false);
    }
  };

  const getTokenStatus = (expiresAt: string | null) => {
    if (!expiresAt) return "unknown";
    const diff = new Date(expiresAt).getTime() - Date.now();
    if (diff > 3600000) return "healthy";      // > 1h
    if (diff > 0) return "expiring_soon";       // < 1h mas válido
    return "auto_renewing";                     // expirado — Celery renova automaticamente
  };

  return (
    <div className="p-8 space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Configuracoes</h1>
        <p className="text-muted-foreground mt-1">
          Gerencie seu perfil, contas do Mercado Livre e produtos
        </p>
      </div>

      {/* Perfil do Usuário */}
      <div className="rounded-lg border bg-card">
        <div className="px-6 py-4 border-b flex items-center gap-3">
          <User className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-lg font-semibold">Perfil</h2>
            <p className="text-sm text-muted-foreground">
              Informações da sua conta
            </p>
          </div>
        </div>

        <div className="p-6 space-y-4">
          {userLoading ? (
            <p className="text-muted-foreground text-sm">Carregando perfil...</p>
          ) : currentUser ? (
            <div className="space-y-3">
              <div className="pb-3 border-b">
                <p className="text-sm text-muted-foreground mb-1">Email</p>
                <p className="font-medium">{currentUser.email}</p>
              </div>
              <div className="pb-3 border-b">
                <p className="text-sm text-muted-foreground mb-1">ID da Conta</p>
                <p className="font-mono text-sm text-muted-foreground">
                  {currentUser.id}
                </p>
              </div>
              <div className="pb-3">
                <p className="text-sm text-muted-foreground mb-1">Status</p>
                <span className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-green-100 text-green-700">
                  Ativa
                </span>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Contas ML */}
      <div className="rounded-lg border bg-card">
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Contas Mercado Livre</h2>
            <p className="text-sm text-muted-foreground">
              Conecte suas contas ML para sincronizar anuncios
            </p>
          </div>
          <button
            onClick={handleConnect}
            disabled={connectLoading}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            {connectLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            {connectLoading ? "Aguarde..." : "Conectar conta"}
          </button>
        </div>
        {connectError && (
          <div className="mx-6 mt-4 flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {connectError}
          </div>
        )}

        <div className="p-6">
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Carregando contas...</p>
          ) : mlError ? (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              Erro ao carregar contas do Mercado Livre. Tente recarregar a pagina.
            </div>
          ) : !mlAccounts || mlAccounts.length === 0 ? (
            <div className="text-center py-8">
              <Settings className="h-10 w-10 text-muted-foreground/30 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                Nenhuma conta conectada ainda.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {mlAccounts.map((account) => {
                const tokenStatus = getTokenStatus(account.token_expires_at);
                const isInactive = !account.is_active;
                return (
                  <div
                    key={account.id}
                    className={`flex items-center justify-between rounded-lg border p-4 ${
                      isInactive ? "bg-red-50 dark:bg-red-950" : ""
                    }`}
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{account.nickname}</p>
                        {tokenStatus === "healthy" && (
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                        )}
                        {tokenStatus === "expiring_soon" && (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                        {tokenStatus === "auto_renewing" && (
                          <RefreshCw className="h-4 w-4 text-blue-500" />
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {account.email ?? account.ml_user_id}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {tokenStatus === "healthy" && (
                          <>Conexao ativa — renova automaticamente</>
                        )}
                        {tokenStatus === "expiring_soon" && (
                          <>Renovando em breve (automatico)</>
                        )}
                        {tokenStatus === "auto_renewing" && (
                          <span className="text-blue-600">Renovacao automatica em andamento</span>
                        )}
                        {tokenStatus === "unknown" && (
                          <>Token nao disponivel</>
                        )}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          isInactive
                            ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                            : tokenStatus === "healthy"
                              ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                              : "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                        }`}
                      >
                        {isInactive ? "Inativa" : "Ativa"}
                      </span>
                      {(account as any).active_listings_count > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {(account as any).active_listings_count} anuncios
                        </span>
                      )}
                      <button
                        onClick={() => {
                          if (window.confirm(`Desconectar conta "${account.nickname}"? Esta ação é irreversível.`)) {
                            deleteMutation.mutate(account.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="rounded-md border p-2 text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                        title="Desconectar conta"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Segurança */}
      <div className="rounded-lg border bg-card">
        <div className="px-6 py-4 border-b flex items-center gap-3">
          <Lock className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-lg font-semibold">Segurança</h2>
            <p className="text-sm text-muted-foreground">
              Gerencie sua senha e sessões
            </p>
          </div>
        </div>

        <div className="p-6">
          <button className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50 cursor-not-allowed" disabled>
            <Lock className="h-4 w-4" />
            Alterar senha (em breve)
          </button>
        </div>
      </div>

      {/* Produtos (SKUs) */}
      <div className="rounded-lg border bg-card p-6">
        <h2 className="text-lg font-semibold mb-2">Produtos (SKUs)</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Gerencie seu catalogo de produtos com custos para calcular margens.
        </p>
        <a
          href="/produtos"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Settings className="h-4 w-4" />
          Gerenciar Produtos
        </a>
      </div>
    </div>
  );
}
