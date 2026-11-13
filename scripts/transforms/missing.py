"""Regra única de valor ausente para os transforms.

As linhas lidas do Postgres trazem None para NULL; o NaN do tipo float também conta
como ausente, para um valor vindo de planilha ou de cálculo ter a mesma resposta.
"""

import math


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))
