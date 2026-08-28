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

# Planilha de origem 
XLSX_PATH = Path("./data/briófitas JB_UFRRJ - Oliveira_Santos.xlsx")

# Configuração de conexão com o PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "jabotur")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

DUCKDB_PATH = Path("./jabotur_test.duckdb")

# Nome da tabela registrada no DuckDB durante o transform()
DUCKDB_STAGING_ALIAS = "df_input"


SPP_SHEET_NAME = "SPP - JB"
SPP_USECOLS = "A:K"  # colunas com dados reais 

# Nome na planilha original -> nome da coluna normalizado
SPP_COLUMN_MAP = {
    "Parcela": "parcela",
    "Amostra": "amostra",
    "StatusIdentificacao*": "identificacao",
    "Filo": "filo",
    "Família": "familia",
    "Gênero": "genero",
    "Espécie": "epiteto_especifico",
    "Autor": "autor",
    "Forma de Vida": "forma_vida",
    "Substrato": "substrato",
    "Observações": "observacao",
}

# === Colunas usadas na camada clean (derivadas de SPP_COLUMN_MAP) ===
COL_IDENTIFICACAO = SPP_COLUMN_MAP["StatusIdentificacao*"]
COL_OBSERVACAO = SPP_COLUMN_MAP["Observações"]
COL_OBSERVACOES = "observacoes"
COL_STATUS_IDENTIFICACAO = "status_identificacao"

STG_SPP_TABLE = "stg_spp_briofitas"
CLN_SPP_TABLE = "cln_spp_briofitas"

# === Nomes das tabelas finais normalizadas ===
TB_FILO = "filo"
TB_FAMILIA = "familia"
TB_GENERO = "genero"
TB_AUTOR = "autor"
TB_EPITETO_ESPECIFICO = "epiteto_especifico"
TB_FORMA_VIDA = "forma_vida"
TB_PARCELA = "parcela"
TB_SUBSTRATO = "substrato"
TB_IDENTIFICACAO = "identificacao"
TB_COLETA = "coleta"
TB_COLETA_SUBSTRATO = "coleta_substrato"
TB_COLETA_OBSERVACAO = "coleta_observacao"
TB_OBSERVACAO = "observacao"

# === Constantes de negócio usadas na etapa clean ===

# Correções pontuais de digitação em Parcela (SPP).
PARCELA_FIXES = {
    "4*": "4",
}

# Correções de vocabulário em Observações (SPP)
OBSERVACAO_REGEX_FIXES = [
    (r"poste de cimento", "cimento"),
    (r"cimento de placa[^;]*pau[\s\-]?brasil", "cimento"),
    (r"acro\s*\[\s*fotos\s*\]", "acro"),
    (r"\bacro\b", "acrocárpico"),
    (r"\bpleuro\b", "pleurocárpico"),
    (r"\bc(?:\s*[\./]\s*|\s+)?esp\b", "com esporófito"),
]

OBSERVACAO_NULL_PLACEHOLDER = "sem observações registradas"
OBSERVACOES_REGEX_FIXES = OBSERVACAO_REGEX_FIXES
OBSERVACOES_NULL_PLACEHOLDER = OBSERVACAO_NULL_PLACEHOLDER

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
 
