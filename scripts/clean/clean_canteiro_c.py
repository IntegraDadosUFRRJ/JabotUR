import pandas as pd
import numpy as np
from scripts import config
from scripts.db import db_utils

def clean_canteiro_c_data():
   
    # 1. Lê os dados brutos salvos na staging
    df = db_utils.read_dataframe_from_postgres("stg_canteiro_c")

    # Inicializa colunas de controle de qualidade
    df["needs_review"] = False
    df["parse_status"] = "OK"

    # 2. Tratamento do campo Altura (m)
    def parse_altura(val):
        if pd.isna(val):
            return None
        val_str = str(val).strip().replace(",", ".")
        try:
            return float(val_str)
        except ValueError:
            return None  # Retorna None para textos invalidos (ex: 'A', 'B')

    # Aplica o parse na altura
    altura_original = df[config.COL_CANTEIRO_C_ALTURA]
    df["altura_m"] = altura_original.apply(parse_altura)

    # Marca needs_review caso haja texto invalido na altura onde havia conteudo original
    invalid_altura_mask = altura_original.notna() & df["altura_m"].isna()
    df.loc[invalid_altura_mask, "needs_review"] = True
    df.loc[invalid_altura_mask, "parse_status"] = "ALTURA_INVALIDA"

    # 3. Tratamento de campos em branco / "na"
    for col in [config.COL_CANTEIRO_C_ESPECIE, config.COL_CANTEIRO_C_FAMILIA]:
        if col in df.columns:
            # Substitui 'na' ou 'sem id' por Nulo
            df[col] = df[col].replace(["na", "NA", "sem id", "SEM ID"], None)

    # Marca para revisão se a espécie estiver ausente
    df.loc[df[config.COL_CANTEIRO_C_ESPECIE].isna(), "needs_review"] = True

    # 4. Salva o resultado na camada clean
    db_utils.write_dataframe_to_postgres(
        df, 
        table_name=config.CLN_CANTEIRO_C_TABLE, 
        mode="replace"
    )
    print("Limpeza (Clean) do Canteiro C realizada com sucesso!")

if __name__ == "__main__":
    clean_canteiro_c_data()