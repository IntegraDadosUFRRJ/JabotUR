from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine

try:
    from . import config
except ImportError: 
    import config


def get_postgres_url() -> str:
    password = quote_plus(config.POSTGRES_PASSWORD)
    return (
        f"postgresql+psycopg2://{config.POSTGRES_USER}:{password}@"
        f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
    )


def get_connection():
    """Retorna o engine do PostgreSQL usado para persistir as tabelas do pipeline."""
    return create_engine(get_postgres_url(), future=True)


def write_dataframe_to_postgres(df: pd.DataFrame, table_name: str) -> None:
    engine = get_connection()
    with engine.begin() as conn:
        df.to_sql(name=table_name, con=conn, if_exists="replace", index=False)


def read_dataframe_from_postgres(table_name: str) -> pd.DataFrame:
    engine = get_connection()
    return pd.read_sql_query(f'SELECT * FROM "{table_name}"', con=engine)