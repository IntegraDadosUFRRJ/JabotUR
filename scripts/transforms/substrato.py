"""Transforma a coluna de substrato para a representação estrutural usada nas tabelas finais

Cada valor pode ser multivalorado, separado por "+". As siglas conhecidas são
resolvidas para nomes completos via configuração; siglas desconhecidas são
mantidas no texto original e registradas para revisão manual.
"""

import pandas as pd

import scripts.config as config


def expand_multivalued(series: pd.Series) -> pd.Series:
    mapping = config.SUBSTRATO_NOME_MAP

    def _expand(value):
        if pd.isna(value) or str(value).strip() == "":
            return []
        tokens = [t.strip() for t in str(value).split("+") if t.strip()]
        nomes = []
        for token in tokens:
            key = token.upper()
            if key not in mapping:
                print(f"[transforms.substrato] sigla de substrato desconhecida: {token!r} (mantendo original)")
                nome = token
            else:
                nome = mapping[key]
            if nome not in nomes:
                nomes.append(nome)
        return nomes

    return series.map(_expand)