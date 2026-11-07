"""Apoio para os testes que rodam o pipeline num banco de teste.

Tudo que apaga dados passa por require_test_database(): só um banco cujo nome
termina em "_test" pode ser resetado, para o banco compartilhado nunca ser tocado.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import scripts.config as config
from scripts.db import db_utils
from scripts.db import init_postgres as init_postgres_module

TEST_DATABASE_SUFFIX = "_test"


def require_test_database() -> None:
    """Aborta se o banco alvo não for de teste; chamada antes de qualquer escrita."""
    if not config.POSTGRES_DB.endswith(TEST_DATABASE_SUFFIX):
        raise RuntimeError(
            f"Recusado: POSTGRES_DB={config.POSTGRES_DB!r} não termina em "
            f"{TEST_DATABASE_SUFFIX!r}; os testes de banco só rodam num banco de teste."
        )


def reset_schema() -> None:
    """Apaga e recria o schema public do banco de teste."""
    require_test_database()
    # O DROP vem antes do schema.sql: sobras de uma rodada anterior com outro formato
    # fariam o CREATE INDEX do schema.sql falhar. Se a conexão falhar (no caso
    # esperado, o banco ainda não existe no primeiro run), o init_postgres() cria o
    # banco; qualquer outra falha de conexão reaparece no init_postgres() ou no DROP.
    try:
        _drop_public_schema()
    except OperationalError:
        init_postgres_module.init_postgres()
        _drop_public_schema()


def _drop_public_schema() -> None:
    with db_utils.get_connection().begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def run_pipeline_once() -> None:
    """Roda o pipeline completo no mesmo processo (o config já leu o POSTGRES_DB)."""
    require_test_database()
    from scripts import run_pipeline

    run_pipeline.main()


def invariants_skip_reason() -> str | None:
    """Motivo para pular os testes de invariantes, ou None se dá para rodar."""
    if not config.POSTGRES_DB.endswith(TEST_DATABASE_SUFFIX):
        return (
            f"POSTGRES_DB={config.POSTGRES_DB!r} não é banco de teste; rode com "
            f"POSTGRES_DB={config.POSTGRES_DB}{TEST_DATABASE_SUFFIX}"
        )
    missing = [str(p) for p in (config.SPP_XLSX_PATH, config.ARBORETO_XLSX_PATH) if not p.exists()]
    if missing:
        return f"planilhas reais ausentes em data/: {', '.join(missing)}"
    return None


def table_snapshot(conn, tables: list[str]) -> dict[str, tuple[int, str | None]]:
    """Contagem e md5 das linhas inteiras de cada tabela, para comparar duas rodadas.

    O md5 cobre todas as colunas (t::text), então uma mudança em qualquer valor,
    não só no id, aparece na comparação.
    """
    snapshot = {}
    for table in tables:
        snapshot[table] = tuple(
            conn.execute(
                text(
                    f'SELECT count(*), md5(string_agg(t::text, E\'\\n\' ORDER BY t::text)) '
                    f'FROM "{table}" AS t'
                )
            ).one()
        )
    return snapshot
