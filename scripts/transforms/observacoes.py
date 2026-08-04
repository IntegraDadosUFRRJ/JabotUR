"""Transforma a coluna de observações para a representação estruturada usada nas tabelas finais

  - separa valores multivalorados por ";"
  - converte o placeholder de ausência de observação em uma lista vazia
"""

import pandas as pd

try:
    from .. import config
except ImportError:
    import config


def split_multivalued(series: pd.Series) -> pd.Series:
    placeholder = config.OBSERVACAO_NULL_PLACEHOLDER

    def _split(value):
        if pd.isna(value):
            return []
        text = str(value).strip()
        if text == "" or text == placeholder:
            return []
        return [t.strip() for t in text.split(";") if t.strip()]

    return series.map(_split)