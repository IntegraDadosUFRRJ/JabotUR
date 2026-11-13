"""Leitura de abas xlsx pelo DuckDB (extensão excel) e gravação da tabela de staging.

Os stagings de SPP, Citações e Espécimes usam este módulo para que as regras de leitura
fiquem num lugar só:
  - all_varchar: a leitura padrão infere tipo pela coluna e aborta em célula de texto
    numa coluna numérica; ignore_errors não é usado porque transforma essa célula em
    NULL sem aviso;
  - stop_at_empty=false: o padrão para na primeira linha em branco e perderia, sem
    erro, as linhas que vêm depois dela;
  - linhas ocultas são lidas como qualquer outra (o leitor não as filtra).
"""

from pathlib import Path

from scripts.db import db_utils
import scripts.config as config

# O export do Google Sheets grava número inteiro como float (<v>1.0</v>) e o all_varchar
# devolve '1.0'; o pandas convertia float inteiro em int e o staging guardava '1'.
# A regex reproduz isso para o staging não mudar. Como o all_varchar não distingue célula
# numérica de célula de texto, um texto digitado '3.0' também viraria '3': o teste
# test_staging_duckdb garante que nenhuma célula de texto lida tem esse formato.
INTEGER_FLOAT_PATTERN = r"^(-?\d+)\.0$"


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sheet_query(path: Path, sheet: str, column_map: dict[str, str]) -> str:
    renamed = ", ".join(
        f"regexp_replace({_sql_identifier(source)}, {_sql_literal(INTEGER_FLOAT_PATTERN)}, '\\1') "
        f"AS {_sql_identifier(target)}"
        for source, target in column_map.items()
    )
    data_cols = ", ".join(_sql_identifier(col) for col in column_map.values())
    # A ordinalidade é a posição da linha na saída do read_xlsx; com stop_at_empty=false
    # nenhuma linha é pulada, então ordinalidade + 1 (o cabeçalho é a linha 1) é a linha
    # da planilha. row_number() OVER () não serviria: sem ORDER BY, a ordem não é garantida.
    # O read_xlsx tira o espaço final do cabeçalho ('Quant '), por isso as chaves do
    # column_map, já sem espaço, batem com ele.
    # Linhas 100% vazias (fim da aba, linhas em branco) não entram, como no staging com pandas.
    return f"""
        SELECT
            {_sql_literal(path.name)} AS {config.SOURCE_FILE_COL},
            {_sql_literal(sheet)} AS {config.SOURCE_SHEET_COL},
            {config.SOURCE_ROW_COL},
            {data_cols},
            CAST(now() AS TIMESTAMPTZ) AS _loaded_at
        FROM (
            SELECT ordinality + 1 AS {config.SOURCE_ROW_COL}, {renamed}
            FROM read_xlsx(
                {_sql_literal(str(path))},
                sheet = {_sql_literal(sheet)},
                all_varchar = true,
                stop_at_empty = false
            ) WITH ORDINALITY
            ORDER BY ordinality
        )
        WHERE coalesce({data_cols}) IS NOT NULL
    """


def sheets_query(path: Path, sheets: list[str], column_map: dict[str, str]) -> str:
    """SELECT com as abas empilhadas na ordem de `sheets`, colunas renomeadas pelo
    column_map e as colunas de linhagem; não grava nada.

    Exige a extensão excel carregada na conexão que executar a query.
    """
    union = "\nUNION ALL BY NAME\n".join(
        f"({_sheet_query(path, sheet, column_map)})" for sheet in sheets
    )
    sheet_order = "[" + ", ".join(_sql_literal(sheet) for sheet in sheets) + "]"
    return (
        f"SELECT * FROM ({union}) "
        f"ORDER BY list_position({sheet_order}, {config.SOURCE_SHEET_COL}), {config.SOURCE_ROW_COL}"
    )


def write_staging(table_name: str, query: str, log_prefix: str) -> None:
    """Recria a tabela de staging com o resultado da query, numa única transação.

    Um erro de leitura (aba ou arquivo inexistente, cabeçalho que não bate com o
    column_map) interrompe o staging e deixa a tabela anterior intacta.
    """
    with db_utils.postgres_duckdb() as con:
        con.execute("LOAD excel")
        db_utils.replace_table(con, table_name, query)
        count = db_utils.read_table(con, table_name, order_by=[]).aggregate("count(*)").fetchone()[0]
    print(f"[{log_prefix}] {table_name}: {count} linhas carregadas.")
