"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

A transformação é executada principalmente com DuckDB, aplicando:
  - preenchimento de campos como parcela, amostra e substrato;
  - limpeza e normalização textual em observações;
  - conversão de status de identificação para inteiro;
  - trimming em campos textuais de metadados taxonômicos.
"""

from pathlib import Path

import pandas as pd
import duckdb

from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
import scripts.config as config

SQL_PATH = Path(__file__).with_name("clean_SPP.sql")


def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.STG_SPP_TABLE, order_by=config.SPP_STAGING_ORDER)


def _staging_order_sql() -> str:
    # _source_row comparado como número: como texto, a linha 10 viria antes da 9
    return ", ".join(
        f"CAST({col} AS INTEGER)" if col == config.SOURCE_ROW_COL else col
        for col in config.SPP_STAGING_ORDER
    )


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    working = df.copy()
    if config.COL_OBSERVACAO not in working.columns and config.COL_OBSERVACOES in working.columns:
        working = working.rename(columns={config.COL_OBSERVACOES: config.COL_OBSERVACAO})
    if config.COL_IDENTIFICACAO not in working.columns and config.COL_STATUS_IDENTIFICACAO in working.columns:
        working = working.rename(columns={config.COL_STATUS_IDENTIFICACAO: config.COL_IDENTIFICACAO})
    con = duckdb.connect()
    con.register(config.DUCKDB_STAGING_ALIAS, working)
    return con


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


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)

    # A query e o comentário-resumo dela estão em clean_SPP.sql; aqui só entram os
    # trechos montados a partir de listas do config.py
    sql = SQL_PATH.read_text(encoding="utf-8").format(
        staging_order=_staging_order_sql(),
        observation_expression=_build_observation_expression(),
    )

    out = con.execute(sql).df()
    con.close()

    if "parcela" in out.columns:
        out["parcela"] = out["parcela"].replace("", pd.NA)
    if "observacoes" in out.columns:
        out["observacoes"] = out["observacoes"].replace("", pd.NA)

    return out


def load_clean(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.CLN_SPP_TABLE, mode="replace")
    loaded_df = read_dataframe_from_postgres(config.CLN_SPP_TABLE)
    count = len(loaded_df)
    print(f"[clean_spp] {config.CLN_SPP_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    staged = load_staging_df()
    cleaned = transform(staged)
    load_clean(cleaned)