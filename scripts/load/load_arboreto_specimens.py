"""
Lê `cln_arboreto_specimens` e povoa:
  - núcleo taxonômico compartilhado com SPP e citations: filo, familia,
    genero, autor, epiteto_especifico;
  - sector, reproductive_status (dimensões exclusivas desta fonte);
  - occurrence (base, compartilhada) + occurrence_arboretum (satélite);

Arboreto não tem Filo fica NULL.
"""

import pandas as pd

try:
    from .. import config
    from ..db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from . import taxonomy
except ImportError:
    import config
    from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from scripts.load import taxonomy


def load_clean_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.CLN_ARBORETO_SPECIMENS_TABLE)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["filo_nome"] = None

    out["source_file"] = out["_source_file"]
    out["source_sheet"] = out["_source_sheet"]
    out["source_row"] = out["_source_row"]

    # morfo-espécie nunca reconcilia entre fontes
    is_morphospecies = ~out["reconcile_across_sources"]
    out.loc[is_morphospecies, "epiteto_especifico"] = (
        out.loc[is_morphospecies, "epiteto_especifico"]
        + " [" + out.loc[is_morphospecies, "source_sheet"]
        + "#" + out.loc[is_morphospecies, "source_row"].astype(str) + "]"
    )

    out["epiteto"] = out["epiteto_especifico"]
    return out


def build_sector(df: pd.DataFrame):
    existing = taxonomy._load_existing(config.TB_SECTOR)
    existing_ids = dict(zip(existing["name"], existing["id"])) if not existing.empty else {}
    valores = df["setor"].dropna().unique().tolist()
    ids = taxonomy._merge_ids(existing_ids, valores)
    dim = pd.DataFrame({"id": list(ids.values()), "name": list(ids.keys())})
    return dim, ids


def build_reproductive_status(df: pd.DataFrame):
    existing = taxonomy._load_existing(config.TB_REPRODUCTIVE_STATUS)
    existing_ids = dict(zip(existing["name"], existing["id"])) if not existing.empty else {}
    valores = df["estado_reprodutivo"].dropna().unique().tolist()
    ids = taxonomy._merge_ids(existing_ids, valores)
    dim = pd.DataFrame({"id": list(ids.values()), "name": list(ids.keys())})
    return dim, ids


def build_occurrence_specimens(df: pd.DataFrame, epiteto_ids: dict, sector_ids: dict, reproductive_status_ids: dict):
    existing = taxonomy._load_existing(config.TB_OCCURRENCE)
    existing_keys_to_id = {}
    if not existing.empty and "origin_file" in existing.columns and "origin_sheet" in existing.columns:
        for _, row in existing.iterrows():
            existing_keys_to_id[(row["origin_file"], row["origin_sheet"], row["origin_row"])] = row["id"]
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    occurrence_rows = []
    satellite_rows = []
    for row in df.itertuples(index=True):
        chave_especie = (
            taxonomy._none_if_nan(row.genero),
            taxonomy._none_if_nan(row.epiteto),
            taxonomy._none_if_nan(row.infraespecifico),
            taxonomy._none_if_nan(row.autor),
        )
        id_especie = epiteto_ids.get(chave_especie)
        if id_especie is None:
            print(
                f"[load_arboreto_specimens] linha {row.Index} "
                f"({row.source_sheet}#{row.source_row}): não encontrei "
                f"epíteto para {chave_especie!r}, pulando occurrence"
            )
            continue

        natural_key = (row.source_file, row.source_sheet, row.source_row)
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1

        occurrence_rows.append(
            {
                "id": occurrence_id,
                "id_species": id_especie,
                "basis_of_record": config.ARBORETO_SPECIMENS_BASIS_OF_RECORD,
                "identification_qualifier": row.identification_qualifier,
                "origin_file": row.source_file,
                "origin_sheet": row.source_sheet,
                "origin_row": row.source_row,
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_reproductive_status": reproductive_status_ids.get(row.estado_reprodutivo)
                    if pd.notna(row.estado_reprodutivo) else None,
                "id_sector": sector_ids.get(row.setor) if pd.notna(row.setor) else None,
                "registration_number": row.registration_number if pd.notna(row.registration_number) else None,
                "location_description": row.descricao_localizacao if pd.notna(row.descricao_localizacao) else None,
                "height_m": None,  # não existe em Espécimes -- só entra com Canteiro C
            }
        )
    return pd.DataFrame(occurrence_rows), pd.DataFrame(satellite_rows)


def populate_normalized_tables() -> None:
    df = prepare(load_clean_df())

    filo_dim, filo_ids = taxonomy.build_filo(df)
    familia_dim, familia_by_nome = taxonomy.build_familia(df, filo_ids, filo_dim)
    genero_dim, genero_by_nome = taxonomy.build_genero(df, familia_by_nome, familia_dim)
    autor_dim, autor_ids = taxonomy.build_autor(df)
    epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico(df, genero_by_nome, autor_ids, genero_dim)

    sector_dim, sector_ids = build_sector(df)
    reproductive_status_dim, reproductive_status_ids = build_reproductive_status(df)

    occurrence_df, occurrence_arboretum_df = build_occurrence_specimens(
        df, epiteto_ids, sector_ids, reproductive_status_ids
    )

    tabelas_upsert = {
        config.TB_FILO: filo_dim,
        config.TB_FAMILIA: familia_dim,
        config.TB_GENERO: genero_dim,
        config.TB_AUTOR: autor_dim,
        config.TB_EPITETO_ESPECIFICO: epiteto_dim,
        config.TB_SECTOR: sector_dim,
        config.TB_REPRODUCTIVE_STATUS: reproductive_status_dim,
        config.TB_OCCURRENCE: occurrence_df,
        config.TB_OCCURRENCE_ARBORETUM: occurrence_arboretum_df,
    }
    for nome_tabela, tabela_df in tabelas_upsert.items():
        write_dataframe_to_postgres(tabela_df, nome_tabela, mode="upsert")
        print(f"[load_arboreto_specimens] {nome_tabela}: {len(tabela_df)} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()