from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    db_type: Mapped[str] = mapped_column(String(50), default="postgresql")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    database_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schema_record: Mapped["DatabaseSchema"] = relationship(
        "DatabaseSchema",
        back_populates="connection",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="connection")
    query_logs: Mapped[list["QueryLog"]] = relationship("QueryLog", back_populates="connection")


class DatabaseSchema(Base):
    __tablename__ = "database_schemas"
    __table_args__ = (UniqueConstraint("connection_id", name="uq_database_schema_connection_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("database_connections.id"), index=True)
    schema_details: Mapped[str] = mapped_column(Text)
    summary_instructions: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    connection: Mapped[DatabaseConnection] = relationship("DatabaseConnection", back_populates="schema_record")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[str] = mapped_column(String(255), index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("database_connections.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    message_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    connection: Mapped[DatabaseConnection | None] = relationship("DatabaseConnection", back_populates="chat_messages")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[str] = mapped_column(String(255), index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("database_connections.id"), nullable=True, index=True)
    user_query: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(50))
    generated_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthesized_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    connection: Mapped[DatabaseConnection | None] = relationship("DatabaseConnection", back_populates="query_logs")
