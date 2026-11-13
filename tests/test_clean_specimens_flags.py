import sys
import unittest
from pathlib import Path

from unittest import mock

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.clean import clean_arboreto_specimens, duckdb_parsers
from scripts.load import load_arboreto_specimens
from scripts.transforms.scientific_name import (
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
)
from scripts.transforms.registration_number import STATUS_AZUL, STATUS_UNPARSEABLE


def _staging_df():
    """Linhas no formato do staging (tudo texto, como vem do Postgres), fora de ordem."""
    rows = [
        # (_source_row, especie, numero_registro)
        ("10", "sem identificação", "RBRv90000293"),
        ("2", "Astronium concinnum Schott", "0015130"),
        ("3", "Morfo-Espécie 1", "LACRE AZUL 0015131"),
        ("4", "Inga vera Willd.", "lacre ilegível"),
    ]
    return pd.DataFrame(
        {
            "_source_file": "teste.xlsx",
            "_source_sheet": "Espécimes",
            "_source_row": [r[0] for r in rows],
            "familia": "Fabaceae",
            "especie": [r[1] for r in rows],
            "numero_registro": [r[2] for r in rows],
            "setor": None,
            "descricao_localizacao": None,
            "estado_reprodutivo": None,
        }
    )


def _transform(df):
    # Registra o DataFrame no lugar da view do staging, que no pipeline vem do Postgres
    con = duckdb.connect()
    try:
        con.register(config.DUCKDB_STAGING_ALIAS, df)
        return clean_arboreto_specimens.transform(con).df()
    finally:
        con.close()


def _transform_rows(df):
    """Saída do clean como as linhas que o load lê com db_utils.read_rows
    (timestamptz como texto, porque o pytz não está instalado)."""
    con = duckdb.connect()
    try:
        con.register(config.DUCKDB_STAGING_ALIAS, df)
        result = clean_arboreto_specimens.transform(con)
        select = ", ".join(
            f'CAST("{col}" AS VARCHAR) AS "{col}"' if str(col_type) == "TIMESTAMP WITH TIME ZONE" else f'"{col}"'
            for col, col_type in zip(result.columns, result.types)
        )
        projected = result.project(select)
        return [dict(zip(projected.columns, row)) for row in projected.fetchall()]
    finally:
        con.close()


class CleanSpecimensFlagsTests(unittest.TestCase):
    def setUp(self):
        out = _transform(_staging_df())
        self.by_row = out.set_index("_source_row")
        self.out = out

    def test_rows_are_numbered_by_numeric_source_row(self):
        # sem o CAST, "10" ordenaria antes de "2"
        self.assertEqual(self.out["_source_row"].tolist(), ["2", "3", "4", "10"])

    def test_no_row_is_dropped(self):
        self.assertEqual(len(self.out), len(_staging_df()))

    def test_unparseable_does_not_reconcile_and_needs_review(self):
        row = self.by_row.loc["10"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_UNPARSEABLE)
        self.assertFalse(row["reconcile_across_sources"])
        self.assertTrue(row["needs_review"])

    def test_morphospecies_does_not_reconcile_and_needs_no_review(self):
        row = self.by_row.loc["3"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_MORPHOSPECIES)
        self.assertFalse(row["reconcile_across_sources"])
        self.assertFalse(row["needs_review"])

    def test_ok_reconciles(self):
        row = self.by_row.loc["2"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_OK)
        self.assertTrue(row["reconcile_across_sources"])
        self.assertFalse(row["needs_review"])

    def test_bare_registration_number_is_blue(self):
        row = self.by_row.loc["2"]
        self.assertEqual(row["registration_status"], STATUS_AZUL)
        self.assertEqual(row["registration_number"], "LACRE AZUL 0015130")

    def test_unparseable_registration_needs_review(self):
        row = self.by_row.loc["4"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_OK)
        self.assertEqual(row["registration_status"], STATUS_UNPARSEABLE)
        self.assertTrue(row["needs_review"])

    def test_load_prepare_keeps_unparseable_epithet_null(self):
        # reconcile_across_sources=False em unparseable não muda a carga:
        # prepare() só anexa [aba#linha] ao epíteto, que aqui é NULL
        prepared = {
            row["_source_row"]: row for row in load_arboreto_specimens.prepare(_transform_rows(_staging_df()))
        }
        self.assertIsNone(prepared["10"]["epiteto"])
        self.assertIsNone(prepared["10"]["genero"])
        self.assertEqual(prepared["3"]["epiteto"], "Morfo-Espécie 1 [Espécimes#3]")
        self.assertEqual(prepared["2"]["epiteto"], "concinnum")


class RegisteredParserTests(unittest.TestCase):
    """Uma exceção num dos dois parsers registrados no DuckDB interrompe o clean."""

    def _assert_parser_failure_stops_clean(self, parser_name, parser, message):
        with mock.patch.object(duckdb_parsers, parser_name, parser):
            with self.assertRaisesRegex(duckdb.Error, message):
                _transform(_staging_df())

    def test_scientific_name_exception_stops_clean(self):
        def broken_parser(_):
            raise ValueError("parser quebrou")

        self._assert_parser_failure_stops_clean("parse_scientific_name", broken_parser, "parser quebrou")

    def test_registration_number_exception_stops_clean(self):
        def broken_parser(_):
            raise ValueError("parser quebrou")

        self._assert_parser_failure_stops_clean(
            "parse_registration_number", broken_parser, "parser quebrou"
        )

    def test_registration_return_outside_declared_struct_is_refused(self):
        self._assert_parser_failure_stops_clean(
            "parse_registration_number",
            lambda value: {"registration_number_raw": value},
            "devolveu as chaves",
        )


if __name__ == "__main__":
    unittest.main()
