# Lê `cln_spp_bryophytes` e povoa as tabelas normalizadas finais do schema no PostgreSQL

import scripts.config as config
from scripts.db import db_utils
from scripts.load import taxonomy
import scripts.transforms.phylum as phylum_t
import scripts.transforms.epithet as epithet_t
import scripts.transforms.substrate as substrate_t
import scripts.transforms.remarks as remarks_t

_none_if_nan = taxonomy._none_if_nan
_load_existing_rows = taxonomy._load_existing_rows
_distinct_non_null = taxonomy._distinct_non_null
_merge_ids = taxonomy._merge_ids


def load_clean_rows(con) -> list[dict]:
    # Os ids saem na ordem das linhas lidas; cln_* não tem id, então a ordem vem da planilha
    return db_utils.read_rows(con, config.CLN_SPP_TABLE, order_by=config.SPP_STAGING_ORDER)


def prepare(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    phylum_names = phylum_t.expand([row["phylum"] for row in rows])
    split_epithets = epithet_t.split_epithet([row["epithet"] for row in rows])
    substrates = substrate_t.expand_multivalued([row["substrate"] for row in rows])
    remarks = remarks_t.split_multivalued([row["remarks"] for row in rows])

    out = []
    for row, phylum_name, (clean_epithet, qualifier), substrate_list, remarks_list in zip(
        rows, phylum_names, split_epithets, substrates, remarks
    ):
        out.append({
            **row,
            "phylum_name": phylum_name,
            "clean_epithet": clean_epithet,
            "substrate_list": substrate_list,
            "remarks_list": remarks_list,
            "source_file": row["_source_file"],
            "source_row": row["_source_row"],
            # epithet sem a abreviação do gênero e sem o qualificador, que é a chave lida pelo
            # taxonomy.py; o qualificador é do registro e vai para occurrence (ADR-0006);
            # SPP nunca tem infraespecífico;
            "epithet": clean_epithet,
            "identification_qualifier": qualifier,
            "infraspecific": None,
        })
    return out


def build_life_form(con, rows: list[dict]):
    existing_ids = {row["type"]: row["id"] for row in _load_existing_rows(con, config.TB_LIFE_FORM)}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["life_form"] for row in rows))
    dim = [{"id": i, "type": life_form_type} for life_form_type, i in ids.items()]
    return dim, ids


def build_plot(con, rows: list[dict]):
    existing_ids = {row["code"]: row["id"] for row in _load_existing_rows(con, config.TB_PLOT)}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["plot"] for row in rows))
    dim = [
        {"id": i, "code": code, "coordinate": config.PLOT_COORDINATES.get(str(code))}
        for code, i in ids.items()
    ]
    return dim, ids


def build_identification_status():
    dim = [
        {"id": code, "description": description}
        for code, description in config.IDENTIFICATION_STATUS_DESCRIPTION_MAP.items()
    ]
    ids = {code: code for code in config.IDENTIFICATION_STATUS_DESCRIPTION_MAP}
    return dim, ids


def build_substrate(con, rows: list[dict]):
    abbreviation_by_name = {v: k for k, v in config.SUBSTRATE_NAME_MAP.items()}
    existing_ids = {row["name"]: row["id"] for row in _load_existing_rows(con, config.TB_SUBSTRATE)}
    # sorted() do Python, não ORDER BY do banco: a ordem alfabética decide os ids novos
    names = sorted({name for row in rows for name in row["substrate_list"]})
    ids = _merge_ids(existing_ids, names)
    dim = [{"id": i, "name": name, "abbreviation": abbreviation_by_name.get(name)} for name, i in ids.items()]
    return dim, ids


def build_remark(con, rows: list[dict]):
    existing_ids = {
        row["comment"]: row["id"] for row in _load_existing_rows(con, config.TB_REMARK)
    }
    comments = sorted({c for row in rows for c in row["remarks_list"]})
    ids = _merge_ids(existing_ids, comments)
    dim = [{"id": i, "comment": comment} for comment, i in ids.items()]
    return dim, ids


def build_occurrence(con, rows: list[dict], species_ids: dict, life_form_ids: dict, identification_status_ids: dict, plot_ids: dict):
    existing_keys_to_id = {
        (row["origin_file"], row["origin_row"]): row["id"]
        for row in _load_existing_rows(con, config.TB_OCCURRENCE)
    }
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    occurrence_rows = []
    satellite_rows = []
    for index, row in enumerate(rows):
        # SPP sempre passa infraspecific=None
        species_key = (
            _none_if_nan(row["genus"]),
            _none_if_nan(row["epithet"]),
            _none_if_nan(row["infraspecific"]),
            _none_if_nan(row["author"]),
        )
        id_species = species_ids.get(species_key)
        if id_species is None:
            print(
                f"[load_spp_bryophytes] linha {index} ({row['source_file']}#{row['source_row']}): "
                f"não encontrei epíteto para {species_key!r}, pulando occurrence"
            )
            continue

        natural_key = (row["source_file"], row["source_row"])
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1

        identification_status_code = _none_if_nan(row["identification_status"])
        life_form = _none_if_nan(row["life_form"])
        plot = _none_if_nan(row["plot"])
        sample = _none_if_nan(row["sample"])

        occurrence_rows.append(
            {
                "id": occurrence_id,
                "id_species": id_species,
                "basis_of_record": config.SPP_BASIS_OF_RECORD,
                "origin_file": row["source_file"],
                "origin_row": row["source_row"],
                "identification_qualifier": row["identification_qualifier"],
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_life_form": life_form_ids.get(life_form) if life_form is not None else None,
                "id_identification_status": identification_status_ids.get(int(identification_status_code)) if identification_status_code is not None else None,
                "id_plot": plot_ids.get(plot) if plot is not None else None,
                "sample": int(sample) if sample is not None else None,
            }
        )
    return occurrence_rows, satellite_rows


def build_bridges(rows: list[dict], occurrence_rows: list[dict], substrate_ids: dict, remark_ids: dict):
    occurrence_id_by_key = {(row["origin_file"], row["origin_row"]): row["id"] for row in occurrence_rows}

    # Pares como chaves de dict: o repetido some e fica a ordem da primeira ocorrência
    subs_pairs = {}
    obs_pairs = {}
    for row in rows:
        id_occurrence = occurrence_id_by_key.get((row["source_file"], row["source_row"]))
        if id_occurrence is None:
            continue
        for name in row["substrate_list"]:
            subs_pairs[(id_occurrence, substrate_ids[name])] = None
        for comment in row["remarks_list"]:
            obs_pairs[(id_occurrence, remark_ids[comment])] = None

    subs_rows = [{"id_occurrence": b, "id_substrate": s} for b, s in subs_pairs]
    obs_rows = [{"id_occurrence": b, "id_remark": o} for b, o in obs_pairs]
    return subs_rows, obs_rows


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
        life_form_dim, life_form_ids = build_life_form(con, rows)
        plot_dim, plot_ids = build_plot(con, rows)
        identification_status_dim, identification_status_ids = build_identification_status()
        substrate_dim, substrate_ids = build_substrate(con, rows)
        remark_dim, remark_ids = build_remark(con, rows)

        occurrence_rows, occurrence_bryophyte_rows = build_occurrence(
            con, rows, species_ids, life_form_ids, identification_status_ids, plot_ids
        )
        occurrence_substrate_rows, occurrence_remark_rows = build_bridges(
            rows, occurrence_rows, substrate_ids, remark_ids
        )

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
        upsert_tables = {
            config.TB_PHYLUM: phylum_dim,
            config.TB_FAMILY: family_dim,
            config.TB_GENUS: genus_dim,
            config.TB_AUTHOR: author_dim,
            config.TB_SPECIES: species_dim,
            config.TB_LIFE_FORM: life_form_dim,
            config.TB_PLOT: plot_dim,
            config.TB_IDENTIFICATION_STATUS: identification_status_dim,
            config.TB_SUBSTRATE: substrate_dim,
            config.TB_REMARK: remark_dim,
            config.TB_OCCURRENCE: occurrence_rows,
            config.TB_OCCURRENCE_BRYOPHYTE: occurrence_bryophyte_rows,
        }
        for table_name, table_rows in upsert_tables.items():
            db_utils.upsert_rows(con, table_name, table_rows)
            written.append((table_name, len(table_rows)))

        db_utils.insert_ignore_rows(
            con, config.TB_OCCURRENCE_SUBSTRATE, occurrence_substrate_rows, ["id_occurrence", "id_substrate"]
        )
        written.append((config.TB_OCCURRENCE_SUBSTRATE, len(occurrence_substrate_rows)))
        db_utils.insert_ignore_rows(
            con, config.TB_OCCURRENCE_REMARK, occurrence_remark_rows, ["id_occurrence", "id_remark"]
        )
        written.append((config.TB_OCCURRENCE_REMARK, len(occurrence_remark_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for table_name, total in written:
        print(f"[load_spp_bryophytes] {table_name}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
