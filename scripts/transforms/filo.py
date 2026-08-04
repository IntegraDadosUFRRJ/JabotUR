"""Transforma a coluna de filo para o nome completo usado nas tabelas finais

Converte as siglaa de entrada (M/H) para o nome completo (Musgos/Hepáticas),
se encontrar uma sigla não prevista, mantém o valor original e registra um aviso no console
"""

import numpy as np
import pandas as pd

try:
    from .. import config
except ImportError:
    import config


def expand(series: pd.Series) -> pd.Series:
    mapping = config.FILO_NOME_MAP

    def _map(value):
        if pd.isna(value):
            return np.nan
        key = str(value).strip().upper()
        if key not in mapping:
            print(f"[transforms.filo] sigla de filo desconhecida: {value!r} (mantendo original)")
            return str(value).strip()
        return mapping[key]

    return series.map(_map)