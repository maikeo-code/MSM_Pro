import api from './api';

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  action_url: string | null;
  created_at: string;
}

export interface NotificationCount {
  count: number;
}

const notificationsService = {
  /**
   * Busca todas as notificações não lidas do usuário
   */
  getUnread: async (): Promise<Notification[]> => {
    const response = await api.get<Notification[]>('/notifications/unread');
    return response.data;
  },

  /**
   * Busca contagem de notificações não lidas
   */
  getCount: async (): Promise<NotificationCount> => {
    const response = await api.get<NotificationCount>('/notifications/count');
    return response.data;
  },

  /**
   * Marca uma notificação específica como lida
   */
  markAsRead: async (id: string): Promise<void> => {
    await api.post(`/notifications/${id}/read`);
  },

  /**
   * Marca todas as notificações como lidas
   */
  markAllAsRead: async (): Promise<void> => {
    await api.post('/notifications/read-all');
  },

  /**
   * Busca todas as notificações (incluindo lidas)
   */
  getAll: async (limit: number = 50): Promise<Notification[]> => {
    const response = await api.get<Notification[]>('/notifications', {
      params: { limit },
    });
    return response.data;
  },
};

export default notificationsService;
