"""Leitura e escrita no Postgres pelo DuckDB (db_utils.postgres_duckdb e funções irmãs).

Os testes de banco só rodam num banco cujo nome termina em "_test":
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
Eles criam e apagam só tabelas próprias (prefixo test_duckdb_).
"""

import contextlib
import io
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

import duckdb
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.db import db_utils
from scripts.db.init_postgres import init_postgres
from tests import db_test_support

TABLE = "test_duckdb_table"
SKIP_REASON = (
    None
    if config.POSTGRES_DB.endswith(db_test_support.TEST_DATABASE_SUFFIX)
    else f"POSTGRES_DB={config.POSTGRES_DB!r} não é banco de teste"
)


class TestPostgresDsn(unittest.TestCase):
    """Roda sempre, sem banco."""

    def test_password_with_quote_and_space_is_escaped(self):
        with mock.patch.object(config, "POSTGRES_PASSWORD", "a b'c\\d"):
            dsn = db_utils._postgres_dsn()
        self.assertIn("password='a b\\'c\\\\d'", dsn)

    def test_lock_timeout_goes_in_dsn(self):
        with mock.patch.object(config, "POSTGRES_LOCK_TIMEOUT", "7s"):
            self.assertIn("options='-c lock_timeout=7s'", db_utils._postgres_dsn())


class TestEngineCache(unittest.TestCase):
    """Roda sempre, sem banco: create_engine() não abre conexão."""

    def tearDown(self):
        db_utils.dispose_connections()

    def test_same_url_reuses_engine(self):
        self.assertIs(db_utils.get_connection(), db_utils.get_connection())

    def test_other_database_gets_other_engine(self):
        engine = db_utils.get_connection()
        with mock.patch.object(config, "POSTGRES_DB", config.POSTGRES_DB + "_outro"):
            self.assertIsNot(db_utils.get_connection(), engine)

    def test_concurrent_calls_create_one_engine(self):
        db_utils.dispose_connections()
        engines = []
        threads = [threading.Thread(target=lambda: engines.append(db_utils.get_connection())) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len({id(engine) for engine in engines}), 1)

    def test_dispose_connections_forgets_engines(self):
        engine = db_utils.get_connection()
        db_utils.dispose_connections()
        self.assertIsNot(db_utils.get_connection(), engine)


@unittest.skipUnless(SKIP_REASON is None, SKIP_REASON or "")
class TestPostgresDuckdb(unittest.TestCase):
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
        self._drop_table()

    def tearDown(self):
        self._drop_table()

    def _drop_table(self):
        with self.engine.begin() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{TABLE}"'))

    def _pg_rows(self, query: str) -> list[tuple]:
        with self.engine.connect() as conn:
            return [tuple(row) for row in conn.execute(text(query))]

    def _column_types(self) -> dict[str, str]:
        return dict(self._pg_rows(
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{TABLE}'"
        ))

    def _create_id_table(self):
        with self.engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE "{TABLE}" (id integer PRIMARY KEY, nome text)'))
            conn.execute(text(f"INSERT INTO \"{TABLE}\" VALUES (3, 'c'), (1, 'a'), (2, 'b')"))

    def test_read_table_uses_order_by(self):
        with self.engine.begin() as conn:
            conn.execute(text(f'CREATE TABLE "{TABLE}" (_source_file text, _source_row bigint)'))
            conn.execute(text(f"INSERT INTO \"{TABLE}\" VALUES ('b', 1), ('a', 10), ('a', 9)"))
        with db_utils.postgres_duckdb() as con:
            rows = db_utils.read_table(
                con, TABLE, order_by=[config.SOURCE_FILE_COL, config.SOURCE_ROW_COL]
            ).fetchall()
        self.assertEqual(rows, [("a", 9), ("a", 10), ("b", 1)])

    def test_read_table_without_order_uses_id(self):
        self._create_id_table()
        with db_utils.postgres_duckdb() as con:
            rows = db_utils.read_table(con, TABLE).fetchall()
        self.assertEqual([row[0] for row in rows], [1, 2, 3])

    def test_replace_keeps_types(self):
        with db_utils.postgres_duckdb() as con:
            db_utils.replace_table(
                con, TABLE,
                "SELECT 'x' AS nome, CAST(5 AS BIGINT) AS _source_row, CURRENT_TIMESTAMP AS _cleaned_at",
            )
        self.assertEqual(self._column_types(), {
            "nome": "character varying",
            "_source_row": "bigint",
            "_cleaned_at": "timestamp with time zone",
        })

    def test_replace_twice_gives_same_content(self):
        query = "SELECT range AS _source_row, 'v' || range AS valor FROM range(5)"
        snapshots = []
        for _ in range(2):
            with db_utils.postgres_duckdb() as con:
                db_utils.replace_table(con, TABLE, query)
            with self.engine.connect() as conn:
                snapshots.append(db_test_support.table_snapshot(conn, [TABLE]))
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(snapshots[0][TABLE][0], 5)

    def test_replace_error_keeps_previous_table(self):
        with db_utils.postgres_duckdb() as con:
            db_utils.replace_table(con, TABLE, "SELECT 'antes' AS valor")
            with self.assertRaises(duckdb.Error):
                db_utils.replace_table(con, TABLE, "SELECT 'depois' AS valor, error('falha') AS x")
        self.assertEqual(self._pg_rows(f'SELECT * FROM "{TABLE}"'), [("antes",)])

    def test_upsert_inserts_updates_and_is_idempotent(self):
        self._create_id_table()
        query = "SELECT 2 AS id, 'B' AS nome UNION ALL SELECT 4, 'd'"
        expected = [(1, "a"), (2, "B"), (3, "c"), (4, "d")]
        for _ in range(2):
            with db_utils.postgres_duckdb() as con:
                db_utils.upsert_table(con, TABLE, query)
            self.assertEqual(self._pg_rows(f'SELECT * FROM "{TABLE}" ORDER BY id'), expected)

    def test_upsert_with_repeated_id_fails_and_keeps_table(self):
        self._create_id_table()
        with db_utils.postgres_duckdb() as con:
            with self.assertRaisesRegex(ValueError, "id repetido.*: 2"):
                db_utils.upsert_table(con, TABLE, "SELECT 2 AS id, 'x' AS nome UNION ALL SELECT 2, 'y'")
        self.assertEqual(
            self._pg_rows(f'SELECT * FROM "{TABLE}" ORDER BY id'), [(1, "a"), (2, "b"), (3, "c")]
        )

    def test_lock_held_elsewhere_raises_after_lock_timeout(self):
        self._create_id_table()
        errors = []

        def read_locked_table():
            try:
                with mock.patch.object(config, "POSTGRES_LOCK_TIMEOUT", "1s"):
                    with db_utils.postgres_duckdb() as con:
                        db_utils.read_table(con, TABLE, order_by=["id"]).fetchall()
            except duckdb.Error as err:
                errors.append(err)

        # A leitura roda numa thread para que, sem o lock_timeout, o teste falhe em vez
        # de travar a suíte: o join tem prazo e o lock é solto logo depois
        with self.engine.connect() as other:
            other.execute(text(f'LOCK TABLE "{TABLE}" IN ACCESS EXCLUSIVE MODE'))
            reader = threading.Thread(target=read_locked_table, daemon=True)
            reader.start()
            reader.join(timeout=10)
            still_waiting = reader.is_alive()
            other.rollback()
        reader.join(timeout=10)
        self.assertFalse(still_waiting, "leitura esperou o lock além do lock_timeout")
        self.assertEqual(len(errors), 1)
        self.assertIn("lock timeout", str(errors[0]))

    def test_no_open_transaction_after_exit(self):
        # Prova o resultado (nenhuma transação sobra no Postgres), não qual passo o garante:
        # o close() sozinho também a encerra. O ROLLBACK em erro é provado por
        # test_replace_error_keeps_previous_table.
        # A leitura dentro do BEGIN abre a transação no Postgres; o erro vem depois dela
        self._create_id_table()
        with self.assertRaises(RuntimeError):
            with db_utils.postgres_duckdb() as con:
                con.execute("BEGIN")
                db_utils.read_table(con, TABLE).fetchall()
                raise RuntimeError("falha no meio da transação")
        idle = self._pg_rows(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database() AND state LIKE 'idle in transaction%' "
            "AND pid <> pg_backend_pid()"
        )
        self.assertEqual(idle, [(0,)])


if __name__ == "__main__":
    unittest.main()
