"""Lê a tabela de staging no PostgreSQL e grava a tabela limpa no PostgreSQL.

Leitura, transformação e gravação acontecem dentro do DuckDB, com o Postgres anexado:
os dados não passam por DataFrame. A transformação combina:
  - SQL: fill-down de família, trim, cast de quantidade, linha de totais e flags;
  - Python para o parsing do nome científico, chamado pelo SQL como função registrada no DuckDB;
"""

from pathlib import Path

import duckdb

from scripts.clean import duckdb_parsers
from scripts.db.db_utils import postgres_duckdb, read_table, replace_table
import scripts.config as config

from scripts.transforms.scientific_name import (
    PARSE_STATUS_GENUS_ONLY,
    PARSE_STATUS_MORPHOSPECIES,
    PARSE_STATUS_OK,
    PARSE_STATUS_UNPARSEABLE,
)

UNPARSEABLE_QUANTIDADE = "unparseable_quantidade"
SQL_PATH = Path(__file__).with_name("clean_arboreto_citations.sql")

OUTPUT_COLUMNS = [
    "_source_file", "_source_sheet", "_source_row",
    "familia", "genero", "epiteto_especifico", "infraespecifico", "autor",
    "identification_qualifier",
    "quantidade", "nome_raw", "nome_normalizado",
    "parse_status", "reconcile_across_sources", "needs_review",
]


def create_staging_view(con: duckdb.DuckDBPyConnection) -> None:
    """Expõe o staging, na ordem da planilha, como a view lida pela query do clean."""
    read_table(
        con, config.STG_ARBORETO_CITATIONS_TABLE, order_by=config.ARBORETO_CITATION_STAGING_ORDER
    ).create_view(config.DUCKDB_STAGING_ALIAS)


def _staging_order_sql() -> str:
    # _source_row comparado como número: como texto, a linha 10 viria antes da 9
    return ", ".join(
        f"CAST({col} AS INTEGER)" if col == config.SOURCE_ROW_COL else col
        for col in config.ARBORETO_CITATION_STAGING_ORDER
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _full_query() -> str:
    # A query e o comentário-resumo dela estão em clean_arboreto_citations.sql; aqui só
    # entram os trechos que vêm do config.py e do parser. O resultado traz também as
    # colunas de controle da soma, que o log usa e a tabela limpa não grava.
    return SQL_PATH.read_text(encoding="utf-8").format(
        staging_order=_staging_order_sql(),
        family_raw_col=config.ARBORETO_CITATION_COL_FAMILY_RAW,
        parse_function=duckdb_parsers.SCIENTIFIC_NAME_FUNCTION,
        status_ok=_sql_literal(PARSE_STATUS_OK),
        status_genus_only=_sql_literal(PARSE_STATUS_GENUS_ONLY),
        status_morphospecies=_sql_literal(PARSE_STATUS_MORPHOSPECIES),
        status_unparseable=_sql_literal(PARSE_STATUS_UNPARSEABLE),
        status_total_row=_sql_literal(config.PARSE_STATUS_TOTAL_ROW),
        status_unparseable_quantidade=_sql_literal(UNPARSEABLE_QUANTIDADE),
    )


def _clean_query() -> str:
    columns = ", ".join(OUTPUT_COLUMNS)
    return f"SELECT {columns}, CURRENT_TIMESTAMP AS _cleaned_at FROM ({_full_query()}) ORDER BY rn"


def _log_control_sums(con: duckdb.DuckDBPyConnection) -> None:
    # Registra, por aba, se a soma de controle da linha de totais conferiu.
    # Só filtra e imprime: a soma e o flag is_total_row vêm da query.
    family_raw = config.ARBORETO_CITATION_COL_FAMILY_RAW
    full = _full_query()
    # abas na ordem em que aparecem na planilha
    sheets = con.execute(
        f"SELECT _source_file, _source_sheet FROM ({full}) "
        "GROUP BY _source_file, _source_sheet ORDER BY min(rn)"
    ).fetchall()
    candidates = con.execute(
        f"SELECT _source_file, _source_sheet, _source_row, quantidade, previous_quantity_sum, "
        f"is_total_row, parse_status FROM ({full}) "
        f"WHERE {family_raw} = '' AND especie_raw = '' AND quantidade IS NOT NULL ORDER BY rn"
    ).fetchall()
    for source_file, sheet in sheets:
        rows = [row for row in candidates if row[:2] == (source_file, sheet)]
        if not rows:
            print(f"[clean_arboreto_citations] aba '{sheet}': sem linha de totais.")
            continue
        for _, _, row_number, found, expected, is_total_row, parse_status in rows:
            if is_total_row:
                print(
                    f"[clean_arboreto_citations] aba '{sheet}' linha {row_number}: "
                    f"soma de controle conferiu ({found:g} == {expected:g})."
                )
            else:
                print(
                    f"[clean_arboreto_citations] aba '{sheet}' linha {row_number}: "
                    f"soma de controle NÃO conferiu (esperado {expected:g}, achei {found:g}); "
                    f"mantida como {parse_status}."
                )


def _prepare(con: duckdb.DuckDBPyConnection) -> str:
    """Registra o parser, registra o log da soma de controle e devolve a query do clean.

    Comum a transform() e clean_citations(), para os testes exercitarem o mesmo
    caminho do pipeline.
    """
    duckdb_parsers.register_scientific_name_parser(con)
    _log_control_sums(con)
    return _clean_query()


def transform(con: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyRelation:
    """Clean das Citações sobre a view config.DUCKDB_STAGING_ALIAS já registrada em con."""
    return con.sql(_prepare(con))


def clean_citations() -> None:
    with postgres_duckdb() as con:
        create_staging_view(con)
        # Passa o texto da query, e não transform(con): a relação do con.sql() é
        # preguiçosa e não deve ser consumida dentro da transação do replace_table
        replace_table(con, config.CLN_ARBORETO_CITATIONS_TABLE, _prepare(con))
        count = read_table(con, config.CLN_ARBORETO_CITATIONS_TABLE).aggregate("count(*)").fetchone()[0]
    print(f"[clean_arboreto_citations] {config.CLN_ARBORETO_CITATIONS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    clean_citations()
