"""Carrega a aba "SPP - JB" da planilha original para a tabela de staging no PostgreSQL.

O módulo é responsável por:
  - renomear cabeçalhos para o padrão snake_case via config.SPP_COLUMN_MAP;
  - registrar a linhagem dos dados (arquivo, planilha e linha de origem);
  - persistir os dados brutos na tabela de staging.

A leitura e a gravação são feitas pelo DuckDB (scripts.staging.xlsx_sheet), sem DataFrame.
"""

from scripts.staging import xlsx_sheet
import scripts.config as config


def spp_query() -> str:
    return xlsx_sheet.sheets_query(config.SPP_XLSX_PATH, [config.SPP_SHEET_NAME], config.SPP_COLUMN_MAP)


def stage_spp() -> None:
    xlsx_sheet.write_staging(config.STG_SPP_TABLE, spp_query(), "stage_spp")


if __name__ == "__main__":
    stage_spp()
