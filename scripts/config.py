"""
Configuração central do pipeline de ETL do JabotUR

- caminhos de arquivo;
- nomes de planilha/aba;
- nomes de tabela no PostgreSQL;
- constantes de negócio usadas na etapa de limpeza;
"""

import os
from pathlib import Path

# === Caminhos ===

# Planilha de origem — SPP (briófitas)
SPP_XLSX_PATH = Path("data/bryophyte_collections.xlsx")

# Planilha de origem — arboreto
ARBORETO_XLSX_PATH = Path("data/arboretum_floristic_diversity.xlsx")

# Configuração de conexão com o PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "jabotur")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# Nome do banco Postgres anexado ao DuckDB (ATTACH ... AS <alias>)
DUCKDB_POSTGRES_ALIAS = "pg"
# Espera máxima por lock na conexão do DuckDB com o Postgres: um lock preso vira erro
POSTGRES_LOCK_TIMEOUT = "30s"

# Nome da tabela registrada no DuckDB durante o transform()
DUCKDB_STAGING_ALIAS = "df_input"

# === Briofitas (SPP) ===
SPP_SHEET_NAME = "SPP - JB"

# === Arboreto (Especimes) ===
ARBORETO_SPECIMENS_SHEET_NAME = "Espécimes"

# === Arboreto (Monografia Gabriel, Livro Pesquisas, JABOT) ===
ARBORETO_CITATION_SHEETS = [
    "Monografia Gabriel",
    "Livro Pesquisas no JB",
    "JABOT",
]


# === COLUMN MAPS: Nome na planilha original -> nome da coluna normalizado ===

SPP_COLUMN_MAP = {
    "Parcela": "plot",
    "Amostra": "sample",
    "StatusIdentificacao*": "identification_status",
    "Filo": "phylum",
    "Família": "family",
    "Gênero": "genus",
    "Espécie": "epithet",
    "Autor": "author",
    "Forma de Vida": "life_form",
    "Substrato": "substrate",
    "Observações": "remark",
}

# Nome na planilha original -> nome da coluna normalizado
ARBORETO_CITATION_COLUMN_MAP = {
    "Família": "family",
    "Espécie": "species_raw",
    "Quant": "quantity",
}

ARBORETO_SPECIMENS_COLUMN_MAP = {
    "Família": "family",
    "Espécie": "species_raw",
    "N° de registro": "registration_number",
    "Setor": "sector",
    "Descrição da localização": "location_description",
    "Estado reprodutivo": "reproductive_status",
}

STG_SPP_TABLE = "stg_spp_bryophytes"
CLN_SPP_TABLE = "cln_spp_bryophytes"
STG_ARBORETO_CITATIONS_TABLE = "stg_arboretum_citations"
CLN_ARBORETO_CITATIONS_TABLE = "cln_arboretum_citations"
STG_ARBORETO_SPECIMENS_TABLE = "stg_arboretum_specimens"
CLN_ARBORETO_SPECIMENS_TABLE = "cln_arboretum_specimens"

# Citações do arboreto: linhas de totais
PARSE_STATUS_TOTAL_ROW = "total_row"
ARBORETO_CITATION_COL_FAMILY_RAW = "family_raw"

# Colunas de linhagem que o staging grava em toda fonte
SOURCE_FILE_COL = "_source_file"
SOURCE_SHEET_COL = "_source_sheet"
SOURCE_ROW_COL = "_source_row"

# Ordem da planilha usada na leitura do staging, no row_number() do clean e na leitura do clean pelos loads
ARBORETO_CITATION_STAGING_ORDER = [SOURCE_FILE_COL, SOURCE_SHEET_COL, SOURCE_ROW_COL]
ARBORETO_SPECIMENS_STAGING_ORDER = [SOURCE_FILE_COL, SOURCE_SHEET_COL, SOURCE_ROW_COL]
SPP_STAGING_ORDER = [SOURCE_FILE_COL, SOURCE_ROW_COL]

# === Nomes das tabelas finais normalizadas ===
TB_FILO = "phylum"
TB_FAMILIA = "family"
TB_GENERO = "genus"
TB_AUTOR = "author"
TB_EPITETO_ESPECIFICO = "species"
TB_FORMA_VIDA = "life_form"
TB_PARCELA = "plot"
TB_SUBSTRATO = "substrate"
TB_IDENTIFICACAO = "identification_status"
TB_OCCURRENCE = "occurrence"
TB_OCCURRENCE_BRYOPHYTE = "occurrence_bryophyte"
TB_COLETA_SUBSTRATO = "occurrence_substrate"
TB_COLETA_OBSERVACAO = "occurrence_remark"
TB_OBSERVACAO = "remark"
TB_BIBLIOGRAPHIC_CITATION = "bibliographic_citation"
TB_SECTOR = "sector"
TB_REPRODUCTIVE_STATUS = "reproductive_status"
TB_OCCURRENCE_ARBORETUM = "occurrence_arboretum"

# === Constantes de negócio usadas na etapa clean ===

# Correções de vocabulário em Observações (SPP)
OBSERVACAO_REGEX_FIXES = [
    (r"poste de cimento", "cimento"),
    (r"cimento de placa[^;]*pau[\s\-]?brasil", "cimento"),
    (r"acro\s*\[\s*fotos\s*\]", "acro"),
    (r"\bacro\b", "acrocárpico"),
    (r"\bpleuro\b", "pleurocárpico"),
    (r"\bc(?:\s*[\./]\s*|\s+)?esp\b", "com esporófito"),
]

# === Constantes de negócio usadas no load final ===
 
# Legendas Tabela_Briofitas: FILO id/nome/sigla
FILO_NOME_MAP = {
    "M": "Musgos",
    "H": "Hepáticas",
}
 
# Legendas Tabela_Briofitas: Substrato
SUBSTRATO_NOME_MAP = {
    "RZ": "Raiz de árvore",
    "S": "Solo",
    "TD": "Tronco em decomposição",
    "TV": "Tronco vivo",
    "A": "Artificial",
}
 
# Legendas Tabela_Briofitas: StatusIdentificacao
IDENTIFICACAO_DESCRICAO_MAP = {
    1: "Identificada",
    2: "Parcialmente Identificada",
    3: "Dúvida",
}
 
# Coordenadas das parcelas 
PARCELA_COORDENADAS = {
    "1": "22° 45' 54.2\"S 43° 41' 31.1\"O",  
    "2": "22° 45' 57.3\"S 43° 41' 34\"O",     
    "3": "22° 45' 54.3\"S 43° 41' 33.7\"O",   
    "4": "22° 45' 54.9\"S 43° 41' 34.5\"O",   
    "5": "22° 45' 59.3\"S 43° 41' 37.5\"O",   
}

# Briófitas coletadas e herborizadas (Darwin Core basisOfRecord)
SPP_BASIS_OF_RECORD = "PreservedSpecimen"

# São as árvores vivas do arboreto, não material herborizado como o SPP
ARBORETO_SPECIMENS_BASIS_OF_RECORD = "LivingSpecimen"
 

# Canteiro C 
CANTEIRO_C_SHEET_NAME = "Canteiro C - Rosa dos Ventos"

COL_CANTEIRO_C_FAMILIA = "Família"
COL_CANTEIRO_C_ESPECIE = "Espécie"
COL_CANTEIRO_C_ORIGEM = "Origem"
COL_CANTEIRO_C_DOMINIO = "Domínio fitogeográfico"
COL_CANTEIRO_C_CATEGORIA_CNCFLORA = "Categoria CNCFlora"
COL_CANTEIRO_C_NUMERO_LACRE = "Numeração lacre"
COL_CANTEIRO_C_LOCALIZACAO = "Localização canteiro"
COL_CANTEIRO_C_ALTURA = "height_m"

CLN_CANTEIRO_C_TABLE = "cln_canteiro_c"
