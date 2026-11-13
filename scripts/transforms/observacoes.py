"""Transforma a coluna de observações para a representação estruturada usada nas tabelas finais

  - separa valores multivalorados por ";"
  - converte a ausência de observação (NULL ou texto vazio) em uma lista vazia
"""

from scripts.transforms.missing import is_missing


def split_multivalued_value(value) -> list:
    if is_missing(value):
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


def split_multivalued(values: list) -> list:
    return [split_multivalued_value(value) for value in values]
