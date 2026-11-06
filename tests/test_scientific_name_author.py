import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.transforms.scientific_name import parse_scientific_name, PARSE_STATUS_OK


class ScientificNameAuthorTests(unittest.TestCase):
    # Regressão da issue #21: autor em nomes sem infraespecífico e "cf." nos
    # caminhos de retorno do parser após o casamento gênero + epíteto

    def test_author_kept_without_infraspecific(self):
        result = parse_scientific_name("Astronium concinnum Schott")
        self.assertEqual(result["parse_status"], PARSE_STATUS_OK)
        self.assertEqual(result["genero"], "Astronium")
        self.assertEqual(result["epiteto_especifico"], "concinnum")
        self.assertIsNone(result["infraespecifico"])
        self.assertEqual(result["autor"], "Schott")
        self.assertIsNone(result["identification_qualifier"])

    def test_cf_fills_qualifier_with_author(self):
        result = parse_scientific_name("Astronium cf. concinnum Schott")
        self.assertEqual(result["identification_qualifier"], "cf.")
        self.assertEqual(result["epiteto_especifico"], "concinnum")
        self.assertEqual(result["autor"], "Schott")

    def test_cf_fills_qualifier_without_author(self):
        # caminho "gênero + epíteto" sem resto: antes perdia o qualifier
        result = parse_scientific_name("Astronium cf. concinnum")
        self.assertEqual(result["identification_qualifier"], "cf.")
        self.assertEqual(result["epiteto_especifico"], "concinnum")
        self.assertIsNone(result["autor"])

    def test_cf_fills_qualifier_with_infraspecific(self):
        result = parse_scientific_name("Inga cf. vera subsp. affinis (DC.) T.D.Penn.")
        self.assertEqual(result["identification_qualifier"], "cf.")
        self.assertEqual(result["infraespecifico"], "subsp. affinis")


if __name__ == "__main__":
    unittest.main()
