"""
Configuracao central do pipeline de ETL do JabotUR
"""

import os
from pathlib import Path

# === Caminhos ===
SPP_XLSX_PATH = Path("data/briófitas-coletas.xlsx")
ARBORETO_XLSX_PATH = Path("data/diversidade-floristica-do-arboreto-do-JB.xlsx")

# Configuracao de conexao com o PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "jabotur")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

DUCKDB_PATH = Path("./jabotur_test.duckdb")

SPP_SHEET_NAME = "SPP - JB"
SPP_USECOLS = "A:K"

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

STG_SPP_TABLE = "stg_spp_briofitas"
CLN_SPP_TABLE = "cln_spp_briofitas"

ARBORETO_CITATION_SHEETS = [
    "Monografia Gabriel",
    "Livro Pesquisas no JB",
    "JABOT",
]
ARBORETO_CITATION_USECOLS = "A:C"

ARBORETO_CITATION_COLUMN_MAP = {
    "Família": "familia",
    "Espécie": "especie",
    "Quant": "quantidade",
}

STG_ARBORETO_CITATIONS_TABLE = "stg_arboreto_citations"
CLN_ARBORETO_CITATIONS_TABLE = "cln_arboreto_citations"

# === Nomes das tabelas finais ===
TB_FILO = "filo"
TB_FAMILIA = "familia"
TB_GENERO = "genero"
TB_AUTOR = "autor"
TB_EPITETO_ESPECIFICO = "epiteto_especifico"
TB_FORMA_VIDA = "forma_vida"
TB_PARCELA = "parcela"
TB_SUBSTRATO = "substrato"
TB_IDENTIFICACAO = "identificacao"
TB_OCCURRENCE = "occurrence"
TB_OCCURRENCE_BRYOPHYTE = "occurrence_bryophyte"
TB_COLETA_SUBSTRATO = "coleta_substrato"
TB_COLETA_OBSERVACAO = "coleta_observacao"
TB_OBSERVACAO = "observacao"
TB_BIBLIOGRAPHIC_CITATION = "bibliographic_citation"

# === Constantes de negocio ===
PARCELA_FIXES = {
    "4*": "4",
}

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

FILO_NOME_MAP = {
    "M": "Musgos",
    "H": "Hepáticas",
}

SUBSTRATO_NOME_MAP = {
    "RZ": "Raiz de árvore",
    "S": "Solo",
    "TD": "Tronco em decomposição",
    "TV": "Tronco vivo",
    "A": "Artificial",
}

IDENTIFICACAO_DESCRICAO_MAP = {
    1: "Identificada",
    2: "Parcialmente Identificada",
    3: "Dúvida",
}

PARCELA_COORDENADAS = {
    "1": "22° 45' 54.2\"S 43° 41' 31.1\"O",
    "2": "22° 45' 57.3\"S 43° 41' 34\"O",
    "3": "22° 45' 54.3\"S 43° 41' 33.7\"O",
    "4": "22° 45' 54.9\"S 43° 41' 34.5\"O",
    "5": "22° 45' 59.3\"S 43° 41' 37.5\"O",
}

# Staging - Arboreto (Espécimes e Fitogeografia)
STG_ARBORETO_ESPECIMES_TABLE = "stg_arboreto_especimes"
STG_ARBORETO_LISTA_SPS_TABLE = "stg_arboreto_lista_sps"