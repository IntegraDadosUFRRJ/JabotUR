"""Parsers registrados como funções no DuckDB (scripts.clean.duckdb_parsers)."""

import sys
import unittest
from pathlib import Path
from unittest import mock

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.clean import duckdb_parsers
from scripts.transforms.registration_number import STATUS_NULL, parse_registration_number
from scripts.transforms.scientific_name import PARSE_STATUS_UNPARSEABLE, parse_scientific_name


class RegisteredParserTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()

    def tearDown(self):
        self.con.close()

    def _call(self, function, value_sql):
        return self.con.execute(f"SELECT {function}({value_sql})").fetchone()[0]

    def test_null_reaches_scientific_name_parser(self):
        duckdb_parsers.register_scientific_name_parser(self.con)
        result = self._call(duckdb_parsers.SCIENTIFIC_NAME_FUNCTION, "NULL")
        self.assertEqual(result["parse_status"], PARSE_STATUS_UNPARSEABLE)

    def test_null_reaches_registration_number_parser(self):
        duckdb_parsers.register_registration_number_parser(self.con)
        result = self._call(duckdb_parsers.REGISTRATION_NUMBER_FUNCTION, "NULL")
        self.assertEqual(result["registration_status"], STATUS_NULL)

    def test_real_parsers_return_the_declared_fields(self):
        # Compara as chaves do próprio parser, não a saída da função registrada (que sempre traz
        # os campos declarados)
        self.assertEqual(
            set(parse_scientific_name("Inga vera Willd.")), set(duckdb_parsers.SCIENTIFIC_NAME_FIELDS)
        )
        self.assertEqual(
            set(parse_registration_number("0015130")), set(duckdb_parsers.REGISTRATION_NUMBER_FIELDS)
        )

    def test_missing_key_is_refused(self):
        with mock.patch.object(duckdb_parsers, "parse_scientific_name", lambda value: {"nome_raw": value}):
            duckdb_parsers.register_scientific_name_parser(self.con)
        with self.assertRaisesRegex(duckdb.Error, "devolveu as chaves"):
            self._call(duckdb_parsers.SCIENTIFIC_NAME_FUNCTION, "'Inga vera'")

    def test_renamed_key_is_refused(self):
        # Mesma quantidade de chaves, uma com outro nome: o STRUCT sozinho aceitaria
        def parser_with_renamed_key(value):
            result = parse_scientific_name(value)
            result["genus"] = result.pop("genero")
            return result

        with mock.patch.object(duckdb_parsers, "parse_scientific_name", parser_with_renamed_key):
            duckdb_parsers.register_scientific_name_parser(self.con)
        with self.assertRaisesRegex(duckdb.Error, "devolveu as chaves"):
            self._call(duckdb_parsers.SCIENTIFIC_NAME_FUNCTION, "'Inga vera Willd.'")

    def test_extra_key_is_refused(self):
        def parser_with_extra_key(value):
            return {**{field: None for field in duckdb_parsers.REGISTRATION_NUMBER_FIELDS}, "extra": value}

        with mock.patch.object(duckdb_parsers, "parse_registration_number", parser_with_extra_key):
            duckdb_parsers.register_registration_number_parser(self.con)
        with self.assertRaisesRegex(duckdb.Error, "devolveu as chaves"):
            self._call(duckdb_parsers.REGISTRATION_NUMBER_FUNCTION, "'0015130'")

    def test_registering_twice_on_same_connection_is_allowed(self):
        duckdb_parsers.register_scientific_name_parser(self.con)
        duckdb_parsers.register_scientific_name_parser(self.con)
        self.assertIsNotNone(self._call(duckdb_parsers.SCIENTIFIC_NAME_FUNCTION, "'Inga vera'"))


if __name__ == "__main__":
    unittest.main()
