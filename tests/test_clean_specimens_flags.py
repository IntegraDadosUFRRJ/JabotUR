import unittest

from unittest import mock

import duckdb

import scripts.config as config
from scripts.clean import clean_arboretum_specimens, duckdb_parsers
from scripts.load import load_arboretum_specimens
from scripts.transforms.scientific_name import (
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
)
from scripts.transforms.registration_number import STATUS_BLUE, STATUS_UNPARSEABLE

STAGING_COLUMNS = [
    "_source_file", "_source_sheet", "_source_row", "family", "species_raw", "registration_number",
    "sector", "location_description", "reproductive_status",
]


def _staging_rows():
    """Linhas no formato do staging (tudo texto, como vem do Postgres), fora de ordem."""
    rows = [
        # (_source_row, species_raw, registration_number)
        ("10", "sem identificação", "RBRv90000293"),
        ("2", "Astronium concinnum Schott", "0015130"),
        ("3", "Morfo-Espécie 1", "LACRE AZUL 0015131"),
        ("4", "Inga vera Willd.", "lacre ilegível"),
    ]
    return [
        ("teste.xlsx", "Espécimes", source_row, "Fabaceae", species_raw, registration_number, None, None, None)
        for source_row, species_raw, registration_number in rows
    ]


def _transform_rows(rows):
    """Saída do clean como as linhas que o load lê com db_utils.read_rows
    (timestamptz como texto, porque o pytz não está instalado)."""
    # A tabela ocupa o lugar da view do staging, que no pipeline vem do Postgres
    con = duckdb.connect()
    try:
        column_defs = ", ".join(f'"{col}" VARCHAR' for col in STAGING_COLUMNS)
        con.execute(f"CREATE TABLE {config.DUCKDB_STAGING_ALIAS} ({column_defs})")
        placeholders = ", ".join("?" for _ in STAGING_COLUMNS)
        con.executemany(f"INSERT INTO {config.DUCKDB_STAGING_ALIAS} VALUES ({placeholders})", rows)
        result = clean_arboretum_specimens.transform(con)
        select = ", ".join(
            f'CAST("{col}" AS VARCHAR) AS "{col}"' if str(col_type) == "TIMESTAMP WITH TIME ZONE" else f'"{col}"'
            for col, col_type in zip(result.columns, result.types)
        )
        projected = result.project(select)
        return [dict(zip(projected.columns, row)) for row in projected.fetchall()]
    finally:
        con.close()


def _source_key(row: dict) -> tuple:
    # Ordem da planilha segundo o config, com a linha comparada como número
    return tuple(
        int(row[col]) if col == config.SOURCE_ROW_COL else row[col]
        for col in config.ARBORETUM_SPECIMENS_SOURCE_ORDER
    )


def _without_cleaned_at(out: list[dict]) -> list[dict]:
    # _cleaned_at é o horário da execução
    return [{col: value for col, value in row.items() if col != "_cleaned_at"} for row in out]


class CleanSpecimensOrderTests(unittest.TestCase):
    def _rows(self):
        # Dois arquivos e duas abas cujas linhas se intercalam pelo número: a ordem só
        # por _source_row misturaria as origens
        rows = [
            ("a.xlsx", "Espécimes", "10", "Inga vera Willd.", "0015130"),
            ("b.xlsx", "Espécimes", "2", "Astronium concinnum Schott", "0015131"),
            ("a.xlsx", "Outra", "3", "Morfo-Espécie 1", "RBRv90000293"),
            ("a.xlsx", "Espécimes", "9", "sem identificação", "0015132"),
        ]
        return [
            (source_file, sheet, source_row, "Fabaceae", species_raw, registration_number, None, None, None)
            for source_file, sheet, source_row, species_raw, registration_number in rows
        ]

    def test_rows_follow_config_source_order(self):
        out = _transform_rows(self._rows())
        keys = [_source_key(row) for row in out]
        self.assertEqual(keys, sorted(keys))

    def test_shuffled_input_gives_same_clean(self):
        rows = self._rows()
        expected = _transform_rows(rows)
        actual = _transform_rows([rows[i] for i in (3, 1, 0, 2)])
        self.assertEqual(_without_cleaned_at(actual), _without_cleaned_at(expected))


class CleanSpecimensFlagsTests(unittest.TestCase):
    def setUp(self):
        self.out = _transform_rows(_staging_rows())
        self.by_row = {row["_source_row"]: row for row in self.out}

    def test_rows_are_numbered_by_numeric_source_row(self):
        # sem o CAST, "10" ordenaria antes de "2"
        self.assertEqual([row["_source_row"] for row in self.out], ["2", "3", "4", "10"])

    def test_no_row_is_dropped(self):
        self.assertEqual(len(self.out), len(_staging_rows()))

    def test_unparseable_does_not_reconcile_and_needs_review(self):
        row = self.by_row["10"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_UNPARSEABLE)
        self.assertFalse(row["reconcile_across_sources"])
        self.assertTrue(row["needs_review"])

    def test_morphospecies_does_not_reconcile_and_needs_no_review(self):
        row = self.by_row["3"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_MORPHOSPECIES)
        self.assertFalse(row["reconcile_across_sources"])
        self.assertFalse(row["needs_review"])

    def test_ok_reconciles(self):
        row = self.by_row["2"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_OK)
        self.assertTrue(row["reconcile_across_sources"])
        self.assertFalse(row["needs_review"])

    def test_bare_registration_number_is_blue(self):
        row = self.by_row["2"]
        self.assertEqual(row["registration_status"], STATUS_BLUE)
        self.assertEqual(row["registration_number"], "LACRE AZUL 0015130")

    def test_unparseable_registration_needs_review(self):
        row = self.by_row["4"]
        self.assertEqual(row["parse_status"], PARSE_STATUS_OK)
        self.assertEqual(row["registration_status"], STATUS_UNPARSEABLE)
        self.assertTrue(row["needs_review"])

    def test_load_prepare_keeps_unparseable_epithet_null(self):
        # reconcile_across_sources=False em unparseable não muda a carga:
        # prepare() só anexa [aba#linha] ao epíteto, que aqui é NULL
        prepared = {
            row["_source_row"]: row for row in load_arboretum_specimens.prepare(_transform_rows(_staging_rows()))
        }
        self.assertIsNone(prepared["10"]["epithet"])
        self.assertIsNone(prepared["10"]["genus"])
        self.assertEqual(prepared["3"]["epithet"], "Morfo-Espécie 1 [Espécimes#3]")
        self.assertEqual(prepared["2"]["epithet"], "concinnum")


class RegisteredParserTests(unittest.TestCase):
    """Uma exceção num dos dois parsers registrados no DuckDB interrompe o clean."""

    def _assert_parser_failure_stops_clean(self, parser_name, parser, message):
        with mock.patch.object(duckdb_parsers, parser_name, parser):
            with self.assertRaisesRegex(duckdb.Error, message):
                _transform_rows(_staging_rows())

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
