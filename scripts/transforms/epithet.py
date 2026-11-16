"""Transforma a coluna epithet para o nome completo usado nas tabelas finais

- remove o primeiro token da string quando ele termina em "." (para remover a abreviação de gênero)
- separa o qualificador de identificação ("cf.", "aff."), que é do registro e não da espécie
"""

import re

from scripts.transforms.missing import is_missing
from scripts.transforms.scientific_name import QUALIFIER_PATTERN, normalize_qualifier

_GENUS_ABBREVIATION_RE = re.compile(r"^\s*[^\s.]+\.\s*")

# O qualificador precisa ser um token inteiro: "affinis" é epíteto, não "aff" + "inis"
_LEADING_QUALIFIER_RE = re.compile(rf"^(?P<qualifier>{QUALIFIER_PATTERN})(?:\s+|$)")


def split_epithet(values: list) -> list:
    return [split_epithet_from_value(value) for value in values]


def split_epithet_from_value(value):
    """Devolve (epíteto, qualificador); sem qualificador, o segundo é None."""
    if is_missing(value):
        return None, None
    text = str(value).strip()
    # "cf." também termina em ponto: sem essa checagem, viraria abreviação de gênero e se perderia
    if not _LEADING_QUALIFIER_RE.match(text):
        text = _GENUS_ABBREVIATION_RE.sub("", text).strip()
    match = _LEADING_QUALIFIER_RE.match(text)
    if not match:
        return text, None
    return text[match.end():].strip() or None, normalize_qualifier(match.group("qualifier"))
