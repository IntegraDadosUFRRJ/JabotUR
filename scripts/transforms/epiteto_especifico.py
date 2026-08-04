"""Transforma a coluna de epiteto_especifico para o nome completo usado nas tabelas finais

- remove o primeiro token da string quando ele termina em "." (para remover a abreviação de gênero)
"""

import re

import numpy as np
import pandas as pd

_GENERO_ABREVIADO_RE = re.compile(r"^\s*[^\s.]+\.\s*")


def strip_genero_abbreviation(series: pd.Series) -> pd.Series:
    def _clean(value):
        if pd.isna(value):
            return np.nan
        text = str(value).strip()
        return _GENERO_ABREVIADO_RE.sub("", text).strip()

    return series.map(_clean)


def strip_genero_abbreviation_from_value(value):
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    return _GENERO_ABREVIADO_RE.sub("", text).strip()