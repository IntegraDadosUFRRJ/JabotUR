import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
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
    # DataFrame mínimo na entrada: inevitável enquanto transform() receber um
    # DataFrame (a E/S ainda é pandas; migração prevista no item 5.5).
    return pd.DataFrame(
        [
            {
                "_source_file": "teste.xlsx",
                "_source_sheet": sheet,
                "_source_row": row,
                "familia": familia,
                "especie": especie,
                "quantidade": quantidade,
            }
            for sheet, row, familia, especie, quantidade in rows
        ]
    )


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
    """Colunas independentes da ordem de entrada, indexadas por (aba, linha)."""
    return result.set_index(["_source_sheet", "_source_row"])[
        ["parse_status", "needs_review", "reconcile_across_sources"]
    ].sort_index()


class TotalRowTests(unittest.TestCase):
    def test_sheet_with_matching_total(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        self.assertEqual(len(result), 7)

        total = _flags(result).loc[("A", 4)]
        self.assertEqual(total["parse_status"], config.PARSE_STATUS_TOTAL_ROW)
        self.assertFalse(total["needs_review"])
        self.assertFalse(total["reconcile_across_sources"])

    def test_sheet_without_total_keeps_last_row(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        sheet_b = result[result["_source_sheet"] == "B"]

        self.assertEqual(len(sheet_b), 2)
        self.assertNotIn(config.PARSE_STATUS_TOTAL_ROW, set(sheet_b["parse_status"]))
        last = sheet_b[sheet_b["_source_row"] == 3].iloc[0]
        self.assertEqual(last["genero"], "Citharexylum")
        self.assertEqual(last["parse_status"], "ok")

    def test_empty_row_with_mismatching_sum_is_unparseable(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))

        mismatch = _flags(result).loc[("C", 3)]
        self.assertEqual(mismatch["parse_status"], "unparseable")
        self.assertTrue(mismatch["needs_review"])
        self.assertEqual(
            (result["parse_status"] == config.PARSE_STATUS_TOTAL_ROW).sum(), 1
        )

    def test_shuffled_input_gives_same_flags(self):
        # compara só parse_status, needs_review e reconcile_across_sources;
        # nunca `familia` (o fill-down depende da ordem de entrada, Etapa 3)
        rows = _staging_rows()
        shuffled = [rows[i] for i in (4, 2, 6, 0, 3, 1, 5)]

        expected = _flags(clean_arboreto_citations.transform(_to_input(rows)))
        actual = _flags(clean_arboreto_citations.transform(_to_input(shuffled)))

        pd.testing.assert_frame_equal(expected, actual)

    def test_control_columns_not_in_output(self):
        result = clean_arboreto_citations.transform(_to_input(_staging_rows()))
        for column in CONTROL_COLUMNS:
            self.assertNotIn(column, result.columns)


class StagingTests(unittest.TestCase):
    def test_staging_preserves_all_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.xlsx"
            _write_mini_xlsx(path)

            with mock.patch.object(config, "ARBORETO_XLSX_PATH", path), \
                 mock.patch.object(config, "ARBORETO_CITATION_SHEETS", ["Aba1"]):
                df = stage_arboreto_citations.extract_citations()

        self.assertEqual(len(df), 3)
        self.assertEqual(list(df["_source_row"]), [2, 3, 4])
        self.assertEqual(df["quantidade"].iloc[-1], "5")


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
        self.assertNotIn(config.PARSE_STATUS_TOTAL_ROW, set(prepared["parse_status"]))
        logged = " ".join(str(call.args[0]) for call in fake_print.call_args_list)
        self.assertIn("linha de totais, ignorada", logged)


if __name__ == "__main__":
    unittest.main()
