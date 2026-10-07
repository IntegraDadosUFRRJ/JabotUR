import sys
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.transforms.nome_cientifico import (
    parse_nome_cientifico,
    parse_nome_cientifico_series,
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_OK,
    PARSE_STATUS_MORPHOSPECIES,
)


class NomeCientificoSpTests(unittest.TestCase):
    def test_genus_sp_returns_genus_only(self):
        # Escopo do bug: "sp." e "sp" com espaço final opcional
        names = ["Citrus sp.", "Pinus sp. ", "Eugenia sp"]
        for name in names:
            result = parse_nome_cientifico(name)
            self.assertEqual(result["parse_status"], PARSE_STATUS_GENUS_ONLY)
            self.assertEqual(result["genero"], name.split()[0])
            self.assertIsNone(result["epiteto_especifico"])
            self.assertIsNone(result["infraespecifico"])
            self.assertIsNone(result["autor"])
            self.assertIsNone(result["identification_qualifier"])

    def test_genus_sp_is_identical_to_pure_genus(self):
        # Mesma resposta do construtor de resultado de um gênero-só
        res_sp = parse_nome_cientifico("Citrus sp.")
        res_pure = parse_nome_cientifico("Citrus")
        for k in ["parse_status", "genero", "epiteto_especifico", "infraespecifico", "autor", "identification_qualifier"]:
            self.assertEqual(res_sp[k], res_pure[k])

    def test_series_processing(self):
        # A série processa os mesmos casos
        series = pd.Series(["Citrus sp.", "Pinus sp."])
        df = parse_nome_cientifico_series(series)
        self.assertEqual(len(df), 2)
        self.assertTrue((df["parse_status"] == PARSE_STATUS_GENUS_ONLY).all())
        self.assertListEqual(df["genero"].tolist(), ["Citrus", "Pinus"])

    def test_epithets_starting_with_sp_remain_ok(self):
        # Não pode casar "speciosa" ou "spinosa"
        names = ["Ceiba speciosa", "Jacaratia spinosa"]
        for name in names:
            result = parse_nome_cientifico(name)
            self.assertEqual(result["parse_status"], PARSE_STATUS_OK)
            self.assertIsNotNone(result["epiteto_especifico"])

    def test_normal_binomial_remains_ok(self):
        # Baseline
        result = parse_nome_cientifico("Astronium urundeuva")
        self.assertEqual(result["parse_status"], PARSE_STATUS_OK)
        self.assertEqual(result["genero"], "Astronium")
        self.assertEqual(result["epiteto_especifico"], "urundeuva")

    def test_morphospecies_remains_morphospecies(self):
        # Baseline
        result = parse_nome_cientifico("Morfo-Espécie 1")
        self.assertEqual(result["parse_status"], PARSE_STATUS_MORPHOSPECIES)
        self.assertIsNone(result["genero"])


if __name__ == "__main__":
    unittest.main()
