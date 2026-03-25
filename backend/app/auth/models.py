import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.crypto import EncryptedString
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relacionamentos
    ml_accounts: Mapped[list["MLAccount"]] = relationship(
        "MLAccount", back_populates="user", cascade="all, delete-orphan"
    )
    products: Mapped[list] = relationship(
        "Product", back_populates="user", cascade="all, delete-orphan"
    )
    listings: Mapped[list] = relationship(
        "Listing", back_populates="user", cascade="all, delete-orphan"
    )
    alert_configs: Mapped[list] = relationship(
        "AlertConfig", back_populates="user", cascade="all, delete-orphan"
    )
    response_templates: Mapped[list] = relationship(
        "ResponseTemplate", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class MLAccount(Base):
    __tablename__ = "ml_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ml_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Tokens armazenados criptografados via Fernet (EncryptedString)
    access_token: Mapped[str | None] = mapped_column(EncryptedString(2000), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(EncryptedString(2000), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="ml_accounts")
    listings: Mapped[list] = relationship(
        "Listing", back_populates="ml_account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MLAccount id={self.id} nickname={self.nickname}>"


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_ml_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", backref="preferences")
    active_ml_account: Mapped["MLAccount | None"] = relationship("MLAccount")

    def __repr__(self) -> str:
        return f"<UserPreference user_id={self.user_id} active_ml_account_id={self.active_ml_account_id}>"
