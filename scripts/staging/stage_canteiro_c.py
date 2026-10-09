import pandas as pd
from scripts import config
from scripts.db import db_utils

def stage_canteiro_c_data():
    
    # 1. Lê a aba do Canteiro C usando as variáveis do config.py
    df = pd.read_excel(
        config.ARBORETO_XLSX_PATH,
        sheet_name=config.CANTEIRO_C_SHEET_NAME
    )

    # 2. Adiciona os metadados de linhagem
    df["_source_file"] = "Diversidade florística do arboreto do JB.xlsx"
    df["_source_sheet"] = config.CANTEIRO_C_SHEET_NAME
    df["_source_row"] = df.index + 2  # Considera o cabeçalho no Excel

    # 3. Salva no banco usando mode="replace" para staging
    db_utils.write_dataframe_to_postgres(
        df, 
        table_name="stg_canteiro_c", 
        mode="replace"
    )
    print("Staging do Canteiro C realizado com sucesso!")

if __name__ == "__main__":
    stage_canteiro_c_data()