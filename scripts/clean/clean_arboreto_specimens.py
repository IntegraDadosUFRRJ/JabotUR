"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Leitura, transformação e gravação acontecem dentro do DuckDB, com o Postgres anexado:
os dados não passam por DataFrame. Mesma divisão de responsabilidade de
clean_arboreto_citations.py:
  - DuckDB (SQL) pro mecânico: trim e normalização pontual de
    familia/setor/descrição/estado reprodutivo, e as flags;
  - Python puro pros dois parsers especializados, chamados pelo SQL como funções
    registradas no DuckDB (scripts.clean.duckdb_parsers): nome científico (transforms.scientific_name, o mesmo
    de citations) e número de registro/lacre (transforms.registration_number,
    exclusivo desta fonte).

Nenhuma linha é descartada -- mesma política de citations: problema vira
coluna (parse_status, registration_status, needs_review), nunca linha
removida ou tabela separada.
"""

from pathlib import Path

import duckdb

from scripts.clean import duckdb_parsers
from scripts.db.db_utils import postgres_duckdb, read_table, replace_table
import scripts.config as config
from scripts.transforms.scientific_name import (
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
)
from scripts.transforms.registration_number import STATUS_UNPARSEABLE as REG_STATUS_UNPARSEABLE

SQL_PATH = Path(__file__).with_name("clean_arboreto_specimens.sql")

OUTPUT_COLUMNS = [
    "_source_file", "_source_sheet", "_source_row",
    "familia", "genero", "epiteto_especifico", "infraespecifico", "autor",
    "identification_qualifier",
    "nome_raw", "nome_normalizado", "parse_status",
    "setor", "descricao_localizacao", "estado_reprodutivo",
    "registration_number", "registration_number_raw", "registration_status",
    "reconcile_across_sources", "needs_review",
]


def create_staging_view(con: duckdb.DuckDBPyConnection) -> None:
    """Expõe o staging, na ordem da planilha, como a view lida pela query do clean."""
    read_table(
        con, config.STG_ARBORETO_SPECIMENS_TABLE, order_by=config.ARBORETO_SPECIMENS_STAGING_ORDER
    ).create_view(config.DUCKDB_STAGING_ALIAS)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _clean_query() -> str:
    # A query e o comentário-resumo dela estão em clean_arboreto_specimens.sql; aqui só
    # entram os nomes das funções registradas no DuckDB e os valores de status
    full = SQL_PATH.read_text(encoding="utf-8").format(
        name_function=duckdb_parsers.SCIENTIFIC_NAME_FUNCTION,
        registration_function=duckdb_parsers.REGISTRATION_NUMBER_FUNCTION,
        status_ok=_sql_literal(PARSE_STATUS_OK),
        status_genus_only=_sql_literal(PARSE_STATUS_GENUS_ONLY),
        status_morphospecies=_sql_literal(PARSE_STATUS_MORPHOSPECIES),
        status_unparseable=_sql_literal(PARSE_STATUS_UNPARSEABLE),
        registration_status_unparseable=_sql_literal(REG_STATUS_UNPARSEABLE),
    )
    columns = ", ".join(OUTPUT_COLUMNS)
    return f"SELECT {columns}, CURRENT_TIMESTAMP AS _cleaned_at FROM ({full}) ORDER BY rn"


def _prepare(con: duckdb.DuckDBPyConnection) -> str:
    """Registra os parsers e devolve a query do clean.

    Comum a transform() e clean_specimens(), para os testes exercitarem o mesmo
    caminho do pipeline.
    """
    duckdb_parsers.register_scientific_name_parser(con)
    duckdb_parsers.register_registration_number_parser(con)
    return _clean_query()


def transform(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
    """Clean dos Espécimes sobre a view config.DUCKDB_STAGING_ALIAS já registrada em con."""
    return con.sql(_prepare(con))


def clean_specimens() -> None:
    with postgres_duckdb() as con:
        create_staging_view(con)
        # Passa o texto da query, e não transform(con): a relação do con.sql() é
        # preguiçosa e não deve ser consumida dentro da transação do replace_table
        replace_table(con, config.CLN_ARBORETO_SPECIMENS_TABLE, _prepare(con))
        count = read_table(con, config.CLN_ARBORETO_SPECIMENS_TABLE).aggregate("count(*)").fetchone()[0]
    print(f"[clean_arboreto_specimens] {config.CLN_ARBORETO_SPECIMENS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    clean_specimens()
