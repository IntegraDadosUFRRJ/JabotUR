# JabotUR ETL

## Sobre

O Jardim Botânico da UFRRJ (JB-UFRRJ) reúne seus dados de pesquisa em planilhas, sistemas e inventários que não conversam entre si. O **JabotUR** é um pipeline ETL que integra essas fontes em um banco PostgreSQL unificado e normalizado.

O pipeline segue três camadas (staging -> clean -> load), não descarta nenhuma linha por incerteza de dado (problemas de qualidade viram colunas de sinalização, como `needs_review`) e reconcilia a mesma espécie citada em fontes diferentes em um único registro taxonômico central. Com isso, busca reduzir retrabalho, melhorar a qualidade dos dados e preparar a base para catalogação, mapeamento e pesquisa científica.

## Documentação

Comece pelo [ONBOARDING.md](docs/ONBOARDING.md); ele indica a ordem de leitura do resto.

- [docs/ONBOARDING.md](docs/ONBOARDING.md): por onde começar, convenções e erros comuns
- [docs/data_dictionary.md](docs/data_dictionary.md): o que cada coluna de cada fonte significa
- [docs/processos_de_etl.md](docs/processos_de_etl.md): que transformação cada coluna sofre (staging -> clean -> load)
- [docs/der/JabotUR_DER.md](docs/der/JabotUR_DER.md): schema completo (DBML, abrir no dbdiagram.io)
- [docs/adr/](docs/adr/): por que o schema é do jeito que é
- [docs/panorama_tecnico_jabotur.md](docs/panorama_tecnico_jabotur.md): referência técnica completa (consultar sob demanda)
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md): fluxo de branch e PR

## Fontes integradas

| Fonte | Status |
|---|---|
| Briófitas (SPP) | Integrada |
| Arboreto: citações bibliográficas | Integrada |
| Arboreto: espécimes | Integrada |
| Arboreto: Canteiro C | Em desenvolvimento |

## Executando o projeto

**Requisitos:**
- Python 3.12
- PostgreSQL

**1. Clonando o repositório:**
```bash
git clone <url-do-repositorio>
cd jabotur
```

**2. Instalação e Ambiente Virtual:**
```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
pip install -e .
```

**3. Configurando o Banco de Dados:**
Verifique o arquivo `config.py` e certifique-se de possuir o PostgreSQL rodando localmente (ou via Docker).

**4. Inicializando o Banco:**
```bash
python3 -m scripts.init_postgres
```

**5. Rodando o Pipeline:**
```bash
python3 -m scripts.run_pipeline
```
> **Nota:** o uso do `-m` é obrigatório. Como os módulos utilizam imports absolutos a partir da raiz do projeto (ex: `from scripts.clean...`), tentar rodar o script diretamente (`python3 scripts/run_pipeline.py`) causará um `ModuleNotFoundError`.

## Help

- Entre em contato em davidson_wasserman@ufrrj.com | juliaprearo@ufrrj.br

### Membros

- Cássio Lima 
- Davidson Wasserman
- Julia Prearo
- Liliane Kunstmann


---

*Projeto de Iniciação Científica do Jardim Botânico da UFRRJ.*