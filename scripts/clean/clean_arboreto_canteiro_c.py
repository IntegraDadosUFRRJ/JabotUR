import os
import duckdb
from scripts import config
from scripts.db import db_utils

def clean_arboreto_canteiro_c_data():
    df_stg = db_utils.read_dataframe_from_postgres("stg_canteiro_c")
    con = duckdb.connect(database=":memory:")
    
    try:
        con.register("stg_canteiro_c", df_stg)

        sql_path = os.path.join(os.path.dirname(__file__), "clean_arboreto_canteiro_c.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            query = f.read()

        df_clean = con.execute(query).df()

        df_clean[config.COL_CANTEIRO_C_FAMILIA] = df_clean["family_clean"]
        df_clean[config.COL_CANTEIRO_C_ESPECIE] = df_clean["species_clean"]
        df_clean[config.COL_CANTEIRO_C_ORIGEM] = df_clean["origin_clean"]
        df_clean[config.COL_CANTEIRO_C_DOMINIO] = df_clean["domain_clean"]
        df_clean[config.COL_CANTEIRO_C_CATEGORIA_CNCFLORA] = df_clean["cncflora_clean"]
        df_clean[config.COL_CANTEIRO_C_ALTURA] = df_clean["height_m_clean"]

        colunas_para_remover = [
            "family_clean", "species_clean", "origin_clean", "domain_clean", "cncflora_clean", "height_m_clean",
            "Família", "Espécie", "Origem", "Domínio fitogeográfico", "Categoria CNCFlora", "Altura (m)"
        ]
        
        colunas_existentes = [col for col in colunas_para_remover if col in df_clean.columns]
        df_clean = df_clean.drop(columns=colunas_existentes)

        db_utils.write_dataframe_to_postgres(
            df_clean, 
            table_name=config.CLN_CANTEIRO_C_TABLE, 
            mode="replace"
        )
        print("Limpeza do Canteiro C realizada com sucesso")

    finally:
        con.close()

if __name__ == "__main__":
    clean_arboreto_canteiro_c_data()