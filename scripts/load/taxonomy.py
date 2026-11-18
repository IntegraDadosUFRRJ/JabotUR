"""
Get-or-create compartilhado do núcleo taxonômico (phylum, family, genus,
author, species), sobre linhas (list[dict]) lidas e gravadas pelo DuckDB.

Chaves esperadas em cada linha de entrada:
  phylum_name (pode ser None em todas)
  family
  genus (pode ser None)
  epithet (pode ser None)
  infraspecific (opcional)
  author (pode ser None)

Os ids existentes entram ordenados por id e as chaves novas na ordem de primeira aparição
em `rows`: mudar essa ordem muda os ids gravados.
Os mapas por nome (family_by_name, genus_by_name) ficam com o último id quando o mesmo
nome aparece sob pais diferentes.
"""

import math

try:
    from ..db.db_utils import read_rows
    from .. import config
except ImportError:
    from scripts.db.db_utils import read_rows
    import scripts.config as config


def _none_if_nan(value):
    # NaN do tipo float também é ausência de valor, a mesma regra de transforms.missing.is_missing
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def _merge_ids(existing_keys_to_id: dict, new_keys) -> dict:
    ids = dict(existing_keys_to_id)
    next_id = (max(ids.values()) + 1) if ids else 1
    for key in new_keys:
        if key not in ids:
            ids[key] = next_id
            next_id += 1
    return ids


def _load_existing_rows(con, table_name: str) -> list[dict]:
    # Só a tabela inexistente vira "nenhuma linha": qualquer outro erro sobe, porque
    # engolido dentro da transação do load deixaria a transação abortada
    try:
        return read_rows(con, table_name)
    except LookupError:
        return []


def _distinct_non_null(values) -> list:
    # Sem NULL e na ordem de primeira aparição, que decide os ids novos
    return list(dict.fromkeys(v for v in map(_none_if_nan, values) if v is not None))


def build_phylum_rows(con, rows: list[dict]):
    existing = _load_existing_rows(con, config.TB_PHYLUM)
    existing_ids = {row["name"]: row["id"] for row in existing}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["phylum_name"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_family_rows(con, rows: list[dict], phylum_ids: dict, phylum_dim: list[dict]):
    phylum_id_to_name = {row["id"]: row["name"] for row in phylum_dim}
    existing_keys = {
        (
            _none_if_nan(phylum_id_to_name.get(row["id_phylum"])),
            _none_if_nan(row["name"]),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_FAMILY)
    }
    pairs = [
        (_none_if_nan(row["phylum_name"]), _none_if_nan(row["family"]))
        for row in rows
        if _none_if_nan(row["family"]) is not None
    ]
    ids = _merge_ids(existing_keys, pairs)
    dim = [{"id": i, "id_phylum": phylum_ids.get(phylum_name), "name": name} for (phylum_name, name), i in ids.items()]
    family_by_name = {name: i for (phylum_name, name), i in ids.items()}
    return dim, family_by_name


def build_genus_rows(con, rows: list[dict], family_by_name: dict, family_dim: list[dict]):
    family_id_to_name = {row["id"]: row["name"] for row in family_dim}
    existing_keys = {
        (
            _none_if_nan(family_id_to_name.get(row["id_family"])),
            _none_if_nan(row["name"]),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_GENUS)
    }
    pairs = [
        (_none_if_nan(row["family"]), _none_if_nan(row["genus"]))
        for row in rows
        if _none_if_nan(row["genus"]) is not None
    ]
    ids = _merge_ids(existing_keys, pairs)
    dim = [
        {"id": i, "id_family": family_by_name.get(family_name), "name": name}
        for (family_name, name), i in ids.items()
    ]
    genus_by_name = {name: i for (family_name, name), i in ids.items()}
    return dim, genus_by_name


def build_author_rows(con, rows: list[dict]):
    existing = _load_existing_rows(con, config.TB_AUTHOR)
    existing_ids = {row["name"]: row["id"] for row in existing}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["author"] for row in rows))
    dim = [{"id": i, "name": name} for name, i in ids.items()]
    return dim, ids


def build_species_rows(
    con, rows: list[dict], genus_by_name: dict, author_ids: dict, genus_dim: list[dict]
):
    genus_id_to_name = {row["id"]: row["name"] for row in genus_dim}
    author_id_to_name = {v: k for k, v in author_ids.items()}
    existing_keys = {
        (
            _none_if_nan(genus_id_to_name.get(row["id_genus"])),
            _none_if_nan(row["epithet"]),
            _none_if_nan(row.get("infraspecific")),
            _none_if_nan(author_id_to_name.get(row["id_author"])),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_SPECIES)
    }
    species_keys = [
        (
            _none_if_nan(row["genus"]),
            _none_if_nan(row["epithet"]),
            _none_if_nan(row.get("infraspecific")),
            _none_if_nan(row["author"]),
        )
        for row in rows
        # mantém a linha se tiver gênero ou epíteto (pelo menos)
        if _none_if_nan(row["genus"]) is not None or _none_if_nan(row["epithet"]) is not None
    ]
    ids = _merge_ids(existing_keys, species_keys)
    dim = [
        {
            "id": i,
            "id_genus": genus_by_name.get(genus_name),
            "id_author": author_ids.get(author_name),
            "epithet": epithet,
            "infraspecific": infra_val,
        }
        for (genus_name, epithet, infra_val, author_name), i in ids.items()
    ]
    return dim, ids
