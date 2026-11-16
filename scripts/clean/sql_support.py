"""Trechos comuns às queries .sql dos cleans, montados a partir do config.py.

Os .sql recebem esses trechos por str.format; aqui fica a única versão de cada um.
"""

import scripts.config as config


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _source_row_number() -> str:
    # _source_row comparado como número: como texto, a linha 10 viria antes da 9
    return f"CAST({config.SOURCE_ROW_COL} AS INTEGER)"


def staging_order_sql(order: list[str]) -> str:
    """ORDER BY da ordem da planilha a partir de uma lista de ordem do config."""
    return ", ".join(
        _source_row_number() if col == config.SOURCE_ROW_COL else col for col in order
    )
