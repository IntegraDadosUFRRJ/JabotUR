"""Carrega a aba "Espécimes" da planilha do arboreto para a tabela de staging no PostgreSQL.

O módulo é responsável por:
  - normalizar cabeçalhos com espaço em branco inconsistente entre abas;
  - registrar a linhagem dos dados (arquivo, aba e linha de origem);
  - persistir os dados brutos na tabela de staging.
"""

from datetime import datetime, timezone

import pandas as pd

try:
    from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    import scripts.config as config
except ImportError:
    from ..db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from .. import config


def extract_specimens() -> pd.DataFrame:
    df = pd.read_excel(
        config.ARBORETO_XLSX_PATH,
        sheet_name=config.ARBORETO_SPECIMENS_SHEET_NAME,
        header=0,
        dtype=str,
        usecols=config.ARBORETO_SPECIMENS_USECOLS,
    )

    # normaliza antes de bater com as chaves de ARBORETO_SPECIMENS_COLUMN_MAP
    df.columns = [str(c).strip() for c in df.columns]

    # linha 0 do DataFrame == linha 2 da planilha (linha 1 é o cabeçalho)
    df.insert(0, "_source_row", range(2, 2 + len(df)))

    # descarta linhas 100% vazias (fim da planilha / linhas em branco)
    data_cols = list(config.ARBORETO_SPECIMENS_COLUMN_MAP.keys())
    df = df[df[data_cols].notna().any(axis=1)].copy()

    df = df.rename(columns=config.ARBORETO_SPECIMENS_COLUMN_MAP)

    df["_source_file"] = str(config.ARBORETO_XLSX_PATH.name)
    df["_source_sheet"] = config.ARBORETO_SPECIMENS_SHEET_NAME
    df["_loaded_at"] = datetime.now(timezone.utc)

    ordered_cols = (
        ["_source_file", "_source_sheet", "_source_row"]
        + list(config.ARBORETO_SPECIMENS_COLUMN_MAP.values())
        + ["_loaded_at"]
    )
    return df[ordered_cols]


def load_staging(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.STG_ARBORETO_SPECIMENS_TABLE, mode="replace")
    loaded_df = read_dataframe_from_postgres(config.STG_ARBORETO_SPECIMENS_TABLE)
    count = len(loaded_df)
    print(f"[stage_arboreto_specimens] {config.STG_ARBORETO_SPECIMENS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    df = extract_specimens()
    load_staging(df)
