"""
Lê `cln_arboreto_specimens` e povoa:
  - núcleo taxonômico compartilhado com SPP e citations: filo, familia,
    genero, autor, epiteto_especifico;
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
        con, config.CLN_ARBORETO_SPECIMENS_TABLE, order_by=config.ARBORETO_SPECIMENS_STAGING_ORDER
    )


def prepare(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        source_sheet = row["_source_sheet"]
        source_row = row["_source_row"]

        # morfo-espécie e unparseable nunca reconciliam entre fontes (ADR-0003);
        # em unparseable o epíteto é NULL e continua NULL depois do sufixo
        epiteto_especifico = row["epiteto_especifico"]
        if not row["reconcile_across_sources"] and epiteto_especifico is not None:
            epiteto_especifico = f"{epiteto_especifico} [{source_sheet}#{source_row}]"

        out.append({
            **row,
            "filo_nome": None,
            "source_file": row["_source_file"],
            "source_sheet": source_sheet,
            "source_row": source_row,
            "epiteto_especifico": epiteto_especifico,
            "epiteto": epiteto_especifico,
        })
    return out


def build_sector(con, rows: list[dict]):
    existing_ids = {row["name"]: row["id"] for row in taxonomy._load_existing_rows(con, config.TB_SECTOR)}
    ids = taxonomy._merge_ids(existing_ids, taxonomy._distinct_non_null(row["setor"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_reproductive_status(con, rows: list[dict]):
    existing_ids = {
        row["name"]: row["id"] for row in taxonomy._load_existing_rows(con, config.TB_REPRODUCTIVE_STATUS)
    }
    ids = taxonomy._merge_ids(existing_ids, taxonomy._distinct_non_null(row["estado_reprodutivo"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_occurrence_specimens(con, rows: list[dict], epiteto_ids: dict, sector_ids: dict, reproductive_status_ids: dict):
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
        chave_especie = (
            taxonomy._none_if_nan(row["genero"]),
            taxonomy._none_if_nan(row["epiteto"]),
            taxonomy._none_if_nan(row["infraespecifico"]),
            taxonomy._none_if_nan(row["autor"]),
        )
        # sem gênero e sem epíteto o taxonomy não cria espécie: a ocorrência
        # entra com id_species NULL; o clean já a marca needs_review
        sem_identificacao = chave_especie[0] is None and chave_especie[1] is None
        id_species = epiteto_ids.get(chave_especie)
        if id_species is None and not sem_identificacao:
            print(
                f"[load_arboreto_specimens] linha {index} "
                f"({row['source_sheet']}#{row['source_row']}): não encontrei "
                f"epíteto para {chave_especie!r}, pulando occurrence"
            )
            continue

        natural_key = (row["source_file"], row["source_sheet"], row["source_row"])
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1

        estado_reprodutivo = taxonomy._none_if_nan(row["estado_reprodutivo"])
        setor = taxonomy._none_if_nan(row["setor"])

        occurrence_rows.append(
            {
                "id": occurrence_id,
                "id_species": id_species,
                "basis_of_record": config.ARBORETO_SPECIMENS_BASIS_OF_RECORD,
                "identification_qualifier": row["identification_qualifier"],
                "origin_file": row["source_file"],
                "origin_sheet": row["source_sheet"],
                "origin_row": row["source_row"],
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_reproductive_status": reproductive_status_ids.get(estado_reprodutivo)
                    if estado_reprodutivo is not None else None,
                "id_sector": sector_ids.get(setor) if setor is not None else None,
                "registration_number": taxonomy._none_if_nan(row["registration_number"]),
                "location_description": taxonomy._none_if_nan(row["descricao_localizacao"]),
                "height_m": None,  # não existe em Espécimes -- só entra com Canteiro C
            }
        )
    return occurrence_rows, satellite_rows


def populate_normalized_tables() -> None:
    # Uma transação para o load inteiro: leitura dos ids existentes e gravação veem o mesmo
    # estado, e um erro no meio desfaz todas as tabelas deste load (os loads anteriores ficam)
    gravadas = []
    with db_utils.postgres_duckdb() as con, db_utils.transaction(con):
        rows = prepare(load_clean_rows(con))

        filo_dim, filo_ids = taxonomy.build_filo_rows(con, rows)
        familia_dim, familia_by_nome = taxonomy.build_familia_rows(con, rows, filo_ids, filo_dim)
        genero_dim, genero_by_nome = taxonomy.build_genero_rows(con, rows, familia_by_nome, familia_dim)
        autor_dim, autor_ids = taxonomy.build_autor_rows(con, rows)
        epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico_rows(
            con, rows, genero_by_nome, autor_ids, genero_dim
        )

        sector_dim, sector_ids = build_sector(con, rows)
        reproductive_status_dim, reproductive_status_ids = build_reproductive_status(con, rows)

        occurrence_rows, occurrence_arboretum_rows = build_occurrence_specimens(
            con, rows, epiteto_ids, sector_ids, reproductive_status_ids
        )

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
        tabelas_upsert = {
            config.TB_FILO: filo_dim,
            config.TB_FAMILIA: familia_dim,
            config.TB_GENERO: genero_dim,
            config.TB_AUTOR: autor_dim,
            config.TB_EPITETO_ESPECIFICO: epiteto_dim,
            config.TB_SECTOR: sector_dim,
            config.TB_REPRODUCTIVE_STATUS: reproductive_status_dim,
            config.TB_OCCURRENCE: occurrence_rows,
            config.TB_OCCURRENCE_ARBORETUM: occurrence_arboretum_rows,
        }
        for nome_tabela, tabela_rows in tabelas_upsert.items():
            db_utils.upsert_rows(con, nome_tabela, tabela_rows)
            gravadas.append((nome_tabela, len(tabela_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for nome_tabela, total in gravadas:
        print(f"[load_arboreto_specimens] {nome_tabela}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
