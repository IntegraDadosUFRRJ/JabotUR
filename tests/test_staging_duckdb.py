"""Staging lido pelo DuckDB (scripts.staging.xlsx_sheet) comparado com o openpyxl.

O openpyxl lê a planilha célula a célula, com o número de linha real e o estado de
linha oculta, e serve de referência para o _source_row e para os valores gravados.
Os testes de gravação só rodam num banco cujo nome termina em "_test":
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
Eles gravam só em tabelas próprias (prefixo test_staging_).
"""

import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb
from openpyxl import Workbook, load_workbook
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres
from scripts.staging import stage_SPP, stage_arboreto_citations, stage_arboreto_specimens, xlsx_sheet
from tests import db_test_support

DB_SKIP_REASON = db_test_support.invariants_skip_reason()
FILES_SKIP_REASON = (
    None
    if config.SPP_XLSX_PATH.exists() and config.ARBORETO_XLSX_PATH.exists()
    else "planilhas reais ausentes em data/"
)


def _as_text(value):
    """Valor do openpyxl no formato texto do all_varchar (inteiro sem '.0')."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _openpyxl_sheet(path: Path, sheet: str, column_map: dict[str, str]):
    """(linhas não vazias {linha: valores do column_map}, linhas ocultas) da aba."""
    # data_only: valor calculado das fórmulas (linhas de totais), que é o que o read_xlsx lê
    ws = load_workbook(path, data_only=True)[sheet]
    header = {str(cell.value).strip(): cell.column for cell in ws[1] if cell.value is not None}
    columns = [header[source] for source in column_map]
    rows = {}
    for row in range(2, ws.max_row + 1):
        values = tuple(_as_text(ws.cell(row, col).value) for col in columns)
        if any(v is not None for v in values):
            rows[row] = values
    hidden = {row for row, dim in ws.row_dimensions.items() if dim.hidden and row > 1}
    return rows, hidden


def _query_rows(query: str, sheet: str, column_map: dict[str, str]):
    """{_source_row: valores} de uma aba no resultado da query, sem gravar nada."""
    con = duckdb.connect()
    con.execute("LOAD excel")
    cols = ", ".join(f'"{col}"' for col in column_map.values())
    rows = con.execute(
        f"SELECT {config.SOURCE_ROW_COL}, {cols} FROM ({query}) "
        f"WHERE {config.SOURCE_SHEET_COL} = ? ORDER BY {config.SOURCE_ROW_COL}",
        [sheet],
    ).fetchall()
    return {row[0]: tuple(row[1:]) for row in rows}


def _table_rows(engine, table_name: str, sheet: str, column_map: dict[str, str]):
    """{_source_row: valores} de uma aba na tabela gravada no Postgres."""
    cols = ", ".join(f'"{col}"' for col in column_map.values())
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f'SELECT "{config.SOURCE_ROW_COL}", {cols} FROM "{table_name}" '
                f'WHERE "{config.SOURCE_SHEET_COL}" = :sheet ORDER BY 1'
            ),
            {"sheet": sheet},
        ).fetchall()
    return {row[0]: tuple(row[1:]) for row in rows}


class SyntheticSheetTests(unittest.TestCase):
    """Roda sempre: planilha montada no teste, sem banco."""

    COLUMN_MAP = {"Família": "familia", "Quant": "quantidade"}

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "sintetica.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Aba1"
        ws.append(["Família", "Quant "])      # espaço no fim, como na JABOT
        ws.append(["Fabaceae", 2])            # linha 2
        ws.append(["Oculta", 3])              # linha 3, oculta
        ws.append([None, "S3C2"])             # linha 4: texto numa coluna numérica
        ws.append([None, None])               # linha 5: em branco no meio
        ws.append(["Depois do branco", 5])    # linha 6
        ws.row_dimensions[3].hidden = True
        other = wb.create_sheet("Aba2")
        other.append(["Família", "Quant"])
        other.append(["Myrtaceae", 1])
        wb.save(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _rows(self, sheets):
        return _query_rows(
            xlsx_sheet.sheets_query(self.path, sheets, self.COLUMN_MAP), "Aba1", self.COLUMN_MAP
        )

    def test_source_row_matches_openpyxl_with_blank_row_in_the_middle(self):
        expected, hidden = _openpyxl_sheet(self.path, "Aba1", self.COLUMN_MAP)
        rows = self._rows(["Aba1"])
        self.assertEqual(rows, expected)
        self.assertEqual(list(rows), [2, 3, 4, 6])
        self.assertEqual(hidden, {3})

    def test_sheets_follow_the_given_order(self):
        con = duckdb.connect()
        con.execute("LOAD excel")
        query = xlsx_sheet.sheets_query(self.path, ["Aba2", "Aba1"], self.COLUMN_MAP)
        sheets = [row[0] for row in con.execute(f"SELECT {config.SOURCE_SHEET_COL} FROM ({query})").fetchall()]
        self.assertEqual(sheets, ["Aba2", "Aba1", "Aba1", "Aba1", "Aba1"])

    def test_header_missing_from_column_map_is_an_error(self):
        with self.assertRaises(duckdb.BinderException):
            _query_rows(
                xlsx_sheet.sheets_query(self.path, ["Aba1"], {"Gênero": "genero"}), "Aba1", {"Gênero": "genero"}
            )


class RealSheetChecks:
    """Comparação com o openpyxl nos arquivos de data/; a subclasse define a fonte."""

    PATH: Path
    SHEETS: list[str]
    COLUMN_MAP: dict[str, str]

    def query(self) -> str:
        raise NotImplementedError

    def test_rows_and_source_row_match_openpyxl(self):
        # Mesmas linhas, cada uma no número de linha da planilha e com os mesmos valores
        for sheet in self.SHEETS:
            with self.subTest(sheet=sheet):
                expected, _ = _openpyxl_sheet(self.PATH, sheet, self.COLUMN_MAP)
                self.assertEqual(_query_rows(self.query(), sheet, self.COLUMN_MAP), expected)

    def test_hidden_rows_are_present(self):
        for sheet in self.SHEETS:
            with self.subTest(sheet=sheet):
                _, hidden = _openpyxl_sheet(self.PATH, sheet, self.COLUMN_MAP)
                rows = _query_rows(self.query(), sheet, self.COLUMN_MAP)
                self.assertEqual(hidden - set(rows), set())


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class SppSheetTests(RealSheetChecks, unittest.TestCase):
    PATH = config.SPP_XLSX_PATH
    SHEETS = [config.SPP_SHEET_NAME]
    COLUMN_MAP = config.SPP_COLUMN_MAP

    def query(self) -> str:
        return stage_SPP.spp_query()


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class NoTextIntegerFloatCellsTests(unittest.TestCase):
    """A regex de xlsx_sheet.INTEGER_FLOAT_PATTERN só é segura se nenhuma célula de
    texto lida pelos stagings tiver o formato 'N.0': ela viraria 'N' sem aviso."""

    SOURCES = [
        (config.SPP_XLSX_PATH, [config.SPP_SHEET_NAME], config.SPP_COLUMN_MAP),
        (config.ARBORETO_XLSX_PATH, config.ARBORETO_CITATION_SHEETS, config.ARBORETO_CITATION_COLUMN_MAP),
        (config.ARBORETO_XLSX_PATH, [config.ARBORETO_SPECIMENS_SHEET_NAME], config.ARBORETO_SPECIMENS_COLUMN_MAP),
    ]

    def test_no_text_cell_looks_like_integer_float(self):
        pattern = re.compile(xlsx_sheet.INTEGER_FLOAT_PATTERN)
        found = []
        for path, sheets, column_map in self.SOURCES:
            workbook = load_workbook(path, data_only=True)
            for sheet in sheets:
                ws = workbook[sheet]
                header = {str(cell.value).strip(): cell.column for cell in ws[1] if cell.value is not None}
                for source in column_map:
                    for row in range(2, ws.max_row + 1):
                        value = ws.cell(row, header[source]).value
                        if isinstance(value, str) and pattern.match(value):
                            found.append(f"{path.name} / {sheet} / {source} / linha {row}: {value!r}")
        self.assertEqual(found, [])


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class CitationsSheetTests(RealSheetChecks, unittest.TestCase):
    PATH = config.ARBORETO_XLSX_PATH
    SHEETS = config.ARBORETO_CITATION_SHEETS
    COLUMN_MAP = config.ARBORETO_CITATION_COLUMN_MAP

    def query(self) -> str:
        return stage_arboreto_citations.citations_query()

    def test_sheets_follow_config_order(self):
        con = duckdb.connect()
        con.execute("LOAD excel")
        rows = con.execute(f"SELECT {config.SOURCE_SHEET_COL} FROM ({self.query()})").fetchall()
        order = list(dict.fromkeys(row[0] for row in rows))
        self.assertEqual(order, config.ARBORETO_CITATION_SHEETS)


@unittest.skipUnless(FILES_SKIP_REASON is None, FILES_SKIP_REASON or "")
class SpecimensSheetTests(RealSheetChecks, unittest.TestCase):
    PATH = config.ARBORETO_XLSX_PATH
    SHEETS = [config.ARBORETO_SPECIMENS_SHEET_NAME]
    COLUMN_MAP = config.ARBORETO_SPECIMENS_COLUMN_MAP

    def query(self) -> str:
        return stage_arboreto_specimens.specimens_query()

    def test_sheet_has_hidden_rows(self):
        # Sem linhas ocultas na referência, test_hidden_rows_are_present passaria sem testar nada
        _, hidden = _openpyxl_sheet(self.PATH, self.SHEETS[0], self.COLUMN_MAP)
        self.assertGreater(len(hidden), 0)

    def test_only_mapped_columns_are_read(self):
        # Colunas escolhidas pelo nome: as da planilha fora do map (Canteiro, na coluna E) não entram
        con = duckdb.connect()
        con.execute("LOAD excel")
        columns = [col[0] for col in con.execute(f"SELECT * FROM ({self.query()}) LIMIT 0").description]
        self.assertEqual(
            columns,
            [config.SOURCE_FILE_COL, config.SOURCE_SHEET_COL, config.SOURCE_ROW_COL]
            + list(self.COLUMN_MAP.values())
            + ["_loaded_at"],
        )


class WrittenStagingChecks:
    """Gravação no Postgres de teste; a subclasse define a fonte e a tabela."""

    TABLE: str
    TABLE_CONFIG_NAME: str
    SHEET_CONFIG_NAME: str
    PATH: Path
    SHEETS: list[str]
    COLUMN_MAP: dict[str, str]

    def stage(self) -> None:
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        db_test_support.require_test_database()
        with contextlib.redirect_stdout(io.StringIO()):
            init_postgres()
        cls.engine = db_utils.get_connection()

    @classmethod
    def tearDownClass(cls):
        db_utils.dispose_connections()

    def setUp(self):
        db_test_support.require_test_database()
        self._drop()
        patcher = mock.patch.object(config, self.TABLE_CONFIG_NAME, self.TABLE)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._drop)

    def _drop(self):
        with self.engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{self.TABLE}"'))

    def _stage_quietly(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.stage()

    def test_written_source_row_matches_openpyxl(self):
        self._stage_quietly()
        for sheet in self.SHEETS:
            with self.subTest(sheet=sheet):
                expected, hidden = _openpyxl_sheet(self.PATH, sheet, self.COLUMN_MAP)
                rows = _table_rows(self.engine, self.TABLE, sheet, self.COLUMN_MAP)
                self.assertEqual(rows, expected)
                self.assertEqual(hidden - set(rows), set())

    def test_loaded_at_is_timestamptz(self):
        self._stage_quietly()
        with self.engine.connect() as conn:
            data_type = conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = :t AND column_name = '_loaded_at'"
                ),
                {"t": self.TABLE},
            ).scalar()
        self.assertEqual(data_type, "timestamp with time zone")

    def test_read_error_keeps_previous_table(self):
        self._stage_quietly()
        with self.engine.connect() as conn:
            before = db_test_support.table_snapshot(conn, [self.TABLE])
        with mock.patch.object(config, self.SHEET_CONFIG_NAME, self._missing_sheet_value()):
            with self.assertRaises(duckdb.Error):
                self._stage_quietly()
        with self.engine.connect() as conn:
            self.assertEqual(db_test_support.table_snapshot(conn, [self.TABLE]), before)

    def _missing_sheet_value(self):
        return "Aba inexistente"


@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class SppWrittenStagingTests(WrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_spp"
    TABLE_CONFIG_NAME = "STG_SPP_TABLE"
    SHEET_CONFIG_NAME = "SPP_SHEET_NAME"
    PATH = config.SPP_XLSX_PATH
    SHEETS = [config.SPP_SHEET_NAME]
    COLUMN_MAP = config.SPP_COLUMN_MAP

    def stage(self) -> None:
        stage_SPP.stage_spp()


@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class CitationsWrittenStagingTests(WrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_citations"
    TABLE_CONFIG_NAME = "STG_ARBORETO_CITATIONS_TABLE"
    SHEET_CONFIG_NAME = "ARBORETO_CITATION_SHEETS"
    PATH = config.ARBORETO_XLSX_PATH
    SHEETS = config.ARBORETO_CITATION_SHEETS
    COLUMN_MAP = config.ARBORETO_CITATION_COLUMN_MAP

    def stage(self) -> None:
        stage_arboreto_citations.stage_citations()

    def _missing_sheet_value(self):
        # Só a última aba falha: o erro no meio da UNION também não pode gravar as outras
        return self.SHEETS[:-1] + ["Aba inexistente"]



@unittest.skipUnless(DB_SKIP_REASON is None, DB_SKIP_REASON or "")
class SpecimensWrittenStagingTests(WrittenStagingChecks, unittest.TestCase):
    TABLE = "test_staging_specimens"
    TABLE_CONFIG_NAME = "STG_ARBORETO_SPECIMENS_TABLE"
    SHEET_CONFIG_NAME = "ARBORETO_SPECIMENS_SHEET_NAME"
    PATH = config.ARBORETO_XLSX_PATH
    SHEETS = [config.ARBORETO_SPECIMENS_SHEET_NAME]
    COLUMN_MAP = config.ARBORETO_SPECIMENS_COLUMN_MAP

    def stage(self) -> None:
        stage_arboreto_specimens.stage_specimens()


if __name__ == "__main__":
    unittest.main()
