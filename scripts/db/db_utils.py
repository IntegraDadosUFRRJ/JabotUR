from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

import scripts.config as config


def get_postgres_url() -> str:
    password = quote_plus(config.POSTGRES_PASSWORD)
    return (
        f"postgresql+psycopg2://{config.POSTGRES_USER}:{password}@"
        f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
    )


def get_connection():
    """Retorna o engine do PostgreSQL usado para persistir as tabelas do pipeline."""
    return create_engine(get_postgres_url(), future=True)


def _none_safe_records(df: pd.DataFrame) -> list[dict]:
    # Converte NaN/NaT/pd.NA para None antes de mandar pro Postgres
    safe = df.astype(object).where(pd.notnull(df), None)
    return safe.to_dict(orient="records")


def _ensure_primary_key(conn, table_name: str, key_columns: list[str]) -> None:
    #Garante que a tabela tenha PK nas colunas certas antes do upsert
    has_pk = conn.execute(
        text(
            "SELECT 1 FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND contype = 'p'"
        ),
        {"table": table_name},
    ).scalar()
    if has_pk:
        return
    pk_cols = ", ".join([f'"{col}"' for col in key_columns])
    conn.execute(text(f'ALTER TABLE "{table_name}" ADD PRIMARY KEY ({pk_cols})'))


def write_dataframe_to_postgres(df: pd.DataFrame, table_name: str, mode : str = "upsert", composite_key: list[str] | None = None) -> None:
    """
    mode="replace": recria a tabela do zero a cada rodada; Usada para Staging e Clean 
    mode="upsert" (default): upsert por coluna "id" (ON CONFLICT DO UPDATE);
    mode="append_composite": tabela associativa sem "id"; Usada para PK composta (ON CONFLICT DO NOTHING)
    """
    if df.empty:
        return

    engine = get_connection()
    with engine.begin() as conn:
        if mode == "replace":
            df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)
            return
 
        if mode not in ("upsert", "append_composite"):
            raise ValueError(f"mode inválido: {mode!r}")
 
        if mode == "append_composite" and not composite_key:
            raise ValueError("mode='append_composite' exige composite_key")
 
        existing = conn.execute(text("SELECT to_regclass(:table)"), {"table": table_name}).scalar()

        # Se for tabela nova: cria e define a PK 
        if existing is None:
            df.to_sql(name=table_name, con=conn, if_exists="fail", index=False)
            if "id" in df.columns:
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD PRIMARY KEY (id)'))
            else:
                pk_cols = ", ".join([f'"{col}"' for col in df.columns])
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD PRIMARY KEY ({pk_cols})'))
            return

        # Se a tabela já existe: upsert 
        if mode == "upsert":
            _ensure_primary_key(conn, table_name, ["id"])
            insert_cols = ", ".join([f'"{col}"' for col in df.columns])
            update_cols = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in df.columns if col != "id"])
            for row in _none_safe_records(df):
                insert_values = [row[col] for col in df.columns]
                values = ", ".join([f":{i}" for i in range(len(insert_values))])
                conn.execute(
                    text(
                        f'INSERT INTO "{table_name}" ({insert_cols}) VALUES ({values}) '
                        f'ON CONFLICT (id) DO UPDATE SET {update_cols}'
                    ),
                    {f"{i}": v for i, v in enumerate(insert_values)},
                )
            return
 
        _ensure_primary_key(conn, table_name, composite_key)
        insert_cols = ", ".join([f'"{col}"' for col in df.columns])
        conflict_cols = ", ".join([f'"{col}"' for col in composite_key])
        for row in _none_safe_records(df):
            insert_values = [row[col] for col in df.columns]
            values = ", ".join([f":{i}" for i in range(len(insert_values))])
            conn.execute(
                text(
                    f'INSERT INTO "{table_name}" ({insert_cols}) VALUES ({values}) '
                    f'ON CONFLICT ({conflict_cols}) DO NOTHING'
                ),
                {f"{i}": v for i, v in enumerate(insert_values)},
            )



def read_dataframe_from_postgres(table_name: str) -> pd.DataFrame:
    engine = get_connection()
    return pd.read_sql_query(f'SELECT * FROM "{table_name}"', con=engine)