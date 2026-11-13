"""Parsers Python de transforms/ registrados como funções no DuckDB, para os cleans.

O SQL do DuckDB não chama código Python sozinho: cada parser é registrado como
função e passa a ser usado na query como qualquer função SQL.
Cada função devolve um STRUCT com as chaves escritas uma só vez aqui
(SCIENTIFIC_NAME_FIELDS, REGISTRATION_NUMBER_FIELDS).
O DuckDB recusa chave a menos ou a mais, mas não percebe uma chave renomeada;
por isso cada retorno passa por uma checagem explícita, que falha alto.
O NULL também chega ao parser (null_handling="special"), que decide o que
devolver para célula vazia, e uma exceção do parser interrompe o clean.
"""

import duckdb
from duckdb.sqltypes import VARCHAR

from scripts.transforms.registration_number import parse_registration_number
from scripts.transforms.scientific_name import parse_scientific_name

SCIENTIFIC_NAME_FUNCTION = "parse_scientific_name"
REGISTRATION_NUMBER_FUNCTION = "parse_registration_number"

SCIENTIFIC_NAME_FIELDS = (
    "nome_raw", "nome_normalizado", "genero", "epiteto_especifico",
    "infraespecifico", "autor", "identification_qualifier", "parse_status",
)
REGISTRATION_NUMBER_FIELDS = (
    "registration_number_raw", "registration_number", "registration_status",
)


def _checked(parser, fields: tuple[str, ...]):
    # O STRUCT do DuckDB recusa chave a menos ou a mais, mas aceita uma chave renomeada
    # e grava nela o valor de outro campo; a comparação explícita fecha essa brecha
    expected = set(fields)

    def checked_parser(value):
        result = parser(value)
        if set(result) != expected:
            raise ValueError(
                f"{parser.__name__} devolveu as chaves {sorted(result)}; esperado {sorted(expected)}"
            )
        return result

    return checked_parser


def _register(con: duckdb.DuckDBPyConnection, name: str, parser, fields: tuple[str, ...]) -> None:
    # Uma vez por conexão: registrar de novo com o mesmo nome é erro no DuckDB
    registered = con.execute(
        "SELECT count(*) FROM duckdb_functions() WHERE function_name = ?", [name]
    ).fetchone()[0]
    if registered:
        return
    con.create_function(
        name,
        _checked(parser, fields),
        [VARCHAR],
        duckdb.struct_type({field: VARCHAR for field in fields}),
        type="native",
        null_handling="special",
    )


def register_scientific_name_parser(con: duckdb.DuckDBPyConnection) -> None:
    # O parser é lido do módulo na hora do registro, para os testes poderem substituí-lo
    _register(con, SCIENTIFIC_NAME_FUNCTION, parse_scientific_name, SCIENTIFIC_NAME_FIELDS)


def register_registration_number_parser(con: duckdb.DuckDBPyConnection) -> None:
    _register(
        con, REGISTRATION_NUMBER_FUNCTION, parse_registration_number, REGISTRATION_NUMBER_FIELDS
    )
