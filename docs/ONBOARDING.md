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
`parse_status`), nunca uma linha a menos.

## 2. Leitura recomendada, nesta ordem

1. Este arquivo
2. `data_dictionary.md`: o que cada coluna de cada fonte significa
3. `JabotUR_DER.md`: schema (DBML, abrir em dbdiagram.io)
4. `docs/adr/`: por que o schema é do jeito que é
5. `panorama_tecnico_jabotur.md`: referência técnica completa (denso, ler sob demanda, não de ponta a ponta)

## 3. Convenções que o código segue (e você deve seguir)

- **Nomenclatura**: tabelas/colunas já existentes (SPP) ficam em português,
  não retroativo. Tabelas/colunas novas seguem inglês/Darwin Core
  (`occurrence`, `identification_qualifier`).
- **Nada de string/literal hardcoded fora de `config.py`**: nomes de
  coluna, tabela, aba, ou qualquer literal de domínio vira constante,
  mesmo que usado só num módulo. Motivo real: já tivemos bug de
  divergência entre o literal em Python e o mesmo literal dentro de uma
  query DuckDB montada por f-string.
- **Convenção de arquivo**: `stage_<fonte>.py` / `clean_<fonte>.py` /
  `load_<fonte>.py`.
- **DuckDB é só motor efêmero em memória**, usado dentro de `transform()`
  na camada clean. Nunca persiste nada, Postgres é a única camada de
  armazenamento real (staging, clean e normalizada).
- **Get-or-create é Python puro**, não SQL, `load/taxonomy.py` resolve
  chave natural -> id via dict com tupla como chave. Índices únicos
  parciais no Postgres são cinto-e-suspensório, não o mecanismo
  principal.
- **Funções de entrada de módulo não se chamam `run()`** — nome
  descritivo do que a função faz (ex.: `populate_normalized_tables()`).

## 4. Erros Comuns

- **Nunca `dropna` sem `needs_review=True`.** Se uma linha tem dado
  ambíguo ou faltando, ela entra mesmo assim, sinalizada. Descartar
  silenciosamente já causou bug real (`clean_arboreto_citations.py`,
  linhas com espécie em branco descartadas por engano).
- **Nunca comparar valor lido do Postgres em chave de dict/tupla sem
  `_none_if_nan()` antes.** `pd.read_sql_query` devolve `float('nan')`
  pra coluna NULL, e `NaN != NaN` mesmo dentro de tupla, quebra o
  `dict.get` silenciosamente (sem erro, só devolve `None` como se a
  chave não existisse).
- **Nunca remova o guard `if id_especie is None: continue` de um
  `build_occurrence*`.** Sem ele, a linha é gravada com
  `id_species=NULL` em vez de pulada, sem erro, sem log, só quebra
  integridade referencial mais tarde.
- **Nunca crie uma linha "N/A"/"na" numa dimensão via get-or-create**
  (ex.: `reproductive_status`, `phytogeographic_domain`) pra representar
  dado ausente. Dado ausente = NULL na FK / nenhuma linha na bridge
  table. Exceção deliberada única: `conservation_status.code = 'NA'` é
  o código IUCN real ("Not Applicable"), não um placeholder.
- **Nunca escape barra invertida em regex passada pro `regexp_replace`
  do DuckDB**, só escape aspas simples. Já quebrou metacaracteres
  (`\b`, `\s`) uma vez.

## 5. Como rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# variáveis de ambiente (ou .env): POSTGRES_HOST, POSTGRES_PORT,
# POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, defaults em config.py

python -m scripts.run_pipeline
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
