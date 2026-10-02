import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.clean import clean_SPP


class CleanSppDuckDBTests(unittest.TestCase):
    def test_transform_normalizes_observations_and_filldown(self) -> None:
        df = pd.DataFrame(
            {
                "parcela": ["4*", None, "5"],
                "amostra": [None, "A1", None],
                "substrato": ["  rocha ", None, "  cimento  "],
                "forma_vida": ["terrestre", None, "epífita"],
                "observacao": ["c/ esp", "acro [fotos]", None],
                "identificacao": ["1", "2", None],
                "filo": [" Bryophyta ", None, "Marchantiophyta"],
                "familia": [None, "Pottiaceae", None],
                "genero": ["Barbula", None, "Riccardia"],
                "epiteto_especifico": ["sp.", None, "latifrons"],
                "autor": ["Hedw.", None, "L."]
            }
        )

        result = clean_SPP.transform(df)

        self.assertEqual(result.loc[0, "parcela"], "4")
        self.assertEqual(result.loc[1, "parcela"], "4")
        self.assertEqual(result.loc[0, "observacoes"], "com esporófito")
        self.assertEqual(result.loc[1, "observacoes"], "acrocárpico")
        self.assertEqual(result.loc[2, "observacoes"], "sem observações registradas")
        self.assertEqual(result.loc[0, "substrato"], "rocha")
        self.assertEqual(result.loc[1, "amostra"], "A1")
        self.assertEqual(result.loc[0, "status_identificacao"], 1)
