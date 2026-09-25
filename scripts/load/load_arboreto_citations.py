# Lê `cln_arboreto_citations` e povoa as tabelas normalizadas finais do schema no PostgreSQL


import pandas as pd

import scripts.config as config
from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
from scripts.load import taxonomy


def load_clean_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.CLN_ARBORETO_CITATIONS_TABLE)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # arboreto não tem Filo
    out["filo_nome"] = None
    out["source_file"] = out["_source_file"]
    out["source_sheet"] = out["_source_sheet"]
    out["source_row"] = out["_source_row"]

    # morfo-espécie recebe a origem no nome
    is_morphospecies = ~out["reconcile_across_sources"]
    out.loc[is_morphospecies, "epiteto_especifico"] = (
        out.loc[is_morphospecies, "epiteto_especifico"]
        + " [" + out.loc[is_morphospecies, "source_sheet"]
        + "#" + out.loc[is_morphospecies, "source_row"].astype(str) + "]"
    )

    out["epiteto"] = out["epiteto_especifico"]
    return out

def build_bibliographic_citation(df: pd.DataFrame, epiteto_ids: dict) -> pd.DataFrame:
    existing = taxonomy._load_existing(config.TB_BIBLIOGRAPHIC_CITATION)
    existing_keys_to_id = {}

    if not existing.empty and "origin_file" in existing.columns:
        for _, row in existing.iterrows():
            existing_keys_to_id[
                (row["origin_file"], row["origin_sheet"], row["origin_row"])
            ] = row["id"]

    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    rows = []

    for row in df.itertuples(index=True):
        chave_especie = tuple(
            taxonomy._none_if_nan(value)
            for value in (
                row.genero,
                row.epiteto,
                row.infraespecifico,
                row.autor,
            )
        )

        id_especie = epiteto_ids.get(chave_especie)

        if id_especie is None:
            print(
                f"[load_arboreto_citations] linha {row.Index} "
                f"({row.source_sheet}#{row.source_row}): não encontrei "
                f"epíteto para {chave_especie!r}, pulando citação"
            )
            continue

        natural_key = (row.source_file, row.source_sheet, row.source_row)

        if natural_key in existing_keys_to_id:
            citation_id = existing_keys_to_id[natural_key]
        else:
            citation_id = next_id
            existing_keys_to_id[natural_key] = citation_id
            next_id += 1

        rows.append(
            {
                "id": citation_id,
                "id_species": id_especie,
                "source": row.source_sheet,
                "quantity": int(row.quantidade) if pd.notna(row.quantidade) else None,
                "identification_qualifier": row.identification_qualifier,
                "origin_file": row.source_file,
                "origin_sheet": row.source_sheet,
                "origin_row": row.source_row,
            }
        )

    return pd.DataFrame(rows)


def populate_normalized_tables() -> None:
    df = prepare(load_clean_df())

    filo_dim, filo_ids = taxonomy.build_filo(df)
    familia_dim, familia_by_nome = taxonomy.build_familia(df, filo_ids, filo_dim)
    genero_dim, genero_by_nome = taxonomy.build_genero(df, familia_by_nome, familia_dim)
    autor_dim, autor_ids = taxonomy.build_autor(df)
    epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico(df, genero_by_nome, autor_ids, genero_dim)

    citation_df = build_bibliographic_citation(df, epiteto_ids)

    tabelas_upsert = {
        config.TB_FILO: filo_dim,
        config.TB_FAMILIA: familia_dim,
        config.TB_GENERO: genero_dim,
        config.TB_AUTOR: autor_dim,
        config.TB_EPITETO_ESPECIFICO: epiteto_dim,
        config.TB_BIBLIOGRAPHIC_CITATION: citation_df,
    }
    for nome_tabela, tabela_df in tabelas_upsert.items():
        write_dataframe_to_postgres(tabela_df, nome_tabela, mode="upsert")
        print(f"[load_arboreto_citations] {nome_tabela}: {len(tabela_df)} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()