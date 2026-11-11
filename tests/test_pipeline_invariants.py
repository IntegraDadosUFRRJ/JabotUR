"""Invariantes dos ADRs conferidos no banco depois do pipeline completo.

Só roda num banco cujo nome termina em "_test" e com as planilhas reais em data/:
    POSTGRES_DB=jabotur_test python -m unittest discover -s tests -v
Sem isso os testes de invariantes são pulados; os testes da guarda rodam sempre.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

import scripts.config as config
from scripts import run_pipeline
from scripts.db import db_utils
from scripts.transforms.scientific_name import (
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
)
from tests import db_test_support

FINAL_TABLES = [
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
    config.TB_SECTOR,
    config.TB_REPRODUCTIVE_STATUS,
    config.TB_OCCURRENCE,
    config.TB_OCCURRENCE_BRYOPHYTE,
    config.TB_OCCURRENCE_ARBORETUM,
    config.TB_COLETA_SUBSTRATO,
    config.TB_COLETA_OBSERVACAO,
    config.TB_BIBLIOGRAPHIC_CITATION,
]

STAGE_TO_CLEAN = [
    (config.STG_SPP_TABLE, config.CLN_SPP_TABLE),
    (config.STG_ARBORETO_CITATIONS_TABLE, config.CLN_ARBORETO_CITATIONS_TABLE),
    (config.STG_ARBORETO_SPECIMENS_TABLE, config.CLN_ARBORETO_SPECIMENS_TABLE),
]

# Só as fontes cujo clean tem parse_status e needs_review; o SPP ainda não tem
FLAGGED_CLEAN_TABLES = [
    config.CLN_ARBORETO_CITATIONS_TABLE,
    config.CLN_ARBORETO_SPECIMENS_TABLE,
]

# (filho, coluna, pai): cada relação tem FK no schema.sql e consulta de órfãos aqui
REFERENCES = [
    (config.TB_FAMILIA, "id_filo", config.TB_FILO),
    (config.TB_GENERO, "id_familia", config.TB_FAMILIA),
    (config.TB_EPITETO_ESPECIFICO, "id_genero", config.TB_GENERO),
    (config.TB_EPITETO_ESPECIFICO, "id_autor", config.TB_AUTOR),
    (config.TB_OCCURRENCE, "id_species", config.TB_EPITETO_ESPECIFICO),
    (config.TB_OCCURRENCE_BRYOPHYTE, "id", config.TB_OCCURRENCE),
    (config.TB_OCCURRENCE_BRYOPHYTE, "id_forma", config.TB_FORMA_VIDA),
    (config.TB_OCCURRENCE_BRYOPHYTE, "id_identificacao", config.TB_IDENTIFICACAO),
    (config.TB_OCCURRENCE_BRYOPHYTE, "id_parcela", config.TB_PARCELA),
    (config.TB_OCCURRENCE_ARBORETUM, "id", config.TB_OCCURRENCE),
    (config.TB_OCCURRENCE_ARBORETUM, "id_reproductive_status", config.TB_REPRODUCTIVE_STATUS),
    (config.TB_OCCURRENCE_ARBORETUM, "id_sector", config.TB_SECTOR),
    (config.TB_COLETA_SUBSTRATO, "id_briofita", config.TB_OCCURRENCE_BRYOPHYTE),
    (config.TB_COLETA_SUBSTRATO, "id_substrato", config.TB_SUBSTRATO),
    (config.TB_COLETA_OBSERVACAO, "id_briofita", config.TB_OCCURRENCE_BRYOPHYTE),
    (config.TB_COLETA_OBSERVACAO, "id_observacao", config.TB_OBSERVACAO),
    (config.TB_BIBLIOGRAPHIC_CITATION, "id_species", config.TB_EPITETO_ESPECIFICO),
]

KNOWN_PARSE_STATUSES = {
    PARSE_STATUS_OK,
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_UNPARSEABLE,
    config.PARSE_STATUS_TOTAL_ROW,
}

# Comparados após lower(trim()); "NA" não entra porque é código IUCN válido (ADR-0005)
PLACEHOLDERS = sorted(
    {"", "n/a", "-", "sem identificação", "sem observações registradas"}
)

SKIP_REASON = db_test_support.invariants_skip_reason()


def _scalar(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


class TestDatabaseGuard(unittest.TestCase):
    """Roda sempre, sem banco: a guarda recusa antes de qualquer conexão.

    O run_pipeline é importado no topo do arquivo: se o import acontecesse aqui,
    durante o patch, o "from ... import init_postgres" dele guardaria o mock e a
    suíte de invariantes rodaria depois sem aplicar o schema.sql.
    """

    def test_refuses_non_test_database(self):
        with mock.patch.object(config, "POSTGRES_DB", "jabotur"), \
                mock.patch.object(db_test_support.init_postgres_module, "init_postgres") as init_mock, \
                mock.patch.object(db_test_support.db_utils, "get_connection") as conn_mock, \
                mock.patch.object(run_pipeline, "main") as pipeline_mock:
            with self.assertRaises(RuntimeError):
                db_test_support.reset_schema()
            with self.assertRaises(RuntimeError):
                db_test_support.run_pipeline_once()
            init_mock.assert_not_called()
            conn_mock.assert_not_called()
            pipeline_mock.assert_not_called()

    def test_skip_reason_for_non_test_database(self):
        with mock.patch.object(config, "POSTGRES_DB", "jabotur"):
            self.assertIsNotNone(db_test_support.invariants_skip_reason())


@unittest.skipUnless(SKIP_REASON is None, SKIP_REASON or "")
class TestPipelineInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_test_support.reset_schema()
        cls.engine = db_utils.get_connection()

        db_test_support.run_pipeline_once()
        with cls.engine.connect() as conn:
            cls.first_snapshot = db_test_support.table_snapshot(conn, FINAL_TABLES)
            cls.first_layer_counts = db_test_support.table_snapshot(
                conn, [t for pair in STAGE_TO_CLEAN for t in pair]
            )

        db_test_support.run_pipeline_once()
        with cls.engine.connect() as conn:
            cls.second_snapshot = db_test_support.table_snapshot(conn, FINAL_TABLES)
            cls.second_layer_counts = db_test_support.table_snapshot(
                conn, [t for pair in STAGE_TO_CLEAN for t in pair]
            )

    @classmethod
    def tearDownClass(cls):
        # Relatório informativo: não falha, só deixa a mudança de número visível na revisão
        lines = ["", "== Relatório de sinalização (informativo) =="]
        with cls.engine.connect() as conn:
            for table in FLAGGED_CLEAN_TABLES:
                rows = conn.execute(
                    text(
                        f'SELECT parse_status, needs_review, count(*) FROM "{table}" '
                        f"GROUP BY 1, 2 ORDER BY 1, 2"
                    )
                ).all()
                lines.append(f"{table}: parse_status/needs_review = {[tuple(r) for r in rows]}")
            for table in [config.CLN_SPP_TABLE, *FLAGGED_CLEAN_TABLES]:
                null_author = _scalar(conn, f'SELECT count(*) FROM "{table}" WHERE autor IS NULL')
                lines.append(f"{table}: autor nulo = {null_author}")
            lines.append(
                f"{config.TB_EPITETO_ESPECIFICO}: id_autor nulo = "
                f"{_scalar(conn, f'SELECT count(*) FROM {config.TB_EPITETO_ESPECIFICO} WHERE id_autor IS NULL')}"
            )
        print("\n".join(lines), file=sys.stderr)
        cls.engine.dispose()

    # --- Contagens por fonte: nenhuma linha some entre as camadas ---

    def test_staging_equals_clean(self):
        for stg, cln in STAGE_TO_CLEAN:
            with self.subTest(stg=stg):
                # > 0 para uma extração vazia não passar como 0 = 0
                self.assertGreater(self.second_layer_counts[stg][0], 0)
                self.assertEqual(self.second_layer_counts[stg][0], self.second_layer_counts[cln][0])

    def test_citations_clean_equals_loaded_plus_total_rows(self):
        with self.engine.connect() as conn:
            cln = _scalar(conn, f'SELECT count(*) FROM "{config.CLN_ARBORETO_CITATIONS_TABLE}"')
            total_rows = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.CLN_ARBORETO_CITATIONS_TABLE}" WHERE parse_status = :s',
                s=config.PARSE_STATUS_TOTAL_ROW,
            )
            loaded = _scalar(conn, f'SELECT count(*) FROM "{config.TB_BIBLIOGRAPHIC_CITATION}"')
        self.assertGreater(loaded, 0)
        self.assertEqual(cln, loaded + total_rows)

    def test_specimens_clean_equals_loaded(self):
        with self.engine.connect() as conn:
            cln = _scalar(conn, f'SELECT count(*) FROM "{config.CLN_ARBORETO_SPECIMENS_TABLE}"')
            occurrences = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.TB_OCCURRENCE}" WHERE basis_of_record = :b',
                b=config.ARBORETO_SPECIMENS_BASIS_OF_RECORD,
            )
            satellites = _scalar(conn, f'SELECT count(*) FROM "{config.TB_OCCURRENCE_ARBORETUM}"')
        self.assertGreater(cln, 0)
        self.assertEqual(cln, occurrences)
        self.assertEqual(cln, satellites)

    def test_spp_clean_equals_loaded(self):
        with self.engine.connect() as conn:
            cln = _scalar(conn, f'SELECT count(*) FROM "{config.CLN_SPP_TABLE}"')
            occurrences = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.TB_OCCURRENCE}" WHERE basis_of_record = :b',
                b=config.SPP_BASIS_OF_RECORD,
            )
            satellites = _scalar(conn, f'SELECT count(*) FROM "{config.TB_OCCURRENCE_BRYOPHYTE}"')
        self.assertGreater(cln, 0)
        self.assertEqual(cln, occurrences)
        self.assertEqual(cln, satellites)

    def test_every_occurrence_has_exactly_one_satellite(self):
        with self.engine.connect() as conn:
            bad = _scalar(
                conn,
                f"""
                SELECT count(*) FROM "{config.TB_OCCURRENCE}" o
                WHERE (EXISTS (SELECT 1 FROM "{config.TB_OCCURRENCE_ARBORETUM}" a WHERE a.id = o.id))::int
                    + (EXISTS (SELECT 1 FROM "{config.TB_OCCURRENCE_BRYOPHYTE}" b WHERE b.id = o.id))::int
                    <> 1
                """,
            )
        self.assertEqual(bad, 0)

    # --- Idempotência: a segunda rodada não muda nada ---

    def test_second_run_changes_no_final_table(self):
        for table in FINAL_TABLES:
            with self.subTest(table=table):
                # Tabela vazia daria md5 NULL nas duas rodadas e passaria sem comparar nada
                self.assertGreater(self.first_snapshot[table][0], 0)
                self.assertEqual(self.first_snapshot[table], self.second_snapshot[table])

    def test_second_run_keeps_layer_counts(self):
        for table, (count, _) in self.first_layer_counts.items():
            with self.subTest(table=table):
                self.assertEqual(count, self.second_layer_counts[table][0])

    # --- Integridade ---

    def test_no_orphan_references(self):
        with self.engine.connect() as conn:
            for child, column, parent in REFERENCES:
                with self.subTest(reference=f"{child}.{column} -> {parent}"):
                    orphans = _scalar(
                        conn,
                        f'SELECT count(*) FROM "{child}" c LEFT JOIN "{parent}" p ON p.id = c."{column}" '
                        f'WHERE p.id IS NULL AND c."{column}" IS NOT NULL',
                    )
                    self.assertEqual(orphans, 0)

    def test_every_reference_has_foreign_key(self):
        # Igualdade, não inclusão: FK fora da lista também aparece, e a lista de
        # órfãos e as FKs do schema.sql não se separam
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT c.conrelid::regclass::text, a.attname, c.confrelid::regclass::text, "
                    "fa.attname, cardinality(c.conkey) "
                    "FROM pg_constraint c "
                    "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1] "
                    "JOIN pg_attribute fa ON fa.attrelid = c.confrelid AND fa.attnum = c.confkey[1] "
                    "WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace"
                )
            ).all()
        for child, column, parent, parent_column, n_columns in rows:
            with self.subTest(foreign_key=f"{child}.{column} -> {parent}"):
                self.assertEqual(n_columns, 1)
                self.assertEqual(parent_column, "id")
        self.assertEqual({(child, column, parent) for child, column, parent, _, _ in rows}, set(REFERENCES))
        # o conjunto esconderia uma FK duplicada
        self.assertEqual(len(rows), len(REFERENCES))

    def test_origin_is_unique(self):
        # ADR-0007: a origem identifica a linha da planilha
        with self.engine.connect() as conn:
            for table in (config.TB_OCCURRENCE, config.TB_BIBLIOGRAPHIC_CITATION):
                with self.subTest(table=table):
                    duplicates = _scalar(
                        conn,
                        f'SELECT count(*) FROM (SELECT 1 FROM "{table}" '
                        f"GROUP BY origin_file, COALESCE(origin_sheet, ''), origin_row "
                        f"HAVING count(*) > 1) d",
                    )
                    self.assertEqual(duplicates, 0)

    def test_citation_origin_sheet_is_not_null(self):
        # ADR-0007: em citações a aba faz parte da origem. Não há índice único em
        # bibliographic_citation, e o COALESCE acima esconderia a aba perdida
        with self.engine.connect() as conn:
            without_sheet = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.TB_BIBLIOGRAPHIC_CITATION}" WHERE origin_sheet IS NULL',
            )
        self.assertEqual(without_sheet, 0)

    def test_spp_origin_is_file_and_row(self):
        # O SPP não grava aba: a origem dele é só (arquivo, linha)
        with self.engine.connect() as conn:
            with_sheet = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.TB_OCCURRENCE}" '
                f"WHERE basis_of_record = :b AND origin_sheet IS NOT NULL",
                b=config.SPP_BASIS_OF_RECORD,
            )
            duplicates = _scalar(
                conn,
                f'SELECT count(*) FROM (SELECT 1 FROM "{config.TB_OCCURRENCE}" WHERE basis_of_record = :b '
                f"GROUP BY origin_file, origin_row HAVING count(*) > 1) d",
                b=config.SPP_BASIS_OF_RECORD,
            )
        self.assertEqual(with_sheet, 0)
        self.assertEqual(duplicates, 0)

    # --- Regras dos ADRs ---

    def test_no_placeholders_in_final_text_columns(self):
        # ADR-0008: ausência é NULL, nunca texto de preenchimento
        with self.engine.connect() as conn:
            columns = conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND data_type = 'text' "
                    "AND table_name = ANY(:tables) ORDER BY 1, 2"
                ),
                {"tables": FINAL_TABLES},
            ).all()
            self.assertTrue(columns)
            for table, column in columns:
                with self.subTest(column=f"{table}.{column}"):
                    found = conn.execute(
                        text(
                            f'SELECT DISTINCT "{column}" FROM "{table}" '
                            f'WHERE lower(trim("{column}")) = ANY(:placeholders)'
                        ),
                        {"placeholders": PLACEHOLDERS},
                    ).scalars().all()
                    self.assertEqual(found, [])

    def test_parse_status_is_known(self):
        with self.engine.connect() as conn:
            for table in FLAGGED_CLEAN_TABLES:
                with self.subTest(table=table):
                    statuses = set(
                        conn.execute(text(f'SELECT DISTINCT parse_status FROM "{table}"')).scalars()
                    )
                    self.assertLessEqual(statuses, KNOWN_PARSE_STATUSES)

    def test_unparseable_needs_review(self):
        unparseable_total = 0
        with self.engine.connect() as conn:
            for table in FLAGGED_CLEAN_TABLES:
                unparseable_total += _scalar(
                    conn,
                    f'SELECT count(*) FROM "{table}" WHERE parse_status = :s',
                    s=PARSE_STATUS_UNPARSEABLE,
                )
                with self.subTest(table=table):
                    unflagged = _scalar(
                        conn,
                        f'SELECT count(*) FROM "{table}" '
                        f"WHERE parse_status = :s AND needs_review IS NOT TRUE",
                        s=PARSE_STATUS_UNPARSEABLE,
                    )
                    self.assertEqual(unflagged, 0)
        # Somado entre as fontes: uma fonte sem unparseable é válida, nenhuma não testa nada
        self.assertGreater(unparseable_total, 0)

    def test_total_rows_are_not_flagged(self):
        # ADR-0012: a linha de totais não representa um táxon, então não entra na lista dos curadores
        with self.engine.connect() as conn:
            total_rows = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.CLN_ARBORETO_CITATIONS_TABLE}" WHERE parse_status = :s',
                s=config.PARSE_STATUS_TOTAL_ROW,
            )
            flagged = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.CLN_ARBORETO_CITATIONS_TABLE}" '
                f"WHERE parse_status = :s AND needs_review IS NOT FALSE",
                s=config.PARSE_STATUS_TOTAL_ROW,
            )
        self.assertGreater(total_rows, 0)
        self.assertEqual(flagged, 0)

    def test_no_sp_as_specific_epithet(self):
        with self.engine.connect() as conn:
            sp = _scalar(
                conn,
                f'SELECT count(*) FROM "{config.TB_EPITETO_ESPECIFICO}" '
                f"WHERE lower(trim(nome)) IN ('sp', 'sp.')",
            )
        self.assertEqual(sp, 0)

    def test_null_species_occurrences_are_unparseable_specimens(self):
        # Comparação de conjuntos de origem, não só de contagem
        with self.engine.connect() as conn:
            loaded = set(
                conn.execute(
                    text(
                        f'SELECT origin_file, origin_sheet, origin_row::bigint FROM "{config.TB_OCCURRENCE}" '
                        f"WHERE id_species IS NULL"
                    )
                ).all()
            )
            unparseable = set(
                conn.execute(
                    text(
                        f'SELECT _source_file, _source_sheet, _source_row::bigint '
                        f'FROM "{config.CLN_ARBORETO_SPECIMENS_TABLE}" WHERE parse_status = :s'
                    ),
                    {"s": PARSE_STATUS_UNPARSEABLE},
                ).all()
            )
        self.assertTrue(unparseable)
        self.assertEqual(loaded, unparseable)

    def test_no_duplicate_species_including_null_author(self):
        # GROUP BY trata NULLs como iguais, então pega o autor NULL que os índices parciais deixam passar
        with self.engine.connect() as conn:
            duplicates = conn.execute(
                text(
                    f'SELECT id_genero, nome, infraespecifico, id_autor, count(*) '
                    f'FROM "{config.TB_EPITETO_ESPECIFICO}" '
                    f"GROUP BY 1, 2, 3, 4 HAVING count(*) > 1"
                )
            ).all()
        self.assertEqual(duplicates, [])

    # --- Coerência da sinalização (sem teto: needs_review é a lista dos curadores) ---

    def test_flagged_rows_have_origin_and_status(self):
        with self.engine.connect() as conn:
            for table in FLAGGED_CLEAN_TABLES:
                with self.subTest(table=table):
                    incoherent = _scalar(
                        conn,
                        f'SELECT count(*) FROM "{table}" WHERE needs_review '
                        f"AND (_source_file IS NULL OR _source_sheet IS NULL "
                        f"OR _source_row IS NULL OR parse_status IS NULL)",
                    )
                    self.assertEqual(incoherent, 0)

    def test_parse_status_counts_add_up_to_total(self):
        with self.engine.connect() as conn:
            for table in FLAGGED_CLEAN_TABLES:
                with self.subTest(table=table):
                    total = _scalar(conn, f'SELECT count(*) FROM "{table}"')
                    by_status = _scalar(
                        conn,
                        f'SELECT sum(n) FROM (SELECT count(*) AS n FROM "{table}" '
                        f"WHERE parse_status IS NOT NULL GROUP BY parse_status) s",
                    )
                    self.assertEqual(by_status, total)


if __name__ == "__main__":
    unittest.main()
