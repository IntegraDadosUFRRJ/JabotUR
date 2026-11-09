import os
import duckdb
from scripts import config
from scripts.db import db_utils

def read_staging():
    return db_utils.read_dataframe_from_postgres("stg_canteiro_c")


def transform(df_stg):
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
            "Altura (m)" 
        ]
        
        colunas_existentes = [col for col in colunas_para_remover if col in df_clean.columns]
        df_clean = df_clean.drop(columns=colunas_existentes)

        return df_clean
    finally:
        con.close()


def save_clean(df_clean):
    db_utils.write_dataframe_to_postgres(
        df_clean, 
        table_name=config.CLN_CANTEIRO_C_TABLE, 
        mode="replace"
    )


def clean_arboreto_canteiro_c_data():
    df_stg = read_staging()
    df_clean = transform(df_stg)
    save_clean(df_clean)
    print("Limpeza do Canteiro C realizada com sucesso")


if __name__ == "__main__":
    clean_arboreto_canteiro_c_data()