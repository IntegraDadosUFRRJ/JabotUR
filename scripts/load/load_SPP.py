# Lê `cln_spp_briofitas` e povoa as tabelas normalizadas finais do schema no PostgreSQL


import pandas as pd

import scripts.config as config
from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
from scripts.load import taxonomy
import scripts.transforms.filo as filo_t
import scripts.transforms.epiteto_especifico as epiteto_t
import scripts.transforms.substrato as substrato_t
import scripts.transforms.observacoes as observacoes_t


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


_load_existing = taxonomy._load_existing
_merge_ids = taxonomy._merge_ids


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

    # taxonomy.py espera a coluna "epiteto";
    # SPP nunca tem infraespecífico;
    out["epiteto"] = out["epiteto_limpo"]
    out["infraespecifico"] = None
    return out


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
        # SPP sempre passa infraespecifico=None 
        chave_especie = (row.genero, row.epiteto, row.infraespecifico, row.autor)
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



def populate_normalized_tables() -> None:
    df = prepare(load_clean_df())
 
    filo_dim, filo_ids = taxonomy.build_filo(df)
    familia_dim, familia_by_nome = taxonomy.build_familia(df, filo_ids, filo_dim)
    genero_dim, genero_by_nome = taxonomy.build_genero(df, familia_by_nome, familia_dim)
    autor_dim, autor_ids = taxonomy.build_autor(df)
    epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico(df, genero_by_nome, autor_ids, genero_dim)
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
    populate_normalized_tables()
