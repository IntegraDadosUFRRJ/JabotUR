"""Parser para a coluna "N° de registro" da aba Espécimes do arboreto.

Cada espécime é identificado por um lacre físico preso à planta. Dois esquemas
de numeração coexistem na planilha, às vezes os dois no mesmo registro:
  - lacre amarelo: prefixo "RBRv" + dígitos (ex.: "RBRv90000293")
  - lacre azul: só numeração; a planilha às vezes grafa com rótulo
    "LACRE AZUL"/"Lacre azul"/"AZUL" + dígitos (ex.: "LACRE AZUL 0015130")
    e às vezes só o número (ex.: "0015130"), que também é azul (ADR-0009)

Regra de negócio: quando um espécime tem os dois lacres significa que o azul substituiu o amarelo fisicamente,
por ser mais recente ex.: "RBRv90000293 (LACRE AZUL 0015124)" -> guardar só o azul.
"""

import re

from scripts.transforms.missing import is_missing

STATUS_AZUL = "azul"
STATUS_AMARELO = "amarelo"
STATUS_NULL = "null"
STATUS_UNPARSEABLE = "unparseable"

_AZUL_RE = re.compile(r"\(?\s*(?:LACRE\s+)?AZUL\s*-?\s*(?P<number>\d+)\s*\)?", re.IGNORECASE)
_AMARELO_RE = re.compile(r"^RBRv\s*\d+$", re.IGNORECASE)
# ADR-0009: número sem prefixo "RBRv" é lacre azul, mesmo sem a palavra AZUL
_BLUE_UNLABELED_RE = re.compile(r"^(?P<number>\d+)$")
_NA_RE = re.compile(r"^n/?a$", re.IGNORECASE)


def _normalize_raw(value):
    if is_missing(value):
        return None
    s = str(value).strip()
    s = re.sub(r"\s+", " ", s)
    return s or None


def _result(raw, normalized, status, number=None):
    return {
        "registration_number_raw": raw,
        "registration_number": number,
        "registration_status": status,
    }


def parse_registration_number(raw_value):
    """
    Registration_status indica o que aconteceu:
      "azul"        -> lacre azul extraído (com ou sem amarelo junto quando os dois existem, o azul vence)
      "amarelo"     -> só lacre amarelo (RBRv...), sem azul
      "null"        -> sem lacre (célula vazia ou "NA")
      "unparseable" -> não bateu com nenhum padrão conhecido; revisão manual
    """
    norm = _normalize_raw(raw_value)
    if not norm or _NA_RE.match(norm):
        return _result(raw_value, norm, status=STATUS_NULL, number=None)

    azul_match = _AZUL_RE.search(norm)
    if azul_match:
        number = azul_match.group("number")
        return _result(raw_value, norm, status=STATUS_AZUL, number=f"LACRE AZUL {number}")

    if _AMARELO_RE.match(norm):
        return _result(raw_value, norm, status=STATUS_AMARELO, number=norm)

    unlabeled_match = _BLUE_UNLABELED_RE.match(norm)
    if unlabeled_match:
        number = unlabeled_match.group("number")
        return _result(raw_value, norm, status=STATUS_AZUL, number=f"LACRE AZUL {number}")

    return _result(raw_value, norm, status=STATUS_UNPARSEABLE, number=None)
