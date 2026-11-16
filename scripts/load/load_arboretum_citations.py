# Lê `cln_arboretum_citations` e povoa as tabelas normalizadas finais do schema no PostgreSQL


import scripts.config as config
from scripts.db import db_utils
from scripts.load import taxonomy

_none_if_nan = taxonomy._none_if_nan


def load_clean_rows(con) -> list[dict]:
    # Os ids saem na ordem das linhas lidas; cln_* não tem id, então a ordem vem da planilha
    return db_utils.read_rows(
        con, config.CLN_ARBORETUM_CITATIONS_TABLE, order_by=config.ARBORETUM_CITATION_STAGING_ORDER
    )


def prepare(rows: list[dict]) -> list[dict]:
    out = []
    for clean_index, row in enumerate(rows):
        # clean_index é a posição na leitura do clean, contando as linhas de totais
        # descartadas: é o número que os logs mostram para localizar a linha
        source_sheet = row[config.SOURCE_SHEET_COL]
        source_row = row[config.SOURCE_ROW_COL]

        # linha de totais não gera citação, sai antes do bloco de morfo-espécie
        if row["parse_status"] == config.PARSE_STATUS_TOTAL_ROW:
            print(
                f"[load_arboretum_citations] linha {clean_index} "
                f"({source_sheet}#{source_row}): linha de totais, ignorada"
            )
            continue

        # morfo-espécie e unparseable nunca reconciliam entre fontes (ADR-0003);
        # recebem a origem no nome; epíteto NULL continua NULL
        epithet = row["epithet"]
        if not row["reconcile_across_sources"] and epithet is not None:
            epithet = f"{epithet} [{source_sheet}#{source_row}]"

        out.append({
            **row,
            # arboreto não tem Filo
            "phylum_name": None,
            "source_file": row[config.SOURCE_FILE_COL],
            "source_sheet": source_sheet,
            "source_row": source_row,
            "epithet": epithet,
            "clean_index": clean_index,
        })
    return out


def build_bibliographic_citation(con, rows: list[dict], species_ids: dict) -> list[dict]:
    existing_keys_to_id = {
        (row["origin_file"], row["origin_sheet"], row["origin_row"]): row["id"]
        for row in taxonomy._load_existing_rows(con, config.TB_BIBLIOGRAPHIC_CITATION)
    }
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    citation_rows = []

    for row in rows:
        species_key = tuple(
            _none_if_nan(row[column])
            for column in ("genus", "epithet", "infraspecific", "author")
        )
        id_species = species_ids.get(species_key)

        if id_species is None:
            print(
                f"[load_arboretum_citations] linha {row['clean_index']} "
                f"({row['source_sheet']}#{row['source_row']}): não encontrei "
                f"epíteto para {species_key!r}, pulando citação"
            )
            continue

        natural_key = (row["source_file"], row["source_sheet"], row["source_row"])

        if natural_key in existing_keys_to_id:
            citation_id = existing_keys_to_id[natural_key]
        else:
            citation_id = next_id
            existing_keys_to_id[natural_key] = citation_id
            next_id += 1

        quantity = _none_if_nan(row["quantity"])
        citation_rows.append(
            {
                "id": citation_id,
                "id_species": id_species,
                "source": row["source_sheet"],
                "quantity": int(quantity) if quantity is not None else None,
                "identification_qualifier": row["identification_qualifier"],
                "origin_file": row["source_file"],
                "origin_sheet": row["source_sheet"],
                "origin_row": row["source_row"],
            }
        )

    return citation_rows


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

        citation_rows = build_bibliographic_citation(con, rows, species_ids)

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
        upsert_tables = {
            config.TB_PHYLUM: phylum_dim,
            config.TB_FAMILY: family_dim,
            config.TB_GENUS: genus_dim,
            config.TB_AUTHOR: author_dim,
            config.TB_SPECIES: species_dim,
            config.TB_BIBLIOGRAPHIC_CITATION: citation_rows,
        }
        for table_name, table_rows in upsert_tables.items():
            db_utils.upsert_rows(con, table_name, table_rows)
            written.append((table_name, len(table_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for table_name, total in written:
        print(f"[load_arboretum_citations] {table_name}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
