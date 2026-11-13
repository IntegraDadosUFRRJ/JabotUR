import sys
from pathlib import Path
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.config as config
from scripts.clean import clean_SPP


def _transform(columns: dict[str, list], source_row_type: str = "BIGINT") -> tuple[dict, list[dict]]:
    """Roda o clean sobre uma tabela de staging montada a partir das colunas.

    A tabela ocupa o lugar da view do staging, que no pipeline vem do Postgres: tudo
    VARCHAR, como no staging, menos _source_row, no tipo pedido.
    Devolve ({coluna: tipo}, linhas na ordem da saída). _cleaned_at fica de fora: é o
    horário da execução e só sai como objeto Python com o pytz instalado.
    """
    names = list(columns)
    con = duckdb.connect()
    try:
        column_defs = ", ".join(
            f'"{name}" {source_row_type if name == "_source_row" else "VARCHAR"}' for name in names
        )
        con.execute(f"CREATE TABLE {config.DUCKDB_STAGING_ALIAS} ({column_defs})")
        placeholders = ", ".join("?" for _ in names)
        con.executemany(
            f"INSERT INTO {config.DUCKDB_STAGING_ALIAS} VALUES ({placeholders})",
            [list(row) for row in zip(*columns.values())],
        )
        result = clean_SPP.transform(con)
        kept = [(col, str(col_type)) for col, col_type in zip(result.columns, result.types) if col != "_cleaned_at"]
        projected = result.project(", ".join(f'"{col}"' for col, _ in kept))
        rows = [dict(zip(projected.columns, row)) for row in projected.fetchall()]
        return dict(kept), rows
    finally:
        con.close()


def _reorder(columns: dict[str, list], order: list[int]) -> dict[str, list]:
    return {name: [values[i] for i in order] for name, values in columns.items()}


class CleanSppDuckDBTests(unittest.TestCase):
    def test_transform_normalizes_observations_and_filldown(self) -> None:
        columns = {
            "parcela": ["4*", None, "5"],
            "amostra": [None, "A1", None],
            "substrato": ["  rocha ", None, "  cimento  "],
            "forma_vida": ["terrestre", None, "epífita"],
            "observacao": ["c/ esp", "acro [fotos]", None],
            "identificacao": ["1", "2", None],
            "filo": [" Bryophyta ", None, "Marchantiophyta"],
            "familia": [None, "Pottiaceae", None],
            "genero": ["Barbula", None, "Riccardia"],
            "epiteto_especifico": ["sp.", None, "latifrons"],
            "autor": ["Hedw.", None, "L."],
            # Lineage como o stage_SPP grava; o clean exige _source_file e _source_row
            "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
            "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
            "_source_row": [2, 3, 4],
        }

        _, result = _transform(columns)

        self.assertEqual(result[0]["parcela"], "4")
        self.assertEqual(result[1]["parcela"], "4")
        self.assertEqual(result[0]["observacoes"], "com esporófito")
        self.assertEqual(result[1]["observacoes"], "acrocárpico")
        self.assertIsNone(result[2]["observacoes"])
        self.assertEqual(result[0]["substrato"], "rocha")
        self.assertEqual(result[1]["amostra"], "A1")
        self.assertEqual(result[0]["status_identificacao"], 1)

    def test_blank_forma_vida_stays_null(self) -> None:
        # forma de vida é da coleta: a linha em branco não herda a de cima
        columns = {
            "parcela": ["4", None, None],
            "amostra": ["A1", None, None],
            "substrato": ["rocha", None, None],
            "forma_vida": [" Tufo ", None, "Tapete"],
            "observacao": [None, None, None],
            "identificacao": ["1", "1", "1"],
            "filo": ["Bryophyta", "Bryophyta", "Bryophyta"],
            "familia": ["Pottiaceae", "Pottiaceae", "Pottiaceae"],
            "genero": ["Barbula", "Barbula", "Barbula"],
            "epiteto_especifico": ["indica", "indica", "indica"],
            "autor": ["Hedw.", "Hedw.", "Hedw."],
            "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
            "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
            "_source_row": [2, 3, 4],
        }

        _, result = _transform(columns)

        self.assertEqual(result[0]["forma_vida"], "Tufo")
        self.assertIsNone(result[1]["forma_vida"])
        self.assertEqual(result[2]["forma_vida"], "Tapete")
        # parcela continua com fill-down
        self.assertEqual(result[1]["parcela"], "4")

    def test_shuffled_input_gives_same_clean(self) -> None:
        # o fill-down segue (arquivo, linha), não a ordem em que o staging chega;
        # _source_row em texto cobre a ordem numérica ('10' < '9' como texto)
        columns = {
            "parcela": ["4", "5", None],
            "amostra": ["A1", None, None],
            "substrato": ["rocha", "cimento", None],
            "forma_vida": ["terrestre", None, None],
            "observacao": [None, None, None],
            "identificacao": ["1", "1", "1"],
            "filo": ["Bryophyta", "Bryophyta", "Bryophyta"],
            "familia": ["Pottiaceae", "Pottiaceae", "Pottiaceae"],
            "genero": ["Barbula", "Barbula", "Barbula"],
            "epiteto_especifico": ["indica", "indica", "indica"],
            "autor": ["Hedw.", "Hedw.", "Hedw."],
            "_source_file": ["SPP.xlsx", "SPP.xlsx", "SPP.xlsx"],
            "_source_sheet": ["Planilha1", "Planilha1", "Planilha1"],
            "_source_row": ["8", "9", "10"],
        }
        shuffled = _reorder(columns, [2, 0, 1])

        expected = _transform(columns, source_row_type="VARCHAR")
        actual = _transform(shuffled, source_row_type="VARCHAR")

        # tipos das colunas e linhas, na ordem da saída
        self.assertEqual(expected, actual)
        last = next(row for row in actual[1] if row["_source_row"] == "10")
        self.assertEqual(last["parcela"], "5")
        self.assertEqual(last["amostra"], "A1")
        self.assertEqual(last["substrato"], "cimento")
