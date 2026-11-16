import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import config
from scripts.clean import clean_arboretum_citations, duckdb_parsers
from scripts.load import load_arboretum_citations, taxonomy
from scripts.staging import stage_arboretum_citations
from scripts.transforms.scientific_name import (
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
    parse_scientific_name,
)

CONTROL_COLUMNS = [
    config.ARBORETUM_CITATION_COL_FAMILY_RAW,
    "previous_quantity_sum",
    "is_total_row",
]


# --- dados de entrada (num lugar só, compartilhados pelos testes) ---

def _staging_rows():
    """(aba, linha, family, species_raw, quantity) no formato do staging."""
    return [
        # aba com totais (soma 2 + 3 = 5)
        ("A", 2, "Fabaceae", "Inga edulis Mart.", "2"),
        ("A", 3, None, "Inga vera Willd.", "3"),
        ("A", 4, None, None, "5"),
        # aba sem totais (a última linha é um registro real)
        ("B", 2, "Rutaceae", "Citrus limon (L.) Osbeck", "1"),
        ("B", 3, "Verbenaceae", "Citharexylum myrianthum Cham.", "4"),
        # aba com linha vazia cuja quantidade NÃO bate com a soma
        ("C", 2, "Fabaceae", "Inga edulis Mart.", "2"),
        ("C", 3, None, None, "99"),
    ]


def _ordering_rows():
    """_staging_rows() mais uma aba com família em branco na linha 10, herdada da 9."""
    return _staging_rows() + [
        ("D", 9, "Malvaceae", "Pachira aquatica Aubl.", "1"),
        ("D", 10, None, "Pachira glabra Pasq.", "1"),
    ]


# Um nome de cada classe do parser e as formas de quantidade que o clean não aceita
NAMES_BY_STATUS = {
    PARSE_STATUS_OK: "Inga edulis Mart.",
    PARSE_STATUS_MORPHOSPECIES: "Morfo-Espécie 1",
    PARSE_STATUS_GENUS_ONLY: "Inga sp.",
    PARSE_STATUS_UNPARSEABLE: "???",
}
# None é a célula ausente, que o staging guarda como NULL
INVALID_QUANTITIES = ["abc", "NaN", "inf", "", None]


def _invalid_quantity_rows():
    """Cada nome com cada quantidade inválida, em duas abas que repetem os mesmos
    números de linha: só a chave (arquivo, aba, linha) identifica a linha."""
    rows = []
    sheets = ["X", "Y"]
    for i, quantity in enumerate(INVALID_QUANTITIES):
        sheet = sheets[i % 2]
        for j, name in enumerate(NAMES_BY_STATUS.values()):
            source_row = 2 + (i // 2) * len(NAMES_BY_STATUS) + j
            family = "Fabaceae" if source_row == 2 else None
            rows.append((sheet, source_row, family, name, quantity))
    return rows


def _load_staging(con, rows, source_row_type="BIGINT"):
    """Tabela no formato do staging no lugar da view que, no pipeline, vem do Postgres."""
    con.execute(
        f"""
        CREATE TABLE {config.DUCKDB_STAGING_ALIAS} (
            _source_file VARCHAR,
            _source_sheet VARCHAR,
            _source_row {source_row_type},
            family VARCHAR,
            species_raw VARCHAR,
            quantity VARCHAR
        )
        """
    )
    con.executemany(
        f"INSERT INTO {config.DUCKDB_STAGING_ALIAS} VALUES ('teste.xlsx', ?, ?, ?, ?, ?)", rows
    )


def _transform(rows, source_row_type="BIGINT"):
    """Conexão com a saída do clean gravada na tabela "result"; quem chama a fecha."""
    con = duckdb.connect()
    try:
        _load_staging(con, rows, source_row_type)
        clean_arboretum_citations.transform(con).create("result")
    except BaseException:
        con.close()
        raise
    return con


def _transform_rows(rows):
    """Saída do clean como as linhas que o load lê com db_utils.read_rows
    (timestamptz como texto, porque o pytz não está instalado)."""
    con = duckdb.connect()
    try:
        _load_staging(con, rows)
        result = clean_arboretum_citations.transform(con)
        select = ", ".join(
            f'CAST("{col}" AS VARCHAR) AS "{col}"' if str(col_type) == "TIMESTAMP WITH TIME ZONE" else f'"{col}"'
            for col, col_type in zip(result.columns, result.types)
        )
        projected = result.project(select)
        return [dict(zip(projected.columns, row)) for row in projected.fetchall()]
    finally:
        con.close()


def _write_mini_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Aba1"
    ws.append(["Família", "Espécie", "Quant"])
    ws.append(["Fabaceae", "Inga edulis Mart.", 2])
    ws.append([None, "Inga vera Willd.", 3])
    ws.append([None, None, 5])
    wb.save(path)


def _flags(con):
    """Colunas independentes da ordem de entrada, ordenadas por (aba, linha)."""
    return con.execute(
        """
        SELECT _source_sheet, _source_row, parse_status, needs_review, reconcile_across_sources
        FROM result
        ORDER BY _source_sheet, _source_row
        """
    ).fetchall()


def _families(con):
    """Família após o fill-down, ordenada por (aba, linha)."""
    return con.execute(
        """
        SELECT _source_sheet, _source_row, family
        FROM result
        ORDER BY _source_sheet, _source_row
        """
    ).fetchall()


def _family_at(con, sheet, row):
    return con.execute(
        f"""
        SELECT family FROM result
        WHERE _source_sheet = '{sheet}' AND CAST(_source_row AS INTEGER) = {row}
        """
    ).fetchone()[0]


class TotalRowTests(unittest.TestCase):
    def _clean(self, rows, source_row_type="BIGINT"):
        con = _transform(rows, source_row_type)
        self.addCleanup(con.close)
        return con

    def test_sheet_with_matching_total(self):
        cleaned = self._clean(_staging_rows())
        self.assertEqual(cleaned.execute("SELECT count(*) FROM result").fetchone()[0], 7)

        total = cleaned.execute(
            """
            SELECT parse_status, needs_review, reconcile_across_sources
            FROM result
            WHERE _source_sheet = 'A' AND _source_row = 4
            """
        ).fetchone()
        self.assertEqual(total, (config.PARSE_STATUS_TOTAL_ROW, False, False))

    def test_sheet_without_total_keeps_last_row(self):
        cleaned = self._clean(_staging_rows())
        b_count, total_in_b = cleaned.execute(
            """
            SELECT 
                count(*),
                count(*) FILTER (WHERE parse_status = 'total_row')
            FROM result
            WHERE _source_sheet = 'B'
            """
        ).fetchone()

        self.assertEqual(b_count, 2)
        self.assertEqual(total_in_b, 0)
        last = cleaned.execute(
            """
            SELECT genus, parse_status
            FROM result
            WHERE _source_sheet = 'B' AND _source_row = 3
            """
        ).fetchone()
        self.assertEqual(last, ("Citharexylum", "ok"))

    def test_unparseable_and_total_rows_do_not_reconcile(self):
        # ADR-0003 (unparseable) e ADR-0012 (total_row): nenhuma reconcilia entre fontes
        cleaned = self._clean(_staging_rows())
        flags = cleaned.execute(
            """
            SELECT _source_sheet, _source_row, parse_status, reconcile_across_sources
            FROM result
            WHERE (_source_sheet = 'A' AND _source_row = 4)
               OR (_source_sheet = 'C' AND _source_row = 3)
               OR (_source_sheet = 'B' AND _source_row = 3)
            ORDER BY _source_sheet, _source_row
            """
        ).fetchall()
        self.assertEqual(
            flags,
            [
                ("A", 4, config.PARSE_STATUS_TOTAL_ROW, False),
                ("B", 3, "ok", True),
                ("C", 3, "unparseable", False),
            ],
        )

    def test_empty_row_with_mismatching_sum_is_unparseable(self):
        cleaned = self._clean(_staging_rows())

        mismatch = cleaned.execute(
            """
            SELECT parse_status, needs_review
            FROM result
            WHERE _source_sheet = 'C' AND _source_row = 3
            """
        ).fetchone()
        self.assertEqual(mismatch, ("unparseable", True))

        total_rows_count = cleaned.execute(
            f"""
            SELECT count(*)
            FROM result
            WHERE parse_status = '{config.PARSE_STATUS_TOTAL_ROW}'
            """
        ).fetchone()[0]
        self.assertEqual(total_rows_count, 1)

    def test_shuffled_input_gives_same_clean(self):
        # o fill-down segue (arquivo, aba, linha), não a ordem em que o staging chega
        rows = _ordering_rows()
        shuffled = [rows[i] for i in (8, 4, 2, 6, 0, 7, 3, 1, 5)]

        expected = self._clean(rows)
        actual = self._clean(shuffled)

        self.assertEqual(_flags(expected), _flags(actual))
        self.assertEqual(_families(expected), _families(actual))
        self.assertEqual(_family_at(actual, "D", 10), "Malvaceae")

    def test_source_row_is_ordered_as_number(self):
        # com _source_row em texto, '10' < '9' e a linha 10 herdaria da aba C (Fabaceae)
        rows = _ordering_rows()
        shuffled = [rows[i] for i in (8, 7, 0, 1, 2, 3, 4, 5, 6)]
        cleaned = self._clean(shuffled, source_row_type="VARCHAR")

        self.assertEqual(_family_at(cleaned, "D", 10), "Malvaceae")

    def test_control_columns_not_in_output(self):
        cleaned = self._clean(_staging_rows())
        cols = [c[0] for c in cleaned.execute("DESCRIBE result").fetchall()]
        for column in CONTROL_COLUMNS:
            self.assertNotIn(column, cols)


class InvalidQuantityTests(unittest.TestCase):
    """Quantidade ausente ou inválida marca needs_review e mais nada: o parse_status é o
    do parser do nome, e só a linha de totais vence esse status."""

    STAGING_KEY = "_source_file, _source_sheet, _source_row"

    def _clean(self, rows):
        con = _transform(rows)
        self.addCleanup(con.close)
        return con

    def test_fixture_names_cover_each_parser_status(self):
        for status, name in NAMES_BY_STATUS.items():
            with self.subTest(name=name):
                self.assertEqual(parse_scientific_name(name)["parse_status"], status)

    def test_name_status_wins_over_invalid_quantity(self):
        cleaned = self._clean(_invalid_quantity_rows())
        rows = cleaned.execute(
            f"""
            SELECT s.species_raw, s.quantity, r.parse_status, r.needs_review, r.quantity,
                   r.genus, r.reconcile_across_sources
            FROM result r
            JOIN {config.DUCKDB_STAGING_ALIAS} s USING (_source_file, _source_sheet, _source_row)
            ORDER BY r._source_sheet, r._source_row
            """
        ).fetchall()
        self.assertEqual(len(rows), len(INVALID_QUANTITIES) * len(NAMES_BY_STATUS))
        for name, quantity_raw, status, needs_review, quantity, genus, reconcile in rows:
            with self.subTest(name=name, quantity=quantity_raw):
                self.assertEqual(status, parse_scientific_name(name)["parse_status"])
                self.assertTrue(needs_review)
                self.assertIsNone(quantity)
                if status == PARSE_STATUS_MORPHOSPECIES:
                    self.assertIsNone(genus)
                if status in (PARSE_STATUS_MORPHOSPECIES, PARSE_STATUS_UNPARSEABLE):
                    self.assertFalse(reconcile)
                else:
                    # a quantidade não impede o nome de reconciliar entre fontes
                    self.assertTrue(reconcile)

    def test_invalid_quantity_is_recovered_from_staging(self):
        # O clean não guarda a quantidade original; o motivo da sinalização se lê
        # no staging, pela chave completa da linha
        rows = _invalid_quantity_rows()
        cleaned = self._clean(rows)
        for table in ("result", config.DUCKDB_STAGING_ALIAS):
            total, distinct_keys, distinct_rows = cleaned.execute(
                f"SELECT count(*), count(DISTINCT ({self.STAGING_KEY})), "
                f"count(DISTINCT _source_row) FROM {table}"
            ).fetchone()
            with self.subTest(table=table):
                self.assertEqual(total, len(rows))
                self.assertEqual(distinct_keys, total)
                # só a linha se repete entre abas: a junção precisa da chave inteira
                self.assertLess(distinct_rows, total)

        recovered = cleaned.execute(
            f"""
            SELECT s._source_sheet, s._source_row, s.quantity
            FROM result r
            JOIN {config.DUCKDB_STAGING_ALIAS} s USING (_source_file, _source_sheet, _source_row)
            WHERE r.needs_review AND r.quantity IS NULL
            ORDER BY s._source_sheet, s._source_row
            """
        ).fetchall()
        expected = sorted((sheet, row, quantity) for sheet, row, _, _, quantity in rows)
        self.assertEqual(recovered, expected)

    def test_total_row_wins_over_name_and_quantity(self):
        # a linha 3 tem quantidade inválida, que soma 0; a linha 4 fecha a aba com a
        # soma das anteriores e, sem nome, o parser a daria como unparseable
        cleaned = self._clean(
            [
                ("T", 2, "Fabaceae", "Inga edulis Mart.", "2"),
                ("T", 3, None, "Morfo-Espécie 1", "abc"),
                ("T", 4, None, None, "2"),
            ]
        )
        self.assertEqual(
            _flags(cleaned),
            [
                ("T", 2, PARSE_STATUS_OK, False, True),
                ("T", 3, PARSE_STATUS_MORPHOSPECIES, True, False),
                ("T", 4, config.PARSE_STATUS_TOTAL_ROW, False, False),
            ],
        )

    def test_clean_keeps_every_staging_row(self):
        rows = _invalid_quantity_rows() + _staging_rows()
        cleaned = self._clean(rows)
        self.assertEqual(cleaned.execute("SELECT count(*) FROM result").fetchone()[0], len(rows))


class RegisteredParserTests(unittest.TestCase):
    """Parser registrado no DuckDB: recebe NULL, uma exceção interrompe o clean e um
    retorno fora do STRUCT declarado é recusado."""

    def setUp(self):
        self.con = duckdb.connect()

    def tearDown(self):
        self.con.close()

    def test_null_reaches_parser(self):
        # NULL também é passado ao parser, que devolve unparseable (e não NULL)
        duckdb_parsers.register_scientific_name_parser(self.con)
        status = self.con.execute(
            f"SELECT {duckdb_parsers.SCIENTIFIC_NAME_FUNCTION}(NULL).parse_status"
        ).fetchone()[0]
        self.assertEqual(status, PARSE_STATUS_UNPARSEABLE)

    def test_parser_exception_stops_clean(self):
        def broken_parser(_):
            raise ValueError("parser quebrou")

        with mock.patch.object(duckdb_parsers, "parse_scientific_name", broken_parser):
            with self.assertRaisesRegex(duckdb.Error, "parser quebrou"):
                _transform(_staging_rows()).close()

    def test_return_outside_declared_struct_is_refused(self):
        with mock.patch.object(
            duckdb_parsers, "parse_scientific_name", lambda value: {"name_raw": value}
        ):
            with self.assertRaisesRegex(duckdb.Error, "devolveu as chaves"):
                _transform(_staging_rows()).close()


class StagingTests(unittest.TestCase):
    def test_staging_preserves_all_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.xlsx"
            _write_mini_xlsx(path)

            with mock.patch.object(config, "ARBORETO_XLSX_PATH", path), \
                 mock.patch.object(config, "ARBORETUM_CITATION_SHEETS", ["Aba1"]):
                query = stage_arboretum_citations.citations_query()

            con = duckdb.connect()
            con.execute("LOAD excel")
            rows = con.execute(
                f"""
                SELECT _source_row, quantity
                FROM ({query})
                ORDER BY _source_row
                """
            ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual([r[0] for r in rows], [2, 3, 4])
        self.assertEqual(rows[-1][1], "5")


class LoadPrepareTests(unittest.TestCase):
    def test_prepare_drops_total_rows_and_logs(self):
        # A linha de totais (A#4) fica no meio da leitura: as linhas da aba C provam que o
        # índice não é renumerado depois do filtro
        cleaned = _transform_rows(
            [
                ("A", 2, "Fabaceae", "Inga edulis Mart.", "2"),
                ("A", 3, None, "Morfo-Espécie 1", "3"),
                ("A", 4, None, None, "5"),
                ("C", 2, "Fabaceae", "Inga edulis Mart.", "2"),
                ("C", 3, None, None, "99"),
            ]
        )
        with mock.patch("builtins.print") as fake_print:
            prepared = load_arboretum_citations.prepare(cleaned)

        self.assertEqual([(row["source_sheet"], row["source_row"]) for row in prepared],
                         [("A", 2), ("A", 3), ("C", 2), ("C", 3)])
        # o índice dos logs conta a linha de totais descartada (posição na leitura do clean)
        self.assertEqual([row["clean_index"] for row in prepared], [0, 1, 3, 4])
        by_origin = {(row["source_sheet"], row["source_row"]): row for row in prepared}
        # morfo-espécie não reconcilia: recebe a origem no nome
        self.assertFalse(by_origin[("A", 3)]["reconcile_across_sources"])
        self.assertTrue(by_origin[("A", 3)]["epithet"].endswith(" [A#3]"))
        # unparseable sem espécie também não reconcilia, e o epíteto NULL continua NULL
        self.assertEqual(by_origin[("C", 3)]["parse_status"], PARSE_STATUS_UNPARSEABLE)
        self.assertFalse(by_origin[("C", 3)]["reconcile_across_sources"])
        self.assertIsNone(by_origin[("C", 3)]["epithet"])
        logged = [str(call.args[0]) for call in fake_print.call_args_list]
        self.assertEqual(logged, ["[load_arboretum_citations] linha 2 (A#4): linha de totais, ignorada"])

    def test_morphospecies_without_quantity_becomes_citation(self):
        # Sem o Postgres anexado, os ids existentes vêm vazios (tabela inexistente):
        # o caminho de montagem do load roda inteiro numa conexão DuckDB vazia
        cleaned = _transform_rows(
            [
                ("A", 2, "Fabaceae", "Inga edulis Mart.", "2"),
                ("A", 3, None, "Morfo-Espécie 1", ""),
            ]
        )
        con = duckdb.connect()
        self.addCleanup(con.close)
        with mock.patch("builtins.print") as fake_print:
            rows = load_arboretum_citations.prepare(cleaned)
            phylum_dim, phylum_ids = taxonomy.build_phylum_rows(con, rows)
            family_dim, family_by_name = taxonomy.build_family_rows(con, rows, phylum_ids, phylum_dim)
            genus_dim, genus_by_name = taxonomy.build_genus_rows(con, rows, family_by_name, family_dim)
            _, author_ids = taxonomy.build_author_rows(con, rows)
            _, species_ids = taxonomy.build_species_rows(con, rows, genus_by_name, author_ids, genus_dim)
            citations = load_arboretum_citations.build_bibliographic_citation(con, rows, species_ids)

        by_origin = {(row["origin_sheet"], row["origin_row"]): row for row in citations}
        self.assertEqual(sorted(by_origin), [("A", 2), ("A", 3)])
        self.assertIsNone(by_origin[("A", 3)]["quantity"])
        self.assertIsNotNone(by_origin[("A", 3)]["id_species"])
        logged = [str(call.args[0]) for call in fake_print.call_args_list]
        self.assertFalse([line for line in logged if "pulando citação" in line])


if __name__ == "__main__":
    unittest.main()
