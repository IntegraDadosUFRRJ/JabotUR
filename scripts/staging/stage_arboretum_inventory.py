"""Carrega as abas "CAP_Coluna" e "tabela_campo_coordenadas" do inventário do arboreto
para as tabelas de staging no PostgreSQL.

O módulo é responsável por:
  - renomear cabeçalhos para o padrão snake_case via config.ARBORETUM_INVENTORY_*_COLUMN_MAP;
  - registrar a linhagem dos dados (arquivo, aba e linha de origem);
  - persistir os dados brutos na tabela de staging de cada aba.

As duas abas têm colunas diferentes e o xlsx_sheet só empilha abas com o mesmo
column_map, por isso cada uma vai para a sua tabela. A leitura e a gravação são feitas
pelo DuckDB (scripts.staging.xlsx_sheet), sem DataFrame.
As linhas da CAP_Coluna que só têm Nome Científico (resíduo de fórmula, '#N/A') não
entram: a coluna não está no column_map, e linha sem nenhuma coluna mapeada é ignorada.
Latitude, longitude e as medidas ficam como texto, do jeito que vieram; a conversão é do clean.
"""

from scripts.staging import xlsx_sheet
import scripts.config as config


def stems_query() -> str:
    return xlsx_sheet.sheets_query(
        config.ARBORETUM_INVENTORY_XLSX_PATH,
        [config.ARBORETUM_INVENTORY_STEMS_SHEET_NAME],
        config.ARBORETUM_INVENTORY_STEMS_COLUMN_MAP,
    )


def field_query() -> str:
    return xlsx_sheet.sheets_query(
        config.ARBORETUM_INVENTORY_XLSX_PATH,
        [config.ARBORETUM_INVENTORY_FIELD_SHEET_NAME],
        config.ARBORETUM_INVENTORY_FIELD_COLUMN_MAP,
    )


def stage_stems() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_INVENTORY_STEMS_TABLE, stems_query(), "stage_arboretum_inventory")


def stage_field() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_INVENTORY_FIELD_TABLE, field_query(), "stage_arboretum_inventory")


def stage_inventory() -> None:
    stage_stems()
    stage_field()


if __name__ == "__main__":
    stage_inventory()
