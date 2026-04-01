# Sistema de Notificações — Frontend

## Visão geral
O frontend possui um sistema completo de notificações com:
- Sino na topbar (NotificationBell) com contagem de não lidas
- Dropdown com lista de notificações não lidas
- Página completa de notificações em `/notificacoes`
- Hook customizado `useNotifications()` para uso em outras páginas
- Polling automático a cada 60 segundos para contagem
- React Query para cache e gerenciamento de estado

## Componentes

### 1. NotificationBell.tsx
Componente que mostra um sino na topbar com:
- Badge vermelho com contagem de notificações não lidas
- Dropdown ao clicar que lista as notificações não lidas
- SVG inline (sem dependências externas de ícones)
- Fechar dropdown ao clicar fora
- Links para notificações com `action_url`
- Polling automático a cada 60 segundos

**Uso:**
```tsx
import { NotificationBell } from "@/components/NotificationBell";

<NotificationBell />
```

### 2. notificationsService.ts
Service com métodos para chamar a API de notificações:

```typescript
import notificationsService from '@/services/notificationsService';

// Buscar notificações não lidas
const notificacoes = await notificationsService.getUnread();

// Buscar contagem de não lidas
const { count } = await notificationsService.getCount();

// Marcar como lida
await notificationsService.markAsRead('notification-id');

// Marcar todas como lidas
await notificationsService.markAllAsRead();

// Buscar todas as notificações (incluindo lidas)
const todas = await notificationsService.getAll(50);
```

### 3. useNotifications.ts
Hook customizado que gerencia notificações com React Query:

```tsx
import { useNotifications } from '@/hooks/useNotifications';

function MyComponent() {
  const {
    count,           // número de notificações não lidas
    notifications,   // array de Notification
    markAsRead,      // função para marcar como lida
    markAllAsRead,   // função para marcar todas como lidas
  } = useNotifications();

  return (
    <div>
      <p>Você tem {count} notificações não lidas</p>
    </div>
  );
}
```

### 4. Página Notificacoes (pages/Notificacoes/index.tsx)
Página completa com:
- Filtro "Todas" / "Não lidas"
- Badges coloridas por tipo de notificação
- Tempo relativo ("há 2h")
- Clique para marcar como lida e navegar se houver `action_url`
- Botão para marcar todas como lidas

**URL:** `/notificacoes`

## Tipos de Notificação

| Tipo | Badge | Cor |
|------|-------|-----|
| `alert` | Alerta | Vermelho |
| `promotion` | Promoção | Verde |
| `order` | Pedido | Azul |
| `competitor` | Concorrente | Laranja |
| `reputacao` | Reputação | Roxo |
| `system` | Sistema | Cinza |

## Interface Notification

```typescript
interface Notification {
  id: string;
  type: string;                    // alert, promotion, order, etc
  title: string;                   // Título da notificação
  message: string;                 // Mensagem (pode ser longa)
  is_read: boolean;                // Já foi lida?
  action_url: string | null;       // URL para navegar ao clicar
  created_at: string;              // ISO 8601 timestamp
}
```

## Endpoints esperados no Backend

### GET /notifications/unread
Retorna array de notificações não lidas.

```json
[
  {
    "id": "uuid",
    "type": "alert",
    "title": "Estoque baixo",
    "message": "SKU X tem estoque menor que 10 unidades",
    "is_read": false,
    "action_url": "/anuncios/mlb123",
    "created_at": "2026-04-01T10:30:00Z"
  }
]
```

### GET /notifications/count
Retorna contagem de não lidas.

```json
{
  "count": 5
}
```

### POST /notifications/{id}/read
Marca uma notificação como lida. Retorna 204 No Content.

### POST /notifications/read-all
Marca todas como lidas. Retorna 204 No Content.

### GET /notifications?limit=50
Retorna todas as notificações (incluindo lidas).

```json
[
  { "id": "...", "is_read": true, ... },
  { "id": "...", "is_read": false, ... }
]
```

## Polling e Cache

- **Contagem**: polling a cada 60 segundos
- **Lista de não lidas**: polling apenas quando dropdown está aberto (30 segundos)
- **Página de todas**: polling a cada 30 segundos
- **staleTime**: 10-30 segundos (dados são revalidados após esse tempo)

## Como adicionar notificações no Backend

No backend (`backend/app/notificacoes/service.py` ou similar):

```python
from uuid import uuid4
from datetime import datetime
from sqlalchemy import insert

async def create_notification(
    user_id: UUID,
    type: str,
    title: str,
    message: str,
    action_url: Optional[str] = None,
):
    """Cria uma nova notificação para um usuário"""
    stmt = insert(UserNotification).values(
        id=uuid4(),
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        is_read=False,
        action_url=action_url,
        created_at=datetime.utcnow(),
    )
    await db.execute(stmt)
    await db.commit()
```

## Exemplo de Uso em um Componente

```tsx
import { useNotifications } from '@/hooks/useNotifications';

export function MeuComponente() {
  const { count, notifications, markAsRead } = useNotifications();

  return (
    <div>
      <h2>Notificações não lidas: {count}</h2>
      <ul>
        {notifications.map((notif) => (
          <li
            key={notif.id}
            onClick={() => markAsRead(notif.id)}
          >
            {notif.title} - {notif.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Notas Importantes

1. **O sino só aparece em desktop** (hidden em móvel via `hidden lg:block`)
2. **Dropdown fecha ao clicar fora** usando useRef + useEffect
3. **SVG inline** — não há dependência com react-icons
4. **React Query** gerencia cache automaticamente
5. **Mutações invalidam cache** — após marcar como lida, busca é feita novamente
6. **Tempo relativo é calculado localmente** — não precisa sincronizar com servidor

## Próximas melhorias (futuro)

- [ ] WebSocket para notificações em tempo real
- [ ] Suporte a notificações no móvel (toast)
- [ ] Filtro por tipo de notificação
- [ ] Busca de notificações antigas
- [ ] Deletar notificações
