"""Get-or-create do taxonomy (build_*_rows): dimensões e ids esperados para uma entrada fixa,
na primeira rodada e com dados já gravados.

Os ids fixos travam a regra de ordem: os existentes mantêm o id e vêm antes, e as chaves novas
entram por primeira aparição. A ordem por id dos existentes vem do read_rows (ORDER BY id).
Roda sempre, sem banco: a leitura das tabelas existentes é substituída por mock.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.load import taxonomy

# Ficus aparece em duas famílias: genus_by_name fica com o id do último par
FIRST_RUN_ROWS = [
    {"phylum_name": None, "family": "Moraceae", "genus": "Ficus", "epithet": "elastica",
     "infraspecific": None, "author": "Roxb."},
    # filo preenchido: na segunda rodada, uma família existente com id_phylum não nulo
    {"phylum_name": "Musgos", "family": "Fabaceae", "genus": "Inga", "epithet": "vera",
     "infraspecific": "affinis", "author": None},
    {"phylum_name": None, "family": "Urticaceae", "genus": "Ficus", "epithet": "sp. [Espécimes#7]",
     "infraspecific": None, "author": None},
    {"phylum_name": None, "family": None, "genus": "Sem familia", "epithet": None,
     "infraspecific": None, "author": "L."},
    {"phylum_name": None, "family": "Moraceae", "genus": None, "epithet": None,
     "infraspecific": None, "author": None},
    {"phylum_name": None, "family": "Moraceae", "genus": "Ficus", "epithet": "elastica",
     "infraspecific": None, "author": "Roxb."},
    # NaN, como os transforms do SPP devolvem para célula vazia, conta como NULL
    {"phylum_name": float("nan"), "family": "Moraceae", "genus": "Ficus", "epithet": "elastica",
     "infraspecific": None, "author": "Roxb."},
]

# Segunda fonte: com filo, chaves repetidas da primeira e chaves novas
SECOND_RUN_ROWS = [
    {"phylum_name": "Musgos", "family": "Bryaceae", "genus": "Bryum", "epithet": "argenteum",
     "infraspecific": None, "author": "Hedw."},
    {"phylum_name": None, "family": "Moraceae", "genus": "Ficus", "epithet": "elastica",
     "infraspecific": None, "author": "Roxb."},
    {"phylum_name": "Hepáticas", "family": "Moraceae", "genus": "Ficus", "epithet": "benjamina",
     "infraspecific": None, "author": "L."},
    {"phylum_name": None, "family": None, "genus": None, "epithet": "solto",
     "infraspecific": None, "author": None},
]

TABLES = [
    config.TB_PHYLUM, config.TB_FAMILY, config.TB_GENUS, config.TB_AUTHOR, config.TB_SPECIES,
]

FIRST_RUN_DIMS = {
    config.TB_PHYLUM: [{"id": 1, "name": "Musgos"}],
    config.TB_FAMILY: [
        {"id": 1, "id_phylum": None, "name": "Moraceae"},
        {"id": 2, "id_phylum": 1, "name": "Fabaceae"},
        {"id": 3, "id_phylum": None, "name": "Urticaceae"},
    ],
    config.TB_GENUS: [
        {"id": 1, "id_family": 1, "name": "Ficus"},
        {"id": 2, "id_family": 2, "name": "Inga"},
        {"id": 3, "id_family": 3, "name": "Ficus"},
        {"id": 4, "id_family": None, "name": "Sem familia"},
    ],
    config.TB_AUTHOR: [{"id": 1, "name": "Roxb."}, {"id": 2, "name": "L."}],
    config.TB_SPECIES: [
        {"id": 1, "id_genus": 3, "id_author": 1, "epithet": "elastica", "infraspecific": None},
        {"id": 2, "id_genus": 2, "id_author": None, "epithet": "vera", "infraspecific": "affinis"},
        {"id": 3, "id_genus": 3, "id_author": None, "epithet": "sp. [Espécimes#7]", "infraspecific": None},
        {"id": 4, "id_genus": 4, "id_author": 2, "epithet": None, "infraspecific": None},
    ],
}

SECOND_RUN_DIMS = {
    config.TB_PHYLUM: [{"id": 1, "name": "Musgos"}, {"id": 2, "name": "Hepáticas"}],
    config.TB_FAMILY: [
        {"id": 1, "id_phylum": None, "name": "Moraceae"},
        {"id": 2, "id_phylum": 1, "name": "Fabaceae"},
        {"id": 3, "id_phylum": None, "name": "Urticaceae"},
        {"id": 4, "id_phylum": 1, "name": "Bryaceae"},
        {"id": 5, "id_phylum": 2, "name": "Moraceae"},
    ],
    # O gênero 1 já gravado passa a apontar para a família 5: family_by_name["Moraceae"]
    # fica com o último id, e a gravação é upsert
    config.TB_GENUS: [
        {"id": 1, "id_family": 5, "name": "Ficus"},
        {"id": 2, "id_family": 2, "name": "Inga"},
        {"id": 3, "id_family": 3, "name": "Ficus"},
        {"id": 4, "id_family": None, "name": "Sem familia"},
        {"id": 5, "id_family": 4, "name": "Bryum"},
    ],
    config.TB_AUTHOR: [{"id": 1, "name": "Roxb."}, {"id": 2, "name": "L."}, {"id": 3, "name": "Hedw."}],
    config.TB_SPECIES: FIRST_RUN_DIMS[config.TB_SPECIES] + [
        {"id": 5, "id_genus": 5, "id_author": 3, "epithet": "argenteum", "infraspecific": None},
        {"id": 6, "id_genus": 3, "id_author": 2, "epithet": "benjamina", "infraspecific": None},
        {"id": 7, "id_genus": None, "id_author": None, "epithet": "solto", "infraspecific": None},
    ],
}

SECOND_RUN_SPECIES_IDS = [
    (("Ficus", "elastica", None, "Roxb."), 1),
    (("Inga", "vera", "affinis", None), 2),
    (("Ficus", "sp. [Espécimes#7]", None, None), 3),
    (("Sem familia", None, None, "L."), 4),
    (("Bryum", "argenteum", None, "Hedw."), 5),
    (("Ficus", "benjamina", None, "L."), 6),
    ((None, "solto", None, None), 7),
]


def _run_rows(rows, existing: dict[str, list[dict]]):
    def fake_load(con, table_name):
        return [dict(row) for row in existing.get(table_name, [])]

    con = mock.Mock()
    with mock.patch.object(taxonomy, "_load_existing_rows", side_effect=fake_load):
        phylum_dim, phylum_ids = taxonomy.build_phylum_rows(con, rows)
        family_dim, family_by_name = taxonomy.build_family_rows(con, rows, phylum_ids, phylum_dim)
        genus_dim, genus_by_name = taxonomy.build_genus_rows(con, rows, family_by_name, family_dim)
        author_dim, author_ids = taxonomy.build_author_rows(con, rows)
        species_dim, species_ids = taxonomy.build_species_rows(
            con, rows, genus_by_name, author_ids, genus_dim
        )
    dims = dict(zip(TABLES, [phylum_dim, family_dim, genus_dim, author_dim, species_dim]))
    maps = [phylum_ids, family_by_name, genus_by_name, author_ids, species_ids]
    return dims, maps


class TaxonomyRowsTest(unittest.TestCase):
    def test_first_run_without_existing_rows(self):
        dims, (phylum_ids, family_by_name, genus_by_name, author_ids, _) = _run_rows(FIRST_RUN_ROWS, existing={})
        self.assertEqual(dims, FIRST_RUN_DIMS)
        # Listas de pares, não dicts: a ordem de inserção também é conferida
        self.assertEqual(list(phylum_ids.items()), [("Musgos", 1)])
        self.assertEqual(list(family_by_name.items()), [("Moraceae", 1), ("Fabaceae", 2), ("Urticaceae", 3)])
        self.assertEqual(list(genus_by_name.items()), [("Ficus", 3), ("Inga", 2), ("Sem familia", 4)])
        self.assertEqual(list(author_ids.items()), [("Roxb.", 1), ("L.", 2)])

    def test_second_source_with_existing_rows(self):
        # As dimensões gravadas pela primeira fonte viram as existentes da segunda
        dims, (_, family_by_name, _, _, species_ids) = _run_rows(SECOND_RUN_ROWS, existing=FIRST_RUN_DIMS)
        self.assertEqual(dims, SECOND_RUN_DIMS)
        self.assertEqual(list(family_by_name.items()), [("Moraceae", 5), ("Fabaceae", 2), ("Urticaceae", 3), ("Bryaceae", 4)])
        self.assertEqual(list(species_ids.items()), SECOND_RUN_SPECIES_IDS)

    def test_homonym_genus_keeps_last_id(self):
        dims, (_, _, genus_by_name, _, _) = _run_rows(FIRST_RUN_ROWS, existing={})
        ficus_ids = [row["id"] for row in dims[config.TB_GENUS] if row["name"] == "Ficus"]
        self.assertEqual(ficus_ids, [1, 3])
        self.assertEqual(genus_by_name["Ficus"], 3)
        # as duas espécies de Ficus apontam para o último gênero Ficus
        ficus_species = [row for row in dims[config.TB_SPECIES] if row["id_genus"] in ficus_ids]
        self.assertEqual({row["id_genus"] for row in ficus_species}, {3})

    def test_none_if_nan(self):
        self.assertIsNone(taxonomy._none_if_nan(None))
        self.assertIsNone(taxonomy._none_if_nan(float("nan")))
        self.assertEqual(taxonomy._none_if_nan(0), 0)
        self.assertEqual(taxonomy._none_if_nan(""), "")
        self.assertEqual(taxonomy._none_if_nan("Ficus"), "Ficus")

    def test_missing_table_reads_as_no_rows(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=LookupError("sem tabela")):
            self.assertEqual(taxonomy._load_existing_rows(mock.Mock(), config.TB_PHYLUM), [])

    def test_other_read_errors_are_not_swallowed(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=RuntimeError("conexão caiu")):
            with self.assertRaises(RuntimeError):
                taxonomy._load_existing_rows(mock.Mock(), config.TB_PHYLUM)


if __name__ == "__main__":
    unittest.main()
