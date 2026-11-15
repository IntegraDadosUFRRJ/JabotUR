"""O prepare() do load do SPP entrega ao taxonomy o epíteto sem a abreviação do gênero.

Roda sempre, sem banco: a leitura das tabelas existentes é substituída por mock.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.load import load_spp_bryophytes, taxonomy


def _clean_row(epithet):
    """Uma linha no formato de cln_spp_bryophytes."""
    return {
        "_source_file": "teste.xlsx",
        "_source_row": 2,
        "plot": "1",
        "sample": "1",
        "substrate": None,
        "life_form": None,
        "remarks": None,
        "identification_status": 1,
        "phylum": "M",
        "family": "Pottiaceae",
        "genus": "Barbula",
        "epithet": epithet,
        "author": "Hedw.",
    }


class PrepareEpithetTest(unittest.TestCase):
    def test_taxonomy_receives_epithet_without_genus_abbreviation(self):
        rows = load_spp_bryophytes.prepare([_clean_row("B. indica")])
        con = mock.Mock()
        with mock.patch.object(taxonomy, "_load_existing_rows", return_value=[]):
            genus_dim, genus_by_name = taxonomy.build_genus_rows(con, rows, {}, [])
            _, author_ids = taxonomy.build_author_rows(con, rows)
            species_dim, species_ids = taxonomy.build_species_rows(
                con, rows, genus_by_name, author_ids, genus_dim
            )
        self.assertEqual([row["epithet"] for row in species_dim], ["indica"])
        self.assertEqual(list(species_ids), [("Barbula", "indica", None, "Hedw.")])


if __name__ == "__main__":
    unittest.main()
