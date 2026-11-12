"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Mesma divisão de responsabilidade de clean_arboreto_citations.py:
  - DuckDB (SQL) pro mecânico: trim e normalização pontual de
    familia/setor/descrição/estado reprodutivo;
  - Python puro pros dois parsers especializados: nome científico
    (transforms.scientific_name, reaproveitado de citations sem
    modificação nenhuma) e número de registro/lacre
    (transforms.registration_number, exclusivo desta fonte).

Nenhuma linha é descartada -- mesma política de citations: problema vira
coluna (parse_status, registration_status, needs_review), nunca linha
removida ou dataframe separado.
"""

from pathlib import Path

import pandas as pd
import duckdb

from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
import scripts.config as config
from scripts.transforms.scientific_name import (
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
    parse_scientific_name_series,
)
from scripts.transforms.registration_number import (
    parse_registration_number_series,
    STATUS_UNPARSEABLE as REG_STATUS_UNPARSEABLE,
)

SQL_PATH = Path(__file__).with_name("clean_arboreto_specimens.sql")


def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(
        config.STG_ARBORETO_SPECIMENS_TABLE, order_by=config.ARBORETO_SPECIMENS_STAGING_ORDER
    )


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.register("df_input", df)
    return con


def _trim_and_normalize(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # A query e o comentário-resumo dela estão em clean_arboreto_specimens.sql; sem
    # trechos dinâmicos, o arquivo é executado como está (sem format)
    return con.execute(SQL_PATH.read_text(encoding="utf-8")).df()


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)
    filled = _trim_and_normalize(con)
    con.close()

    nome_parsed = parse_scientific_name_series(filled["especie_raw"])
    reg_parsed = parse_registration_number_series(filled["numero_registro_raw"])
    out = pd.concat([filled.reset_index(drop=True), nome_parsed, reg_parsed], axis=1)

    # morfo-espécie: mesma convenção de clean_arboreto_citations.py -- não
    # visto nos dados reais de Espécimes ainda, mas mantido por consistência
    # caso apareça numa atualização futura da planilha
    is_morphospecies = out["parse_status"] == PARSE_STATUS_MORPHOSPECIES
    out.loc[is_morphospecies, "epiteto_especifico"] = out.loc[is_morphospecies, "nome_normalizado"]
    out.loc[is_morphospecies, "genero"] = None

    # ADR-0003: morfo-espécie e unparseable nunca reconciliam entre fontes
    is_unparseable = out["parse_status"] == PARSE_STATUS_UNPARSEABLE
    out["reconcile_across_sources"] = ~(is_morphospecies | is_unparseable)

    out["needs_review"] = (
        ~out["parse_status"].isin([PARSE_STATUS_OK, PARSE_STATUS_GENUS_ONLY, PARSE_STATUS_MORPHOSPECIES])
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
