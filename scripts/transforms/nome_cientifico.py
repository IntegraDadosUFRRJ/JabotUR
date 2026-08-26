"""Transforma a coluna de espécie em divisões separadas usadas nas tabelas finais

Parser para o campo "Espécie" das planilhas do arboreto, que vem como uma
única string combinando Gênero + Epíteto Específico + Infraespecífico(nem todas possuem) + Autor, SEM SEPARADOR 
"""

import re
import pandas as pd

PARSE_STATUS_OK = "ok"
PARSE_STATUS_GENUS_ONLY = "genus_only"
PARSE_STATUS_MORPHOSPECIES = "morphospecies"
PARSE_STATUS_UNPARSEABLE = "unparseable"

_QUALIFIER = r"(?:cf\.?|aff\.?)"

_MORPHOSPECIES_RE = re.compile(r"^Morfo-Esp[ée]cie\s+\d+$", re.IGNORECASE)

_GENUS_ONLY_RE = re.compile(r"^[A-ZÀ-Ý][a-zà-ÿ]+$")

_GENUS_EPITHET_RE = re.compile(
    r"^(?P<genus>[A-ZÀ-Ý][a-zà-ÿ]+)"
    rf"(?:\s+(?P<qualifier>{_QUALIFIER}))?"
    r"\s+(?P<epithet>[a-zà-ÿ×]+)"
    r"(?P<rest>.*)$"
)

# Marcador de rank infraespecífico seguido do epíteto infraespecífico
_INFRA_RANK_RE = re.compile(r"\b(var\.|subsp\.|f\.|forma)\s+([A-Za-zà-ÿ-]+)")


def _normalize_raw(nome):
    # Normaliza erro de digitação na planilha antes do parsing.
    if nome is None or (isinstance(nome, float) and pd.isna(nome)):
        return None
    s = str(nome).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\(\s+", "(", s)
    s = re.sub(r"\s+\)", ")", s)
    s = re.sub(r"([A-Za-zÀ-ÿ])\.\s*-\s*", r"\1.-", s)
    return s

def _normalize_qualifier(raw_qualifier):
    # Normaliza "cf", "cf.", "aff", "aff." pra forma padrão com ponto
    if not raw_qualifier:
        return None
    base = raw_qualifier.rstrip(".").lower()
    return f"{base}."


def _result(nome_raw, nome_normalizado, status, genero=None, epiteto=None,
            infra=None, autor=None, qualifier=None):
    return {
        "nome_raw": nome_raw,
        "nome_normalizado": nome_normalizado,
        "genero": genero,
        "epiteto_especifico": epiteto,
        "infraespecifico": infra,
        "autor": autor,
        "identification_qualifier": qualifier,
        "parse_status": status,
    }


def parse_nome_cientifico(nome_raw):
    """Faz o parsing de uma string de espécie do arboreto.

    Retorna um dicionário com os componentes taxonômicos extraídos e
    um ``parse_status`` indicando o resultado do parsing:

    - ``PARSE_STATUS_OK``: nome processado com sucesso;
    - ``PARSE_STATUS_MORPHOSPECIES``: registro de morfo-espécie;
    - ``PARSE_STATUS_GENUS_ONLY``: registro contendo apenas o gênero;
    - ``PARSE_STATUS_UNPARSEABLE``: não corresponde ao padrão esperado.
    """
    nome_norm = _normalize_raw(nome_raw)

    if not nome_norm:
        return _result(
            nome_raw,
            nome_norm,
            status=PARSE_STATUS_UNPARSEABLE,
        )

    if _MORPHOSPECIES_RE.match(nome_norm):
        return _result(
            nome_raw,
            nome_norm,
            status=PARSE_STATUS_MORPHOSPECIES,
        )

    if _GENUS_ONLY_RE.match(nome_norm):
        return _result(
            nome_raw,
            nome_norm,
            status=PARSE_STATUS_GENUS_ONLY,
            genero=nome_norm,
        )

    m = _GENUS_EPITHET_RE.match(nome_norm)
    if not m:
        return _result(nome_raw, nome_norm, status="unparseable")

    genus = m.group("genus")
    epithet = m.group("epithet")
    qualifier = _normalize_qualifier(m.group("qualifier"))
    rest = m.group("rest").strip()

    if not rest:
        # só "genero + epiteto"
        return _result(nome_raw, nome_norm, status="ok", genero=genus,
                        epiteto=epithet, infra=None, autor=None)

    infra_match = _INFRA_RANK_RE.search(rest)
    if infra_match:
        rank, infra_epithet = infra_match.group(1), infra_match.group(2)
        author_before = rest[: infra_match.start()].strip()
        author_after = rest[infra_match.end():].strip()
        # autor do táxon infraespecífico tem prioridade sobre o da espécie quando os dois existem
        autor = author_after or author_before or None
        infra = f"{rank} {infra_epithet}"
        return _result(nome_raw, nome_norm, status=PARSE_STATUS_OK, genero=genus,
                        epiteto=epithet, infra=infra, autor=autor, qualifier=qualifier)

    return _result(
        nome_raw,
        nome_norm,
        status=PARSE_STATUS_OK,
        genero=genus,
        epiteto=epithet,
        infra=None,
        autor=rest or None,
        qualifier=qualifier,
    )


def parse_nome_cientifico_series(serie: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(serie.map(parse_nome_cientifico).tolist())