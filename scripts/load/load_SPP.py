"""
Lê `cln_spp_briofitas` e povoa as tabelas normalizadas finais do schema
briofitasSPP.md no PostgreSQL:

    filo, familia, genero, autor, epiteto_especifico, forma_vida, parcela,
    substrato, identificacao, coleta, coleta_substrato, coleta_observacao,
    observacao
"""

import pandas as pd

try:
    from .. import config
    from ..db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from ..transforms import epiteto_especifico as epiteto_t
    from ..transforms import filo as filo_t
    from ..transforms import observacoes as observacoes_t
    from ..transforms import substrato as substrato_t
except ImportError:
    import config
    from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from transforms import epiteto_especifico as epiteto_t
    from transforms import filo as filo_t
    from transforms import observacoes as observacoes_t
    from transforms import substrato as substrato_t


def _expand_filo(values: pd.Series) -> pd.Series:
    return filo_t.expand(values)


def _strip_genero_abbreviation(values: pd.Series) -> pd.Series:
    return epiteto_t.strip_genero_abbreviation(values)


def _expand_multivalued_substrato(values: pd.Series) -> pd.Series:
    return substrato_t.expand_multivalued(values)


def _split_multivalued_observacoes(values: pd.Series) -> pd.Series:
    return observacoes_t.split_multivalued(values)


def load_clean_df() -> pd.DataFrame:
    return read_dataframe_from_postgres(config.CLN_SPP_TABLE)


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


def _resolve_epiteto_column(df: pd.DataFrame) -> str:
    for column_name in ("epiteto_especifico", "especie"):
        if column_name in df.columns:
            return column_name
    raise KeyError("Nenhuma coluna de epíteto encontrada em cln_spp_briofitas")


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    epiteto_column = _resolve_epiteto_column(df)
    out["epiteto_especifico"] = out[epiteto_column]
    out["filo_nome"] = _expand_filo(out["filo"])
    out["epiteto_limpo"] = _strip_genero_abbreviation(out["epiteto_especifico"])
    out["substrato_lista"] = _expand_multivalued_substrato(out["substrato"])
    out["observacoes_lista"] = _split_multivalued_observacoes(out["observacoes"])
    out["source_file"] = out["_source_file"]
    out["source_row"] = out["_source_row"]
    return out


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


def build_epiteto_especifico(df: pd.DataFrame, genero_by_nome: dict, autor_ids: dict, genero_dim: pd.DataFrame):
    genero_id_to_nome = dict(zip(genero_dim["id"], genero_dim["nome"]))
    autor_id_to_nome = {v: k for k, v in autor_ids.items()}
    existing = _load_existing(config.TB_EPITETO_ESPECIFICO)
    existing_keys = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            key = (
                genero_id_to_nome.get(row["id_genero"]),
                row["nome"],
                autor_id_to_nome.get(row["id_autor"]),
            )
            existing_keys[key] = row["id"]
 
    chave = list(
        df.dropna(subset=["epiteto_limpo"])[["genero", "epiteto_limpo", "autor"]]
        .itertuples(index=False, name=None)
    )
    ids = _merge_ids(existing_keys, chave)
    rows = [
        {
            "id": i,
            "id_genero": genero_by_nome.get(genero_nome),
            "id_autor": autor_ids.get(autor_nome),
            "nome": epiteto_nome,
        }
        for (genero_nome, epiteto_nome, autor_nome), i in ids.items()
    ]
    dim = pd.DataFrame(rows)
    return dim, ids


def build_forma_vida(df: pd.DataFrame):
    existing = _load_existing(config.TB_FORMA_VIDA)
    existing_ids = dict(zip(existing["tipo"], existing["id"])) if not existing.empty else {}
    tipos = df["forma_vida"].dropna().unique().tolist()
    ids = _merge_ids(existing_ids, tipos)
    dim = pd.DataFrame({"id": list(ids.values()), "tipo": list(ids.keys())})
    return dim, ids


def build_parcela(df: pd.DataFrame):
    existing = _load_existing(config.TB_PARCELA)
    existing_ids = {}
    if not existing.empty and "codigo" in existing.columns:
        existing_ids = dict(zip(existing["codigo"], existing["id"]))

    valores = df["parcela"].dropna().unique().tolist()
    ids = _merge_ids(existing_ids, valores)
    dim = pd.DataFrame(
        {
            "id": list(ids.values()),
            "codigo": list(ids.keys()),
            "coordenada": [config.PARCELA_COORDENADAS.get(str(v)) for v in ids.keys()],
        }
    )
    return dim, ids


def build_identificacao():
    dim = pd.DataFrame(
        {
            "id": list(config.IDENTIFICACAO_DESCRICAO_MAP.keys()),
            "descricao": list(config.IDENTIFICACAO_DESCRICAO_MAP.values()),
        }
    )
    ids = {codigo: codigo for codigo in config.IDENTIFICACAO_DESCRICAO_MAP}
    return dim, ids


def build_substrato(df: pd.DataFrame):
    sigla_by_nome = {v: k for k, v in config.SUBSTRATO_NOME_MAP.items()}
    existing = _load_existing(config.TB_SUBSTRATO)
    existing_ids = dict(zip(existing["nome"], existing["id"])) if not existing.empty else {}
    nomes = sorted({nome for lista in df["substrato_lista"] for nome in lista})
    sigla_by_nome = {v: k for k, v in config.SUBSTRATO_NOME_MAP.items()}
    ids = _merge_ids(existing_ids, nomes)
    dim = pd.DataFrame(
        {
            "id": list(ids.values()),
            "nome": list(ids.keys()),
            "sigla": [sigla_by_nome.get(nome) for nome in ids.keys()],
        }
    )
    return dim, ids


def build_observacao(df: pd.DataFrame):
    existing = _load_existing(config.TB_OBSERVACAO)
    existing_ids = dict(zip(existing["comentario"], existing["id"])) if not existing.empty else {}
    comentarios = sorted({c for lista in df["observacoes_lista"] for c in lista})
    ids = _merge_ids(existing_ids, comentarios)
    dim = pd.DataFrame({"id": list(ids.values()), "comentario": list(ids.keys())})
    return dim, ids


def build_coleta(df: pd.DataFrame, epiteto_ids: dict, forma_ids: dict, identificacao_ids: dict, parcela_ids: dict):
    existing = _load_existing(config.TB_COLETA)
    existing_keys_to_id = {}
    if not existing.empty and "origin_file" in existing.columns:
        for _, row in existing.iterrows():
            existing_keys_to_id[(row["origin_file"], row["origin_row"])] = row["id"]
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1
 
    rows = []
    for row in df.itertuples(index=True):
        chave_especie = (row.genero, row.epiteto_limpo, row.autor)
        id_especie = epiteto_ids.get(chave_especie)
        if id_especie is None:
            print(
                f"[load_SPP] linha {row.Index} ({row.source_file}#{row.source_row}): "
                f"não encontrei epíteto para {chave_especie!r}, pulando coleta"
            )
            continue
 
        natural_key = (row.source_file, row.source_row)
        if natural_key in existing_keys_to_id:
            coleta_id = existing_keys_to_id[natural_key]
        else:
            coleta_id = next_id
            existing_keys_to_id[natural_key] = coleta_id
            next_id += 1
 
        codigo_status = row.status_identificacao
        id_identificacao = identificacao_ids.get(int(codigo_status)) if pd.notna(codigo_status) else None
 
        rows.append(
            {
                "id": coleta_id,
                "origin_file": row.source_file,
                "origin_row": row.source_row,
                "id_especie": id_especie,
                "id_forma": forma_ids.get(row.forma_vida) if pd.notna(row.forma_vida) else None,
                "id_identificacao": id_identificacao,
                "id_parcela": parcela_ids.get(row.parcela) if pd.notna(row.parcela) else None,
                "amostra": int(row.amostra) if pd.notna(row.amostra) else None,
            }
        )
    return pd.DataFrame(rows)

def build_occurrence(df: pd.DataFrame, epiteto_ids: dict, forma_ids: dict, identificacao_ids: dict, parcela_ids: dict):
    existing = _load_existing(config.TB_OCCURRENCE)
    existing_keys_to_id = {}
    if not existing.empty and "origin_file" in existing.columns:
        for _, row in existing.iterrows():
            existing_keys_to_id[(row["origin_file"], row["origin_row"])] = row["id"]
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1
 
    occurrence_rows = []
    satellite_rows = []
    for row in df.itertuples(index=True):
        chave_especie = (row.genero, row.epiteto_limpo, row.autor)
        id_especie = epiteto_ids.get(chave_especie)
        if id_especie is None:
            print(
                f"[load_SPP] linha {row.Index} ({row.source_file}#{row.source_row}): "
                f"não encontrei epíteto para {chave_especie!r}, pulando occurrence"
            )
            continue
 
        natural_key = (row.source_file, row.source_row)
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1
 
        codigo_status = row.status_identificacao
        id_identificacao = identificacao_ids.get(int(codigo_status)) if pd.notna(codigo_status) else None
 
        occurrence_rows.append(
            {
                "id": occurrence_id,
                "origin_file": row.source_file,
                "origin_row": row.source_row,
                "id_especie": id_especie,
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_forma": forma_ids.get(row.forma_vida) if pd.notna(row.forma_vida) else None,
                "id_identificacao": id_identificacao,
                "id_parcela": parcela_ids.get(row.parcela) if pd.notna(row.parcela) else None,
                "amostra": int(row.amostra) if pd.notna(row.amostra) else None,
            }
        )
    return pd.DataFrame(occurrence_rows), pd.DataFrame(satellite_rows)
 


def build_bridges(df: pd.DataFrame, occurrence_df: pd.DataFrame, substrato_ids: dict, observacao_ids: dict):
    occurrence_id_by_key = dict(zip(zip(occurrence_df["origin_file"], occurrence_df["origin_row"]), occurrence_df["id"]))
 
    subs_rows = []
    for key_tuple, lista in zip(zip(df["source_file"], df["source_row"]), df["substrato_lista"]):
        id_briofita = occurrence_id_by_key.get(key_tuple)
        if id_briofita is None:
            continue
        for nome in lista:
            subs_rows.append({"id_briofita": id_briofita, "id_substrato": substrato_ids[nome]})
 
    obs_rows = []
    for key_tuple, lista in zip(zip(df["source_file"], df["source_row"]), df["observacoes_lista"]):
        id_briofita = occurrence_id_by_key.get(key_tuple)
        if id_briofita is None:
            continue
        for comentario in lista:
            obs_rows.append({"id_briofita": id_briofita, "id_observacao": observacao_ids[comentario]})
 
    subs_df = pd.DataFrame(subs_rows).drop_duplicates() if subs_rows else pd.DataFrame(columns=["id_briofita", "id_substrato"])
    obs_df = pd.DataFrame(obs_rows).drop_duplicates() if obs_rows else pd.DataFrame(columns=["id_briofita", "id_observacao"])
    return subs_df, obs_df



def run() -> None:
    df = prepare(load_clean_df())
 
    filo_dim, filo_ids = build_filo(df)
    familia_dim, familia_by_nome = build_familia(df, filo_ids, filo_dim)
    genero_dim, genero_by_nome = build_genero(df, familia_by_nome, familia_dim)
    autor_dim, autor_ids = build_autor(df)
    epiteto_dim, epiteto_ids = build_epiteto_especifico(df, genero_by_nome, autor_ids, genero_dim)
    forma_dim, forma_ids = build_forma_vida(df)
    parcela_dim, parcela_ids = build_parcela(df)
    identificacao_dim, identificacao_ids = build_identificacao()
    substrato_dim, substrato_ids = build_substrato(df)
    observacao_dim, observacao_ids = build_observacao(df)
 
    occurrence_df, occurrence_bryophyte_df = build_occurrence(df, epiteto_ids, forma_ids, identificacao_ids, parcela_ids)
    coleta_substrato_df, coleta_observacao_df = build_bridges(df, occurrence_df, substrato_ids, observacao_ids)
 
    tabelas_upsert = {
        config.TB_FILO: filo_dim,
        config.TB_FAMILIA: familia_dim,
        config.TB_GENERO: genero_dim,
        config.TB_AUTOR: autor_dim,
        config.TB_EPITETO_ESPECIFICO: epiteto_dim,
        config.TB_FORMA_VIDA: forma_dim,
        config.TB_PARCELA: parcela_dim,
        config.TB_IDENTIFICACAO: identificacao_dim,
        config.TB_SUBSTRATO: substrato_dim,
        config.TB_OBSERVACAO: observacao_dim,
        config.TB_OCCURRENCE: occurrence_df,
        config.TB_OCCURRENCE_BRYOPHYTE: occurrence_bryophyte_df,
    }
    for nome_tabela, tabela_df in tabelas_upsert.items():
        write_dataframe_to_postgres(tabela_df, nome_tabela, mode="upsert")
        print(f"[load_SPP] {nome_tabela}: {len(tabela_df)} linhas gravadas.")
 
    write_dataframe_to_postgres(
        coleta_substrato_df, config.TB_COLETA_SUBSTRATO,
        mode="append_composite", composite_key=["id_briofita", "id_substrato"],
    )
    print(f"[load_SPP] {config.TB_COLETA_SUBSTRATO}: {len(coleta_substrato_df)} linhas gravadas.")
 
    write_dataframe_to_postgres(
        coleta_observacao_df, config.TB_COLETA_OBSERVACAO,
        mode="append_composite", composite_key=["id_briofita", "id_observacao"],
    )
    print(f"[load_SPP] {config.TB_COLETA_OBSERVACAO}: {len(coleta_observacao_df)} linhas gravadas.")


if __name__ == "__main__":
    run()
