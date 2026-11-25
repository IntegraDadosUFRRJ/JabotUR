"""Carrega as abas "CAP_Coluna", "tabela_campo_coordenadas" e "Atualizada" do inventário
do arboreto para as tabelas de staging no PostgreSQL.

O módulo é responsável por:
  - renomear cabeçalhos para o padrão snake_case via config.ARBORETUM_INVENTORY_*_COLUMN_MAP;
  - registrar a linhagem dos dados (arquivo, aba e linha de origem);
  - persistir os dados brutos na tabela de staging de cada aba.

As abas têm colunas diferentes e o xlsx_sheet só empilha abas com o mesmo
column_map, por isso cada uma vai para a sua tabela. A leitura e a gravação são feitas
pelo DuckDB (scripts.staging.xlsx_sheet), sem DataFrame.
As linhas da CAP_Coluna que só têm Nome Científico (resíduo de fórmula, '#N/A') não
entram: a coluna não está no column_map, e linha sem nenhuma coluna mapeada é ignorada.
A Atualizada tem um fuste por linha e o Número só na primeira linha de cada árvore; as
linhas seguintes entram como vieram, sem Número, porque o fill-down é do clean. Os blocos
sem cabeçalho à direita da coluna L não entram: só as colunas do column_map são lidas.
Latitude, longitude e as medidas ficam como texto, do jeito que vieram; a conversão é do clean.
Célula em formato de data chega como o número serial do Excel, em texto.
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


def updated_query() -> str:
    return xlsx_sheet.sheets_query(
        config.ARBORETUM_INVENTORY_XLSX_PATH,
        [config.ARBORETUM_INVENTORY_UPDATED_SHEET_NAME],
        config.ARBORETUM_INVENTORY_UPDATED_COLUMN_MAP,
    )


def stage_stems() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_INVENTORY_STEMS_TABLE, stems_query(), "stage_arboretum_inventory")


def stage_field() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_INVENTORY_FIELD_TABLE, field_query(), "stage_arboretum_inventory")


def stage_updated() -> None:
    xlsx_sheet.write_staging(config.STG_ARBORETUM_INVENTORY_UPDATED_TABLE, updated_query(), "stage_arboretum_inventory")


def stage_inventory() -> None:
    stage_stems()
    stage_field()
    stage_updated()


if __name__ == "__main__":
    stage_inventory()
