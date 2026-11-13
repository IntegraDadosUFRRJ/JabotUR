"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Leitura, transformação e gravação acontecem dentro do DuckDB, com o Postgres anexado:
os dados não passam por DataFrame. A transformação aplica:
  - preenchimento de campos como parcela, amostra e substrato;
  - limpeza e normalização textual em observações;
  - conversão de status de identificação para inteiro;
  - trimming em campos textuais de metadados taxonômicos.
"""

from pathlib import Path

import duckdb

from scripts.db.db_utils import postgres_duckdb, read_table, replace_table
import scripts.config as config

SQL_PATH = Path(__file__).with_name("clean_SPP.sql")

# Nome alternativo no staging -> nome que a query espera
_INPUT_RENAMES = (
    (config.COL_OBSERVACOES, config.COL_OBSERVACAO),
    (config.COL_STATUS_IDENTIFICACAO, config.COL_IDENTIFICACAO),
)


def create_staging_view(con: duckdb.DuckDBPyConnection) -> None:
    """Expõe o staging, na ordem da planilha, como a view lida pela query do clean."""
    staging = read_table(con, config.STG_SPP_TABLE, order_by=config.SPP_STAGING_ORDER)
    renames = [
        f"{old} AS {new}"
        for old, new in _INPUT_RENAMES
        if new not in staging.columns and old in staging.columns
    ]
    if renames:
        staging = staging.project(f"* RENAME ({', '.join(renames)})")
    staging.create_view(config.DUCKDB_STAGING_ALIAS)


def _staging_order_sql() -> str:
    # _source_row comparado como número: como texto, a linha 10 viria antes da 9
    return ", ".join(
        f"CAST({col} AS INTEGER)" if col == config.SOURCE_ROW_COL else col
        for col in config.SPP_STAGING_ORDER
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_observation_expression() -> str:
    expression = "trim(coalesce(observacao, ''))"
    for pattern, replacement in config.OBSERVACAO_REGEX_FIXES:
        expression = (
            f"regexp_replace({expression}, {_sql_literal(pattern)}, {_sql_literal(replacement)}, 'gi')"
        )
    # Célula vazia é ausência de observação: NULL, não texto de preenchimento
    return (
        f"CASE WHEN trim(coalesce(observacao, '')) = '' THEN NULL "
        f"ELSE trim({expression}) END"
    )


def _clean_query() -> str:
    # A query e o comentário-resumo dela estão em clean_SPP.sql; aqui só entram os
    # trechos montados a partir de listas do config.py
    return SQL_PATH.read_text(encoding="utf-8").format(
        staging_order=_staging_order_sql(),
        observation_expression=_build_observation_expression(),
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
    print(f"[clean_spp] {config.CLN_SPP_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    clean_spp()
