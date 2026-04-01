# Sistema de Notificações — Backend

## Visão Geral
O frontend espera endpoints de notificações no backend para funcionar. Este documento descreve a arquitetura esperada.

## Modelo de Dados

### Tabela user_notifications
```sql
CREATE TABLE user_notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    type VARCHAR(50),          -- alert, promotion, order, competitor, reputacao, system
    title VARCHAR(255),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    action_url VARCHAR(500) NULL,
    created_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_user_notifications_user_id_is_read 
    ON user_notifications(user_id, is_read, created_at DESC);
```

## Modelos SQLAlchemy

### models.py
```python
from uuid import UUID
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.core.database import Base

class UserNotification(Base):
    __tablename__ = "user_notifications"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)  # alert, promotion, order, competitor, etc
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_notifications_user_id_is_read', 
              'user_id', 'is_read', 'created_at'),
    )
```

### schemas.py
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    is_read: bool
    action_url: Optional[str]
    created_at: datetime
    
    model_config = {"from_attributes": True}

class NotificationCountOut(BaseModel):
    count: int
```

## Endpoints Esperados

### GET /api/v1/notifications/unread
Retorna notificações não lidas do usuário autenticado.

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "alert",
    "title": "Estoque baixo",
    "message": "SKU X tem menos de 10 unidades em estoque",
    "is_read": false,
    "action_url": "/anuncios/mlb123456",
    "created_at": "2026-04-01T10:30:00Z"
  }
]
```

### GET /api/v1/notifications/count
Retorna quantidade de notificações não lidas.

**Response:**
```json
{
  "count": 5
}
```

### GET /api/v1/notifications?limit=50
Retorna todas as notificações (incluindo lidas).

**Query Parameters:**
- `limit` (int, default=50): Número máximo de notificações
- `offset` (int, default=0): Paginação

**Response:**
```json
[
  {
    "id": "...",
    "is_read": true,
    ...
  }
]
```

### POST /api/v1/notifications/{id}/read
Marca uma notificação como lida.

**Response:** 204 No Content

### POST /api/v1/notifications/read-all
Marca todas as notificações como lidas.

**Response:** 204 No Content

## Implementação Sugerida

### router.py
```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.auth.dependencies import get_current_user
from app.users.schemas import UserOut
from . import service, schemas

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/unread", response_model=list[schemas.NotificationOut])
async def get_unread_notifications(
    current_user: UserOut = Depends(get_current_user)
):
    """Retorna notificações não lidas"""
    return await service.get_unread_notifications(current_user.id)

@router.get("/count", response_model=schemas.NotificationCountOut)
async def get_notification_count(
    current_user: UserOut = Depends(get_current_user)
):
    """Retorna contagem de não lidas"""
    count = await service.get_notification_count(current_user.id)
    return {"count": count}

@router.get("", response_model=list[schemas.NotificationOut])
async def get_all_notifications(
    current_user: UserOut = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """Retorna todas as notificações"""
    return await service.get_all_notifications(current_user.id, limit, offset)

@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    current_user: UserOut = Depends(get_current_user),
):
    """Marca como lida"""
    await service.mark_as_read(notification_id, current_user.id)
    return {"ok": True}

@router.post("/read-all")
async def mark_all_as_read(
    current_user: UserOut = Depends(get_current_user),
):
    """Marca todas como lidas"""
    await service.mark_all_as_read(current_user.id)
    return {"ok": True}
```

### service.py
```python
from uuid import UUID
from sqlalchemy import select, update
from app.core.database import async_session_maker
from . import models

async def get_unread_notifications(user_id: UUID, limit: int = 50):
    """Busca notificações não lidas"""
    async with async_session_maker() as session:
        stmt = (
            select(models.UserNotification)
            .where(
                (models.UserNotification.user_id == user_id) &
                (models.UserNotification.is_read == False)
            )
            .order_by(models.UserNotification.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_notification_count(user_id: UUID) -> int:
    """Conta notificações não lidas"""
    async with async_session_maker() as session:
        stmt = (
            select(func.count(models.UserNotification.id))
            .where(
                (models.UserNotification.user_id == user_id) &
                (models.UserNotification.is_read == False)
            )
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

async def mark_as_read(notification_id: UUID, user_id: UUID):
    """Marca notificação como lida"""
    async with async_session_maker() as session:
        stmt = (
            update(models.UserNotification)
            .where(
                (models.UserNotification.id == notification_id) &
                (models.UserNotification.user_id == user_id)
            )
            .values(is_read=True)
        )
        await session.execute(stmt)
        await session.commit()

async def mark_all_as_read(user_id: UUID):
    """Marca todas como lidas"""
    async with async_session_maker() as session:
        stmt = (
            update(models.UserNotification)
            .where(models.UserNotification.user_id == user_id)
            .values(is_read=True)
        )
        await session.execute(stmt)
        await session.commit()
```

## Criando Notificações

Para criar notificações em qualquer parte do backend (durante alertas, pedidos, etc):

```python
from uuid import uuid4
from datetime import datetime
from app.notificacoes.models import UserNotification
from app.core.database import async_session_maker

async def create_notification(
    user_id: UUID,
    type: str,
    title: str,
    message: str,
    action_url: Optional[str] = None,
):
    """Cria uma nova notificação"""
    async with async_session_maker() as session:
        notification = UserNotification(
            id=uuid4(),
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            is_read=False,
            action_url=action_url,
            created_at=datetime.utcnow(),
        )
        session.add(notification)
        await session.commit()
```

## Exemplos de Notificações

### Alerta de estoque baixo
```python
await create_notification(
    user_id=user.id,
    type="alert",
    title="Estoque baixo",
    message="SKU 'Teclado Mecânico' tem apenas 3 unidades em estoque",
    action_url="/produtos/sku123"
)
```

### Novo pedido
```python
await create_notification(
    user_id=user.id,
    type="order",
    title="Novo pedido",
    message="Pedido #MLB987654321 recebido - R$ 150,00",
    action_url="/pedidos/order123"
)
```

### Alerta de concorrente
```python
await create_notification(
    user_id=user.id,
    type="competitor",
    title="Concorrente mudou preço",
    message="UpSeller reduziu preço para R$ 89,90",
    action_url="/concorrencia/competitor123"
)
```

### Alerta de reputação
```python
await create_notification(
    user_id=user.id,
    type="reputacao",
    title="Avaliação recebida",
    message="Cliente avaliou seu atendimento com 5 estrelas",
    action_url="/reputacao"
)
```

## Migrações Alembic

```python
# alembic/versions/xxxx_create_user_notifications.py

def upgrade() -> None:
    op.create_table(
        'user_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('action_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'idx_user_notifications_user_id_is_read',
        'user_notifications',
        ['user_id', 'is_read', 'created_at'],
        unique=False
    )

def downgrade() -> None:
    op.drop_index('idx_user_notifications_user_id_is_read', table_name='user_notifications')
    op.drop_table('user_notifications')
```

## Integração com main.py

No `backend/app/main.py`, adicionar o router:

```python
from app.notificacoes import router as notificacoes_router

app.include_router(notificacoes_router.router)
```

## Testes

```python
# tests/test_notificacoes.py

import pytest
from uuid import uuid4
from app.notificacoes.service import create_notification, get_unread_notifications

@pytest.mark.asyncio
async def test_create_notification():
    user_id = uuid4()
    await create_notification(
        user_id=user_id,
        type="alert",
        title="Test",
        message="Test message",
    )
    notifications = await get_unread_notifications(user_id)
    assert len(notifications) == 1
    assert notifications[0].title == "Test"
```

## Performance

- Índice em `(user_id, is_read, created_at)` para queries rápidas
- Soft-delete pode ser considerado no futuro (adicionar `deleted_at`)
- Limpeza periódica de notificações antigas (> 90 dias) pode ser feita via Celery task
