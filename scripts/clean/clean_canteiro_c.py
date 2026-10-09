import duckdb
from scripts import config
from scripts.db import db_utils

def clean_canteiro_c_data():
    
    df_stg = db_utils.read_dataframe_from_postgres("stg_canteiro_c")
    con = duckdb.connect(database=":memory:")
    con.register("stg_canteiro_c", df_stg)

    query = f"""
    SELECT 
        *,
        CASE 
            WHEN TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IS NOT NULL 
                THEN TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE)
            ELSE NULL 
        END AS altura_m,
        CASE 
            WHEN "{config.COL_CANTEIRO_C_ESPECIE}" IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
            ELSE "{config.COL_CANTEIRO_C_ESPECIE}" 
        END AS especie_clean,
        CASE 
            WHEN "Família" IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
            ELSE "Família" 
        END AS familia_clean,
        CASE 
            WHEN "{config.COL_CANTEIRO_C_ESPECIE}" IS NULL 
              OR "{config.COL_CANTEIRO_C_ESPECIE}" IN ('na', 'NA', 'sem id', 'SEM ID')
              OR ("{config.COL_CANTEIRO_C_ALTURA}" IS NOT NULL 
                  AND TRY_CAST(REPLACE(CAST("{config.COL_CANTEIRO_C_ALTURA}" AS VARCHAR), ',', '.') AS DOUBLE) IS NULL)
            THEN TRUE 
            ELSE FALSE 
        END AS needs_review
    FROM stg_canteiro_c
    """

    df_clean = con.execute(query).df()

    df_clean[config.COL_CANTEIRO_C_ESPECIE] = df_clean["especie_clean"]
    df_clean["Família"] = df_clean["familia_clean"]
    df_clean = df_clean.drop(columns=["especie_clean", "familia_clean"])

    db_utils.write_dataframe_to_postgres(
        df_clean, 
        table_name=config.CLN_CANTEIRO_C_TABLE, 
        mode="replace"
    )
    print("Limpeza do Canteiro C com DuckDB realizada com sucesso!")

if __name__ == "__main__":
    clean_canteiro_c_data()