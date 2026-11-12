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

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.clean import clean_SPP
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres
from scripts.load import load_SPP
from scripts.staging import stage_SPP
from tests import db_test_support

SPP_FINAL_TABLES = [
    config.TB_FILO,
    config.TB_FAMILIA,
    config.TB_GENERO,
    config.TB_AUTOR,
    config.TB_EPITETO_ESPECIFICO,
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

SKIP_REASON = db_test_support.invariants_skip_reason()


class TestLoadReadsCleanInSheetOrder(unittest.TestCase):
    """Roda sempre, sem banco: confere a ordem pedida na leitura do clean."""

    def test_load_spp_orders_by_source_columns(self):
        with mock.patch.object(
            load_SPP, "read_dataframe_from_postgres", return_value=pd.DataFrame()
        ) as fake_read:
            load_SPP.load_clean_df()
        fake_read.assert_called_once_with(config.CLN_SPP_TABLE, order_by=config.SPP_STAGING_ORDER)


def _stage_and_clean_spp() -> None:
    stage_SPP.load_staging(stage_SPP.extract_spp())
    clean_SPP.load_clean(clean_SPP.transform(clean_SPP.load_staging_df()))


def _reverse_clean_table(table_name: str) -> None:
    # Regravada de trás para frente, a ordem física fica o oposto da planilha
    df = db_utils.read_dataframe_from_postgres(table_name)
    db_utils.write_dataframe_to_postgres(df.iloc[::-1], table_name, mode="replace")


@unittest.skipUnless(SKIP_REASON is None, SKIP_REASON or "")
class TestLoadSppIgnoresPhysicalOrder(unittest.TestCase):
    def _load_spp_from_scratch(self, reverse_clean: bool) -> dict:
        db_test_support.reset_schema()
        with contextlib.redirect_stdout(io.StringIO()):
            init_postgres()
            _stage_and_clean_spp()
            if reverse_clean:
                _reverse_clean_table(config.CLN_SPP_TABLE)
            load_SPP.populate_normalized_tables()
        with db_utils.get_connection().connect() as conn:
            return db_test_support.table_snapshot(conn, SPP_FINAL_TABLES)

    def test_reversed_clean_gives_same_ids(self):
        expected = self._load_spp_from_scratch(reverse_clean=False)
        actual = self._load_spp_from_scratch(reverse_clean=True)
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
