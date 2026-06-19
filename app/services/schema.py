from __future__ import annotations

from collections import defaultdict

from sqlalchemy import create_engine, text

from app.agent.chains import schema_summary_chain
from app.core.config import Settings
from app.core.llm import build_chat_model


INTROSPECTION_SQL = """
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default
FROM information_schema.columns AS c
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.ordinal_position;
"""

FOREIGN_KEY_SQL = """
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name, kcu.column_name;
"""


def build_postgres_connection_url(*, host: str, port: int, username: str, password: str, database_name: str) -> str:
    return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database_name}"


def fetch_postgres_schema(connection_url: str) -> str:
    engine = create_engine(connection_url, future=True)
    try:
        with engine.connect() as connection:
            column_rows = connection.execute(text(INTROSPECTION_SQL)).mappings().all()
            foreign_key_rows = connection.execute(text(FOREIGN_KEY_SQL)).mappings().all()
    finally:
        engine.dispose()

    tables: dict[str, list[str]] = defaultdict(list)
    for row in column_rows:
        tables[row["table_name"]].append(
            (
                f"- {row['column_name']} ({row['data_type']}, "
                f"nullable={row['is_nullable']}, default={row['column_default']})"
            )
        )

    foreign_keys: dict[str, list[str]] = defaultdict(list)
    for row in foreign_key_rows:
        foreign_keys[row["table_name"]].append(
            f"- {row['column_name']} -> {row['foreign_table_name']}.{row['foreign_column_name']}"
        )

    lines: list[str] = []
    for table_name in sorted(tables):
        lines.append(f"Table: {table_name}")
        lines.extend(tables[table_name])
        if foreign_keys[table_name]:
            lines.append("Foreign keys:")
            lines.extend(foreign_keys[table_name])
        lines.append("")

    return "\n".join(lines).strip()


def generate_schema_summary(
    settings: Settings,
    *,
    schema_text: str,
    provider: str | None = None,
    model_name: str | None = None,
) -> str:
    try:
        llm = build_chat_model(settings, provider=provider, model_name=model_name, temperature=0)
        response = schema_summary_chain(llm, schema_text).invoke({})
        return response.content.strip()
    except Exception:  # noqa: BLE001
        table_count = schema_text.count("Table:")
        preview = "\n".join(schema_text.splitlines()[:12])
        return (
            f"This PostgreSQL database currently exposes {table_count} tables in the public schema. "
            "Use the stored schema snapshot as the source of truth for SQL generation.\n\n"
            f"Schema preview:\n{preview}"
        )
