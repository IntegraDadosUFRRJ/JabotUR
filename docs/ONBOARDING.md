# Onboarding — JabotUR

> Leitura de entrada. Não repete o conteúdo técnico denso do
> `panorama_tecnico_jabotur.md`, só orienta por onde começar e o que
> nunca fazer. Para decisões arquiteturais específicas, ver `docs/adr/`.

## 1. O que é o projeto, em 3 frases

ETL que integra planilhas heterogêneas de biodiversidade (Jardim Botânico
UFRRJ, briófitas e arboreto, com fontes novas a caminho) numa base
PostgreSQL normalizada única. O pipeline segue três camadas:
**staging -> clean -> load** e nunca descarta linha por incerteza de
dado: problemas de qualidade viram colunas (`needs_review`,
`parse_status`), nunca uma linha a menos. O staging (`scripts/staging/xlsx_sheet.py`)
só deixa de gravar linhas que não têm nenhum dado nas colunas
mapeadas (`WHERE coalesce(...) IS NOT NULL`).

## 2. Leitura recomendada, nesta ordem

1. Este arquivo
2. `data_dictionary.md`: o que cada coluna de cada fonte significa
3. `processos_de_etl.md`: que transformação cada coluna sofre, staging -> clean -> load
4. `der/JabotUR_DER.md`: schema (DBML, abrir em dbdiagram.io)
5. `docs/adr/`: por que o schema é do jeito que é
6. `panorama_tecnico_jabotur.md`: referência técnica completa (denso, ler sob demanda, não de ponta a ponta)

## 3. Convenções que o código segue
- **Nomenclatura (ADR-0010)**: a regra "não retroativo" foi revogada. Todas as
  tabelas e colunas das fontes integradas seguem inglês/Darwin Core
  (`occurrence`, `identification_qualifier`, `species`).
- **Nada de string/literal hardcoded fora de `config.py`**: nomes de
  coluna, tabela, aba, ou qualquer literal de domínio vira constante,
  mesmo que usado só num módulo. Motivo real: já tivemos bug de
  divergência entre o literal em Python e o mesmo literal dentro de uma
  query DuckDB montada por f-string.
- **Convenção de arquivo**: `stage_<fonte>.py` / `clean_<fonte>.py` /
  `load_<fonte>.py`.
- **DuckDB em todas as camadas (ADR-0013):** lê as planilhas no staging com
  `read_xlsx` (`scripts/staging/xlsx_sheet.py`) e lê/grava direto no Postgres
  anexado via `ATTACH` (`db_utils.postgres_duckdb()`) em staging, clean e
  load. Exige `INSTALL excel` e `INSTALL postgres` uma vez por máquina e por
  versão do DuckDB. Postgres continua sendo a camada de armazenamento real,
  com o esquema criado por `scripts/db/init_postgres.py` a partir de
  `scripts/db/schema.sql`.
- **Get-or-create é Python puro**, não SQL, `load/taxonomy.py` resolve
  chave natural -> id via dict com tupla como chave. Índices únicos
  parciais no Postgres são cinto-e-suspensório, não o mecanismo
  principal.
- **Funções de entrada de módulo não se chamam `run()`** — nome
  descritivo do que a função faz (ex.: `populate_normalized_tables()`).

## 4. Erros Comuns

- **Nunca filtrar linha com problema na query do clean.** Se uma linha tem
  dado ambíguo ou faltando, ela entra mesmo assim em `cln_*`, sinalizada
  com `needs_review = True` e `parse_status`. Descartar linha em silêncio
  já causou bug real (`clean_arboretum_citations.py`, linhas com espécie em
  branco descartadas por engano).
- **Não comparar valor em chave de dict/tupla sem `_none_if_nan()` antes.**
  `db_utils.read_rows` já devolve `None` para coluna `NULL`, mas `_none_if_nan()`
  evita que um `float('nan')` em memória entre na tupla (`NaN != NaN` quebra
  o `dict.get` em silêncio), e `db_utils._stage_rows` levanta `ValueError` se
  receber `NaN`.
- **Atenção ao guard `if id_species is None: continue` nos loaders:** ele vale
  em Citações (`load_arboretum_citations.py`) e no SPP
  (`load_spp_bryophytes.py`), onde a linha sem espécie é
  pulada com log. Já em Espécimes (`load_arboretum_specimens.py`), uma ocorrência sem gênero e sem epíteto (`unidentified`) **entra**
  em `occurrence` com `id_species = NULL`.
- **Não crie uma linha "N/A"/"na" numa dimensão via get-or-create**
  (ex.: `reproductive_status`, `phytogeographic_domain`) pra representar
  dado ausente. Dado ausente = NULL na FK / nenhuma linha na bridge
  table. Exceção deliberada única: `conservation_status.code = 'NA'` é
  o código IUCN real ("Not Applicable"), não um placeholder.
- **Não escape barra invertida em regex passada pro `regexp_replace`
  do DuckDB**, só escape aspas simples. Já quebrou metacaracteres
  (`\b`, `\s`) uma vez.

## 5. Como rodar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# instala as extensões do DuckDB (pede rede uma vez por máquina e por versão do DuckDB)
python3 -c "import duckdb; duckdb.sql('INSTALL excel; INSTALL postgres')"

# variáveis de ambiente (o projeto não lê arquivo .env): POSTGRES_HOST, POSTGRES_PORT,
# POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, defaults em scripts/config.py

python -m scripts.run_pipeline

# suíte de testes contra o banco de teste
POSTGRES_DB=jabotur_test python -m unittest discover -s tests
```

## 6. Onde as decisões de arquitetura ficam registradas

Toda decisão que muda schema, padrão entre fontes, ou nomenclatura vira
um ADR em `docs/adr/000X-titulo.md` (template em `template_adr.md`).
Antes de propor uma mudança estrutural nova, dar uma olhada em
`docs/adr/`, pode já ter sido discutida e descartada por um motivo
específico.

## 7. Fluxo de trabalho (GitHub)

- Branch por fonte/tabela, PR pequeno, review cruzado antes de merge na
  `main`, especialmente em qualquer mudança que toque `load/taxonomy.py`
  ou o padrão `occurrence`, que são compartilhados entre todas as fontes.
- Ao abrir um PR, siga o **checklist do template**, garantindo que atualizou os ADRs e documentação e pediu a revisão exigida no `CODEOWNERS`.