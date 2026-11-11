"""Transforma a coluna de observações para a representação estruturada usada nas tabelas finais

  - separa valores multivalorados por ";"
  - converte a ausência de observação (NULL ou texto vazio) em uma lista vazia
"""

import pandas as pd


def split_multivalued(series: pd.Series) -> pd.Series:
    def _split(value):
        if pd.isna(value):
            return []
        text = str(value).strip()
        if text == "":
            return []
        parts = [t.strip() for t in text.split(";") if t.strip()]
        seen = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return seen


    return series.map(_split)