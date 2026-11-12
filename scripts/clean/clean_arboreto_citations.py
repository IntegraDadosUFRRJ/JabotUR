"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

A transformação combina:
  - DuckDB: fill-down de família, trim, cast de quantidade;
  - Python para o parsing do nome científico;
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

UNPARSEABLE_QUANTIDADE = "unparseable_quantidade"
SQL_PATH = Path(__file__).with_name("clean_arboreto_citations.sql")

def load_staging_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(
        config.STG_ARBORETO_CITATIONS_TABLE, order_by=config.ARBORETO_CITATION_STAGING_ORDER
    )


def _staging_order_sql() -> str:
    # _source_row comparado como número: como texto, a linha 10 viria antes da 9
    return ", ".join(
        f"CAST({col} AS INTEGER)" if col == config.SOURCE_ROW_COL else col
        for col in config.ARBORETO_CITATION_STAGING_ORDER
    )


def _to_duckdb_table(df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.register("df_input", df)
    return con


def _fill_down_and_trim(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    # A query e o comentário-resumo dela estão em clean_arboreto_citations.sql; aqui só
    # entram os trechos que vêm do config.py
    sql = SQL_PATH.read_text(encoding="utf-8").format(
        staging_order=_staging_order_sql(),
        family_raw_col=config.ARBORETO_CITATION_COL_FAMILY_RAW,
    )
    return con.execute(sql).df()


def _log_control_sums(out: pd.DataFrame) -> None:
    # Registra, por aba, se a soma de controle da linha de totais conferiu.
    # Só filtra e imprime: a soma e o flag is_total_row vêm da query.
    family_raw = config.ARBORETO_CITATION_COL_FAMILY_RAW
    for (_, sheet), group in out.groupby(["_source_file", "_source_sheet"], sort=False):
        candidates = group[
            (group[family_raw] == "")
            & (group["especie_raw"] == "")
            & group["quantidade"].notna()
        ]
        if candidates.empty:
            print(f"[clean_arboreto_citations] aba '{sheet}': sem linha de totais.")
            continue
        for idx in candidates.index:
            row_number = out.at[idx, "_source_row"]
            found = out.at[idx, "quantidade"]
            expected = out.at[idx, "previous_quantity_sum"]
            if out.at[idx, "is_total_row"]:
                print(
                    f"[clean_arboreto_citations] aba '{sheet}' linha {row_number}: "
                    f"soma de controle conferiu ({found:g} == {expected:g})."
                )
            else:
                print(
                    f"[clean_arboreto_citations] aba '{sheet}' linha {row_number}: "
                    f"soma de controle NÃO conferiu (esperado {expected:g}, achei {found:g}); "
                    f"mantida como {out.at[idx, 'parse_status']}."
                )


def transform(df: pd.DataFrame) -> pd.DataFrame:
    con = _to_duckdb_table(df)
    filled = _fill_down_and_trim(con)
    con.close()

    parsed = parse_scientific_name_series(filled["especie_raw"])
    out = pd.concat([filled.reset_index(drop=True), parsed], axis=1)

    # quantidade (DOUBLE, inválido = NULL) já vem da query
    bad_quantidade = out["quantidade"].isna()
    out.loc[bad_quantidade, "parse_status"] = UNPARSEABLE_QUANTIDADE

    # linha de totais (ADR-0012): o flag is_total_row é calculado na query
    is_total_row = out["is_total_row"].astype(bool)
    out.loc[is_total_row, "parse_status"] = config.PARSE_STATUS_TOTAL_ROW
    _log_control_sums(out)

    # usa "morfo-espécie" como epiteto_especifico e não possui gênero associado
    is_morphospecies = out["parse_status"] == PARSE_STATUS_MORPHOSPECIES
    out.loc[is_morphospecies, "epiteto_especifico"] = out.loc[is_morphospecies, "nome_normalizado"]
    out.loc[is_morphospecies, "genero"] = None

    # "morfo-espécie", "unparseable" (ADR-0003) e "total_row" não reconciliam entre fontes na carga
    # Quando só possui genero(sem epiteto) reconcilia normal
    is_unparseable = out["parse_status"] == PARSE_STATUS_UNPARSEABLE
    out["reconcile_across_sources"] = ~(is_morphospecies | is_total_row | is_unparseable)

    # sinaliza "erros" a serem alterados
    out["needs_review"] = ~out["parse_status"].isin(
        [
            PARSE_STATUS_OK,
            PARSE_STATUS_GENUS_ONLY,
            PARSE_STATUS_MORPHOSPECIES,
            config.PARSE_STATUS_TOTAL_ROW,
        ]
    )

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