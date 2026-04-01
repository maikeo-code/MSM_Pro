import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import notificationsService from '@/services/notificationsService';

/**
 * Hook customizado para gerenciar notificações
 */
export function useNotifications() {
  const queryClient = useQueryClient();

  // Buscar contagem de não lidas
  const countQuery = useQuery({
    queryKey: ['notifications-count'],
    queryFn: notificationsService.getCount,
    refetchInterval: 60000,
    staleTime: 30000,
  });

  // Buscar lista de não lidas
  const unreadQuery = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: notificationsService.getUnread,
    staleTime: 10000,
  });

  // Marcar como lida (mutação)
  const markAsReadMutation = useMutation({
    mutationFn: notificationsService.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
    },
  });

  // Marcar todas como lidas (mutação)
  const markAllAsReadMutation = useMutation({
    mutationFn: notificationsService.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
    },
  });

  return {
    count: countQuery.data?.unread_count ?? 0,
    countLoading: countQuery.isLoading,
    countError: countQuery.error,

    notifications: unreadQuery.data ?? [],
    notificationsLoading: unreadQuery.isLoading,
    notificationsError: unreadQuery.error,

    markAsRead: markAsReadMutation.mutate,
    isMarkingAsRead: markAsReadMutation.isPending,

    markAllAsRead: markAllAsReadMutation.mutate,
    isMarkingAllAsRead: markAllAsReadMutation.isPending,
  };
}
