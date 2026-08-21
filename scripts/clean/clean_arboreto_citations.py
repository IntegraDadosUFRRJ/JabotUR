"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

A transformação combina:
  - DuckDB: fill-down de família, trim, cast de quantidade;
  - Python para o parsing do nome científico;
"""

import pandas as pd
import duckdb

try:
    from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    import scripts.config as config
except ImportError:
    from ..db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from .. import config

try:
    from scripts.transforms.nome_cientifico import parse_nome_cientifico_series
except ImportError:
    from ..transforms.nome_cientifico import parse_nome_cientifico_series


def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.STG_ARBORETO_CITATIONS_TABLE)


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.register("df_input", df)
    return con


def _fill_down_and_trim(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # Numera as linhas de staging para preservar a ordem original e aplica
    # fill-down de familia com last_value() IGNORE NULLS
    # (linhas sem familia recebem o último valor, não-nulo, anterior)
    # Normaliza familia com trim + regex e prepara especie/quantidade como
    # campos *_raw, aplicando trim e substituindo valores nulos por strings vazias
    sql = """
    CREATE OR REPLACE TEMP TABLE filled AS
    WITH numbered AS (
        SELECT row_number() OVER () AS rn, * FROM df_input
    )
    SELECT
        rn,
        _source_file,
        _source_sheet,
        _source_row,
        last_value(
            CASE
                WHEN trim(coalesce(familia, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(familia, '')), '^\\s+|\\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS familia,
        trim(coalesce(especie, '')) AS especie_raw,
        trim(coalesce(quantidade, '')) AS quantidade_raw
    FROM numbered
    """
    con.execute(sql)
    return con.execute("SELECT * FROM filled ORDER BY rn").df()


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)
    filled = _fill_down_and_trim(con)
    con.close()

    parsed = parse_nome_cientifico_series(filled["especie_raw"])
    out = pd.concat([filled.reset_index(drop=True), parsed], axis=1)

    out["quantidade"] = pd.to_numeric(out["quantidade_raw"], errors="coerce")
    bad_quantidade = out["quantidade"].isna()
    out.loc[bad_quantidade, "parse_status"] = "unparseable_quantidade"

    # usa "morfo-espécie" como epiteto_especifico e não possui gênero associado
    is_morphospecies = out["parse_status"] == "morphospecies"
    out.loc[is_morphospecies, "epiteto_especifico"] = out.loc[is_morphospecies, "nome_normalizado"]
    out.loc[is_morphospecies, "genero"] = None

    # "morfo-espécie" não reconcilia entre fontes na carga 
    # Quando só possui genero(sem epiteto) reconcilia normal
    out["reconcile_across_sources"] = ~is_morphospecies

    # sinaliza "erros" a serem alterados
    out["needs_review"] = ~out["parse_status"].isin(["ok", "genus_only", "morphospecies"])

    out["_cleaned_at"] = pd.Timestamp.now(tz="UTC")

    return out[[
        "_source_file", "_source_sheet", "_source_row",
        "familia", "genero", "epiteto_especifico", "infraespecifico", "autor",
        "identification_qualifier",
        "quantidade", "nome_raw", "nome_normalizado",
        "parse_status", "reconcile_across_sources", "needs_review",
        "_cleaned_at",
    ]]


def load_clean(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.CLN_ARBORETO_CITATIONS_TABLE, mode="replace")
    loaded_df = read_dataframe_from_postgres(config.CLN_ARBORETO_CITATIONS_TABLE)
    count = len(loaded_df)
    print(f"[clean_arboreto_citations] {config.CLN_ARBORETO_CITATIONS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    staged = load_staging_df()
    cleaned = transform(staged)
    load_clean(cleaned)