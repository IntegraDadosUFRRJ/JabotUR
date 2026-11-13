"""Transforma a coluna de epiteto_especifico para o nome completo usado nas tabelas finais

- remove o primeiro token da string quando ele termina em "." (para remover a abreviação de gênero)
"""

import re

from scripts.transforms.missing import is_missing

_GENERO_ABREVIADO_RE = re.compile(r"^\s*[^\s.]+\.\s*")


def strip_genero_abbreviation(values: list) -> list:
    return [strip_genero_abbreviation_from_value(value) for value in values]


def strip_genero_abbreviation_from_value(value):
    if is_missing(value):
        return None
    text = str(value).strip()
    return _GENERO_ABREVIADO_RE.sub("", text).strip()
