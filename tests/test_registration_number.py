import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.transforms.registration_number import (
    STATUS_AMARELO,
    STATUS_AZUL,
    STATUS_NULL,
    STATUS_UNPARSEABLE,
    parse_registration_number,
)


class RegistrationNumberTests(unittest.TestCase):
    def _assert_parsed(self, raw, status, number):
        result = parse_registration_number(raw)
        self.assertEqual(result["registration_status"], status, raw)
        self.assertEqual(result["registration_number"], number, raw)
        self.assertEqual(result["registration_number_raw"], raw)

    def test_bare_number_is_blue(self):
        # ADR-0009: sem prefixo RBRv e sem a palavra AZUL ainda é lacre azul
        self._assert_parsed("0015130", STATUS_AZUL, "LACRE AZUL 0015130")
        self._assert_parsed("  0015130 ", STATUS_AZUL, "LACRE AZUL 0015130")

    def test_labeled_blue(self):
        self._assert_parsed("LACRE AZUL 0015130", STATUS_AZUL, "LACRE AZUL 0015130")
        self._assert_parsed("Lacre azul 0015130", STATUS_AZUL, "LACRE AZUL 0015130")
        self._assert_parsed("AZUL 0015130", STATUS_AZUL, "LACRE AZUL 0015130")

    def test_yellow(self):
        self._assert_parsed("RBRv90000293", STATUS_AMARELO, "RBRv90000293")

    def test_yellow_with_seven_digits(self):
        # a regra do amarelo não fixa a quantidade de dígitos
        self._assert_parsed("RBRv9000285", STATUS_AMARELO, "RBRv9000285")

    def test_both_seals_keep_blue(self):
        self._assert_parsed(
            "RBRv90000293 (LACRE AZUL 0015124)", STATUS_AZUL, "LACRE AZUL 0015124"
        )

    def test_empty_and_na_are_null(self):
        for raw in [None, float("nan"), "", "   ", "NA", "n/a"]:
            result = parse_registration_number(raw)
            self.assertEqual(result["registration_status"], STATUS_NULL, repr(raw))
            self.assertIsNone(result["registration_number"], repr(raw))

    def test_free_text_stays_unparseable(self):
        for raw in ["sem lacre visível", "0015130 ?", "12-34"]:
            self._assert_parsed(raw, STATUS_UNPARSEABLE, None)


if __name__ == "__main__":
    unittest.main()
