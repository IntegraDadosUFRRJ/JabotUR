"""O get-or-create sem pandas (build_*_rows) dá as mesmas dimensões e os mesmos ids que o
get-or-create com DataFrame, na primeira rodada e com dados já gravados.

Roda sempre, sem banco: a leitura das tabelas existentes é substituída por mock.
"""

import math
import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.load import taxonomy

# Ficus aparece em duas famílias: genero_by_nome fica com o id do último par
FIRST_RUN_ROWS = [
    {"filo_nome": None, "familia": "Moraceae", "genero": "Ficus", "epiteto": "elastica",
     "infraespecifico": None, "autor": "Roxb."},
    # filo preenchido: na segunda rodada, uma família existente com id_filo não nulo
    {"filo_nome": "Musgos", "familia": "Fabaceae", "genero": "Inga", "epiteto": "vera",
     "infraespecifico": "affinis", "autor": None},
    {"filo_nome": None, "familia": "Urticaceae", "genero": "Ficus", "epiteto": "sp. [Espécimes#7]",
     "infraespecifico": None, "autor": None},
    {"filo_nome": None, "familia": None, "genero": "Sem familia", "epiteto": None,
     "infraespecifico": None, "autor": "L."},
    {"filo_nome": None, "familia": "Moraceae", "genero": None, "epiteto": None,
     "infraespecifico": None, "autor": None},
    {"filo_nome": None, "familia": "Moraceae", "genero": "Ficus", "epiteto": "elastica",
     "infraespecifico": None, "autor": "Roxb."},
]

# Segunda fonte: com filo, chaves repetidas da primeira e chaves novas
SECOND_RUN_ROWS = [
    {"filo_nome": "Musgos", "familia": "Bryaceae", "genero": "Bryum", "epiteto": "argenteum",
     "infraespecifico": None, "autor": "Hedw."},
    {"filo_nome": None, "familia": "Moraceae", "genero": "Ficus", "epiteto": "elastica",
     "infraespecifico": None, "autor": "Roxb."},
    {"filo_nome": "Hepáticas", "familia": "Moraceae", "genero": "Ficus", "epiteto": "benjamina",
     "infraespecifico": None, "autor": "L."},
    {"filo_nome": None, "familia": None, "genero": None, "epiteto": "solto",
     "infraespecifico": None, "autor": None},
]

TABLES = [
    config.TB_FILO, config.TB_FAMILIA, config.TB_GENERO, config.TB_AUTOR, config.TB_EPITETO_ESPECIFICO,
]


def _plain(value):
    # O DataFrame guarda NULL como NaN e id inteiro com NULL como float; a comparação é por valor
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def _records(dim) -> list[dict]:
    if isinstance(dim, pd.DataFrame):
        return [{k: _plain(v) for k, v in row.items()} for row in dim.to_dict("records")]
    return [{k: _plain(v) for k, v in row.items()} for row in dim]


def _run_pandas(rows, existing: dict[str, list[dict]]):
    def fake_load(table_name):
        return pd.DataFrame(existing.get(table_name, []))

    df = pd.DataFrame(rows)
    with mock.patch.object(taxonomy, "_load_existing", side_effect=fake_load):
        filo_dim, filo_ids = taxonomy.build_filo(df)
        familia_dim, familia_by_nome = taxonomy.build_familia(df, filo_ids, filo_dim)
        genero_dim, genero_by_nome = taxonomy.build_genero(df, familia_by_nome, familia_dim)
        autor_dim, autor_ids = taxonomy.build_autor(df)
        epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico(df, genero_by_nome, autor_ids, genero_dim)
    dims = dict(zip(TABLES, [filo_dim, familia_dim, genero_dim, autor_dim, epiteto_dim]))
    maps = [filo_ids, familia_by_nome, genero_by_nome, autor_ids, epiteto_ids]
    return {t: _records(d) for t, d in dims.items()}, maps


def _run_rows(rows, existing: dict[str, list[dict]]):
    def fake_load(con, table_name):
        return [dict(row) for row in existing.get(table_name, [])]

    con = mock.Mock()
    with mock.patch.object(taxonomy, "_load_existing_rows", side_effect=fake_load):
        filo_dim, filo_ids = taxonomy.build_filo_rows(con, rows)
        familia_dim, familia_by_nome = taxonomy.build_familia_rows(con, rows, filo_ids, filo_dim)
        genero_dim, genero_by_nome = taxonomy.build_genero_rows(con, rows, familia_by_nome, familia_dim)
        autor_dim, autor_ids = taxonomy.build_autor_rows(con, rows)
        epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico_rows(
            con, rows, genero_by_nome, autor_ids, genero_dim
        )
    dims = dict(zip(TABLES, [filo_dim, familia_dim, genero_dim, autor_dim, epiteto_dim]))
    maps = [filo_ids, familia_by_nome, genero_by_nome, autor_ids, epiteto_ids]
    return {t: _records(d) for t, d in dims.items()}, maps


def _plain_map(mapping: dict) -> list:
    # Lista de pares, não dict: a ordem de inserção também tem de ser a mesma
    return [(key, _plain(value)) for key, value in mapping.items()]


class TaxonomyRowsMatchesPandasTest(unittest.TestCase):
    def _assert_same(self, rows, existing):
        pandas_dims, pandas_maps = _run_pandas(rows, existing)
        rows_dims, rows_maps = _run_rows(rows, existing)
        self.assertEqual(pandas_dims, rows_dims)
        for pandas_map, rows_map in zip(pandas_maps, rows_maps):
            self.assertEqual(_plain_map(pandas_map), _plain_map(rows_map))
        return rows_dims, rows_maps

    def test_first_run_without_existing_rows(self):
        self._assert_same(FIRST_RUN_ROWS, existing={})

    def test_second_source_with_existing_rows(self):
        # As dimensões gravadas pela primeira fonte viram as "existentes" da segunda
        first_dims, _ = _run_rows(FIRST_RUN_ROWS, existing={})
        dims, _ = self._assert_same(SECOND_RUN_ROWS, existing=first_dims)
        # nenhum id já gravado muda
        for table in TABLES:
            before = {row["id"]: row for row in first_dims[table]}
            after = {row["id"]: row for row in dims[table]}
            for id_, row in before.items():
                self.assertEqual(after[id_]["nome"], row["nome"], table)

    def test_homonym_genus_keeps_last_id(self):
        dims, (_, _, genero_by_nome, _, epiteto_ids) = _run_rows(FIRST_RUN_ROWS, existing={})
        ficus_ids = [row["id"] for row in dims[config.TB_GENERO] if row["nome"] == "Ficus"]
        self.assertEqual(len(ficus_ids), 2)
        self.assertEqual(genero_by_nome["Ficus"], ficus_ids[-1])
        # as duas espécies de Ficus apontam para o último gênero Ficus
        ficus_species = [row for row in dims[config.TB_EPITETO_ESPECIFICO] if row["id_genero"] in ficus_ids]
        self.assertEqual({row["id_genero"] for row in ficus_species}, {ficus_ids[-1]})

    def test_missing_table_reads_as_no_rows(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=LookupError("sem tabela")):
            self.assertEqual(taxonomy._load_existing_rows(mock.Mock(), config.TB_FILO), [])

    def test_other_read_errors_are_not_swallowed(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=RuntimeError("conexão caiu")):
            with self.assertRaises(RuntimeError):
                taxonomy._load_existing_rows(mock.Mock(), config.TB_FILO)


if __name__ == "__main__":
    unittest.main()
