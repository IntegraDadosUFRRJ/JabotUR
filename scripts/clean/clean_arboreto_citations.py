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
    from scripts.transforms.nome_cientifico import (
        PARSE_STATUS_GENUS_ONLY,
        PARSE_STATUS_MORPHOSPECIES,
        PARSE_STATUS_OK,
        PARSE_STATUS_UNPARSEABLE,
        parse_nome_cientifico_series,
    )
except ImportError:
    from ..transforms.nome_cientifico import (
        PARSE_STATUS_GENUS_ONLY,
        PARSE_STATUS_MORPHOSPECIES,
        PARSE_STATUS_OK,
        PARSE_STATUS_UNPARSEABLE,
        parse_nome_cientifico_series,
    )

UNPARSEABLE_QUANTIDADE = "unparseable_quantidade"

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
    #
    # Resumo da query (CTEs encadeadas, cada passo lê só o anterior):
    #   numbered: numera as linhas do staging (rn);
    #   typed:    guarda a família ORIGINAL (family_raw, antes do fill-down), faz o
    #             fill-down de familia, aplica trim em especie/quantidade e faz o
    #             TRY_CAST da quantidade para DOUBLE (inválido vira NULL);
    #   checked:  quantidade finita; NaN/inf viram NULL. Divergência deliberada do
    #             TRY_CAST puro, que aceita 'nan'/'inf', para manter o mesmo
    #             comportamento do antigo pd.to_numeric(errors="coerce") + isna();
    #   summed:   previous_quantity_sum = soma das quantidades das linhas ANTERIORES
    #             da mesma aba, com ORDER BY explícito por _source_row inteiro
    #             (NULL conta como 0);
    #   SELECT final: is_total_row = família original e espécie vazias, quantidade
    #             preenchida e igual à soma anterior da aba (ADR-0012).
    sql = f"""
    CREATE OR REPLACE TEMP TABLE filled AS
    WITH numbered AS (
        SELECT row_number() OVER () AS rn, * FROM df_input
    ),
    typed AS (
        SELECT
            rn,
            _source_file,
            _source_sheet,
            _source_row,
            trim(coalesce(familia, '')) AS {config.ARBORETO_CITATION_COL_FAMILY_RAW},
            last_value(
                CASE
                    WHEN trim(coalesce(familia, '')) = '' THEN NULL
                    ELSE regexp_replace(trim(coalesce(familia, '')), '^\\s+|\\s+$', '', 'g')
                END IGNORE NULLS
            ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS familia,
            trim(coalesce(especie, '')) AS especie_raw,
            trim(coalesce(quantidade, '')) AS quantidade_raw,
            TRY_CAST(NULLIF(trim(coalesce(quantidade, '')), '') AS DOUBLE) AS quantidade_cast
        FROM numbered
    ),
    checked AS (
        SELECT
            *,
            CASE WHEN isfinite(quantidade_cast) THEN quantidade_cast END AS quantidade
        FROM typed
    ),
    summed AS (
        SELECT
            *,
            coalesce(
                sum(quantidade) OVER (
                    PARTITION BY _source_file, _source_sheet
                    ORDER BY CAST(_source_row AS INTEGER)
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ),
                0
            ) AS previous_quantity_sum
        FROM checked
    )
    SELECT
        rn,
        _source_file,
        _source_sheet,
        _source_row,
        {config.ARBORETO_CITATION_COL_FAMILY_RAW},
        familia,
        especie_raw,
        quantidade_raw,
        quantidade,
        previous_quantity_sum,
        coalesce(
            {config.ARBORETO_CITATION_COL_FAMILY_RAW} = ''
            AND especie_raw = ''
            AND quantidade IS NOT NULL
            AND quantidade = previous_quantity_sum,
            FALSE
        ) AS is_total_row
    FROM summed
    """
    con.execute(sql)
    return con.execute("SELECT * FROM filled ORDER BY rn").df()


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

    parsed = parse_nome_cientifico_series(filled["especie_raw"])
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

    # "morfo-espécie" e "total_row" não reconciliam entre fontes na carga
    # Quando só possui genero(sem epiteto) reconcilia normal
    out["reconcile_across_sources"] = ~(is_morphospecies | is_total_row)

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