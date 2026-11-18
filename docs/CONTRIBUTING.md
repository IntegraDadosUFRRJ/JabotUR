# Contribuindo com o JabotUR

Esse documento existe pra qualquer pessoa nova no projeto conseguir rodar o
pipeline e entender as convenções sem precisar perguntar tudo do zero.
Se algo aqui ficar desatualizado, o PR que corrigir o código deve corrigir
este arquivo também trate como parte do "definition of done".

## 1. O que é o projeto

Pipeline de ETL que ingere planilhas heterogêneas de biodiversidade (JB
UFRRJ) numa base PostgreSQL normalizada e única. Ver `docs/panorama_tecnico_jabotur.md`
para o histórico completo e decisões de arquitetura.

## 2. Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
pip install -e .

# Instala as extensões do DuckDB
python -c "import duckdb; duckdb.sql('INSTALL excel; INSTALL postgres')"

# Variáveis de ambiente (ou usar os defaults locais em scripts/config.py)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=jabotur
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

# Rodar uma fonte isolada, ex.:
python -m scripts.staging.stage_arboretum_citations
python -m scripts.clean.clean_arboretum_citations
python -m scripts.load.load_arboretum_citations

# Ou o pipeline completo (já chama init_postgres no início)
python -m scripts.run_pipeline

# Suíte de testes (pula os testes de banco se POSTGRES_DB não terminar em _test)
python -m unittest discover -s tests

# Suíte completa no banco de teste (tests/db_test_support.py recria o schema do banco de teste, cria o banco via init_postgres se ele não existir, e recusa rodar em banco sem sufixo _test)
POSTGRES_DB=jabotur_test python -m unittest discover -s tests
```

## 3. Convenções obrigatórias

- **Nada de string/literal hardcoded fora de `config.py`** nomes de
  coluna, de tabela, de aba, mesmo que usados só dentro de um módulo.
  Motivo: já tivemos bug real de divergência entre o literal usado em
  Python e o mesmo literal dentro de uma query SQL montada por f-string.
- **Convenção de arquivo por fonte**: `stage_<fonte>.py` / `clean_<fonte>.py`
  / `load_<fonte>.py`.
- **Colunas de metadado de linhagem usam prefixo `_`** (`_source_file`,
  `_source_sheet`, `_source_row`, `_loaded_at`) e **toda leitura do Postgres
  precisa de `ORDER BY` explícito** (`ARBORETUM_CITATIONS_SOURCE_ORDER`,
  `ARBORETUM_SPECIMENS_SOURCE_ORDER`, `SPP_SOURCE_ORDER` em `scripts/config.py`,
  ou `id` nas tabelas finais, aplicado por padrão em `db_utils.read_table` e
  `db_utils.read_rows` quando a tabela tem `id`), porque o Postgres devolve
  linhas na ordem física, que muda a cada upsert.
- **Clean nunca descarta linha.** Problema de qualidade vira coluna
  (`parse_status` e, nas fontes do arboreto, `needs_review` e `reconcile_across_sources`), nunca uma
  linha removida ou um dataframe separado.
- **Qualquer lookup de chave natural passa por
  `taxonomy._none_if_nan()` antes de virar chave de dict/tupla.**
  `db_utils.read_rows` já devolve `None` para colunas `NULL`, mas
  `_none_if_nan()` evita que um `float('nan')` em memória quebre a comparação
  de tupla no `dict` (e `db_utils._stage_rows` barra `NaN` com `ValueError`).
- **DuckDB lê as planilhas e grava no Postgres em todas as camadas (ADR-0013).**
  O staging lê o Excel com `read_xlsx` (`scripts/staging/xlsx_sheet.py`) e
  grava com `db_utils.replace_table`; o clean lê e grava no Postgres anexado
  via `ATTACH` (`db_utils.postgres_duckdb()`); os loads leem com
  `db_utils.read_rows` e gravam com `db_utils.upsert_rows` e
  `db_utils.insert_ignore_rows` dentro de `db_utils.transaction()`. O pandas
  (`write_dataframe_to_postgres`/`read_dataframe_from_postgres`) ficou
  restrito ao Canteiro C.
- **Nomenclatura (ADR-0010)**: a regra antiga "não retroativo" foi revogada.
  Tabelas, colunas e índices das fontes integradas estão em inglês (`phylum`,
  `family`, `genus`, `species`, `occurrence`, `basis_of_record`,
  `identification_qualifier`), e tudo que entrar de novo nasce em inglês.
- **Funções de entrada de módulo não se chamam `run()`** usar verbo+objeto
  descritivo (ex.: `populate_normalized_tables()`), pra dar pra saber pelo
  traceback qual etapa falhou.
- **SQL dos cleans em arquivo `.sql` ao lado do script**
  (`scripts/clean/clean_<fonte>.sql`), com cabeçalho de comentário descrevendo
  as CTEs e os placeholders preenchidos por `str.format` a partir de
  `config.py`. Os arquivos `.sql` (`scripts/db/schema.sql` e
  `scripts/clean/*.sql`) ficam declarados em `[tool.setuptools.package-data]`
  no `pyproject.toml`.
- **Esquema único das tabelas finais em `scripts/db/schema.sql`**, aplicado
  por `scripts/db/init_postgres.py` (sem pasta `migrations/`).

## 4. Fluxo de trabalho (branches e PRs)

- Branch a partir de `main`, nome `feature/<fonte>-<etapa>`
  (ex.: `feature/lista-completa-staging`).
- PRs que tocam arquivos protegidos listados em `.github/CODEOWNERS` exigem revisão do Author indicado.
- Se a mudança envolve uma decisão de arquitetura nova (como troca de stack,
  mudança de esquema ou da chave de uma entidade), documentar como ADR em `docs/adr/`
  (ver `docs/adr/template_adr.md`) antes de abrir o PR de código.

## 5. Onde perguntar / quem decide o quê

- Decisão de arquitetura nova (schema, nomenclatura, política de
  reconciliação) -> aprovação da equipe antes de virar código.
- Dúvida de convenção de código já estabelecida → este arquivo + ADRs.
- Regras de negócio específicas de uma planilha (ex.: como tratar "na" em
  Grau de Ameaça) -> `docs/processos_de_etl.md` correspondente + ADR se a
  regra não for óbvia pela planilha.
