"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Leitura, transformação e gravação acontecem dentro do DuckDB, com o Postgres anexado:
os dados não passam por DataFrame. A transformação aplica:
  - preenchimento de campos como plot, sample e substrate;
  - limpeza e normalização textual em observações;
  - conversão de status de identificação para inteiro;
  - trimming em campos textuais de metadados taxonômicos.
"""

from pathlib import Path

import duckdb

from scripts.clean import sql_support
from scripts.db.db_utils import postgres_duckdb, read_table, replace_table
import scripts.config as config

SQL_PATH = Path(__file__).with_name("clean_spp_bryophytes.sql")


def create_staging_view(con: duckdb.DuckDBPyConnection) -> None:
    """Expõe o staging, na ordem da planilha, como a view lida pela query do clean."""
    read_table(con, config.STG_SPP_TABLE, order_by=config.SPP_STAGING_ORDER).create_view(
        config.DUCKDB_STAGING_ALIAS
    )


def _build_remark_expression() -> str:
    expression = "trim(coalesce(remark, ''))"
    for pattern, replacement in config.REMARK_REGEX_FIXES:
        expression = (
            f"regexp_replace({expression}, {sql_support.sql_literal(pattern)}, "
            f"{sql_support.sql_literal(replacement)}, 'gi')"
        )
    # Célula vazia é ausência de observação: NULL, não texto de preenchimento
    return (
        f"CASE WHEN trim(coalesce(remark, '')) = '' THEN NULL "
        f"ELSE trim({expression}) END"
    )


def _clean_query() -> str:
    # A query e o comentário-resumo dela estão em clean_spp_bryophytes.sql; aqui só entram os
    # trechos montados a partir de listas do config.py
    return SQL_PATH.read_text(encoding="utf-8").format(
        staging_order=sql_support.staging_order_sql(config.SPP_SOURCE_ORDER),
        remark_expression=_build_remark_expression(),
    )


def transform(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
    """Clean do SPP sobre a view config.DUCKDB_STAGING_ALIAS já registrada em con."""
    return con.sql(_clean_query())


def clean_spp() -> None:
    with postgres_duckdb() as con:
        create_staging_view(con)
        # Passa o texto da query, e não transform(con): a relação do con.sql() é
        # preguiçosa e não deve ser consumida dentro da transação do replace_table
        replace_table(con, config.CLN_SPP_TABLE, _clean_query())
        count = read_table(con, config.CLN_SPP_TABLE).aggregate("count(*)").fetchone()[0]
    print(f"[clean_spp_bryophytes] {config.CLN_SPP_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    clean_spp()
