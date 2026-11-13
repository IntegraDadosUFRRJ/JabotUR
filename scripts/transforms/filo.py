"""Transforma a coluna de filo para o nome completo usado nas tabelas finais

Converte as siglaa de entrada (M/H) para o nome completo (Musgos/Hepáticas),
se encontrar uma sigla não prevista, mantém o valor original e registra um aviso no console
"""

import scripts.config as config
from scripts.transforms.missing import is_missing


def expand_value(value):
    if is_missing(value):
        return None
    key = str(value).strip().upper()
    if key not in config.FILO_NOME_MAP:
        print(f"[transforms.filo] sigla de filo desconhecida: {value!r} (mantendo original)")
        return str(value).strip()
    return config.FILO_NOME_MAP[key]


def expand(values: list) -> list:
    return [expand_value(value) for value in values]
