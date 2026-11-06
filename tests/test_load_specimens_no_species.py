import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.load import load_arboreto_specimens, taxonomy


def _prepared_df(genero, epiteto):
    """Uma linha no formato de saída de prepare()."""
    return pd.DataFrame(
        {
            "genero": [genero],
            "epiteto": [epiteto],
            "infraespecifico": [None],
            "autor": [None],
            "identification_qualifier": [None],
            "source_file": ["teste.xlsx"],
            "source_sheet": ["Espécimes"],
            "source_row": [10],
            "estado_reprodutivo": [None],
            "setor": [None],
            "registration_number": ["RBRv90000293"],
            "descricao_localizacao": [None],
        }
    )


class OccurrenceWithoutSpeciesTest(unittest.TestCase):
    def setUp(self):
        # sem banco: nenhuma ocorrência existente
        patcher = mock.patch.object(taxonomy, "_load_existing", return_value=pd.DataFrame())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_row_without_genus_and_epithet_loads_with_null_species(self):
        occurrence, satellite = load_arboreto_specimens.build_occurrence_specimens(
            _prepared_df(None, None), epiteto_ids={}, sector_ids={}, reproductive_status_ids={}
        )
        self.assertEqual(1, len(occurrence))
        self.assertIsNone(occurrence.loc[0, "id_species"])
        self.assertEqual(1, len(satellite))
        self.assertEqual(occurrence.loc[0, "id"], satellite.loc[0, "id"])
        self.assertEqual("RBRv90000293", satellite.loc[0, "registration_number"])

    def test_row_with_key_not_found_is_still_skipped(self):
        with mock.patch("builtins.print") as fake_print:
            occurrence, satellite = load_arboreto_specimens.build_occurrence_specimens(
                _prepared_df("Inga", "vera"), epiteto_ids={}, sector_ids={}, reproductive_status_ids={}
            )
        self.assertTrue(occurrence.empty)
        self.assertTrue(satellite.empty)
        self.assertIn("não encontrei", fake_print.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
