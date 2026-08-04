"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

A transformação é executada principalmente com DuckDB, aplicando:
  - preenchimento de campos como parcela, amostra e substrato;
  - limpeza e normalização textual em observações;
  - conversão de status de identificação para inteiro;
  - trimming em campos textuais de metadados taxonômicos.
"""

import pandas as pd
import duckdb

try:
    from . import config
    from .db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
except ImportError:  
    import config
    from db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres


def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.STG_SPP_TABLE)


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    working = df.copy()
    if "observacao" not in working.columns and "observacoes" in working.columns:
        working = working.rename(columns={"observacoes": "observacao"})
    if "identificacao" not in working.columns and "status_identificacao" in working.columns:
        working = working.rename(columns={"status_identificacao": "identificacao"})
    con = duckdb.connect()
    con.register("df_input", working)
    return con


def _sql_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _build_observation_expression() -> str:
    expression = "trim(coalesce(observacao, ''))"
    for pattern, replacement in config.OBSERVACAO_REGEX_FIXES:
        expression = (
            f"regexp_replace({expression}, {_sql_literal(pattern)}, {_sql_literal(replacement)})"
        )
    return (
        f"CASE WHEN trim(coalesce(observacao, '')) = '' THEN {_sql_literal(config.OBSERVACAO_NULL_PLACEHOLDER)} "
        f"ELSE trim({expression}) END"
    )


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)

    observation_expr = _build_observation_expression()

    sql = f"""
    CREATE OR REPLACE TEMP TABLE cleaned AS
    WITH numbered AS (
        SELECT row_number() OVER () AS rn, * FROM df_input
    ), filled AS (
        SELECT
            rn,
            last_value(
                CASE
                    WHEN trim(coalesce(parcela, '')) = '' THEN NULL
                    ELSE regexp_replace(regexp_replace(trim(coalesce(parcela, '')), '^\\s+|\\s+$', '', 'g'), '4\\*', '4')
                END IGNORE NULLS
            ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS parcela,
            last_value(
                CASE
                    WHEN trim(coalesce(amostra, '')) = '' THEN NULL
                    ELSE regexp_replace(trim(coalesce(amostra, '')), '^\\s+|\\s+$', '', 'g')
                END IGNORE NULLS
            ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS amostra,
            last_value(
                CASE
                    WHEN trim(coalesce(substrato, '')) = '' THEN NULL
                    ELSE regexp_replace(regexp_replace(trim(coalesce(substrato, '')), '\\s+', ' ', 'g'), '^\\s+|\\s+$', '', 'g')
                END IGNORE NULLS
            ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS substrato,
            last_value(
                CASE
                    WHEN trim(coalesce(forma_vida, '')) = '' THEN NULL
                    ELSE regexp_replace(trim(coalesce(forma_vida, '')), '^\\s+|\\s+$', '', 'g')
                END IGNORE NULLS
            ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS forma_vida,
            {observation_expr} AS observacoes,
            CASE
                WHEN trim(coalesce(identificacao, '')) = '' THEN NULL
                ELSE CAST(trim(coalesce(identificacao, '')) AS INTEGER)
            END AS status_identificacao,
            CASE
                WHEN trim(coalesce(filo, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(filo, '')), '^\\s+|\\s+$', '', 'g')
            END AS filo,
            CASE
                WHEN trim(coalesce(familia, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(familia, '')), '^\\s+|\\s+$', '', 'g')
            END AS familia,
            CASE
                WHEN trim(coalesce(genero, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(genero, '')), '^\\s+|\\s+$', '', 'g')
            END AS genero,
            CASE
                WHEN trim(coalesce(epiteto_especifico, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(epiteto_especifico, '')), '^\\s+|\\s+$', '', 'g')
            END AS especie,
            CASE
                WHEN trim(coalesce(autor, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(autor, '')), '^\\s+|\\s+$', '', 'g')
            END AS autor
        FROM numbered
    )
    SELECT
        parcela,
        amostra,
        substrato,
        forma_vida,
        observacoes,
        status_identificacao,
        filo,
        familia,
        genero,
        especie,
        autor,
        CURRENT_TIMESTAMP AS _cleaned_at
    FROM filled
    """

    con.execute(sql)
    out = con.execute("SELECT * FROM cleaned").df()
    con.close()

    if "parcela" in out.columns:
        out["parcela"] = out["parcela"].replace("", pd.NA)
    if "observacoes" in out.columns:
        out["observacoes"] = out["observacoes"].replace("", pd.NA)

    return out


def load_clean(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.CLN_SPP_TABLE)
    loaded_df = read_dataframe_from_postgres(config.CLN_SPP_TABLE)
    count = len(loaded_df)
    print(f"[clean_spp] {config.CLN_SPP_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    staged = load_staging_df()
    cleaned = transform(staged)
    load_clean(cleaned)