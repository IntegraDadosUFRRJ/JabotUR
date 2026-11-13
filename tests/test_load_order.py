"""Os loads atribuem ids na ordem das linhas que leem do clean; essa ordem tem de ser
a da planilha, não a ordem física da tabela cln_*, que não tem id.

Os testes do banco só rodam num banco cujo nome termina em "_test":
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.clean import clean_SPP, clean_arboreto_citations, clean_arboreto_specimens
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres
from scripts.load import load_SPP, load_arboreto_citations, load_arboreto_specimens
from scripts.staging import stage_SPP, stage_arboreto_citations, stage_arboreto_specimens
from tests import db_test_support

TAXONOMY_TABLES = [
    config.TB_FILO,
    config.TB_FAMILIA,
    config.TB_GENERO,
    config.TB_AUTOR,
    config.TB_EPITETO_ESPECIFICO,
]

SPP_FINAL_TABLES = TAXONOMY_TABLES + [
    config.TB_FORMA_VIDA,
    config.TB_PARCELA,
    config.TB_IDENTIFICACAO,
    config.TB_SUBSTRATO,
    config.TB_OBSERVACAO,
    config.TB_OCCURRENCE,
    config.TB_OCCURRENCE_BRYOPHYTE,
    config.TB_COLETA_SUBSTRATO,
    config.TB_COLETA_OBSERVACAO,
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

    def _assert_read_order(self, module, read_function, table_name, order_by):
        with mock.patch.object(
            module, "read_dataframe_from_postgres", return_value=pd.DataFrame()
        ) as fake_read:
            read_function()
        fake_read.assert_called_once_with(table_name, order_by=order_by)

    def test_clean_spp_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_SPP, "read_table") as fake_read:
            clean_SPP.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY, config.STG_SPP_TABLE, order_by=config.SPP_STAGING_ORDER
        )

    def test_clean_spp_view_renames_alternative_columns(self):
        # Staging com os nomes alternativos: a view expõe os nomes que a query espera
        con = duckdb.connect()
        try:
            staging = con.sql(
                f"SELECT 'x' AS {config.COL_OBSERVACOES}, '1' AS {config.COL_STATUS_IDENTIFICACAO}"
            )
            with mock.patch.object(clean_SPP, "read_table", return_value=staging):
                clean_SPP.create_staging_view(con)
            columns = con.sql(f"SELECT * FROM {config.DUCKDB_STAGING_ALIAS}").columns
        finally:
            con.close()
        self.assertEqual(columns, [config.COL_OBSERVACAO, config.COL_IDENTIFICACAO])

    def test_clean_citations_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_arboreto_citations, "read_table") as fake_read:
            clean_arboreto_citations.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.STG_ARBORETO_CITATIONS_TABLE,
            order_by=config.ARBORETO_CITATION_STAGING_ORDER,
        )

    def test_load_spp_orders_by_source_columns(self):
        with mock.patch.object(db_utils, "read_rows", return_value=[]) as fake_read:
            load_SPP.load_clean_rows(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY, config.CLN_SPP_TABLE, order_by=config.SPP_STAGING_ORDER
        )

    def test_load_citations_orders_by_source_columns(self):
        self._assert_read_order(
            load_arboreto_citations,
            load_arboreto_citations.load_clean_df,
            config.CLN_ARBORETO_CITATIONS_TABLE,
            config.ARBORETO_CITATION_STAGING_ORDER,
        )

    def test_load_specimens_orders_by_source_columns(self):
        self._assert_read_order(
            load_arboreto_specimens,
            load_arboreto_specimens.load_clean_df,
            config.CLN_ARBORETO_SPECIMENS_TABLE,
            config.ARBORETO_SPECIMENS_STAGING_ORDER,
        )

    def test_clean_specimens_reads_staging_by_source_columns(self):
        with mock.patch.object(clean_arboreto_specimens, "read_table") as fake_read:
            clean_arboreto_specimens.create_staging_view(mock.Mock())
        fake_read.assert_called_once_with(
            mock.ANY,
            config.STG_ARBORETO_SPECIMENS_TABLE,
            order_by=config.ARBORETO_SPECIMENS_STAGING_ORDER,
        )


def _stage_and_clean_spp() -> None:
    stage_SPP.stage_spp()
    clean_SPP.clean_spp()


def _stage_and_clean_citations() -> None:
    stage_arboreto_citations.stage_citations()
    clean_arboreto_citations.clean_citations()


def _stage_and_clean_specimens() -> None:
    stage_arboreto_specimens.stage_specimens()
    clean_arboreto_specimens.clean_specimens()


def _reverse_clean_table(table_name: str) -> None:
    # Regravada de trás para frente, a ordem física fica o oposto da planilha;
    # no arboreto isso inverte também a ordem das abas
    df = db_utils.read_dataframe_from_postgres(table_name)
    db_utils.write_dataframe_to_postgres(df.iloc[::-1], table_name, mode="replace")


@unittest.skipUnless(SKIP_REASON is None, SKIP_REASON or "")
class TestLoadsIgnorePhysicalOrder(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        db_utils.dispose_connections()

    def _load_from_scratch(self, stage_and_clean, clean_table, populate, tables, reverse_clean):
        db_test_support.reset_schema()
        with contextlib.redirect_stdout(io.StringIO()):
            init_postgres()
            stage_and_clean()
            if reverse_clean:
                _reverse_clean_table(clean_table)
            populate()
        with db_utils.get_connection().connect() as conn:
            return db_test_support.table_snapshot(conn, tables)

    def _assert_reversed_clean_gives_same_ids(self, stage_and_clean, clean_table, populate, tables):
        expected = self._load_from_scratch(stage_and_clean, clean_table, populate, tables, reverse_clean=False)
        actual = self._load_from_scratch(stage_and_clean, clean_table, populate, tables, reverse_clean=True)
        self.assertEqual(expected, actual)

    def test_spp_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_spp,
            config.CLN_SPP_TABLE,
            load_SPP.populate_normalized_tables,
            SPP_FINAL_TABLES,
        )

    def test_citations_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_citations,
            config.CLN_ARBORETO_CITATIONS_TABLE,
            load_arboreto_citations.populate_normalized_tables,
            CITATIONS_FINAL_TABLES,
        )

    def test_specimens_reversed_clean_gives_same_ids(self):
        self._assert_reversed_clean_gives_same_ids(
            _stage_and_clean_specimens,
            config.CLN_ARBORETO_SPECIMENS_TABLE,
            load_arboreto_specimens.populate_normalized_tables,
            SPECIMENS_FINAL_TABLES,
        )


if __name__ == "__main__":
    unittest.main()
