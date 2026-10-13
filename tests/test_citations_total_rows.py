import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import config
from scripts.clean import clean_arboreto_citations
from scripts.load import load_arboreto_citations
from scripts.staging import stage_arboreto_citations

CONTROL_COLUMNS = [
    config.ARBORETO_CITATION_COL_FAMILY_RAW,
    "previous_quantity_sum",
    "is_total_row",
]


# --- dados de entrada (isolados aqui para facilitar a migração da fronteira) ---

def _staging_rows():
    """(aba, linha, familia, especie, quantidade) no formato do staging."""
    return [
        # aba com totais (soma 2 + 3 = 5)
        ("A", 2, "Fabaceae", "Inga edulis Mart.", "2"),
        ("A", 3, None, "Inga vera Willd.", "3"),
        ("A", 4, None, None, "5"),
        # aba sem totais (a última linha é um registro real)
        ("B", 2, "Rutaceae", "Citrus limon (L.) Osbeck", "1"),
        ("B", 3, "Verbenaceae", "Citharexylum myrianthum Cham.", "4"),
        # aba com linha vazia cuja quantidade NÃO bate com a soma
        ("C", 2, "Fabaceae", "Inga edulis Mart.", "2"),
        ("C", 3, None, None, "99"),
    ]


def _to_input(rows):
    # Adaptador temporário: converte a tabela DuckDB em DataFrame porque 
    # clean.transform() ainda não teve a E/S migrada (previsto na issue #19).
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE staging (
            _source_file VARCHAR,
            _source_sheet VARCHAR,
            _source_row BIGINT,
            familia VARCHAR,
            especie VARCHAR,
            quantidade VARCHAR
        )
        """
    )
    con.executemany("INSERT INTO staging VALUES ('teste.xlsx', ?, ?, ?, ?, ?)", rows)
    df = con.table("staging").df()
    con.close()
    return df


def _write_mini_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Aba1"
    ws.append(["Família", "Espécie", "Quant"])
    ws.append(["Fabaceae", "Inga edulis Mart.", 2])
    ws.append([None, "Inga vera Willd.", 3])
    ws.append([None, None, 5])
    wb.save(path)


def _flags(result):
    """Colunas independentes da ordem de entrada, ordenadas por (aba, linha)."""
    return duckdb.query(
        """
        SELECT _source_sheet, _source_row, parse_status, needs_review, reconcile_across_sources
        FROM result
        ORDER BY _source_sheet, _source_row
        """
    ).fetchall()


class TotalRowTests(unittest.TestCase):
    def test_sheet_with_matching_total(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        self.assertEqual(len(result), 7)

        total = duckdb.query(
            """
            SELECT parse_status, needs_review, reconcile_across_sources
            FROM result
            WHERE _source_sheet = 'A' AND _source_row = 4
            """
        ).fetchone()
        self.assertEqual(total, (config.PARSE_STATUS_TOTAL_ROW, False, False))

    def test_sheet_without_total_keeps_last_row(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        b_count, total_in_b = duckdb.query(
            """
            SELECT 
                count(*),
                count(*) FILTER (WHERE parse_status = 'total_row')
            FROM result
            WHERE _source_sheet = 'B'
            """
        ).fetchone()

        self.assertEqual(b_count, 2)
        self.assertEqual(total_in_b, 0)
        last = duckdb.query(
            """
            SELECT genero, parse_status
            FROM result
            WHERE _source_sheet = 'B' AND _source_row = 3
            """
        ).fetchone()
        self.assertEqual(last, ("Citharexylum", "ok"))

    def test_empty_row_with_mismatching_sum_is_unparseable(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))

        mismatch = duckdb.query(
            """
            SELECT parse_status, needs_review
            FROM result
            WHERE _source_sheet = 'C' AND _source_row = 3
            """
        ).fetchone()
        self.assertEqual(mismatch, ("unparseable", True))

        total_rows_count = duckdb.query(
            f"""
            SELECT count(*)
            FROM result
            WHERE parse_status = '{config.PARSE_STATUS_TOTAL_ROW}'
            """
        ).fetchone()[0]
        self.assertEqual(total_rows_count, 1)

    def test_shuffled_input_gives_same_flags(self):
        # compara só parse_status, needs_review e reconcile_across_sources;
        # nunca `familia` (o fill-down depende da ordem de entrada, issue #11)
        rows = _staging_rows()
        shuffled = [rows[i] for i in (4, 2, 6, 0, 3, 1, 5)]

        expected = _flags(clean_arboreto_citations.transform(_to_input(rows)))
        actual = _flags(clean_arboreto_citations.transform(_to_input(shuffled)))

        self.assertEqual(expected, actual)

    def test_control_columns_not_in_output(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        cols = [c[0] for c in duckdb.query("DESCRIBE result").fetchall()]
        for column in CONTROL_COLUMNS:
            self.assertNotIn(column, cols)


class StagingTests(unittest.TestCase):
    def test_staging_preserves_all_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.xlsx"
            _write_mini_xlsx(path)

            with mock.patch.object(config, "ARBORETO_XLSX_PATH", path), \
                 mock.patch.object(config, "ARBORETO_CITATION_SHEETS", ["Aba1"]):
                df = stage_arboreto_citations.extract_citations()

        rows = duckdb.query(
            """
            SELECT _source_row, quantidade
            FROM df
            ORDER BY _source_row
            """
        ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual([r[0] for r in rows], [2, 3, 4])
        self.assertEqual(rows[-1][1], "5")


class LoadPrepareTests(unittest.TestCase):
    def test_prepare_drops_total_rows_and_logs(self):
        cleaned = clean_arboreto_citations.transform(
            _to_input(
                [
                    ("A", 2, "Fabaceae", "Inga edulis Mart.", "2"),
                    ("A", 3, None, "Morfo-Espécie 1", "3"),
                    ("A", 4, None, None, "5"),
                ]
            )
        )
        with mock.patch("builtins.print") as fake_print:
            prepared = load_arboreto_citations.prepare(cleaned)

        self.assertEqual(len(prepared), 2)
        total_in_prepared = duckdb.query(
            f"""
            SELECT count(*)
            FROM prepared
            WHERE parse_status = '{config.PARSE_STATUS_TOTAL_ROW}'
            """
        ).fetchone()[0]
        self.assertEqual(total_in_prepared, 0)
        logged = " ".join(str(call.args[0]) for call in fake_print.call_args_list)
        self.assertIn("linha de totais, ignorada", logged)


if __name__ == "__main__":
    unittest.main()
