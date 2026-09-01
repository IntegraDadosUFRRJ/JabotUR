"""
Extração das abas de Espécimes e Lista Completa do Arboreto para o PostgreSQL.
"""

from pathlib import Path
import pandas as pd

try:
    from scripts.db.db_utils import write_dataframe_to_postgres
    import scripts.config as config
except ImportError:
    from ..db.db_utils import write_dataframe_to_postgres
    from .. import config


def stage_arboreto_sheets(xlsx_path: Path = config.ARBORETO_CITATIONS_XLSX_PATH) -> None:
    # 1. Carrega a aba de Espécimes
    print(f"Lendo aba 'Espécimes' de {xlsx_path.name}...")
    df_especimes = pd.read_excel(xlsx_path, sheet_name="Espécimes", dtype=str)
    df_especimes["_source_file"] = xlsx_path.name
    df_especimes["_source_sheet"] = "Espécimes"
    df_especimes["_source_row"] = df_especimes.index + 2
    write_dataframe_to_postgres(df_especimes, config.STG_ARBORETO_ESPECIMES_TABLE, mode="replace")
    print(f"[OK] {config.STG_ARBORETO_ESPECIMES_TABLE}: {len(df_especimes)} registros gravados.")

    # 2. Carrega a aba 'Lista completa Sps' (Fitogeografia e Ameaça)
    print(f"Lendo aba 'Lista completa Sps' de {xlsx_path.name}...")
    df_lista = pd.read_excel(xlsx_path, sheet_name="Lista completa Sps", dtype=str)
    df_lista["_source_file"] = xlsx_path.name
    df_lista["_source_sheet"] = "Lista completa Sps"
    df_lista["_source_row"] = df_lista.index + 2
    write_dataframe_to_postgres(df_lista, config.STG_ARBORETO_LISTA_SPS_TABLE, mode="replace")
    print(f"[OK] {config.STG_ARBORETO_LISTA_SPS_TABLE}: {len(df_lista)} registros gravados.")


if __name__ == "__main__":
    stage_arboreto_sheets()