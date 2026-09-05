import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config


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

    print(f"Banco '{config.POSTGRES_DB}' pronto para uso.")


if __name__ == "__main__":
    init_postgres()
