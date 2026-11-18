"""Transforma a coluna epithet para o nome completo usado nas tabelas finais

- remove o primeiro token da string quando ele termina em "." (para remover a abreviação de gênero)
- separa o qualificador de identificação ("cf.", "aff."), que é do registro e não da espécie
- sem epíteto depois disso (vazio ou só "sp."), devolve None: a espécie é só do gênero (ADR-0003)
"""

import re

from scripts.transforms.missing import is_missing
from scripts.transforms.scientific_name import QUALIFIER_PATTERN, normalize_qualifier

_GENUS_ABBREVIATION_RE = re.compile(r"^\s*[^\s.]+\.\s*")

# O qualificador precisa ser um token inteiro: "affinis" é epíteto, não "aff" + "inis"
_LEADING_QUALIFIER_RE = re.compile(rf"^(?P<qualifier>{QUALIFIER_PATTERN})(?:\s+|$)")

# Mesma forma que o parser de Citações e Espécimes trata como gênero-só ("Genus sp")
_NO_EPITHET_RE = re.compile(r"^(?:sp\.?)?$")


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
        return _epithet_or_none(text), None
    return _epithet_or_none(text[match.end():].strip()), normalize_qualifier(match.group("qualifier"))


def _epithet_or_none(text: str):
    return None if _NO_EPITHET_RE.match(text) else text
