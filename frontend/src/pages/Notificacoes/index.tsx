import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import notificationsService, { Notification } from '@/services/notificationsService';
import { cn } from '@/lib/utils';

/**
 * Calcula tempo relativo (ex: "há 2h", "há 5m")
 */
function getRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  if (diffMs < 60000) return 'agora';
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `há ${diffMins}m`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `há ${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `há ${diffDays}d`;
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 4) return `há ${diffWeeks}w`;
  return `há ${Math.floor(diffDays / 30)}mês`;
}

/**
 * Mapeia tipos de notificação para badges coloridas
 */
function getNotificationBadge(type: string) {
  const badges: Record<string, { bg: string; text: string; label: string }> = {
    alert: { bg: 'bg-red-100', text: 'text-red-800', label: 'Alerta' },
    promotion: { bg: 'bg-green-100', text: 'text-green-800', label: 'Promoção' },
    order: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Pedido' },
    competitor: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Concorrente' },
    reputacao: { bg: 'bg-purple-100', text: 'text-purple-800', label: 'Reputação' },
    system: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Sistema' },
  };

  return badges[type] || badges.system;
}

export default function Notificacoes() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  // Buscar todas as notificações
  const { data: allNotifications = [], isLoading } = useQuery({
    queryKey: ['notifications-all'],
    queryFn: () => notificationsService.getAll(200),
    refetchInterval: 30000,
    staleTime: 15000,
  });

  // Filtrar notificações
  const filteredNotifications =
    filter === 'unread'
      ? allNotifications.filter((n) => !n.is_read)
      : allNotifications;

  // Marcar como lida
  const markAsReadMutation = useMutation({
    mutationFn: notificationsService.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-all'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
    },
  });

  // Marcar todas como lidas
  const markAllAsReadMutation = useMutation({
    mutationFn: notificationsService.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-all'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
    },
  });

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      markAsReadMutation.mutate(notification.id);
    }
    if (notification.action_url) {
      window.location.href = notification.action_url;
    }
  };

  const unreadCount = allNotifications.filter((n) => !n.is_read).length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Notificações</h1>
          <p className="text-muted-foreground mt-1">
            {unreadCount > 0
              ? `${unreadCount} não lida${unreadCount !== 1 ? 's' : ''}`
              : 'Todas as notificações foram lidas'}
          </p>
        </div>

        {unreadCount > 0 && (
          <button
            onClick={() => markAllAsReadMutation.mutate()}
            disabled={markAllAsReadMutation.isPending}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            Marcar todas como lidas
          </button>
        )}
      </div>

      {/* Filtros */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilter('all')}
          className={cn(
            'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            filter === 'all'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          Todas ({allNotifications.length})
        </button>
        <button
          onClick={() => setFilter('unread')}
          className={cn(
            'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            filter === 'unread'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          Não lidas ({unreadCount})
        </button>
      </div>

      {/* Lista de notificações */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">Carregando notificações...</p>
          </div>
        ) : filteredNotifications.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              {filter === 'unread'
                ? 'Nenhuma notificação não lida'
                : 'Nenhuma notificação'}
            </p>
          </div>
        ) : (
          filteredNotifications.map((notification) => {
            const badge = getNotificationBadge(notification.type);
            return (
              <div
                key={notification.id}
                onClick={() => handleNotificationClick(notification)}
                className={cn(
                  'p-4 rounded-lg border transition-all cursor-pointer',
                  notification.is_read
                    ? 'border-border bg-card hover:bg-accent/50'
                    : 'border-blue-200 bg-blue-50 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950',
                )}
              >
                <div className="flex items-start gap-4">
                  {/* Badge de tipo */}
                  <div
                    className={cn(
                      'px-2 py-1 rounded text-xs font-medium flex-shrink-0',
                      badge.bg,
                      badge.text,
                    )}
                  >
                    {badge.label}
                  </div>

                  {/* Conteúdo */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-semibold text-foreground">
                        {notification.title}
                      </h3>
                      {!notification.is_read && (
                        <div className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0 mt-1" />
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {notification.message}
                    </p>
                    <p className="text-xs text-muted-foreground/60 mt-2">
                      {getRelativeTime(notification.created_at)}
                    </p>
                  </div>

                  {/* Indicador de ação */}
                  {notification.action_url && (
                    <div className="text-xs text-primary font-medium flex-shrink-0">
                      →
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
