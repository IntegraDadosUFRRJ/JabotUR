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
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt

# Variáveis de ambiente (ou usar os defaults locais em config.py)
export POSTGRES_HOST=localhost
export POSTGRES_DB=jabotur
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

# Rodar uma fonte isolada, ex.:
python -m scripts.staging.stage_arboreto_citations
python -m scripts.clean.clean_arboreto_citations
python -m scripts.load.load_arboreto_citations

# Ou o pipeline completo
python -m scripts.run_pipeline
```

## 3. Convenções obrigatórias

- **Nada de string/literal hardcoded fora de `config.py`** nomes de
  coluna, de tabela, de aba, mesmo que usados só dentro de um módulo.
  Motivo: já tivemos bug real de divergência entre o literal usado em
  Python e o mesmo literal dentro de uma query SQL montada por f-string.
- **Convenção de arquivo por fonte**: `stage_<fonte>.py` / `clean_<fonte>.py`
  / `load_<fonte>.py`.
- **Colunas de metadado de linhagem usam prefixo `_`** (`_source_file`,
  `_source_sheet`, `_source_row`, `_loaded_at`) mas **precisam de alias
  sem underscore antes de `itertuples()`**, porque pandas renomeia colunas
  com underscore inicial pra posicionais (`_1`, `_2`...), que colidem com
  métodos internos do namedtuple.
- **Clean nunca descarta linha.** Problema de qualidade vira coluna
  (`parse_status`, `needs_review`, `reconcile_across_sources`), nunca uma
  linha removida ou um dataframe separado.
- **Qualquer lookup de chave natural vindo do Postgres passa por
  `taxonomy._none_if_nan()` antes de virar chave de dict/tupla.**
  `pd.read_sql_query` retorna `float('nan')` pra colunas NULL, e isso
  quebra comparação de tupla silenciosamente se não for normalizado.
- **DuckDB só é usado dentro de `transform()`, nunca persiste nada.** Toda
  persistência (staging/clean/tabelas normalizadas) é Postgres via
  `db_utils.py`.
- **Nomenclatura**: tabelas/colunas já existentes (SPP) continuam em
  português — não retroativo. Tabelas/colunas novas seguem inglês/Darwin
  Core (`occurrence`, `basis_of_record`, `identification_qualifier`).
- **Funções de entrada de módulo não se chamam `run()`** usar verbo+objeto
  descritivo (ex.: `populate_normalized_tables()`), pra dar pra saber pelo
  traceback qual etapa falhou.
- **Toda query DuckDB montada por f-string com mais de ~15 linhas, ou que
  combine mais de uma técnica** (window function + regex + cast), ganha um
  comentário-resumo antes do `sql = f"""` explicando o que ela faz como um
  todo.

## 4. Fluxo de trabalho (branches e PRs)

- Branch a partir de `main`, nome `feature/<fonte>-<etapa>`
  (ex.: `feature/lista-completa-staging`).
- PRs que tocam `config.py`, `db_utils.py` ou `load/taxonomy.py` (código
  compartilhado entre todas as fontes) precisam de revisão do Davidson,
  ver `CODEOWNERS`.
- Se a mudança envolve uma decisão de arquitetura nova (não só implementação
  de algo já decidido), documentar como ADR em `docs/adr/` (ver
  `docs/adr/template_adr.md`) antes de abrir o PR de código.

## 5. Onde perguntar / quem decide o quê

- Decisão de arquitetura nova (schema, nomenclatura, política de
  reconciliação) -> aprovação da equipe antes de virar código.
- Dúvida de convenção de código já estabelecida → este arquivo + ADRs.
- Regras de negócio específicas de uma planilha (ex.: como tratar "na" em
  Grau de Ameaça) -> `Processos_de_ETL_*.pdf` correspondente + ADR se a
  regra não for óbvia pela planilha.
