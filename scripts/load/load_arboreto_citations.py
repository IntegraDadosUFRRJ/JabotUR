# Lê `cln_arboreto_citations` e povoa as tabelas normalizadas finais do schema no PostgreSQL


import scripts.config as config
from scripts.db import db_utils
from scripts.load import taxonomy

_none_if_nan = taxonomy._none_if_nan


def load_clean_rows(con) -> list[dict]:
    # Os ids saem na ordem das linhas lidas; cln_* não tem id, então a ordem vem da planilha
    return db_utils.read_rows(
        con, config.CLN_ARBORETO_CITATIONS_TABLE, order_by=config.ARBORETO_CITATION_STAGING_ORDER
    )


def prepare(rows: list[dict]) -> list[dict]:
    out = []
    for clean_index, row in enumerate(rows):
        # clean_index é a posição na leitura do clean, contando as linhas de totais
        # descartadas: é o número que os logs mostram para localizar a linha
        source_sheet = row["_source_sheet"]
        source_row = row["_source_row"]

        # linha de totais não gera citação, sai antes do bloco de morfo-espécie
        if row["parse_status"] == config.PARSE_STATUS_TOTAL_ROW:
            print(
                f"[load_arboreto_citations] linha {clean_index} "
                f"({source_sheet}#{source_row}): linha de totais, ignorada"
            )
            continue

        # morfo-espécie e unparseable nunca reconciliam entre fontes (ADR-0003);
        # recebem a origem no nome; epíteto NULL continua NULL
        epiteto_especifico = row["epiteto_especifico"]
        if not row["reconcile_across_sources"] and epiteto_especifico is not None:
            epiteto_especifico = f"{epiteto_especifico} [{source_sheet}#{source_row}]"

        out.append({
            **row,
            # arboreto não tem Filo
            "filo_nome": None,
            "source_file": row["_source_file"],
            "source_sheet": source_sheet,
            "source_row": source_row,
            "epiteto_especifico": epiteto_especifico,
            "epiteto": epiteto_especifico,
            "clean_index": clean_index,
        })
    return out


def build_bibliographic_citation(con, rows: list[dict], epiteto_ids: dict) -> list[dict]:
    existing_keys_to_id = {
        (row["origin_file"], row["origin_sheet"], row["origin_row"]): row["id"]
        for row in taxonomy._load_existing_rows(con, config.TB_BIBLIOGRAPHIC_CITATION)
    }
    next_id = (max(existing_keys_to_id.values()) + 1) if existing_keys_to_id else 1

    citation_rows = []

    for row in rows:
        chave_especie = tuple(
            _none_if_nan(row[column])
            for column in ("genero", "epiteto", "infraespecifico", "autor")
        )
        id_especie = epiteto_ids.get(chave_especie)

        if id_especie is None:
            print(
                f"[load_arboreto_citations] linha {row['clean_index']} "
                f"({row['source_sheet']}#{row['source_row']}): não encontrei "
                f"epíteto para {chave_especie!r}, pulando citação"
            )
            continue

        natural_key = (row["source_file"], row["source_sheet"], row["source_row"])

        if natural_key in existing_keys_to_id:
            citation_id = existing_keys_to_id[natural_key]
        else:
            citation_id = next_id
            existing_keys_to_id[natural_key] = citation_id
            next_id += 1

        quantidade = _none_if_nan(row["quantidade"])
        citation_rows.append(
            {
                "id": citation_id,
                "id_species": id_especie,
                "source": row["source_sheet"],
                "quantity": int(quantidade) if quantidade is not None else None,
                "identification_qualifier": row["identification_qualifier"],
                "origin_file": row["source_file"],
                "origin_sheet": row["source_sheet"],
                "origin_row": row["source_row"],
            }
        )

    return citation_rows


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

        citation_rows = build_bibliographic_citation(con, rows, epiteto_ids)

        # A ordem respeita as chaves estrangeiras: o Postgres as confere a cada comando
        tabelas_upsert = {
            config.TB_FILO: filo_dim,
            config.TB_FAMILIA: familia_dim,
            config.TB_GENERO: genero_dim,
            config.TB_AUTOR: autor_dim,
            config.TB_EPITETO_ESPECIFICO: epiteto_dim,
            config.TB_BIBLIOGRAPHIC_CITATION: citation_rows,
        }
        for nome_tabela, tabela_rows in tabelas_upsert.items():
            db_utils.upsert_rows(con, nome_tabela, tabela_rows)
            gravadas.append((nome_tabela, len(tabela_rows)))

    # Só depois do COMMIT: com erro no meio, nenhuma tabela foi gravada
    for nome_tabela, total in gravadas:
        print(f"[load_arboreto_citations] {nome_tabela}: {total} linhas gravadas.")


if __name__ == "__main__":
    populate_normalized_tables()
