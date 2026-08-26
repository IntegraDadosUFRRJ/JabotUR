"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Mesma divisão de responsabilidade de clean_arboreto_citations.py:
  - DuckDB (SQL) pro mecânico: trim e normalização pontual de
    familia/setor/descrição/estado reprodutivo;
  - Python puro pros dois parsers especializados: nome científico
    (transforms.nome_cientifico, reaproveitado de citations sem
    modificação nenhuma) e número de registro/lacre
    (transforms.registration_number, exclusivo desta fonte).

Nenhuma linha é descartada -- mesma política de citations: problema vira
coluna (parse_status, registration_status, needs_review), nunca linha
removida ou dataframe separado.
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
    from scripts.transforms.registration_number import (
        parse_registration_number_series,
        STATUS_UNPARSEABLE as REG_STATUS_UNPARSEABLE,
    )
except ImportError:
    from ..transforms.nome_cientifico import parse_nome_cientifico_series
    from ..transforms.registration_number import (
        parse_registration_number_series,
        STATUS_UNPARSEABLE as REG_STATUS_UNPARSEABLE,
    )


def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.STG_ARBORETO_SPECIMENS_TABLE)


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.register("df_input", df)
    return con


def _trim_and_normalize(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # Numera as linhas de staging e normaliza os campos mecânicos
    #   - familia: trim; " - " placeholder usado nas linhas "sem identificação" e vira NULL
    #   - setor: trim; normaliza os casos onde a planilha trouxe só o
    #     número solto para o formato de código igual ao resto da coluna
    #   - descricao_localizacao / estado_reprodutivo: trim, string vazia vira NULL
    sql = r"""
    CREATE OR REPLACE TEMP TABLE filled AS
    WITH numbered AS (
        SELECT row_number() OVER () AS rn, * FROM df_input
    )
    SELECT
        rn,
        _source_file,
        _source_sheet,
        _source_row,
        CASE
            WHEN trim(coalesce(familia, '')) IN ('', '-') THEN NULL
            ELSE regexp_replace(trim(coalesce(familia, '')), '^\s+|\s+$', '', 'g')
        END AS familia,
        trim(coalesce(especie, '')) AS especie_raw,
        trim(coalesce(numero_registro, '')) AS numero_registro_raw,
        CASE
            WHEN trim(coalesce(setor, '')) = '' THEN NULL
            WHEN regexp_matches(trim(coalesce(setor, '')), '^[0-9]+\.0$')
                THEN regexp_replace(trim(setor), '\.0$', '')
            ELSE trim(coalesce(setor, ''))
        END AS setor,
        CASE
            WHEN trim(coalesce(descricao_localizacao, '')) = '' THEN NULL
            ELSE trim(coalesce(descricao_localizacao, ''))
        END AS descricao_localizacao,
        CASE
            WHEN trim(coalesce(estado_reprodutivo, '')) = '' THEN NULL
            ELSE trim(coalesce(estado_reprodutivo, ''))
        END AS estado_reprodutivo
    FROM numbered
    """
    con.execute(sql)
    return con.execute("SELECT * FROM filled ORDER BY rn").df()


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)
    filled = _trim_and_normalize(con)
    con.close()

    nome_parsed = parse_nome_cientifico_series(filled["especie_raw"])
    reg_parsed = parse_registration_number_series(filled["numero_registro_raw"])
    out = pd.concat([filled.reset_index(drop=True), nome_parsed, reg_parsed], axis=1)

    # morfo-espécie: mesma convenção de clean_arboreto_citations.py -- não
    # visto nos dados reais de Espécimes ainda, mas mantido por consistência
    # caso apareça numa atualização futura da planilha
    is_morphospecies = out["parse_status"] == "morphospecies"
    out.loc[is_morphospecies, "epiteto_especifico"] = out.loc[is_morphospecies, "nome_normalizado"]
    out.loc[is_morphospecies, "genero"] = None

    out["reconcile_across_sources"] = ~is_morphospecies

    out["needs_review"] = (
        ~out["parse_status"].isin(["ok", "genus_only", "morphospecies"])
        | (out["registration_status"] == REG_STATUS_UNPARSEABLE)
    )

    out["_cleaned_at"] = pd.Timestamp.now(tz="UTC")

    return out[[
        "_source_file", "_source_sheet", "_source_row",
        "familia", "genero", "epiteto_especifico", "infraespecifico", "autor",
        "identification_qualifier",
        "nome_raw", "nome_normalizado", "parse_status",
        "setor", "descricao_localizacao", "estado_reprodutivo",
        "registration_number", "registration_number_raw", "registration_status",
        "reconcile_across_sources", "needs_review",
        "_cleaned_at",
    ]]


def load_clean(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.CLN_ARBORETO_SPECIMENS_TABLE, mode="replace")
    loaded_df = read_dataframe_from_postgres(config.CLN_ARBORETO_SPECIMENS_TABLE)
    count = len(loaded_df)
    print(f"[clean_arboreto_specimens] {config.CLN_ARBORETO_SPECIMENS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    staged = load_staging_df()
    cleaned = transform(staged)
    load_clean(cleaned)
