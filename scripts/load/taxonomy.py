"""
Get-or-create compartilhado do núcleo taxonômico (filo, familia, genero,
autor, epiteto_especifico) 

Contrato de coluna esperado no DataFrame de entrada:
  filo_nome (pode ser todo None)
  familia
  genero (pode ser None)
  epiteto (pode ser None)
  infraespecifico (opcional)
  autor (pode ser None)
"""

import pandas as pd

try:
    from ..db.db_utils import read_dataframe_from_postgres, read_rows
    from .. import config
except ImportError:
    from scripts.db.db_utils import read_dataframe_from_postgres, read_rows
    import scripts.config as config


def _none_if_nan(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _load_existing(table_name: str) -> pd.DataFrame:
    try:
        return read_dataframe_from_postgres(table_name)
    except Exception:
        return pd.DataFrame()


def _merge_ids(existing_keys_to_id: dict, new_keys) -> dict:
    ids = dict(existing_keys_to_id)
    next_id = (max(ids.values()) + 1) if ids else 1
    for key in new_keys:
        if key not in ids:
            ids[key] = next_id
            next_id += 1
    return ids


def build_filo(df: pd.DataFrame):
    existing = _load_existing(config.TB_FILO)
    existing_ids = dict(zip(existing["nome"], existing["id"])) if not existing.empty else {}
    nomes = df["filo_nome"].dropna().unique().tolist()
    ids = _merge_ids(existing_ids, nomes)
    dim = pd.DataFrame({"id": list(ids.values()), "nome": list(ids.keys())})
    return dim, ids


def build_familia(df: pd.DataFrame, filo_ids: dict, filo_dim: pd.DataFrame):
    filo_id_to_nome = dict(zip(filo_dim["id"], filo_dim["nome"]))
    existing = _load_existing(config.TB_FAMILIA)
    existing_keys = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            key = (
                _none_if_nan(filo_id_to_nome.get(row["id_filo"])),
                _none_if_nan(row["nome"]),
            )
            existing_keys[key] = row["id"]

    pares = [
        (_none_if_nan(filo_nome), _none_if_nan(nome))
        for filo_nome, nome in df.dropna(subset=["familia"])[["filo_nome", "familia"]].itertuples(index=False, name=None)
    ]
    ids = _merge_ids(existing_keys, pares)
    rows = [{"id": i, "id_filo": filo_ids.get(filo_nome), "nome": nome} for (filo_nome, nome), i in ids.items()]
    dim = pd.DataFrame(rows)
    familia_by_nome = {nome: i for (filo_nome, nome), i in ids.items()}
    return dim, familia_by_nome


def build_genero(df: pd.DataFrame, familia_by_nome: dict, familia_dim: pd.DataFrame):
    familia_id_to_nome = dict(zip(familia_dim["id"], familia_dim["nome"]))
    existing = _load_existing(config.TB_GENERO)
    existing_keys = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            key = (
                _none_if_nan(familia_id_to_nome.get(row["id_familia"])),
                _none_if_nan(row["nome"]),
            )
            existing_keys[key] = row["id"]

    pares = [
        (_none_if_nan(familia_nome), _none_if_nan(nome))
        for familia_nome, nome in df.dropna(subset=["genero"])[["familia", "genero"]].itertuples(index=False, name=None)
    ]
    ids = _merge_ids(existing_keys, pares)
    rows = [{"id": i, "id_familia": familia_by_nome.get(familia_nome), "nome": nome} for (familia_nome, nome), i in ids.items()]
    dim = pd.DataFrame(rows)
    genero_by_nome = {nome: i for (familia_nome, nome), i in ids.items()}
    return dim, genero_by_nome


def build_autor(df: pd.DataFrame):
    existing = _load_existing(config.TB_AUTOR)
    existing_ids = dict(zip(existing["nome"], existing["id"])) if not existing.empty else {}
    nomes = df["autor"].dropna().unique().tolist()
    ids = _merge_ids(existing_ids, nomes)
    dim = pd.DataFrame({"id": list(ids.values()), "nome": list(ids.keys())})
    return dim, ids


def build_epiteto_especifico(df: pd.DataFrame, genero_by_nome: dict, autor_ids: dict, genero_dim: pd.DataFrame):
    genero_id_to_nome = dict(zip(genero_dim["id"], genero_dim["nome"]))
    autor_id_to_nome = {v: k for k, v in autor_ids.items()}

    existing = _load_existing(config.TB_EPITETO_ESPECIFICO)
    existing_keys = {}
    if not existing.empty:
        has_infra_col = "infraespecifico" in existing.columns
        for _, row in existing.iterrows():
            key = (
                _none_if_nan(genero_id_to_nome.get(row["id_genero"])),
                _none_if_nan(row["nome"]),
                _none_if_nan(row["infraespecifico"]) if has_infra_col else None,
                _none_if_nan(autor_id_to_nome.get(row["id_autor"])),
            )
            existing_keys[key] = row["id"]

    work = df.copy()
    if "infraespecifico" not in work.columns:
        work["infraespecifico"] = None

    # mantém a linha se tiver gênero ou epíteto (pelo menos)
    work = work.dropna(subset=["genero", "epiteto"], how="all")

    chave = [
        (_none_if_nan(g), _none_if_nan(e), _none_if_nan(i), _none_if_nan(a))
        for g, e, i, a in work[["genero", "epiteto", "infraespecifico", "autor"]]
        .itertuples(index=False, name=None)
    ]
    ids = _merge_ids(existing_keys, chave)
    rows = [
        {
            "id": i,
            "id_genero": genero_by_nome.get(genero_nome),
            "id_autor": autor_ids.get(autor_nome),
            "nome": epiteto_nome,
            "infraespecifico": infra_val,
        }
        for (genero_nome, epiteto_nome, infra_val, autor_nome), i in ids.items()
    ]
    dim = pd.DataFrame(rows)
    return dim, ids

# --- Get-or-create sem pandas ---
# Mesma regra das funções acima, sobre linhas (list[dict]) lidas e gravadas pelo DuckDB.
# A ordem dos ids não pode mudar: os existentes entram ordenados por id e as chaves novas
# na ordem de primeira aparição em `rows`, como o unique()/itertuples() do pandas.
# Contrato de `rows`: as mesmas chaves do DataFrame descrito no topo do módulo.
# Os mapas por nome (familia_by_nome, genero_by_nome) continuam ficando com o último id
# quando o mesmo nome aparece sob pais diferentes: comportamento atual, preservado aqui.


def _load_existing_rows(con, table_name: str) -> list[dict]:
    # Só a tabela inexistente vira "nenhuma linha": qualquer outro erro sobe, porque
    # engolido dentro da transação do load deixaria a transação abortada
    try:
        return read_rows(con, table_name)
    except LookupError:
        return []


def _distinct_non_null(values) -> list:
    # Equivale a Series.dropna().unique().tolist(): sem NULL, ordem de primeira aparição
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
