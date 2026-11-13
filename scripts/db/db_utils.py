from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote_plus

import duckdb
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



def _has_id_column(conn, table_name: str) -> bool:
    # Filtra pelo schema atual para não achar uma tabela homônima em outro schema
    return conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = :table AND column_name = 'id'"
        ),
        {"table": table_name},
    ).scalar() is not None


def read_dataframe_from_postgres(table_name: str, order_by: list[str] | None = None) -> pd.DataFrame:
    """
    Sem ORDER BY o Postgres devolve as linhas na ordem física, que muda a cada upsert.
    order_by: colunas da ordenação; sem ele, ordena por "id" quando a tabela tem essa coluna
    (tabelas finais), para que quem itera o resultado veja sempre a mesma ordem.
    """
    engine = get_connection()
    with engine.connect() as conn:
        if order_by is None and _has_id_column(conn, table_name):
            order_by = ["id"]
        query = f'SELECT * FROM "{table_name}"'
        if order_by:
            query += " ORDER BY " + ", ".join([f'"{col}"' for col in order_by])
        return pd.read_sql_query(text(query), con=conn)

# --- Acesso ao Postgres pelo DuckDB ---
# Substitui aos poucos as funções acima (pandas + SQLAlchemy), que ficam enquanto
# houver chamador delas (staging, loads, taxonomy.py).


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _libpq_value(value) -> str:
    # Valor de DSN libpq entre aspas simples: aceita espaço e caractere especial na senha
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _postgres_dsn() -> str:
    # lock_timeout vai no DSN, e não num SET, porque o DuckDB abre várias conexões
    # (pool) com o Postgres e todas precisam do limite
    return " ".join([
        f"host={_libpq_value(config.POSTGRES_HOST)}",
        f"port={_libpq_value(config.POSTGRES_PORT)}",
        f"dbname={_libpq_value(config.POSTGRES_DB)}",
        f"user={_libpq_value(config.POSTGRES_USER)}",
        f"password={_libpq_value(config.POSTGRES_PASSWORD)}",
        f"options={_libpq_value(f'-c lock_timeout={config.POSTGRES_LOCK_TIMEOUT}')}",
    ])


def _rollback_if_open(con: duckdb.DuckDBPyConnection) -> None:
    # Só é chamada já tratando um erro: se o ROLLBACK também falhar (sem transação
    # aberta ou conexão caída), o erro que sobe é o original, não o do ROLLBACK
    try:
        con.execute("ROLLBACK")
    except duckdb.Error:
        pass


@contextmanager
def postgres_duckdb() -> Iterator[duckdb.DuckDBPyConnection]:
    """Conexão DuckDB em memória com o Postgres anexado como config.DUCKDB_POSTGRES_ALIAS.

    Na saída, mesmo com erro, desfaz transação aberta e fecha a conexão: uma transação
    esquecida deixa o Postgres preso em lock para as outras conexões.
    """
    con = duckdb.connect()
    try:
        con.execute("LOAD postgres")
        dsn_literal = _postgres_dsn().replace("'", "''")
        con.execute(f"ATTACH '{dsn_literal}' AS {config.DUCKDB_POSTGRES_ALIAS} (TYPE postgres)")
        yield con
    except BaseException:
        _rollback_if_open(con)
        raise
    finally:
        con.close()


def _qualified_table(table_name: str) -> str:
    return f"{config.DUCKDB_POSTGRES_ALIAS}.public.{_quote_identifier(table_name)}"


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    rows = con.execute(
        "SELECT column_name FROM duckdb_columns() "
        "WHERE database_name = ? AND schema_name = 'public' AND table_name = ? "
        "ORDER BY column_index",
        [config.DUCKDB_POSTGRES_ALIAS, table_name],
    ).fetchall()
    return [row[0] for row in rows]


def read_table(
    con: duckdb.DuckDBPyConnection, table_name: str, order_by: list[str] | None = None
) -> duckdb.DuckDBPyRelation:
    """Relação DuckDB com a tabela do Postgres; os dados não passam pelo Python.

    Mesma regra de ordem de read_dataframe_from_postgres: sem order_by, ordena por "id"
    quando a tabela tem essa coluna, porque sem ORDER BY a ordem física muda a cada upsert.
    """
    if order_by is None and "id" in _table_columns(con, table_name):
        order_by = ["id"]
    query = f"SELECT * FROM {_qualified_table(table_name)}"
    if order_by:
        query += " ORDER BY " + ", ".join(_quote_identifier(col) for col in order_by)
    return con.sql(query)


def _run_in_transaction(con: duckdb.DuckDBPyConnection, statement: str) -> None:
    # Só execute(), nunca con.sql() dentro do BEGIN: a relação preguiçosa do con.sql()
    # deixou a transação aberta e travou o Postgres no teste do DuckDB
    con.execute("BEGIN")
    try:
        con.execute(statement)
        con.execute("COMMIT")
    except BaseException:
        _rollback_if_open(con)
        raise


def replace_table(con: duckdb.DuckDBPyConnection, table_name: str, query: str) -> None:
    """Recria a tabela do Postgres com o resultado da query (usado em staging e clean).

    Os tipos vêm da query: texto vira character varying, e soma/contagem viram
    double precision se não houver CAST na query.
    Em erro, o ROLLBACK mantém a tabela anterior intacta.
    """
    _run_in_transaction(
        con, f"CREATE OR REPLACE TABLE {_qualified_table(table_name)} AS {query}"
    )


def upsert_table(con: duckdb.DuckDBPyConnection, table_name: str, query: str) -> None:
    """Upsert por "id" do resultado da query numa tabela que já existe no Postgres.

    O DuckDB resolve o ON CONFLICT localmente e, com id repetido na entrada, ficaria com
    a primeira linha, enquanto write_dataframe_to_postgres fica com a última. Para essa
    diferença não mudar dados em silêncio, id repetido é erro.
    """
    # A entrada é materializada uma vez no DuckDB: a checagem e a gravação veem as mesmas
    # linhas mesmo se a query tiver CURRENT_TIMESTAMP ou a origem mudar no meio
    staged = "upsert_input"
    con.execute(f"CREATE OR REPLACE TEMP TABLE {staged} AS {query}")
    try:
        duplicated = con.execute(
            f"SELECT id FROM {staged} GROUP BY id HAVING count(*) > 1 ORDER BY id LIMIT 10"
        ).fetchall()
        if duplicated:
            ids = ", ".join(str(row[0]) for row in duplicated)
            raise ValueError(f"upsert em {table_name!r} com id repetido na entrada: {ids}")

        columns = [col[0] for col in con.execute(f"SELECT * FROM {staged} LIMIT 0").description]
        update_cols = ", ".join(
            f"{_quote_identifier(col)} = EXCLUDED.{_quote_identifier(col)}"
            for col in columns if col != "id"
        )
        _run_in_transaction(
            con,
            f"INSERT INTO {_qualified_table(table_name)} BY NAME (SELECT * FROM {staged}) "
            f"ON CONFLICT (id) DO UPDATE SET {update_cols}",
        )
    finally:
        con.execute(f"DROP TABLE IF EXISTS {staged}")
