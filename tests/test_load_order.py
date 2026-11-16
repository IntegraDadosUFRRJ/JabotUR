"""Os loads atribuem ids na ordem das linhas que leem do clean; essa ordem tem de ser
a da planilha, não a ordem física da tabela cln_*, que não tem id.

Os testes do banco só rodam num banco cujo nome termina em "_test":
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
"""

import contextlib
import io
import unittest
from unittest import mock

import scripts.config as config
from scripts.clean import clean_spp_bryophytes, clean_arboretum_citations, clean_arboretum_specimens
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres
from scripts.load import load_spp_bryophytes, load_arboretum_citations, load_arboretum_specimens
from scripts.staging import stage_spp_bryophytes, stage_arboretum_citations, stage_arboretum_specimens
from tests import db_test_support

TAXONOMY_TABLES = [
    config.TB_PHYLUM,
    config.TB_FAMILY,
    config.TB_GENUS,
    config.TB_AUTHOR,
    config.TB_SPECIES,
]

SPP_FINAL_TABLES = TAXONOMY_TABLES + [
    config.TB_LIFE_FORM,
    config.TB_PLOT,
    config.TB_IDENTIFICATION_STATUS,
    config.TB_SUBSTRATE,
    config.TB_REMARK,
    config.TB_OCCURRENCE,
    config.TB_OCCURRENCE_BRYOPHYTE,
    config.TB_OCCURRENCE_SUBSTRATE,
    config.TB_OCCURRENCE_REMARK,
]

CITATIONS_FINAL_TABLES = TAXONOMY_TABLES + [config.TB_BIBLIOGRAPHIC_CITATION]

SPECIMENS_FINAL_TABLES = TAXONOMY_TABLES + [
    config.TB_SECTOR,
    config.TB_REPRODUCTIVE_STATUS,
    config.TB_OCCURRENCE,
    config.TB_OCCURRENCE_ARBORETUM,
]

SKIP_REASON = db_test_support.invariants_skip_reason()


class TestReadsUseSheetOrder(unittest.TestCase):
    """Roda sempre, sem banco: confere a ordem pedida em cada leitura."""

    def test_clean_spp_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_spp_bryophytes, "read_table") as fake_read:
            clean_spp_bryophytes.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY, config.STG_SPP_TABLE, order_by=config.SPP_STAGING_ORDER
        )

    def test_clean_citations_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_arboretum_citations, "read_table") as fake_read:
            clean_arboretum_citations.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.STG_ARBORETUM_CITATIONS_TABLE,
            order_by=config.ARBORETUM_CITATION_STAGING_ORDER,
        )

    def test_load_spp_orders_by_source_columns(self):
        with mock.patch.object(db_utils, "read_rows", return_value=[]) as fake_read:
            load_spp_bryophytes.load_clean_rows(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY, config.CLN_SPP_TABLE, order_by=config.SPP_STAGING_ORDER
        )

    def test_load_citations_orders_by_source_columns(self):
        with mock.patch.object(db_utils, "read_rows", return_value=[]) as fake_read:
            load_arboretum_citations.load_clean_rows(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.CLN_ARBORETUM_CITATIONS_TABLE,
            order_by=config.ARBORETUM_CITATION_STAGING_ORDER,
        )

    def test_load_specimens_orders_by_source_columns(self):
        with mock.patch.object(db_utils, "read_rows", return_value=[]) as fake_read:
            load_arboretum_specimens.load_clean_rows(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.CLN_ARBORETUM_SPECIMENS_TABLE,
            order_by=config.ARBORETUM_SPECIMENS_STAGING_ORDER,
        )

    def test_clean_specimens_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_arboretum_specimens, "read_table") as fake_read:
            clean_arboretum_specimens.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.STG_ARBORETUM_SPECIMENS_TABLE,
            order_by=config.ARBORETUM_SPECIMENS_STAGING_ORDER,
        )


def _stage_and_clean_spp() -> None:
    stage_spp_bryophytes.stage_spp()
    clean_spp_bryophytes.clean_spp()


def _stage_and_clean_citations() -> None:
    stage_arboretum_citations.stage_citations()
    clean_arboretum_citations.clean_citations()


def _stage_and_clean_specimens() -> None:
    stage_arboretum_specimens.stage_specimens()
    clean_arboretum_specimens.clean_specimens()


def _reverse_clean_table(table_name: str, order_by: list[str]) -> None:
    # Regravada na ordem inversa da leitura do load, a ordem física fica o oposto da
    # planilha; no arboreto isso inverte também a ordem das abas. A cópia em memória
    # existe porque a tabela é lida e recriada: o CREATE OR REPLACE não pode ler dela.
    descending = ", ".join(f'"{col}" DESC' for col in order_by)
    with db_utils.postgres_duckdb() as con:
        db_utils.read_table(con, table_name).order(descending).create("reversed_clean")
        db_utils.replace_table(con, table_name, "SELECT * FROM reversed_clean ORDER BY rowid")


@unittest.skipUnless(SKIP_REASON is None, SKIP_REASON or "")
class TestLoadsIgnorePhysicalOrder(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        db_utils.dispose_connections()

    def _load_from_scratch(self, stage_and_clean, clean_table, order_by, populate, tables, reverse_clean):
        db_test_support.reset_schema()
        with contextlib.redirect_stdout(io.StringIO()):
            init_postgres()
            stage_and_clean()
            if reverse_clean:
                _reverse_clean_table(clean_table, order_by)
            populate()
        with db_utils.get_connection().connect() as conn:
            return db_test_support.table_snapshot(conn, tables)

    def _assert_reversed_clean_gives_same_ids(self, stage_and_clean, clean_table, order_by, populate, tables):
        expected = self._load_from_scratch(
            stage_and_clean, clean_table, order_by, populate, tables, reverse_clean=False
        )
        actual = self._load_from_scratch(
            stage_and_clean, clean_table, order_by, populate, tables, reverse_clean=True
        )
        self.assertEqual(expected, actual)

    def test_spp_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_spp,
            config.CLN_SPP_TABLE,
            config.SPP_STAGING_ORDER,
            load_spp_bryophytes.populate_normalized_tables,
            SPP_FINAL_TABLES,
        )

    def test_citations_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_citations,
            config.CLN_ARBORETUM_CITATIONS_TABLE,
            config.ARBORETUM_CITATION_STAGING_ORDER,
            load_arboretum_citations.populate_normalized_tables,
            CITATIONS_FINAL_TABLES,
        )

    def test_specimens_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_specimens,
            config.CLN_ARBORETUM_SPECIMENS_TABLE,
            config.ARBORETUM_SPECIMENS_STAGING_ORDER,
            load_arboretum_specimens.populate_normalized_tables,
            SPECIMENS_FINAL_TABLES,
        )


if __name__ == "__main__":
    unittest.main()
