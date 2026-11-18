"""
Lê `cln_arboretum_specimens` e povoa:
  - núcleo taxonômico compartilhado com SPP e citations: phylum, family,
    genus, author, species;
  - sector, reproductive_status (dimensões exclusivas desta fonte);
  - occurrence (base, compartilhada) + occurrence_arboretum (satélite);

Arboreto não tem Filo fica NULL.
"""

import scripts.config as config
from scripts.db import db_utils
from scripts.load import taxonomy


def load_clean_rows(con) -> list[dict]:
    # Os ids saem na ordem das linhas lidas; cln_* não tem id, então a ordem vem da planilha
    return db_utils.read_rows(
        con, config.CLN_ARBORETUM_SPECIMENS_TABLE, order_by=config.ARBORETUM_SPECIMENS_SOURCE_ORDER
    )


def prepare(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        source_sheet = row[config.SOURCE_SHEET_COL]
        source_row = row[config.SOURCE_ROW_COL]

        # morfo-espécie e unparseable nunca reconciliam entre fontes (ADR-0003);
        # em unparseable o epíteto é NULL e continua NULL depois do sufixo
        epithet = row["epithet"]
        if not row["reconcile_across_sources"] and epithet is not None:
            epithet = f"{epithet} [{source_sheet}#{source_row}]"

        out.append({
            **row,
            "phylum_name": None,
            "source_file": row[config.SOURCE_FILE_COL],
            "source_sheet": source_sheet,
            "source_row": source_row,
            "epithet": epithet,
        })
    return out


def build_sector(con, rows: list[dict]):
    existing_ids = {row["name"]: row["id"] for row in taxonomy._load_existing_rows(con, config.TB_SECTOR)}
    ids = taxonomy._merge_ids(existing_ids, taxonomy._distinct_non_null(row["sector"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_reproductive_status(con, rows: list[dict]):
    existing_ids = {
        row["name"]: row["id"] for row in taxonomy._load_existing_rows(con, config.TB_REPRODUCTIVE_STATUS)
    }
    ids = taxonomy._merge_ids(existing_ids, taxonomy._distinct_non_null(row["reproductive_status"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_occurrence_specimens(con, rows: list[dict], species_ids: dict, sector_ids: dict, reproductive_status_ids: dict):
    # A occurrence é compartilhada com o SPP: as linhas dele (origin_sheet NULL) entram no
    # mapa e no próximo id, mas nunca casam com a chave de três partes desta fonte
    existing_keys_to_id = {
        (row["origin_file"], row["origin_sheet"], row["origin_row"]): row["id"]
        for row in taxonomy._load_existing_rows(con, config.TB_OCCURRENCE)
    }
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    occurrence_rows = []
    satellite_rows = []
    for index, row in enumerate(rows):
        species_key = (
            taxonomy._none_if_nan(row["genus"]),
            taxonomy._none_if_nan(row["epithet"]),
            taxonomy._none_if_nan(row["infraspecific"]),
            taxonomy._none_if_nan(row["author"]),
        )
        # sem gênero e sem epíteto o taxonomy não cria espécie: a ocorrência
        # entra com id_species NULL; o clean já a marca needs_review
        unidentified = species_key[0] is None and species_key[1] is None
        id_species = species_ids.get(species_key)
        if id_species is None and not unidentified:
            print(
                f"[load_arboretum_specimens] linha {index} "
                f"({row['source_sheet']}#{row['source_row']}): não encontrei "
                f"epíteto para {species_key!r}, pulando occurrence"
            )
            continue

        natural_key = (row["source_file"], row["source_sheet"], row["source_row"])
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1

        reproductive_status = taxonomy._none_if_nan(row["reproductive_status"])
        sector = taxonomy._none_if_nan(row["sector"])

        occurrence_rows.append(
            {
                "id": occurrence_id,
                "id_species": id_species,
                "basis_of_record": config.ARBORETUM_SPECIMENS_BASIS_OF_RECORD,
                "identification_qualifier": row["identification_qualifier"],
                "origin_file": row["source_file"],
                "origin_sheet": row["source_sheet"],
                "origin_row": row["source_row"],
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_reproductive_status": reproductive_status_ids.get(reproductive_status)
                    if reproductive_status is not None else None,
                "id_sector": sector_ids.get(sector) if sector is not None else None,
                "registration_number": taxonomy._none_if_nan(row["registration_number"]),
                "location_description": taxonomy._none_if_nan(row["location_description"]),
                "height_m": None,  # não existe em Espécimes -- só entra com Canteiro C
            }
        )
    return occurrence_rows, satellite_rows


def populate_normalized_tables() -> None:
    # Uma transação para o load inteiro: leitura dos ids existentes e gravação veem o mesmo
    # estado, e um erro no meio desfaz todas as tabelas deste load (os loads anteriores ficam)
    written = []
    with db_utils.postgres_duckdb() as con, db_utils.transaction(con):
        rows = prepare(load_clean_rows(con))

        phylum_dim, phylum_ids = taxonomy.build_phylum_rows(con, rows)
        family_dim, family_by_name = taxonomy.build_family_rows(con, rows, phylum_ids, phylum_dim)
        genus_dim, genus_by_name = taxonomy.build_genus_rows(con, rows, family_by_name, family_dim)
        author_dim, author_ids = taxonomy.build_author_rows(con, rows)
        species_dim, species_ids = taxonomy.build_species_rows(
            con, rows, genus_by_name, author_ids, genus_dim
        )

        sector_dim, sector_ids = build_sector(con, rows)
        reproductive_status_dim, reproductive_status_ids = build_reproductive_status(con, rows)

        occurrence_rows, occurrence_arboretum_rows = build_occurrence_specimens(
            con, rows, species_ids, sector_ids, reproductive_status_ids
        )

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
        upsert_tables = {
            config.TB_PHYLUM: phylum_dim,
            config.TB_FAMILY: family_dim,
            config.TB_GENUS: genus_dim,
            config.TB_AUTHOR: author_dim,
            config.TB_SPECIES: species_dim,
            config.TB_SECTOR: sector_dim,
            config.TB_REPRODUCTIVE_STATUS: reproductive_status_dim,
            config.TB_OCCURRENCE: occurrence_rows,
            config.TB_OCCURRENCE_ARBORETUM: occurrence_arboretum_rows,
        }
        for table_name, table_rows in upsert_tables.items():
            db_utils.upsert_rows(con, table_name, table_rows)
            written.append((table_name, len(table_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for table_name, total in written:
        print(f"[load_arboretum_specimens] {table_name}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
