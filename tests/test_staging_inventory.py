"""Staging do inventário do arboreto (CAP_Coluna, tabela_campo_coordenadas e Atualizada)
comparado com o openpyxl, no mesmo padrão de test_staging_duckdb.

Os testes de gravação só rodam num banco cujo nome termina em "_test":
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
Eles gravam só em tabelas próprias (prefixo test_staging_inventory_).
"""

import datetime
import re
import unittest
from unittest import mock

import duckdb
from openpyxl import load_workbook
from openpyxl.utils.datetime import to_excel
from sqlalchemy import text

import scripts.config as config
from scripts.staging import stage_arboretum_inventory, xlsx_sheet
from tests import db_test_support, test_staging_duckdb
# Só mixins e funções: importar uma classe TestCase faria o discover rodá-la duas vezes
from tests.test_staging_duckdb import RealSheetChecks, WrittenStagingChecks, _openpyxl_sheet, _query_rows

FILES_SKIP_REASON = (
    None
    if config.ARBORETUM_INVENTORY_XLSX_PATH.exists()
    else f"planilha do inventário ausente: {config.ARBORETUM_INVENTORY_XLSX_PATH}"
)
DB_SKIP_REASON = db_test_support.invariants_skip_reason() or FILES_SKIP_REASON

def _residue_rows(sheet: str, column_map: dict[str, str]) -> set[int]:
    """Linhas da aba com alguma célula preenchida, mas nenhuma coluna mapeada (na
    CAP_Coluna, só o Nome Científico com '#N/A'; na Atualizada, os blocos sem cabeçalho)."""
    ws = load_workbook(config.ARBORETUM_INVENTORY_XLSX_PATH, data_only=True)[sheet]
    header = {cell.column: str(cell.value).strip() for cell in ws[1] if cell.value is not None}
    residue = set()
    for row in range(2, ws.max_row + 1):
        filled = {header.get(cell.column) for cell in ws[row] if cell.value is not None}
        if filled and not filled & set(column_map):
            residue.add(row)
    return residue


class InventorySheetChecks(RealSheetChecks):
    PATH = config.ARBORETUM_INVENTORY_XLSX_PATH

    def test_row_count_matches_openpyxl(self):
        expected, _ = _openpyxl_sheet(self.PATH, self.SHEETS[0], self.COLUMN_MAP)
        con = duckdb.connect()
        con.execute("LOAD excel")
        count = con.execute(f"SELECT count(*) FROM ({self.query()})").fetchone()[0]
        self.assertEqual(count, len(expected))


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class StemsSheetTests(InventorySheetChecks, unittest.TestCase):
    SHEETS = [config.ARBORETUM_INVENTORY_STEMS_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_STEMS_COLUMN_MAP

    def query(self) -> str:
        return stage_arboretum_inventory.stems_query()

    def test_residue_rows_are_not_staged(self):
        residue = _residue_rows(self.SHEETS[0], self.COLUMN_MAP)
        # Sem resíduo o teste não provaria nada; ele também some se o Nome Científico
        # entrar no column_map, porque aí essas linhas passam a ter coluna mapeada
        self.assertTrue(residue)
        staged = set(_query_rows(self.query(), self.SHEETS[0], self.COLUMN_MAP))
        self.assertEqual(staged & residue, set())


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class FieldSheetTests(InventorySheetChecks, unittest.TestCase):
    SHEETS = [config.ARBORETUM_INVENTORY_FIELD_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_FIELD_COLUMN_MAP

    def query(self) -> str:
        return stage_arboretum_inventory.field_query()


_plain_as_text = test_staging_duckdb._as_text


def _as_text_with_excel_dates(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        value = to_excel(value)
    return _plain_as_text(value)


class ExcelDatesAsSerial:
    """Na comparação com o openpyxl, célula de data vira o número serial do Excel, que é
    o que o read_xlsx com all_varchar devolve; o openpyxl devolve um datetime.

    O _openpyxl_sheet de test_staging_duckdb é reaproveitado como está, trocando só o
    _as_text durante o teste: as outras fontes não têm célula de data e não mudam."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(test_staging_duckdb, "_as_text", _as_text_with_excel_dates)
        patcher.start()
        self.addCleanup(patcher.stop)


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class UpdatedSheetTests(ExcelDatesAsSerial, InventorySheetChecks, unittest.TestCase):
    SHEETS = [config.ARBORETUM_INVENTORY_UPDATED_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_UPDATED_COLUMN_MAP

    def query(self) -> str:
        return stage_arboretum_inventory.updated_query()

    def test_date_cells_are_compared(self):
        # Sem célula de data na aba, o ExcelDatesAsSerial não estaria provando nada
        ws = load_workbook(self.PATH, data_only=True)[self.SHEETS[0]]
        header = {str(cell.value).strip(): cell.column for cell in ws[1] if cell.value is not None}
        dates = [
            (row, source)
            for source in self.COLUMN_MAP
            for row in range(2, ws.max_row + 1)
            if isinstance(ws.cell(row, header[source]).value, datetime.datetime)
        ]
        self.assertTrue(dates)

    def test_loose_block_rows_are_not_staged(self):
        # Linhas só com os blocos sem cabeçalho à direita da coluna L
        loose = _residue_rows(self.SHEETS[0], self.COLUMN_MAP)
        self.assertTrue(loose)
        staged = set(_query_rows(self.query(), self.SHEETS[0], self.COLUMN_MAP))
        self.assertEqual(staged & loose, set())


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class NoTextIntegerFloatCellsTests(unittest.TestCase):
    """Mesma garantia do teste homônimo em test_staging_duckdb, para as abas do inventário:
    uma célula de texto 'N.0' viraria 'N' sem aviso pela INTEGER_FLOAT_PATTERN."""

    SHEETS = [
        (config.ARBORETUM_INVENTORY_STEMS_SHEET_NAME, config.ARBORETUM_INVENTORY_STEMS_COLUMN_MAP),
        (config.ARBORETUM_INVENTORY_FIELD_SHEET_NAME, config.ARBORETUM_INVENTORY_FIELD_COLUMN_MAP),
        (config.ARBORETUM_INVENTORY_UPDATED_SHEET_NAME, config.ARBORETUM_INVENTORY_UPDATED_COLUMN_MAP),
    ]

    def test_no_text_cell_looks_like_integer_float(self):
        pattern = re.compile(xlsx_sheet.INTEGER_FLOAT_PATTERN)
        workbook = load_workbook(config.ARBORETUM_INVENTORY_XLSX_PATH, data_only=True)
        found = []
        for sheet, column_map in self.SHEETS:
            ws = workbook[sheet]
            header = {str(cell.value).strip(): cell.column for cell in ws[1] if cell.value is not None}
            for source in column_map:
                for row in range(2, ws.max_row + 1):
                    value = ws.cell(row, header[source]).value
                    if isinstance(value, str) and pattern.match(value):
                        found.append(f"{sheet} / {source} / linha {row}: {value!r}")
        self.assertEqual(found, [])


class InventoryWrittenStagingChecks(WrittenStagingChecks):
    PATH = config.ARBORETUM_INVENTORY_XLSX_PATH

    def _data_snapshot(self):
        # O _loaded_at muda a cada gravação; o resto da linha não pode mudar
        with self.engine.connect() as conn:
            return conn.execute(
                text(
                    f"SELECT count(*), md5(string_agg((to_jsonb(t) - '_loaded_at')::text, E'\\n' "
                    f"ORDER BY (to_jsonb(t) - '_loaded_at')::text)) FROM \"{self.TABLE}\" AS t"
                )
            ).one()

    def test_second_write_changes_nothing(self):
        self._stage_quietly()
        first = self._data_snapshot()
        self._stage_quietly()
        self.assertEqual(self._data_snapshot(), first)


@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class StemsWrittenStagingTests(InventoryWrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_inventory_stems"
    TABLE_CONFIG_NAME = "STG_ARBORETUM_INVENTORY_STEMS_TABLE"
    SHEET_CONFIG_NAME = "ARBORETUM_INVENTORY_STEMS_SHEET_NAME"
    SHEETS = [config.ARBORETUM_INVENTORY_STEMS_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_STEMS_COLUMN_MAP

    def stage(self) -> None:
        stage_arboretum_inventory.stage_stems()


@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class FieldWrittenStagingTests(InventoryWrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_inventory_field"
    TABLE_CONFIG_NAME = "STG_ARBORETUM_INVENTORY_FIELD_TABLE"
    SHEET_CONFIG_NAME = "ARBORETUM_INVENTORY_FIELD_SHEET_NAME"
    SHEETS = [config.ARBORETUM_INVENTORY_FIELD_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_FIELD_COLUMN_MAP

    def stage(self) -> None:
        stage_arboretum_inventory.stage_field()


@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class UpdatedWrittenStagingTests(ExcelDatesAsSerial, InventoryWrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_inventory_updated"
    TABLE_CONFIG_NAME = "STG_ARBORETUM_INVENTORY_UPDATED_TABLE"
    SHEET_CONFIG_NAME = "ARBORETUM_INVENTORY_UPDATED_SHEET_NAME"
    SHEETS = [config.ARBORETUM_INVENTORY_UPDATED_SHEET_NAME]
    COLUMN_MAP = config.ARBORETUM_INVENTORY_UPDATED_COLUMN_MAP

    def stage(self) -> None:
        stage_arboretum_inventory.stage_updated()


if __name__ == "__main__":
    unittest.main()
