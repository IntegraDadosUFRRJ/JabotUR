"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

A transformação é executada principalmente com DuckDB, aplicando:
  - preenchimento de campos como parcela, amostra e substrato;
  - limpeza e normalização textual em observações;
  - conversão de status de identificação para inteiro;
  - trimming em campos textuais de metadados taxonômicos.
"""

import pandas as pd
import duckdb

from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
import scripts.config as config



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

    observation_expr = _build_observation_expression()
    order_sql = _staging_order_sql()

    # Numera as linhas de staging na ordem da planilha (arquivo, linha) e aplica fill-down com
    # last_value() IGNORE NULLS em parcela/amostra/substrato, que valem para um bloco de linhas
    # (linhas em branco recebem o último valor, não-nulo, anterior).
    # A ordem vem do ORDER BY, não da entrada: o Postgres devolve as linhas em ordem física.
    # Normaliza (trim + regex) os campos taxonômicos/metadados, converte
    # status_identificacao pra INT e monta a coluna de observações 
    sql = f"""
    CREATE OR REPLACE TEMP TABLE cleaned AS
    WITH numbered AS (
        SELECT row_number() OVER (ORDER BY {order_sql}) AS rn, * FROM df_input
    ), filled AS (
        SELECT
            rn,
            _source_file,
            _source_row,
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
            -- forma de vida é da coleta, não do bloco: sem fill-down, vazio fica NULL
            CASE
                WHEN trim(coalesce(forma_vida, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(forma_vida, '')), '^\\s+|\\s+$', '', 'g')
            END AS forma_vida,
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
        _source_file,
        _source_row,
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
    out = con.execute(f"SELECT * FROM cleaned ORDER BY {order_sql}").df()
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