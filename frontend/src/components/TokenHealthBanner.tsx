import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, AlertCircle, Link as LinkIcon } from 'lucide-react';
import { Link } from 'react-router-dom';
import tokenDiagnosticsService, { type AccountDiagnostic } from '@/services/tokenDiagnosticsService';
import { cn } from '@/lib/utils';

export function TokenHealthBanner() {
  const { data: diagnostics } = useQuery({
    queryKey: ['token-diagnostics'],
    queryFn: () => tokenDiagnosticsService.getDiagnostics(),
    refetchInterval: 300000, // 5 minutos
    retry: 2,
  });

  if (!diagnostics) {
    return null;
  }

  // Filtrar contas que precisam de reauth ou token expirado
  const problematicAccounts = diagnostics.accounts.filter(
    (acc) => acc.needs_reauth || acc.token_status === 'expired'
  );

  if (problematicAccounts.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      {problematicAccounts.map((account) => {
        const isExpired = account.token_status === 'expired';
        const needsReauth = account.needs_reauth;

        return (
          <div
            key={account.id}
            className={cn(
              'rounded-lg border-l-4 p-4 flex items-start gap-3',
              needsReauth || isExpired
                ? 'bg-red-50 border-red-400 dark:bg-red-950 dark:border-red-600'
                : 'bg-amber-50 border-amber-400 dark:bg-amber-950 dark:border-amber-600'
            )}
          >
            {needsReauth || isExpired ? (
              <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            )}

            <div className="flex-1 min-w-0">
              <p className={cn('font-medium', needsReauth || isExpired ? 'text-red-900 dark:text-red-100' : 'text-amber-900 dark:text-amber-100')}>
                Conta "{account.nickname}" desconectada
              </p>
              <p className={cn('text-sm mt-1', needsReauth || isExpired ? 'text-red-800 dark:text-red-200' : 'text-amber-800 dark:text-amber-200')}>
                {needsReauth ? 'Autenticação expirada — reconnecte para sincronizar dados.' : 'Token expirado — reconnecte para continuar.'}
                {account.days_since_last_sync > 0 && ` Sem dados por ${account.days_since_last_sync} dia${account.days_since_last_sync > 1 ? 's' : ''}.`}
              </p>
            </div>

            <Link
              to="/configuracoes"
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium shrink-0 whitespace-nowrap transition-colors',
                needsReauth || isExpired
                  ? 'bg-red-600 text-white hover:bg-red-700'
                  : 'bg-amber-600 text-white hover:bg-amber-700'
              )}
            >
              <LinkIcon className="h-4 w-4" />
              Reconectar
            </Link>
          </div>
        );
      })}
    </div>
  );
}
