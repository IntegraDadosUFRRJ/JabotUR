"""
Lê `cln_spp_briofitas` e povoa as tabelas normalizadas finais do schema
briofitasSPP.md no PostgreSQL:

    filo, familia, genero, autor, epiteto_especifico, forma_vida, parcela,
    substrato, identificacao, coleta, coleta_substrato, coleta_observacao,
    observacao
"""

import pandas as pd

try:
    from . import config
    from .db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from .transforms import epiteto_especifico as epiteto_t
    from .transforms import filo as filo_t
    from .transforms import observacoes as observacoes_t
    from .transforms import substrato as substrato_t
except ImportError:
    import config
    from db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
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


def _assign_ids(keys, start: int = 1) -> dict:
    ids = {}
    next_id = start
    for key in keys:
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
    return out


def build_filo(df: pd.DataFrame):
    nomes = df["filo_nome"].dropna().unique().tolist()
    ids = _assign_ids(nomes)
    dim = pd.DataFrame({"id": list(ids.values()), "nome": list(ids.keys())})
    return dim, ids


def build_familia(df: pd.DataFrame, filo_ids: dict):
    pares = list(df.dropna(subset=["familia"])[["filo_nome", "familia"]].itertuples(index=False, name=None))
    ids = _assign_ids(pares)
    rows = [{"id": i, "id_filo": filo_ids.get(filo_nome), "nome": nome} for (filo_nome, nome), i in ids.items()]
    dim = pd.DataFrame(rows)
    familia_by_nome = {nome: i for (filo_nome, nome), i in ids.items()}
    return dim, familia_by_nome


def build_genero(df: pd.DataFrame, familia_by_nome: dict):
    pares = list(df.dropna(subset=["genero"])[["familia", "genero"]].itertuples(index=False, name=None))
    ids = _assign_ids(pares)
    rows = [{"id": i, "id_familia": familia_by_nome.get(familia_nome), "nome": nome} for (familia_nome, nome), i in ids.items()]
    dim = pd.DataFrame(rows)
    genero_by_nome = {nome: i for (familia_nome, nome), i in ids.items()}
    return dim, genero_by_nome


def build_autor(df: pd.DataFrame):
    nomes = df["autor"].dropna().unique().tolist()
    ids = _assign_ids(nomes)
    dim = pd.DataFrame({"id": list(ids.values()), "nome": list(ids.keys())})
    return dim, ids


def build_epiteto_especifico(df: pd.DataFrame, genero_by_nome: dict, autor_ids: dict):
    chave = list(
        df.dropna(subset=["epiteto_limpo"])[["genero", "epiteto_limpo", "autor"]]
        .itertuples(index=False, name=None)
    )
    ids = _assign_ids(chave)
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
    tipos = df["forma_vida"].dropna().unique().tolist()
    ids = _assign_ids(tipos)
    dim = pd.DataFrame({"id": list(ids.values()), "tipo": list(ids.keys())})
    return dim, ids


def build_parcela(df: pd.DataFrame):
    valores = df["parcela"].dropna().unique().tolist()
    ids = _assign_ids(valores)
    dim = pd.DataFrame(
        {
            "id": list(ids.values()),
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
    nomes = sorted({nome for lista in df["substrato_lista"] for nome in lista})
    sigla_by_nome = {v: k for k, v in config.SUBSTRATO_NOME_MAP.items()}
    ids = _assign_ids(nomes)
    dim = pd.DataFrame(
        {
            "id": list(ids.values()),
            "nome": list(ids.keys()),
            "sigla": [sigla_by_nome.get(nome) for nome in ids.keys()],
        }
    )
    return dim, ids


def build_observacao(df: pd.DataFrame):
    comentarios = sorted({c for lista in df["observacoes_lista"] for c in lista})
    ids = _assign_ids(comentarios)
    dim = pd.DataFrame({"id": list(ids.values()), "comentario": list(ids.keys())})
    return dim, ids


def build_coleta(df: pd.DataFrame, epiteto_ids: dict, forma_ids: dict, identificacao_ids: dict, parcela_ids: dict):
    rows = []
    for row in df.itertuples(index=True):
        chave_especie = (row.genero, row.epiteto_limpo, row.autor)
        id_especie = epiteto_ids.get(chave_especie)
        if id_especie is None:
            print(f"[load_SPP] linha {row.Index}: não encontrei epíteto para {chave_especie!r}, pulando coleta")
            continue

        codigo_status = row.status_identificacao
        id_identificacao = identificacao_ids.get(int(codigo_status)) if pd.notna(codigo_status) else None

        rows.append(
            {
                "id": row.Index + 1,
                "id_especie": id_especie,
                "id_forma": forma_ids.get(row.forma_vida) if pd.notna(row.forma_vida) else None,
                "id_identificacao": id_identificacao,
                "id_parcela": parcela_ids.get(row.parcela) if pd.notna(row.parcela) else None,
                "amostra": int(row.amostra) if pd.notna(row.amostra) else None,
            }
        )
    return pd.DataFrame(rows)


def build_bridges(df: pd.DataFrame, coleta_df: pd.DataFrame, substrato_ids: dict, observacao_ids: dict):
    coleta_id_by_index = {i: i + 1 for i in df.index}
    valid_coleta_ids = set(coleta_df["id"])

    subs_rows = []
    for idx, lista in df["substrato_lista"].items():
        id_briofita = coleta_id_by_index[idx]
        if id_briofita not in valid_coleta_ids:
            continue
        for nome in lista:
            subs_rows.append({"id_briofita": id_briofita, "id_substrato": substrato_ids[nome]})

    obs_rows = []
    for idx, lista in df["observacoes_lista"].items():
        id_briofita = coleta_id_by_index[idx]
        if id_briofita not in valid_coleta_ids:
            continue
        for comentario in lista:
            obs_rows.append({"id_briofita": id_briofita, "id_observacao": observacao_ids[comentario]})

    return pd.DataFrame(subs_rows), pd.DataFrame(obs_rows)


def run() -> None:
    df = prepare(load_clean_df())

    filo_dim, filo_ids = build_filo(df)
    familia_dim, familia_by_nome = build_familia(df, filo_ids)
    genero_dim, genero_by_nome = build_genero(df, familia_by_nome)
    autor_dim, autor_ids = build_autor(df)
    epiteto_dim, epiteto_ids = build_epiteto_especifico(df, genero_by_nome, autor_ids)
    forma_dim, forma_ids = build_forma_vida(df)
    parcela_dim, parcela_ids = build_parcela(df)
    identificacao_dim, identificacao_ids = build_identificacao()
    substrato_dim, substrato_ids = build_substrato(df)
    observacao_dim, observacao_ids = build_observacao(df)

    coleta_df = build_coleta(df, epiteto_ids, forma_ids, identificacao_ids, parcela_ids)
    coleta_substrato_df, coleta_observacao_df = build_bridges(df, coleta_df, substrato_ids, observacao_ids)

    tabelas = {
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
        config.TB_COLETA: coleta_df,
        config.TB_COLETA_SUBSTRATO: coleta_substrato_df,
        config.TB_COLETA_OBSERVACAO: coleta_observacao_df,
    }

    for nome_tabela, tabela_df in tabelas.items():
        write_dataframe_to_postgres(tabela_df, nome_tabela)
        print(f"[load_SPP] {nome_tabela}: {len(tabela_df)} linhas gravadas.")


if __name__ == "__main__":
    run()
