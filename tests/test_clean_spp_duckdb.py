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
                "autor": ["Hedw.", None, "L."],
                # Lineage como o stage_SPP grava; o clean exige _source_file e _source_row
                "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
                "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
                "_source_row": [2, 3, 4],
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

    def test_blank_forma_vida_stays_null(self) -> None:
        # forma de vida é da coleta: a linha em branco não herda a de cima
        df = pd.DataFrame(
            {
                "parcela": ["4", None, None],
                "amostra": ["A1", None, None],
                "substrato": ["rocha", None, None],
                "forma_vida": [" Tufo ", None, "Tapete"],
                "observacao": [None, None, None],
                "identificacao": ["1", "1", "1"],
                "filo": ["Bryophyta", "Bryophyta", "Bryophyta"],
                "familia": ["Pottiaceae", "Pottiaceae", "Pottiaceae"],
                "genero": ["Barbula", "Barbula", "Barbula"],
                "epiteto_especifico": ["indica", "indica", "indica"],
                "autor": ["Hedw.", "Hedw.", "Hedw."],
                "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
                "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
                "_source_row": [2, 3, 4],
            }
        )

        result = clean_SPP.transform(df)

        self.assertEqual(result.loc[0, "forma_vida"], "Tufo")
        self.assertTrue(pd.isna(result.loc[1, "forma_vida"]))
        self.assertEqual(result.loc[2, "forma_vida"], "Tapete")
        # parcela continua com fill-down
        self.assertEqual(result.loc[1, "parcela"], "4")

    def test_shuffled_input_gives_same_clean(self) -> None:
        # o fill-down segue (arquivo, linha), não a ordem em que o staging chega;
        # _source_row em texto cobre a ordem numérica ('10' < '9' como texto)
        df = pd.DataFrame(
            {
                "parcela": ["4", "5", None],
                "amostra": ["A1", None, None],
                "substrato": ["rocha", "cimento", None],
                "forma_vida": ["terrestre", None, None],
                "observacao": [None, None, None],
                "identificacao": ["1", "1", "1"],
                "filo": ["Bryophyta", "Bryophyta", "Bryophyta"],
                "familia": ["Pottiaceae", "Pottiaceae", "Pottiaceae"],
                "genero": ["Barbula", "Barbula", "Barbula"],
                "epiteto_especifico": ["indica", "indica", "indica"],
                "autor": ["Hedw.", "Hedw.", "Hedw."],
                "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
                "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
                "_source_row": ["8", "9", "10"],
            }
        )
        shuffled = df.iloc[[2, 0, 1]].reset_index(drop=True)

        expected = clean_SPP.transform(df).drop(columns="_cleaned_at")
        actual = clean_SPP.transform(shuffled).drop(columns="_cleaned_at")

        pd.testing.assert_frame_equal(expected, actual)
        last = actual[actual["_source_row"] == "10"].iloc[0]
        self.assertEqual(last["parcela"], "5")
        self.assertEqual(last["amostra"], "A1")
        self.assertEqual(last["substrato"], "cimento")
