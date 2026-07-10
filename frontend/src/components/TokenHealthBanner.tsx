import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, AlertCircle, Link as LinkIcon, Clock } from 'lucide-react';
import { Link } from 'react-router-dom';
import tokenDiagnosticsService from '@/services/tokenDiagnosticsService';
import type { AccountDiagnostic } from '@/services/tokenDiagnosticsService';
import { cn } from '@/lib/utils';

// Severidade por conta:
//  - critical: token expirado ou precisa reautenticar -> reconectar resolve.
//  - stale: token saudavel mas os dados pararam de sincronizar (Celery/sync parado)
//           -> reconectar NAO resolve; o aviso e informativo (E19).
type Severity = 'critical' | 'stale';

function severityOf(acc: AccountDiagnostic): Severity | null {
  if (acc.needs_reauth || acc.token_status === 'expired') return 'critical';
  if (acc.data_gap_warning) return 'stale';
  return null;
}

export function TokenHealthBanner() {
  const { data: diagnostics } = useQuery({
    queryKey: ['token-diagnostics'],
    queryFn: () => tokenDiagnosticsService.getDiagnostics(),
    refetchInterval: 300000, // 5 minutos
    retry: 2,
  });

  if (!diagnostics || diagnostics.accounts.length === 0) {
    return null;
  }

  const flagged = diagnostics.accounts
    .map((acc) => ({ acc, severity: severityOf(acc) }))
    .filter((x): x is { acc: AccountDiagnostic; severity: Severity } => x.severity !== null);

  if (flagged.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      {flagged.map(({ acc: account, severity }) => {
        const isCritical = severity === 'critical';

        return (
          <div
            key={account.id}
            className={cn(
              'rounded-lg border-l-4 p-4 flex items-start gap-3',
              isCritical
                ? 'bg-red-50 border-red-400 dark:bg-red-950 dark:border-red-600'
                : 'bg-amber-50 border-amber-400 dark:bg-amber-950 dark:border-amber-600'
            )}
          >
            {isCritical ? (
              <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            )}

            <div className="flex-1 min-w-0">
              <p className={cn('font-medium', isCritical ? 'text-red-900 dark:text-red-100' : 'text-amber-900 dark:text-amber-100')}>
                {isCritical
                  ? `Conta "${account.nickname}" desconectada`
                  : `Conta "${account.nickname}" com sincronização atrasada`}
              </p>
              <div className={cn('text-sm mt-2 space-y-1', isCritical ? 'text-red-800 dark:text-red-200' : 'text-amber-800 dark:text-amber-200')}>
                <p>
                  {isCritical
                    ? account.needs_reauth
                      ? 'Autenticação expirada — reconecte para sincronizar dados.'
                      : 'Token expirado — reconecte para continuar.'
                    : 'A conexão está saudável, mas os dados pararam de atualizar. Podem estar desatualizados.'}
                </p>
                {account.days_since_last_sync > 0 && (
                  <p className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 shrink-0" />
                    {account.days_since_last_sync} dia{account.days_since_last_sync > 1 ? 's' : ''} sem sincronização
                  </p>
                )}
                {account.data_gap_warning && (
                  <p className="text-xs mt-1 italic">{account.data_gap_warning}</p>
                )}
              </div>
            </div>

            <Link
              to="/configuracoes"
              className={cn(
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium shrink-0 whitespace-nowrap transition-colors',
                isCritical
                  ? 'bg-red-600 text-white hover:bg-red-700'
                  : 'bg-amber-600 text-white hover:bg-amber-700'
              )}
            >
              <LinkIcon className="h-4 w-4" />
              {isCritical ? 'Reconectar' : 'Ver diagnóstico'}
            </Link>
          </div>
        );
      })}
    </div>
  );
}
