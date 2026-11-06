import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

import scripts.config as config
from scripts.db.db_utils import get_connection

SCHEMA_SQL_PATH = Path(__file__).with_name("schema.sql")


def apply_schema() -> None:
    """Cria as tabelas finais e os índices únicos no banco alvo (idempotente)."""
    sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    # exec_driver_sql aceita vários comandos e não trata ":nome" como parâmetro,
    # ao contrário de text(); o psycopg2 ainda pode interpretar "%" (o teste
    # garante que o schema.sql não tem nenhum)
    with get_connection().begin() as conn:
        conn.exec_driver_sql(sql)


def init_postgres() -> None:
    engine = create_engine(
        f"postgresql+psycopg2://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}@"
        f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/postgres",
        future=True,
    )

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        existing = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": config.POSTGRES_DB},
        ).scalar()

    if not existing:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f'CREATE DATABASE "{config.POSTGRES_DB}"'))

    apply_schema()
    print(f"Banco '{config.POSTGRES_DB}' pronto para uso.")


if __name__ == "__main__":
    init_postgres()
