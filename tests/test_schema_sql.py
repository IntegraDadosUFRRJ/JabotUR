import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.db.init_postgres import SCHEMA_SQL_PATH


def _table_bodies(sql: str) -> dict[str, str]:
    """{tabela: corpo entre parênteses} para cada CREATE TABLE IF NOT EXISTS."""
    pattern = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", re.S)
    return {name: body for name, body in pattern.findall(sql)}


class SchemaSqlTest(unittest.TestCase):
    """Confere o schema.sql contra o config.py, sem banco."""

    @classmethod
    def setUpClass(cls):
        cls.sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        cls.tables = _table_bodies(cls.sql)
        cls.config_tables = {
            value for name, value in vars(config).items() if name.startswith("TB_")
        }

    def test_every_config_table_has_create_table(self):
        self.assertEqual(set(), self.config_tables - set(self.tables))

    def test_no_table_outside_config(self):
        self.assertEqual(set(), set(self.tables) - self.config_tables)

    def test_every_id_column_is_primary_key(self):
        for name, body in self.tables.items():
            if re.search(r"^\s*id bigint", body, re.M):
                with self.subTest(table=name):
                    self.assertRegex(body, r"(?m)^\s*id bigint PRIMARY KEY,?$")

    def test_association_tables_have_composite_key(self):
        self.assertIn(
            "PRIMARY KEY (id_briofita, id_substrato)", self.tables[config.TB_COLETA_SUBSTRATO]
        )
        self.assertIn(
            "PRIMARY KEY (id_briofita, id_observacao)", self.tables[config.TB_COLETA_OBSERVACAO]
        )

    def test_every_create_is_if_not_exists(self):
        # sem IF NOT EXISTS a segunda execução do init_postgres quebra
        code = re.sub(r"--[^\n]*", "", self.sql)
        creates = re.findall(r"CREATE (?:UNIQUE INDEX|TABLE)\b[^\n]*", code)
        self.assertTrue(creates)
        for statement in creates:
            with self.subTest(statement=statement):
                self.assertRegex(statement, r"^CREATE (UNIQUE INDEX|TABLE) IF NOT EXISTS ")

    def test_no_percent_sign(self):
        # o psycopg2 pode interpretar % mesmo via exec_driver_sql
        self.assertNotIn("%", self.sql)

    def test_no_drop(self):
        # ignora comentários "-- ..." (o cabeçalho cita "sem DROP")
        code = re.sub(r"--[^\n]*", "", self.sql)
        self.assertNotRegex(code.upper(), r"\bDROP\b")


if __name__ == "__main__":
    unittest.main()
