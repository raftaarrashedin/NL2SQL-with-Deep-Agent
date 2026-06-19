from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.db.models import DatabaseConnection, DatabaseSchema


@dataclass
class ResolvedConnection:
    connection: DatabaseConnection
    schema_record: DatabaseSchema | None

    @property
    def connection_url(self) -> str:
        return str(
            URL.create(
                "postgresql+psycopg2",
                username=self.connection.username,
                password=self.connection.password,
                host=self.connection.host,
                port=self.connection.port,
                database=self.connection.database_name,
            )
        )


def upsert_connection(
    db: Session,
    *,
    name: str,
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    db_type: str,
    schema_details: str,
    summary_instructions: str,
) -> DatabaseConnection:
    existing = db.execute(select(DatabaseConnection).where(DatabaseConnection.name == name)).scalar_one_or_none()

    if existing is None:
        existing = DatabaseConnection(
            name=name,
            host=host,
            port=port,
            username=username,
            password=password,
            database_name=database_name,
            db_type=db_type,
            is_active=True,
        )
        db.add(existing)
        db.flush()
    else:
        existing.host = host
        existing.port = port
        existing.username = username
        existing.password = password
        existing.database_name = database_name
        existing.db_type = db_type
        existing.is_active = True

    if existing.schema_record is None:
        existing.schema_record = DatabaseSchema(
            schema_details=schema_details,
            summary_instructions=summary_instructions,
        )
    else:
        existing.schema_record.schema_details = schema_details
        existing.schema_record.summary_instructions = summary_instructions

    db.commit()
    db.refresh(existing)
    return existing


def get_active_connection(db: Session, connection_id: int) -> ResolvedConnection | None:
    connection = db.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if connection is None:
        return None
    return ResolvedConnection(connection=connection, schema_record=connection.schema_record)


def disconnect_connection(db: Session, connection_id: int) -> DatabaseConnection | None:
    connection = db.execute(select(DatabaseConnection).where(DatabaseConnection.id == connection_id)).scalar_one_or_none()
    if connection is None:
        return None
    connection.is_active = False
    db.commit()
    db.refresh(connection)
    return connection
