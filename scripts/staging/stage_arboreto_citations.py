"""Carrega as abas de registro do arboreto (Monografia Gabriel, Livro Pesquisas no JB, JABOT) 
para a tabela de staging no PostgreSQL.
"""

from datetime import datetime, timezone

import pandas as pd

try:
    from scripts.db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    import scripts.config as config
except ImportError:
    from ..db.db_utils import read_dataframe_from_postgres, write_dataframe_to_postgres
    from .. import config


def _extract_one_sheet(sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(
        config.ARBORETO_XLSX_PATH,
        sheet_name=sheet_name,
        header=0,
        dtype=str,
        usecols=config.ARBORETO_CITATION_USECOLS,
    )

    df.columns = [str(c).strip() for c in df.columns]

    # linha 0 do DataFrame == linha 2 da planilha (linha 1 é o cabeçalho)
    df.insert(0, "_source_row", range(2, 2 + len(df)))

    # descarta linhas 100% vazias (fim da planilha / linhas em branco)
    data_cols = list(config.ARBORETO_CITATION_COLUMN_MAP.keys())
    df = df[df[data_cols].notna().any(axis=1)].copy()

    df = df.rename(columns=config.ARBORETO_CITATION_COLUMN_MAP)

    df["_source_file"] = str(config.ARBORETO_XLSX_PATH.name)
    df["_source_sheet"] = sheet_name
    df["_loaded_at"] = datetime.now(timezone.utc)

    ordered_cols = (
        ["_source_file", "_source_sheet", "_source_row"]
        + list(config.ARBORETO_CITATION_COLUMN_MAP.values())
        + ["_loaded_at"]
    )
    return df[ordered_cols]


def extract_citations() -> pd.DataFrame:
    frames = [_extract_one_sheet(sheet_name) for sheet_name in config.ARBORETO_CITATION_SHEETS]
    return pd.concat(frames, ignore_index=True)


def load_staging(df: pd.DataFrame) -> None:
    write_dataframe_to_postgres(df, config.STG_ARBORETO_CITATIONS_TABLE, mode="replace")
    loaded_df = read_dataframe_from_postgres(config.STG_ARBORETO_CITATIONS_TABLE)
    count = len(loaded_df)
    print(f"[stage_arboreto_citations] {config.STG_ARBORETO_CITATIONS_TABLE}: {count} linhas carregadas.")


if __name__ == "__main__":
    df = extract_citations()
    load_staging(df)