"""Get-or-create do taxonomy (build_*_rows): dimensões e ids esperados para uma entrada fixa,
na primeira rodada e com dados já gravados.

Os ids fixos travam a regra de ordem: os existentes mantêm o id e vêm antes, e as chaves novas
entram por primeira aparição. A ordem por id dos existentes vem do read_rows (ORDER BY id).
Roda sempre, sem banco: a leitura das tabelas existentes é substituída por mock.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

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
    # NaN, como os transforms do SPP devolvem para célula vazia, conta como NULL
    {"filo_nome": float("nan"), "familia": "Moraceae", "genero": "Ficus", "epiteto": "elastica",
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

FIRST_RUN_DIMS = {
    config.TB_FILO: [{"id": 1, "nome": "Musgos"}],
    config.TB_FAMILIA: [
        {"id": 1, "id_filo": None, "nome": "Moraceae"},
        {"id": 2, "id_filo": 1, "nome": "Fabaceae"},
        {"id": 3, "id_filo": None, "nome": "Urticaceae"},
    ],
    config.TB_GENERO: [
        {"id": 1, "id_familia": 1, "nome": "Ficus"},
        {"id": 2, "id_familia": 2, "nome": "Inga"},
        {"id": 3, "id_familia": 3, "nome": "Ficus"},
        {"id": 4, "id_familia": None, "nome": "Sem familia"},
    ],
    config.TB_AUTOR: [{"id": 1, "nome": "Roxb."}, {"id": 2, "nome": "L."}],
    config.TB_EPITETO_ESPECIFICO: [
        {"id": 1, "id_genero": 3, "id_autor": 1, "nome": "elastica", "infraespecifico": None},
        {"id": 2, "id_genero": 2, "id_autor": None, "nome": "vera", "infraespecifico": "affinis"},
        {"id": 3, "id_genero": 3, "id_autor": None, "nome": "sp. [Espécimes#7]", "infraespecifico": None},
        {"id": 4, "id_genero": 4, "id_autor": 2, "nome": None, "infraespecifico": None},
    ],
}

SECOND_RUN_DIMS = {
    config.TB_FILO: [{"id": 1, "nome": "Musgos"}, {"id": 2, "nome": "Hepáticas"}],
    config.TB_FAMILIA: [
        {"id": 1, "id_filo": None, "nome": "Moraceae"},
        {"id": 2, "id_filo": 1, "nome": "Fabaceae"},
        {"id": 3, "id_filo": None, "nome": "Urticaceae"},
        {"id": 4, "id_filo": 1, "nome": "Bryaceae"},
        {"id": 5, "id_filo": 2, "nome": "Moraceae"},
    ],
    # O gênero 1 já gravado passa a apontar para a família 5: familia_by_nome["Moraceae"]
    # fica com o último id, e a gravação é upsert
    config.TB_GENERO: [
        {"id": 1, "id_familia": 5, "nome": "Ficus"},
        {"id": 2, "id_familia": 2, "nome": "Inga"},
        {"id": 3, "id_familia": 3, "nome": "Ficus"},
        {"id": 4, "id_familia": None, "nome": "Sem familia"},
        {"id": 5, "id_familia": 4, "nome": "Bryum"},
    ],
    config.TB_AUTOR: [{"id": 1, "nome": "Roxb."}, {"id": 2, "nome": "L."}, {"id": 3, "nome": "Hedw."}],
    config.TB_EPITETO_ESPECIFICO: FIRST_RUN_DIMS[config.TB_EPITETO_ESPECIFICO] + [
        {"id": 5, "id_genero": 5, "id_autor": 3, "nome": "argenteum", "infraespecifico": None},
        {"id": 6, "id_genero": 3, "id_autor": 2, "nome": "benjamina", "infraespecifico": None},
        {"id": 7, "id_genero": None, "id_autor": None, "nome": "solto", "infraespecifico": None},
    ],
}

SECOND_RUN_EPITETO_IDS = [
    (("Ficus", "elastica", None, "Roxb."), 1),
    (("Inga", "vera", "affinis", None), 2),
    (("Ficus", "sp. [Espécimes#7]", None, None), 3),
    (("Sem familia", None, None, "L."), 4),
    (("Bryum", "argenteum", None, "Hedw."), 5),
    (("Ficus", "benjamina", None, "L."), 6),
    ((None, "solto", None, None), 7),
]


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
    return dims, maps


class TaxonomyRowsTest(unittest.TestCase):
    def test_first_run_without_existing_rows(self):
        dims, (filo_ids, familia_by_nome, genero_by_nome, autor_ids, _) = _run_rows(FIRST_RUN_ROWS, existing={})
        self.assertEqual(dims, FIRST_RUN_DIMS)
        # Listas de pares, não dicts: a ordem de inserção também é conferida
        self.assertEqual(list(filo_ids.items()), [("Musgos", 1)])
        self.assertEqual(list(familia_by_nome.items()), [("Moraceae", 1), ("Fabaceae", 2), ("Urticaceae", 3)])
        self.assertEqual(list(genero_by_nome.items()), [("Ficus", 3), ("Inga", 2), ("Sem familia", 4)])
        self.assertEqual(list(autor_ids.items()), [("Roxb.", 1), ("L.", 2)])

    def test_second_source_with_existing_rows(self):
        # As dimensões gravadas pela primeira fonte viram as existentes da segunda
        dims, (_, familia_by_nome, _, _, epiteto_ids) = _run_rows(SECOND_RUN_ROWS, existing=FIRST_RUN_DIMS)
        self.assertEqual(dims, SECOND_RUN_DIMS)
        self.assertEqual(list(familia_by_nome.items()), [("Moraceae", 5), ("Fabaceae", 2), ("Urticaceae", 3), ("Bryaceae", 4)])
        self.assertEqual(list(epiteto_ids.items()), SECOND_RUN_EPITETO_IDS)

    def test_homonym_genus_keeps_last_id(self):
        dims, (_, _, genero_by_nome, _, _) = _run_rows(FIRST_RUN_ROWS, existing={})
        ficus_ids = [row["id"] for row in dims[config.TB_GENERO] if row["nome"] == "Ficus"]
        self.assertEqual(ficus_ids, [1, 3])
        self.assertEqual(genero_by_nome["Ficus"], 3)
        # as duas espécies de Ficus apontam para o último gênero Ficus
        ficus_species = [row for row in dims[config.TB_EPITETO_ESPECIFICO] if row["id_genero"] in ficus_ids]
        self.assertEqual({row["id_genero"] for row in ficus_species}, {3})

    def test_none_if_nan(self):
        self.assertIsNone(taxonomy._none_if_nan(None))
        self.assertIsNone(taxonomy._none_if_nan(float("nan")))
        self.assertEqual(taxonomy._none_if_nan(0), 0)
        self.assertEqual(taxonomy._none_if_nan(""), "")
        self.assertEqual(taxonomy._none_if_nan("Ficus"), "Ficus")

    def test_missing_table_reads_as_no_rows(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=LookupError("sem tabela")):
            self.assertEqual(taxonomy._load_existing_rows(mock.Mock(), config.TB_FILO), [])

    def test_other_read_errors_are_not_swallowed(self):
        with mock.patch.object(taxonomy, "read_rows", side_effect=RuntimeError("conexão caiu")):
            with self.assertRaises(RuntimeError):
                taxonomy._load_existing_rows(mock.Mock(), config.TB_FILO)


if __name__ == "__main__":
    unittest.main()
