import math
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from urllib.parse import quote_plus

import duckdb
import pandas as pd
from sqlalchemy import Engine, create_engine, text

import scripts.config as config


def get_postgres_url() -> str:
    password = quote_plus(config.POSTGRES_PASSWORD)
    return (
        f"postgresql+psycopg2://{config.POSTGRES_USER}:{password}@"
        f"{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
    )


# Um engine por URL, reaproveitado: cada create_engine() abre um pool próprio, e o
# engine tem referências cíclicas, então só sai da memória pelo coletor de ciclos do
# Python; pools esquecidos se acumulavam até esgotar o max_connections do Postgres.
# A chave é a URL inteira para um teste que troca o POSTGRES_DB receber outro engine.
_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()


def get_connection() -> Engine:
    """Retorna o engine do PostgreSQL usado para persistir as tabelas do pipeline."""
    url = get_postgres_url()
    with _engines_lock:
        engine = _engines.get(url)
        if engine is None:
            engine = create_engine(url, future=True)
            _engines[url] = engine
        return engine


def dispose_connections() -> None:
    """Fecha as conexões de todos os engines guardados (fim do pipeline e dos testes,
    ou antes de uma operação que exige o banco sem conexões abertas)."""
    with _engines_lock:
        for engine in _engines.values():
            engine.dispose()
        _engines.clear()


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

# === Acesso ao Postgres pelo DuckDB ===
# read_dataframe_from_postgres e write_dataframe_to_postgres (pandas) servem ao staging e ao
# clean do Canteiro C; get_connection e dispose_connections, ao init_postgres e ao pipeline.


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


def _column_types(con: duckdb.DuckDBPyConnection, table_name: str) -> dict[str, str]:
    rows = con.execute(
        "SELECT column_name, data_type FROM duckdb_columns() "
        "WHERE database_name = ? AND schema_name = 'public' AND table_name = ? "
        "ORDER BY column_index",
        [config.DUCKDB_POSTGRES_ALIAS, table_name],
    ).fetchall()
    return dict(rows)


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> list[str]:
    return list(_column_types(con, table_name))


def read_table(
    con: duckdb.DuckDBPyConnection, table_name: str, order_by: list[str] | None = None
) -> duckdb.DuckDBPyRelation:
    """Relação DuckDB com a tabela do Postgres; os dados não passam pelo Python.

    Sem order_by, ordena por "id" quando a tabela tem essa coluna, porque sem ORDER BY
    a ordem física muda a cada upsert.
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

    Id repetido na entrada é erro: o ON CONFLICT do DuckDB ficaria em silêncio com a
    primeira das linhas repetidas, e qual delas vale é decisão de dado, não do upsert.
    """
    # A entrada é materializada uma vez no DuckDB: a checagem e a gravação veem as mesmas
    # linhas mesmo se a query tiver CURRENT_TIMESTAMP ou a origem mudar no meio
    staged = "upsert_input"
    con.execute(f"CREATE OR REPLACE TEMP TABLE {staged} AS {query}")
    try:
        _raise_if_duplicated_id(con, staged, table_name)
        columns = [col[0] for col in con.execute(f"SELECT * FROM {staged} LIMIT 0").description]
        _run_in_transaction(con, _upsert_by_id_statement(table_name, staged, columns))
    finally:
        con.execute(f"DROP TABLE IF EXISTS {staged}")


def _raise_if_duplicated_id(con: duckdb.DuckDBPyConnection, staged: str, table_name: str) -> None:
    duplicated = con.execute(
        f"SELECT id FROM {staged} GROUP BY id HAVING count(*) > 1 ORDER BY id LIMIT 10"
    ).fetchall()
    if duplicated:
        ids = ", ".join(str(row[0]) for row in duplicated)
        raise ValueError(f"upsert em {table_name!r} com id repetido na entrada: {ids}")


def _upsert_by_id_statement(table_name: str, staged: str, columns: list[str]) -> str:
    # Só as colunas da entrada são atualizadas; as demais da tabela ficam como estão
    update_cols = ", ".join(
        f"{_quote_identifier(col)} = EXCLUDED.{_quote_identifier(col)}"
        for col in columns if col != "id"
    )
    return (
        f"INSERT INTO {_qualified_table(table_name)} BY NAME (SELECT * FROM {staged}) "
        f"ON CONFLICT (id) DO UPDATE SET {update_cols}"
    )


# === Linhas Python <-> Postgres, para os loads ===
# Os loads calculam os ids em Python (dicionários do get-or-create); estas funções levam
# essas linhas (list[dict]) ao Postgres. Não abrem transação própria: o load envolve todas
# as gravações em transaction() para gravar tudo ou nada.


@contextmanager
def transaction(con: duckdb.DuckDBPyConnection) -> Iterator[None]:
    """BEGIN na entrada, COMMIT na saída e ROLLBACK em erro.

    Dentro do bloco, use só con.execute() (ver _run_in_transaction) e as funções sem
    transação própria (read_rows, upsert_rows, insert_ignore_rows). replace_table e
    upsert_table abrem BEGIN próprio e falham aqui dentro: o DuckDB não aninha transações.
    """
    con.execute("BEGIN")
    try:
        yield
        con.execute("COMMIT")
    except BaseException:
        _rollback_if_open(con)
        raise


def read_rows(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    columns: list[str] | None = None,
    order_by: list[str] | None = None,
) -> list[dict]:
    """Linhas da tabela como dicts {coluna: valor}, para o código Python dos loads.

    columns: só essas colunas (padrão: todas). Ordem: a mesma regra de read_table.
    timestamptz chega como texto: o DuckDB só converte timestamptz para objeto Python
    com o pytz instalado, e o pipeline não depende dele (as colunas _loaded_at e
    _cleaned_at do staging e do clean têm esse tipo). O texto sai no fuso da sessão
    DuckDB, que depende da máquina: serve para ler, não para comparar nem regravar.
    Tabela inexistente é LookupError, para quem lê poder tratar só esse caso.
    """
    types = _column_types(con, table_name)
    if not types:
        raise LookupError(f"tabela {table_name!r} não existe no Postgres")
    selected = list(types) if columns is None else columns
    unknown = [col for col in selected if col not in types]
    if unknown:
        raise ValueError(f"colunas inexistentes em {table_name!r}: {unknown}")
    if order_by is None and "id" in types:
        order_by = ["id"]

    select_list = ", ".join(
        f"CAST({_quote_identifier(col)} AS VARCHAR) AS {_quote_identifier(col)}"
        if types[col] == "TIMESTAMP WITH TIME ZONE" else _quote_identifier(col)
        for col in selected
    )
    query = f"SELECT {select_list} FROM {_qualified_table(table_name)}"
    if order_by:
        query += " ORDER BY " + ", ".join(_quote_identifier(col) for col in order_by)
    result = con.execute(query)
    names = [col[0] for col in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def _drop_staged_after_error(con: duckdb.DuckDBPyConnection, staged: str) -> None:
    # Numa transação que o erro abortou, o DROP também falharia e esconderia o erro
    # original; nesse caso o ROLLBACK de transaction() desfaz a tabela temporária
    with suppress(duckdb.Error):
        con.execute(f"DROP TABLE IF EXISTS {staged}")


def _stage_rows(con: duckdb.DuckDBPyConnection, table_name: str, rows: list[dict], staged: str) -> list[str]:
    # A tabela temporária copia os tipos das colunas de destino (LIMIT 0), para o INSERT no
    # Postgres não depender de inferência de tipo. O valor Python é convertido para o tipo
    # da coluna: texto não numérico numa coluna inteira falha aqui, mas texto numérico
    # passa e float é arredondado; quem chama entrega os valores já no tipo certo
    columns = list(rows[0])
    for row in rows:
        if list(row) != columns:
            raise ValueError(f"linhas para {table_name!r} com colunas diferentes: {list(row)} != {columns}")
        # Numa lista, o DuckDB troca NaN por NULL sem avisar; NaN aqui é um _none_if_nan
        # esquecido, e virar NULL esconderia, por exemplo, uma chave estrangeira faltando
        nan_columns = [col for col, value in row.items() if isinstance(value, float) and math.isnan(value)]
        if nan_columns:
            raise ValueError(f"linhas para {table_name!r} com NaN em {nan_columns}; use None para NULL")
    column_list = ", ".join(_quote_identifier(col) for col in columns)
    con.execute(
        f"CREATE OR REPLACE TEMP TABLE {staged} AS "
        f"SELECT {column_list} FROM {_qualified_table(table_name)} LIMIT 0"
    )
    # unnest com uma lista por coluna: um só INSERT, ~1 ms contra ~81 ms do executemany (236 linhas)
    types = [row[1] for row in con.execute(f"DESCRIBE {staged}").fetchall()]
    unnested = ", ".join(f"unnest(CAST(? AS {col_type}[]))" for col_type in types)
    con.execute(
        f"INSERT INTO {staged} SELECT {unnested}",
        [[row[col] for row in rows] for col in columns],
    )
    return columns


def upsert_rows(con: duckdb.DuckDBPyConnection, table_name: str, rows: list[dict]) -> None:
    """Upsert por "id" das linhas numa tabela que já existe, como upsert_table.

    Id repetido na entrada é erro, com a mesma checagem de upsert_table. Sem linhas, não faz nada.
    """
    if not rows:
        return
    staged = "rows_input"
    try:
        columns = _stage_rows(con, table_name, rows, staged)
        _raise_if_duplicated_id(con, staged, table_name)
        con.execute(_upsert_by_id_statement(table_name, staged, columns))
    except BaseException:
        _drop_staged_after_error(con, staged)
        raise
    con.execute(f"DROP TABLE IF EXISTS {staged}")


def insert_ignore_rows(
    con: duckdb.DuckDBPyConnection, table_name: str, rows: list[dict], key_columns: list[str]
) -> None:
    """Insere as linhas que ainda não existem pela chave key_columns (tabelas associativas).

    Linha já gravada, ou repetida na entrada, é ignorada (ON CONFLICT DO NOTHING); nada é atualizado nem apagado.
    """
    if not rows:
        return
    staged = "rows_input"
    try:
        _stage_rows(con, table_name, rows, staged)
        conflict_cols = ", ".join(_quote_identifier(col) for col in key_columns)
        con.execute(
            f"INSERT INTO {_qualified_table(table_name)} BY NAME (SELECT * FROM {staged}) "
            f"ON CONFLICT ({conflict_cols}) DO NOTHING"
        )
    except BaseException:
        _drop_staged_after_error(con, staged)
        raise
    con.execute(f"DROP TABLE IF EXISTS {staged}")
