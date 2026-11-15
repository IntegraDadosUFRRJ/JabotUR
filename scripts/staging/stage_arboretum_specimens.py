"""Carrega a aba "Espécimes" da planilha do arboreto para a tabela de staging no PostgreSQL.

O módulo é responsável por:
  - renomear cabeçalhos para o padrão snake_case via config.ARBORETO_SPECIMENS_COLUMN_MAP;
  - registrar a linhagem dos dados (arquivo, aba e linha de origem);
  - persistir os dados brutos na tabela de staging.

A leitura e a gravação são feitas pelo DuckDB (scripts.staging.xlsx_sheet), sem DataFrame.
As colunas são escolhidas pelo nome do cabeçalho (chaves do column_map), não pela letra:
as que não estão no map (Canteiro, Procedência, ADICIONAR) ficam de fora.
"""

from scripts.staging import xlsx_sheet
import scripts.config as config


def specimens_query() -> str:
    return xlsx_sheet.sheets_query(
        config.ARBORETO_XLSX_PATH, [config.ARBORETO_SPECIMENS_SHEET_NAME], config.ARBORETO_SPECIMENS_COLUMN_MAP
    )


def stage_specimens() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETO_SPECIMENS_TABLE, specimens_query(), "stage_arboreto_specimens")


if __name__ == "__main__":
    stage_specimens()
