# Lê `cln_spp_briofitas` e povoa as tabelas normalizadas finais do schema no PostgreSQL


# Os transforms do SPP (scripts/transforms) recebem pd.Series: o pandas fica só nessa
# fronteira (_expand_filo e irmãs), e o resto do load trabalha com linhas (list[dict])
import pandas as pd

import scripts.config as config
from scripts.db import db_utils
from scripts.load import taxonomy
import scripts.transforms.filo as filo_t
import scripts.transforms.epiteto_especifico as epiteto_t
import scripts.transforms.substrato as substrato_t
import scripts.transforms.observacoes as observacoes_t

_none_if_nan = taxonomy._none_if_nan
_load_existing_rows = taxonomy._load_existing_rows
_distinct_non_null = taxonomy._distinct_non_null
_merge_ids = taxonomy._merge_ids


def _series(values: list) -> pd.Series:
    # dtype=object: coluna de texto com None para NULL, sem o pandas inferir tipo pelos valores
    return pd.Series(values, dtype=object)


def _expand_filo(values: list) -> list:
    return [_none_if_nan(v) for v in filo_t.expand(_series(values)).tolist()]


def _strip_genero_abbreviation(values: list) -> list:
    return [_none_if_nan(v) for v in epiteto_t.strip_genero_abbreviation(_series(values)).tolist()]


def _expand_multivalued_substrato(values: list) -> list:
    return substrato_t.expand_multivalued(_series(values)).tolist()


def _split_multivalued_observacoes(values: list) -> list:
    return observacoes_t.split_multivalued(_series(values)).tolist()


def load_clean_rows(con) -> list[dict]:
    # Os ids saem na ordem das linhas lidas; cln_* não tem id, então a ordem vem da planilha
    return db_utils.read_rows(con, config.CLN_SPP_TABLE, order_by=config.SPP_STAGING_ORDER)


def _resolve_epiteto_column(columns) -> str:
    for column_name in ("epiteto_especifico", "especie"):
        if column_name in columns:
            return column_name
    raise KeyError("Nenhuma coluna de epíteto encontrada em cln_spp_briofitas")


def prepare(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    epiteto_column = _resolve_epiteto_column(rows[0])
    filo_nomes = _expand_filo([row["filo"] for row in rows])
    epitetos_limpos = _strip_genero_abbreviation([row[epiteto_column] for row in rows])
    substratos = _expand_multivalued_substrato([row["substrato"] for row in rows])
    observacoes = _split_multivalued_observacoes([row["observacoes"] for row in rows])

    out = []
    for row, filo_nome, epiteto_limpo, substrato_lista, observacoes_lista in zip(
        rows, filo_nomes, epitetos_limpos, substratos, observacoes
    ):
        out.append({
            **row,
            "epiteto_especifico": row[epiteto_column],
            "filo_nome": filo_nome,
            "epiteto_limpo": epiteto_limpo,
            "substrato_lista": substrato_lista,
            "observacoes_lista": observacoes_lista,
            "source_file": row["_source_file"],
            "source_row": row["_source_row"],
            # taxonomy.py espera a chave "epiteto";
            # SPP nunca tem infraespecífico;
            "epiteto": epiteto_limpo,
            "infraespecifico": None,
        })
    return out


def build_forma_vida(con, rows: list[dict]):
    existing_ids = {row["tipo"]: row["id"] for row in _load_existing_rows(con, config.TB_FORMA_VIDA)}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["forma_vida"] for row in rows))
    dim = [{"id": i, "tipo": tipo} for tipo, i in ids.items()]
    return dim, ids


def build_parcela(con, rows: list[dict]):
    existing_ids = {row["codigo"]: row["id"] for row in _load_existing_rows(con, config.TB_PARCELA)}
    ids = _merge_ids(existing_ids, _distinct_non_null(row["parcela"] for row in rows))
    dim = [
        {"id": i, "codigo": codigo, "coordenada": config.PARCELA_COORDENADAS.get(str(codigo))}
        for codigo, i in ids.items()
    ]
    return dim, ids


def build_identificacao():
    dim = [
        {"id": codigo, "descricao": descricao}
        for codigo, descricao in config.IDENTIFICACAO_DESCRICAO_MAP.items()
    ]
    ids = {codigo: codigo for codigo in config.IDENTIFICACAO_DESCRICAO_MAP}
    return dim, ids


def build_substrato(con, rows: list[dict]):
    sigla_by_nome = {v: k for k, v in config.SUBSTRATO_NOME_MAP.items()}
    existing_ids = {row["nome"]: row["id"] for row in _load_existing_rows(con, config.TB_SUBSTRATO)}
    # sorted() do Python, não ORDER BY do banco: a ordem alfabética decide os ids novos
    nomes = sorted({nome for row in rows for nome in row["substrato_lista"]})
    ids = _merge_ids(existing_ids, nomes)
    dim = [{"id": i, "nome": nome, "sigla": sigla_by_nome.get(nome)} for nome, i in ids.items()]
    return dim, ids


def build_observacao(con, rows: list[dict]):
    existing_ids = {
        row["comentario"]: row["id"] for row in _load_existing_rows(con, config.TB_OBSERVACAO)
    }
    comentarios = sorted({c for row in rows for c in row["observacoes_lista"]})
    ids = _merge_ids(existing_ids, comentarios)
    dim = [{"id": i, "comentario": comentario} for comentario, i in ids.items()]
    return dim, ids


def build_occurrence(con, rows: list[dict], epiteto_ids: dict, forma_ids: dict, identificacao_ids: dict, parcela_ids: dict):
    existing_keys_to_id = {
        (row["origin_file"], row["origin_row"]): row["id"]
        for row in _load_existing_rows(con, config.TB_OCCURRENCE)
    }
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    occurrence_rows = []
    satellite_rows = []
    for index, row in enumerate(rows):
        # SPP sempre passa infraespecifico=None
        chave_especie = (
            _none_if_nan(row["genero"]),
            _none_if_nan(row["epiteto"]),
            _none_if_nan(row["infraespecifico"]),
            _none_if_nan(row["autor"]),
        )
        id_especie = epiteto_ids.get(chave_especie)
        if id_especie is None:
            print(
                f"[load_SPP] linha {index} ({row['source_file']}#{row['source_row']}): "
                f"não encontrei epíteto para {chave_especie!r}, pulando occurrence"
            )
            continue

        natural_key = (row["source_file"], row["source_row"])
        if natural_key in existing_keys_to_id:
            occurrence_id = existing_keys_to_id[natural_key]
        else:
            occurrence_id = next_id
            existing_keys_to_id[natural_key] = occurrence_id
            next_id += 1

        codigo_status = _none_if_nan(row["status_identificacao"])
        forma_vida = _none_if_nan(row["forma_vida"])
        parcela = _none_if_nan(row["parcela"])
        amostra = _none_if_nan(row["amostra"])

        occurrence_rows.append(
            {
                "id": occurrence_id,
                "id_species": id_especie,
                "basis_of_record": config.SPP_BASIS_OF_RECORD,
                "origin_file": row["source_file"],
                "origin_row": row["source_row"],
            }
        )
        satellite_rows.append(
            {
                "id": occurrence_id,
                "id_forma": forma_ids.get(forma_vida) if forma_vida is not None else None,
                "id_identificacao": identificacao_ids.get(int(codigo_status)) if codigo_status is not None else None,
                "id_parcela": parcela_ids.get(parcela) if parcela is not None else None,
                "amostra": int(amostra) if amostra is not None else None,
            }
        )
    return occurrence_rows, satellite_rows


def build_bridges(rows: list[dict], occurrence_rows: list[dict], substrato_ids: dict, observacao_ids: dict):
    occurrence_id_by_key = {(row["origin_file"], row["origin_row"]): row["id"] for row in occurrence_rows}

    # Pares como chaves de dict: o repetido some e fica a ordem da primeira ocorrência
    subs_pairs = {}
    obs_pairs = {}
    for row in rows:
        id_briofita = occurrence_id_by_key.get((row["source_file"], row["source_row"]))
        if id_briofita is None:
            continue
        for nome in row["substrato_lista"]:
            subs_pairs[(id_briofita, substrato_ids[nome])] = None
        for comentario in row["observacoes_lista"]:
            obs_pairs[(id_briofita, observacao_ids[comentario])] = None

    subs_rows = [{"id_briofita": b, "id_substrato": s} for b, s in subs_pairs]
    obs_rows = [{"id_briofita": b, "id_observacao": o} for b, o in obs_pairs]
    return subs_rows, obs_rows


def populate_normalized_tables() -> None:
    # Uma transação para o load inteiro: leitura dos ids existentes e gravação veem o mesmo
    # estado, e um erro no meio desfaz todas as tabelas deste load (os loads anteriores ficam)
    gravadas = []
    with db_utils.postgres_duckdb() as con, db_utils.transaction(con):
        rows = prepare(load_clean_rows(con))

        filo_dim, filo_ids = taxonomy.build_filo_rows(con, rows)
        familia_dim, familia_by_nome = taxonomy.build_familia_rows(con, rows, filo_ids, filo_dim)
        genero_dim, genero_by_nome = taxonomy.build_genero_rows(con, rows, familia_by_nome, familia_dim)
        autor_dim, autor_ids = taxonomy.build_autor_rows(con, rows)
        epiteto_dim, epiteto_ids = taxonomy.build_epiteto_especifico_rows(
            con, rows, genero_by_nome, autor_ids, genero_dim
        )
        forma_dim, forma_ids = build_forma_vida(con, rows)
        parcela_dim, parcela_ids = build_parcela(con, rows)
        identificacao_dim, identificacao_ids = build_identificacao()
        substrato_dim, substrato_ids = build_substrato(con, rows)
        observacao_dim, observacao_ids = build_observacao(con, rows)

        occurrence_rows, occurrence_bryophyte_rows = build_occurrence(
            con, rows, epiteto_ids, forma_ids, identificacao_ids, parcela_ids
        )
        coleta_substrato_rows, coleta_observacao_rows = build_bridges(
            rows, occurrence_rows, substrato_ids, observacao_ids
        )

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
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
            config.TB_OCCURRENCE: occurrence_rows,
            config.TB_OCCURRENCE_BRYOPHYTE: occurrence_bryophyte_rows,
        }
        for nome_tabela, tabela_rows in tabelas_upsert.items():
            db_utils.upsert_rows(con, nome_tabela, tabela_rows)
            gravadas.append((nome_tabela, len(tabela_rows)))

        db_utils.insert_ignore_rows(
            con, config.TB_COLETA_SUBSTRATO, coleta_substrato_rows, ["id_briofita", "id_substrato"]
        )
        gravadas.append((config.TB_COLETA_SUBSTRATO, len(coleta_substrato_rows)))
        db_utils.insert_ignore_rows(
            con, config.TB_COLETA_OBSERVACAO, coleta_observacao_rows, ["id_briofita", "id_observacao"]
        )
        gravadas.append((config.TB_COLETA_OBSERVACAO, len(coleta_observacao_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for nome_tabela, total in gravadas:
        print(f"[load_SPP] {nome_tabela}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
