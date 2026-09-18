"""Transforma a coluna de observações para a representação estruturada usada nas tabelas finais

  - separa valores multivalorados por ";"
  - converte o placeholder de ausência de observação em uma lista vazia
"""

import pandas as pd

import scripts.config as config


def split_multivalued(series: pd.Series) -> pd.Series:
    placeholder = config.OBSERVACAO_NULL_PLACEHOLDER

    def _split(value):
        if pd.isna(value):
            return []
        text = str(value).strip()
        if text == "" or text == placeholder:
            return []
        parts = [t.strip() for t in text.split(";") if t.strip()]
        seen = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return seen


    return series.map(_split)