# JabotUR ETL

## Sobre

O Jardim Botânico da UFRRJ (JB-UFRRJ) reúne seus dados de pesquisa em planilhas, sistemas e inventários que não conversam entre si. O **JabotUR** é um pipeline ETL que integra essas fontes em um banco PostgreSQL unificado e normalizado.

O pipeline segue três camadas (staging -> clean -> load), não descarta nenhuma linha por incerteza de dado (problemas de qualidade viram colunas de sinalização, como `needs_review`) e reconcilia a mesma espécie citada em fontes diferentes em um único registro taxonômico central. Com isso, busca reduzir retrabalho, melhorar a qualidade dos dados e preparar a base para catalogação, mapeamento e pesquisa científica.

## Executando o projeto

**Requisitos:**
- Python (testado em 3.14.4)
- PostgreSQL

**1. Clonando o repositório:**
```bash
git clone <url-do-repositorio>
cd JabotUR
```

**2. Instalação e Ambiente Virtual:**
```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
pip install -e .

# Instala as extensões do DuckDB
python3 -c "import duckdb; duckdb.sql('INSTALL excel; INSTALL postgres')"
```

**3. Configurando o Banco de Dados:**
Verifique as variáveis `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` em `scripts/config.py` (ou exporte no ambiente) e suba o PostgreSQL localmente ou em container Docker. A suíte de testes usa um banco separado terminado em `_test` (`jabotur_test`).

**4. Inicializando o Banco (opcional):**
```bash
python3 -m scripts.db.init_postgres
```
> Este passo separado é opcional porque `python3 -m scripts.run_pipeline` já chama `init_postgres()` no início.

**5. Rodando o Pipeline:**
```bash
python3 -m scripts.run_pipeline
```
> **Nota:** sem instalar o pacote com `pip install -e .`, rodar `python3 scripts/run_pipeline.py` direto falha com `ModuleNotFoundError` porque os módulos usam imports absolutos (`from scripts.clean...`); com `-m` (ou com o pacote instalado em modo editável) funciona da raiz do projeto.

**6. Rodando os Testes:**
```bash
# Roda os testes que não dependem do Postgres (pula os de banco se POSTGRES_DB não terminar em _test)
python3 -m unittest discover -s tests

# Roda a suíte completa contra o banco de teste (cria/reseta jabotur_test via init_postgres)
POSTGRES_DB=jabotur_test python3 -m unittest discover -s tests
```

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

## Help

- Entre em contato em davidson_wasserman@ufrrj.br | juliaprearo@ufrrj.br

### Membros

- Davidson Wasserman
- Julia Prearo
- Liliane Kunstmann


---

*Projeto de Iniciação Científica do Jardim Botânico da UFRRJ.*
