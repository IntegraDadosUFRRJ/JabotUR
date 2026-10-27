import duckdb
from scripts import config
from scripts.db import db_utils

def clean_arboreto_canteiro_c_data():
    df_stg = db_utils.read_dataframe_from_postgres("stg_canteiro_c")
    con = duckdb.connect(database=":memory:")
    
    try:
        con.register("stg_canteiro_c", df_stg)

        query = f"""
        SELECT 
            *,
            -- Limpeza e padronização da Família
            CASE 
                WHEN TRIM("{config.COL_CANTEIRO_C_FAMILIA}") IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
                ELSE TRIM("{config.COL_CANTEIRO_C_FAMILIA}")
            END AS familia_clean,

            -- Limpeza e padronização da Espécie
            CASE 
                WHEN TRIM("{config.COL_CANTEIRO_C_ESPECIE}") IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
                ELSE TRIM("{config.COL_CANTEIRO_C_ESPECIE}")
            END AS especie_clean,

            -- Padronização da Origem
            CASE 
                WHEN LOWER(TRIM("{config.COL_CANTEIRO_C_ORIGEM}")) IN ('exótico', 'exótica') THEN 'Exótica'
                WHEN LOWER(TRIM("{config.COL_CANTEIRO_C_ORIGEM}")) IN ('na', 'sem id') THEN NULL
                ELSE TRIM("{config.COL_CANTEIRO_C_ORIGEM}")
            END AS origem_clean,

            -- Padronização do Domínio Fitogeográfico
            CASE 
                WHEN LOWER(TRIM("{config.COL_CANTEIRO_C_DOMINIO}")) IN ('na', 'sem id') THEN NULL
                ELSE TRIM("{config.COL_CANTEIRO_C_DOMINIO}")
            END AS dominio_clean,

            -- Padronização CNCFlora (mantém 'NA' como código e força maiúsculas)
            CASE 
                WHEN LOWER(TRIM("{config.COL_CANTEIRO_C_CATEGORIA_CNCFLORA}")) = 'na' THEN 'NA'
                ELSE UPPER(TRIM("{config.COL_CANTEIRO_C_CATEGORIA_CNCFLORA}"))
            END AS cncflora_clean,

            -- Conversão de Altura para metros (forçando NULL para 15124 e 15125)
            CASE 
                WHEN TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IN (15124, 15125)
                    THEN NULL
                WHEN TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IS NOT NULL 
                    THEN TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE)
                ELSE NULL 
            END AS height_m,

            -- Marcação de linhas que necessitam de revisão
            CASE 
                WHEN "{config.COL_CANTEIRO_C_ESPECIE}" IS NULL 
                  OR TRIM("{config.COL_CANTEIRO_C_ESPECIE}") IN ('na', 'NA', 'sem id', 'SEM ID')
                  OR ("{config.COL_CANTEIRO_C_ALTURA}" IS NOT NULL 
                      AND TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IS NULL)
                  OR TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IN (15124, 15125)
                THEN TRUE 
                ELSE FALSE 
            END AS needs_review,

            -- Timestamp de rastreabilidade do processamento
            CURRENT_TIMESTAMP AS _cleaned_at

        FROM stg_canteiro_c
        """

        df_clean = con.execute(query).df()

        -- Atualiza as colunas de origem com os valores higienizados
        df_clean[config.COL_CANTEIRO_C_ESPECIE] = df_clean["especie_clean"]
        df_clean[config.COL_CANTEIRO_C_FAMILIA] = df_clean["familia_clean"]
        df_clean[config.COL_CANTEIRO_C_ORIGEM] = df_clean["origem_clean"]
        df_clean[config.COL_CANTEIRO_C_DOMINIO] = df_clean["dominio_clean"]
        df_clean[config.COL_CANTEIRO_C_CATEGORIA_CNCFLORA] = df_clean["cncflora_clean"]

        -- Remove as colunas temporárias
        df_clean = df_clean.drop(columns=[
            "especie_clean", "familia_clean", "origem_clean", "dominio_clean", "cncflora_clean"
        ])

        db_utils.write_dataframe_to_postgres(
            df_clean, 
            table_name=config.CLN_CANTEIRO_C_TABLE, 
            mode="replace"
        )
        print("Limpeza do Canteiro C realizada com sucesso!")

    finally:
        con.close()

if __name__ == "__main__":
    clean_arboreto_canteiro_c_data()