"""Transforma a coluna de substrato para a representação estrutural usada nas tabelas finais

Cada valor pode ser multivalorado, separado por "+". As siglas conhecidas são
resolvidas para nomes completos via configuração; siglas desconhecidas são
mantidas no texto original e registradas para revisão manual.
"""

import scripts.config as config
from scripts.transforms.missing import is_missing


def expand_multivalued_value(value) -> list:
    if is_missing(value) or str(value).strip() == "":
        return []
    tokens = [t.strip() for t in str(value).split("+") if t.strip()]
    names = []
    for token in tokens:
        key = token.upper()
        if key not in config.SUBSTRATE_NAME_MAP:
            print(f"[transforms.substrate] sigla de substrato desconhecida: {token!r} (mantendo original)")
            name = token
        else:
            name = config.SUBSTRATE_NAME_MAP[key]
        if name not in names:
            names.append(name)
    return names


def expand_multivalued(values: list) -> list:
    return [expand_multivalued_value(value) for value in values]
