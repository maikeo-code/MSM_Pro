import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import notificationsService, { Notification } from '@/services/notificationsService';
import { cn } from '@/lib/utils';

/**
 * Calcula tempo relativo (ex: "há 2h", "há 5m")
 */
function getRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  // Segundos
  if (diffMs < 60000) {
    return 'agora';
  }

  // Minutos
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) {
    return `há ${diffMins}m`;
  }

  // Horas
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) {
    return `há ${diffHours}h`;
  }

  // Dias
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return `há ${diffDays}d`;
  }

  // Semanas
  const diffWeeks = Math.floor(diffDays / 7);
  if (diffWeeks < 4) {
    return `há ${diffWeeks}w`;
  }

  // Meses
  const diffMonths = Math.floor(diffDays / 30);
  return `há ${diffMonths}mês`;
}

export function NotificationBell() {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Buscar contagem de notificações não lidas a cada 60 segundos
  const { data: countData = { count: 0 } } = useQuery({
    queryKey: ['notifications-count'],
    queryFn: notificationsService.getCount,
    refetchInterval: 60000, // 60 segundos
    staleTime: 30000, // 30 segundos
  });

  // Buscar lista de notificações não lidas quando dropdown abre
  const { data: notifications = [] } = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: notificationsService.getUnread,
    enabled: isDropdownOpen, // Só buscar quando dropdown está aberto
    refetchInterval: isDropdownOpen ? 30000 : undefined, // Recarregar a cada 30s se aberto
    staleTime: 10000, // 10 segundos
  });

  // Fechar dropdown ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    }

    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isDropdownOpen]);

  const handleNotificationClick = async (notification: Notification) => {
    // Marcar como lida
    if (!notification.is_read) {
      await notificationsService.markAsRead(notification.id);
    }

    // Navegar se houver URL
    if (notification.action_url) {
      window.location.href = notification.action_url;
    }
  };

  const handleMarkAllAsRead = async () => {
    await notificationsService.markAllAsRead();
    setIsDropdownOpen(false);
  };

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        ref={buttonRef}
        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        className="relative p-2 hover:bg-accent rounded-md transition-colors hidden lg:block"
        title="Notificações"
      >
        {/* SVG do sino */}
        <svg
          className="h-5 w-5 text-muted-foreground"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* Badge de contagem */}
        {countData.count > 0 && (
          <span className="absolute top-1 right-1 h-5 w-5 rounded-full bg-red-500 text-white text-xs font-bold flex items-center justify-center">
            {countData.count > 99 ? '99+' : countData.count}
          </span>
        )}
      </button>

      {/* Dropdown de notificações */}
      {isDropdownOpen && (
        <div
          ref={dropdownRef}
          className="absolute right-0 mt-2 w-96 rounded-lg shadow-lg bg-popover border border-border z-50 max-h-96 flex flex-col"
        >
          {/* Header */}
          <div className="px-4 py-3 border-b border-border flex items-center justify-between sticky top-0 bg-popover rounded-t-lg">
            <h3 className="font-semibold text-sm">Notificações</h3>
            {countData.count > 0 && (
              <button
                onClick={handleMarkAllAsRead}
                className="text-xs text-primary hover:underline transition-colors"
              >
                Marcar todas como lidas
              </button>
            )}
          </div>

          {/* Lista de notificações */}
          <div className="flex-1 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-6 text-center">
                <p className="text-sm text-muted-foreground">Nenhuma notificação</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={cn(
                      'px-4 py-3 cursor-pointer transition-colors',
                      notification.is_read
                        ? 'hover:bg-accent/50 bg-transparent'
                        : 'bg-accent hover:bg-accent/80',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {/* Indicador de não lido */}
                      {!notification.is_read && (
                        <div className="mt-1 h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                      )}

                      {/* Conteúdo */}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm text-foreground truncate">
                          {notification.title}
                        </p>
                        <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                          {notification.message}
                        </p>
                        <p className="text-xs text-muted-foreground/60 mt-1">
                          {getRelativeTime(notification.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer (opcional) */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 border-t border-border text-center sticky bottom-0 bg-popover rounded-b-lg">
              <a
                href="/notificacoes"
                className="text-xs text-primary hover:underline transition-colors"
              >
                Ver todas as notificações
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
