"""
Get-or-create compartilhado do núcleo taxonômico (filo, familia, genero,
autor, epiteto_especifico), sobre linhas (list[dict]) lidas e gravadas pelo DuckDB.

Chaves esperadas em cada linha de entrada:
  filo_nome (pode ser None em todas)
  familia
  genero (pode ser None)
  epiteto (pode ser None)
  infraespecifico (opcional)
  autor (pode ser None)

Os ids existentes entram ordenados por id e as chaves novas na ordem de primeira aparição
em `rows`: mudar essa ordem muda os ids gravados.
Os mapas por nome (familia_by_nome, genero_by_nome) ficam com o último id quando o mesmo
nome aparece sob pais diferentes.
"""

import math

try:
    from ..db.db_utils import read_rows
    from .. import config
except ImportError:
    from scripts.db.db_utils import read_rows
    import scripts.config as config


def _none_if_nan(value):
    # NaN também é ausência de valor: os transforms do SPP devolvem NaN para célula vazia
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def _merge_ids(existing_keys_to_id: dict, new_keys) -> dict:
    ids = dict(existing_keys_to_id)
    next_id = (max(ids.values()) + 1) if ids else 1
    for key in new_keys:
        if key not in ids:
            ids[key] = next_id
            next_id += 1
    return ids


def _load_existing_rows(con, table_name: str) -> list[dict]:
    # Só a tabela inexistente vira "nenhuma linha": qualquer outro erro sobe, porque
    # engolido dentro da transação do load deixaria a transação abortada
    try:
        return read_rows(con, table_name)
    except LookupError:
        return []


def _distinct_non_null(values) -> list:
    # Sem NULL e na ordem de primeira aparição, que decide os ids novos
    return list(dict.fromkeys(v for v in map(_none_if_nan, values) if v is not None))


def build_filo_rows(con, rows: list[dict]):
    existing = _load_existing_rows(con, config.TB_FILO)
    existing_ids = {row["nome"]: row["id"] for row in existing}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["filo_nome"] for row in rows))
    dim = [{"id": i, "nome": nome} for nome, i in ids.items()]
    return dim, ids


def build_familia_rows(con, rows: list[dict], filo_ids: dict, filo_dim: list[dict]):
    filo_id_to_nome = {row["id"]: row["nome"] for row in filo_dim}
    existing_keys = {
        (
            _none_if_nan(filo_id_to_nome.get(row["id_filo"])),
            _none_if_nan(row["nome"]),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_FAMILIA)
    }
    pares = [
        (_none_if_nan(row["filo_nome"]), _none_if_nan(row["familia"]))
        for row in rows
        if _none_if_nan(row["familia"]) is not None
    ]
    ids = _merge_ids(existing_keys, pares)
    dim = [{"id": i, "id_filo": filo_ids.get(filo_nome), "nome": nome} for (filo_nome, nome), i in ids.items()]
    familia_by_nome = {nome: i for (filo_nome, nome), i in ids.items()}
    return dim, familia_by_nome


def build_genero_rows(con, rows: list[dict], familia_by_nome: dict, familia_dim: list[dict]):
    familia_id_to_nome = {row["id"]: row["nome"] for row in familia_dim}
    existing_keys = {
        (
            _none_if_nan(familia_id_to_nome.get(row["id_familia"])),
            _none_if_nan(row["nome"]),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_GENERO)
    }
    pares = [
        (_none_if_nan(row["familia"]), _none_if_nan(row["genero"]))
        for row in rows
        if _none_if_nan(row["genero"]) is not None
    ]
    ids = _merge_ids(existing_keys, pares)
    dim = [
        {"id": i, "id_familia": familia_by_nome.get(familia_nome), "nome": nome}
        for (familia_nome, nome), i in ids.items()
    ]
    genero_by_nome = {nome: i for (familia_nome, nome), i in ids.items()}
    return dim, genero_by_nome


def build_autor_rows(con, rows: list[dict]):
    existing = _load_existing_rows(con, config.TB_AUTOR)
    existing_ids = {row["nome"]: row["id"] for row in existing}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["autor"] for row in rows))
    dim = [{"id": i, "nome": nome} for nome, i in ids.items()]
    return dim, ids


def build_epiteto_especifico_rows(
    con, rows: list[dict], genero_by_nome: dict, autor_ids: dict, genero_dim: list[dict]
):
    genero_id_to_nome = {row["id"]: row["nome"] for row in genero_dim}
    autor_id_to_nome = {v: k for k, v in autor_ids.items()}
    existing_keys = {
        (
            _none_if_nan(genero_id_to_nome.get(row["id_genero"])),
            _none_if_nan(row["nome"]),
            _none_if_nan(row.get("infraespecifico")),
            _none_if_nan(autor_id_to_nome.get(row["id_autor"])),
        ): row["id"]
        for row in _load_existing_rows(con, config.TB_EPITETO_ESPECIFICO)
    }
    chave = [
        (
            _none_if_nan(row["genero"]),
            _none_if_nan(row["epiteto"]),
            _none_if_nan(row.get("infraespecifico")),
            _none_if_nan(row["autor"]),
        )
        for row in rows
        # mantém a linha se tiver gênero ou epíteto (pelo menos)
        if _none_if_nan(row["genero"]) is not None or _none_if_nan(row["epiteto"]) is not None
    ]
    ids = _merge_ids(existing_keys, chave)
    dim = [
        {
            "id": i,
            "id_genero": genero_by_nome.get(genero_nome),
            "id_autor": autor_ids.get(autor_nome),
            "nome": epiteto_nome,
            "infraespecifico": infra_val,
        }
        for (genero_nome, epiteto_nome, infra_val, autor_nome), i in ids.items()
    ]
    return dim, ids
