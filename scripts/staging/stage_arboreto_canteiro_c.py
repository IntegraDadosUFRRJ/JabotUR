import duckdb
from scripts import config
from scripts.db import db_utils

def stage_arboreto_canteiro_c_data():
    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL spatial; LOAD spatial;")

    query = f"""
    SELECT 
        *,
        '{config.ARBORETO_XLSX_PATH.name}' AS _source_file,
        '{config.CANTEIRO_C_SHEET_NAME}' AS _source_sheet,
        row_number() OVER () + 1 AS _source_row
    FROM st_read('{config.ARBORETO_XLSX_PATH}', layer='{config.CANTEIRO_C_SHEET_NAME}')
    """
    
    df_stg = con.execute(query).df()

    db_utils.write_dataframe_to_postgres(
        df_stg, 
        table_name="stg_canteiro_c", 
        mode="replace"
    )
    print("Staging do Canteiro C realizado com sucesso via DuckDB!")

if __name__ == "__main__":
    stage_arboreto_canteiro_c_data()