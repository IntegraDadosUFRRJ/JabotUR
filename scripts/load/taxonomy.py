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
    from ..db.db_utils import read_dataframe_from_postgres
    from .. import config
except ImportError:
    from scripts.db.db_utils import read_dataframe_from_postgres
    import scripts.config as config


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
            key = (filo_id_to_nome.get(row["id_filo"]), row["nome"])
            existing_keys[key] = row["id"]

    pares = list(df.dropna(subset=["familia"])[["filo_nome", "familia"]].itertuples(index=False, name=None))
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
            key = (familia_id_to_nome.get(row["id_familia"]), row["nome"])
            existing_keys[key] = row["id"]

    pares = list(df.dropna(subset=["genero"])[["familia", "genero"]].itertuples(index=False, name=None))
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


def _normalize_key_value(value):
    return None if pd.isna(value) else value


def build_epiteto_especifico(df: pd.DataFrame, genero_by_nome: dict, autor_ids: dict, genero_dim: pd.DataFrame):
    genero_id_to_nome = dict(zip(genero_dim["id"], genero_dim["nome"]))
    autor_id_to_nome = {v: k for k, v in autor_ids.items()}

    existing = _load_existing(config.TB_EPITETO_ESPECIFICO)
    existing_keys = {}

    if not existing.empty:
        has_infra_col = "infraespecifico" in existing.columns

        for _, row in existing.iterrows():
            key = (
                _normalize_key_value(genero_id_to_nome.get(row["id_genero"])),
                _normalize_key_value(row["nome"]),
                _normalize_key_value(row["infraespecifico"]) if has_infra_col else None,
                _normalize_key_value(autor_id_to_nome.get(row["id_autor"])),
            )
            existing_keys[key] = row["id"]

    work = df.copy()

    if "infraespecifico" not in work.columns:
        work["infraespecifico"] = None

    # mantém a linha se tiver gênero ou epíteto (pelo menos)
    work = work.dropna(subset=["genero", "epiteto"], how="all")

    chave = [
        tuple(_normalize_key_value(value) for value in row)
        for row in work[
            ["genero", "epiteto", "infraespecifico", "autor"]
        ].itertuples(index=False, name=None)
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