"""Carrega as abas de registro do arboreto (Monografia Gabriel, Livro Pesquisas no JB, JABOT)
para a tabela de staging no PostgreSQL.

O módulo é responsável por:
  - renomear cabeçalhos para o padrão snake_case via config.ARBORETUM_CITATION_COLUMN_MAP;
  - registrar a linhagem dos dados (arquivo, aba e linha de origem);
  - persistir os dados brutos na tabela de staging.

A leitura e a gravação são feitas pelo DuckDB (scripts.staging.xlsx_sheet), sem DataFrame.
As três abas entram numa única query, na ordem de config.ARBORETUM_CITATION_SHEETS.
"""

from scripts.staging import xlsx_sheet
import scripts.config as config


def citations_query() -> str:
    return xlsx_sheet.sheets_query(
        config.ARBORETO_XLSX_PATH, config.ARBORETUM_CITATION_SHEETS, config.ARBORETUM_CITATION_COLUMN_MAP
    )


def stage_citations() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_CITATIONS_TABLE, citations_query(), "stage_arboretum_citations")


if __name__ == "__main__":
    stage_citations()
