"""Parser para a coluna "N° de registro" da aba Espécimes do arboreto.

Cada espécime é identificado por um lacre físico preso à planta. Dois esquemas
de numeração coexistem na planilha, às vezes os dois no mesmo registro:
  - lacre amarelo: prefixo "RBRv" + dígitos (ex.: "RBRv90000293")
  - lacre azul: só numeração, mas a planilha grafa com rótulo
    "LACRE AZUL"/"Lacre azul"/"AZUL" + dígitos (ex.: "LACRE AZUL 0015130")

Regra de negócio: quando um espécime tem os dois lacres significa que o azul substituiu o amarelo fisicamente,
por ser mais recente ex.: "RBRv90000293 (LACRE AZUL 0015124)" -> guardar só o azul.
"""

import re
import pandas as pd

STATUS_AZUL = "azul"
STATUS_AMARELO = "amarelo"
STATUS_NULL = "null"
STATUS_UNPARSEABLE = "unparseable"

_AZUL_RE = re.compile(r"\(?\s*(?:LACRE\s+)?AZUL\s*-?\s*(?P<numero>\d+)\s*\)?", re.IGNORECASE)
_AMARELO_RE = re.compile(r"^RBRv\s*\d+$", re.IGNORECASE)
_NA_RE = re.compile(r"^n/?a$", re.IGNORECASE)


def _normalize_raw(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    s = re.sub(r"\s+", " ", s)
    return s or None


def _result(raw, normalizado, status, numero=None):
    return {
        "registration_number_raw": raw,
        "registration_number": numero,
        "registration_status": status,
    }


def parse_registration_number(valor_raw):
    """
    Registration_status indica o que aconteceu:
      "azul"        -> lacre azul extraído (com ou sem amarelo junto quando os dois existem, o azul vence)
      "amarelo"     -> só lacre amarelo (RBRv...), sem azul
      "null"        -> sem lacre (célula vazia ou "NA")
      "unparseable" -> não bateu com nenhum padrão conhecido; revisão manual
    """
    norm = _normalize_raw(valor_raw)
    if not norm or _NA_RE.match(norm):
        return _result(valor_raw, norm, status=STATUS_NULL, numero=None)

    azul_match = _AZUL_RE.search(norm)
    if azul_match:
        numero = azul_match.group("numero")
        return _result(valor_raw, norm, status=STATUS_AZUL, numero=f"LACRE AZUL {numero}")

    if _AMARELO_RE.match(norm):
        return _result(valor_raw, norm, status=STATUS_AMARELO, numero=norm)

    return _result(valor_raw, norm, status=STATUS_UNPARSEABLE, numero=None)


def parse_registration_number_series(serie: pd.Series) -> pd.DataFrame:
    """Vetoriza parse_registration_number sobre uma coluna inteira."""
    return pd.DataFrame(serie.map(parse_registration_number).tolist())
