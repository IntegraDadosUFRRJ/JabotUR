# JabotUR — Panorama Técnico do Pipeline

> Visão viva do estado do pipeline e das decisões/convenções que não
> chegam a virar um ADR próprio. Complementa, não substitui, os ADRs em
> `docs/adr/`, onde existe ADR pra uma decisão, este arquivo só aponta
> pra ele.

## 1. Objetivo do sistema

Pipeline de ETL que ingere múltiplas planilhas (e, em breve, shapefiles)
heterogêneas de diversidade biológica do Jardim Botânico da UFRRJ numa
base PostgreSQL normalizada e única. Requisitos centrais:

- **Idempotente**: re-rodar o pipeline não duplica dados.
- **Reconciliação entre fontes**: a mesma espécie citada em fontes
  diferentes resolve pro mesmo registro na dimensão de taxonomia.
- **Extensível**: uma planilha nova que compartilhe só algumas colunas
  com as existentes reaproveita o que já existe (família/gênero/autor/
  epíteto) e só adiciona o que é exclusivo dela.
- Projeto de Iniciação Científica (UFRRJ/PROVERDE), orientação da Prof.
  Liliane Kunstmann, decisões de arquitetura aprovadas antes de virarem
  código. API própria de limpeza de nomes (ou o proprio `pytaxon`) antes
  ainda não integrada. Política enquanto isso não entra: **registrar tudo,
  nunca descartar** por incerteza de dado.

## 2. Tech stack

- **Python** (testado em 3.14.4), ambiente virtual `.venv`; **DuckDB** em todas as
  camadas de SPP, Citações e Espécimes (**ADR-0013**): lê as planilhas no
  staging com `read_xlsx(..., all_varchar=true, stop_at_empty=false)`
  (`scripts/staging/xlsx_sheet.py`) e lê/grava no Postgres anexado via `ATTACH`
  (`scripts/db/db_utils.py`); **pandas** restrito ao Canteiro C; **openpyxl**
  usado só nos testes; **PostgreSQL** como único armazenamento persistente
  (staging, clean, tabelas finais), com o esquema inicializado por
  `scripts/db/init_postgres.py` a partir de `scripts/db/schema.sql` via
  SQLAlchemy + `psycopg2`.

## 3. Estado atual do pipeline, por fonte

### Pronto e em produção (validado contra Postgres real)

- **SPP (briófitas)** — completo.
- **Arboreto — Citações** (Monografia Gabriel, Livro Pesquisas no JB,
  JABOT)
- **Arboreto — Espécimes**: lido com `read_xlsx` do DuckDB (que também lê
  linhas ocultas, se houver). As linhas de "Cássia Rosa" e "sem
  identificação" recebem `needs_review = True` no clean, e as ocorrências
  sem gênero e sem epíteto entram em `occurrence` com `id_species = NULL`
  (`load_arboretum_specimens.py`). N° de registro: lacre azul
  prevalece sobre lacre amarelo. Dimensões: `sector` e `reproductive_status`.

### Em desenvolvimento / especificado

- **Arboreto — Canteiro C**: pipeline já mapeado estruturalmente no DER e ADRs (`species_status`, `conservation_status` com regra "na" -> código IUCN `NA` via ADR-0005, `phytogeographic_domain`). Os scripts `stage_arboreto_canteiro_c.py` e `clean_arboreto_canteiro_c.py` já existem no repositório (vieram da `main`), faltando o load e a migração para o padrão sem DataFrame.

### Recebido, integração não iniciada

- Arboreto — Lista Completa Sps (distribuição geográfica: país/estado/
  texto livre)
- Inventário do JB (Gabriel) — normalização já feita, análise de
  integração em andamento
- Percepção sobre polinizadores
- Mapas táteis do DEGEO (**shapefile** — primeira fonte fora do padrão
  planilha)

### Deliberadamente adiado

- Integração do limpador de nomes (API do Cássio / inspirada em
  `pytaxon`) — ponto de encaixe definido: pré-processamento antes de
  `stage_arboretum_*`, sem mudar o resto do pipeline.

## 4. Convenções e decisões — o que não está num ADR

| Decisão de schema | Onde está documentada |
|---|---|
| `occurrence` super-tipo/sub-tipo | ADR-0001 |
| Índices únicos parciais pra `infraespecifico` | ADR-0002 |
| Gênero-só / morfo-espécie (reconciliação) | ADR-0003 |
| `filo` NULL pra famílias de origem arboreto | ADR-0004 |
| `conservation_status.code = 'NA'` é código IUCN real | ADR-0005 |
| `identification_qualifier` no registro, não na espécie | ADR-0006 |
| Chave de idempotência de `bibliographic_citation` | ADR-0007 |
| NULL verdadeiro, nunca placeholder "N/A" | ADR-0008 |
| Regra de prevalência do lacre azul | ADR-0009 |

Convenções que não chegam a ser decisão de schema (ficam aqui mesmo):

- **Nomenclatura (ADR-0010)**: a regra antiga "não retroativo" foi revogada;
  todas as tabelas e colunas das fontes integradas seguem inglês/Darwin Core.
- **Convenção de arquivo**: `stage_<fonte>.py` / `clean_<fonte>.py` /
  `load_<fonte>.py`.
- **Lineage com prefixo `_`** (`_source_file`, `_source_sheet`,
  `_source_row`, `_loaded_at`) lido como `list[dict]` via
  `db_utils.read_rows`, sempre com `ORDER BY` explícito (`*_SOURCE_ORDER` no
  staging/clean ou `id` nas tabelas finais).
- **Nada de literal hardcoded fora de `config.py`**, nomes de coluna,
  tabela, aba.
- **SQL dos cleans em arquivo `.sql` ao lado do módulo**
  (`scripts/clean/clean_<fonte>.sql`), com comentário-resumo das CTEs e dos
  placeholders no topo do arquivo.
- **Função de entrada de módulo não se chama `run()`**, nome
  descritivo (`populate_normalized_tables()`).
- **Organização de pastas**: `docs/adr/`, `docs/der/`,`.github/` (CODEOWNERS + PR template); `data/`
  continua sendo a cópia operacional que o pipeline lê, a submissão
  original do pesquisador fica no Drive, como prova de proveniência.

## 5. Checklist obrigatório de bug (qualquer `build_occurrence*`/`build_bibliographic_citation*` novo)

1. Toda tupla-chave de espécie passa cada campo por
   `taxonomy._none_if_nan()`. `db_utils.read_rows` já devolve `None` para
   `NULL`, mas `_none_if_nan()` barra `float('nan')` em memória antes de
   montar a tupla (`NaN != NaN` quebra `dict.get` em silêncio, e
   `db_utils._stage_rows` levanta `ValueError` se achar `NaN`).
2. Em SPP (`load_spp_bryophytes.py`) e Citações
   (`load_arboretum_citations.py`), mantenha o guard
   `if id_species is None: continue` **antes** de montar `natural_key` /
   dar append na linha. Já em Espécimes (`load_arboretum_specimens.py`), quando `genus` e `epithet` são ambos `None` (`unidentified`),
   a ocorrência entra em `occurrence` com `id_species = NULL`.

**Status confirmado contra o código real:** SPP, Arboreto — Citações,
Arboreto — Espécimes.

## 6. Débito técnico conhecido

Os débitos técnicos ativos do projeto estão mapeados no painel de Issues do repositório no GitHub. Consulte as issues para visualizar os problemas conhecidos e as decisões de implementação.
## 7. Próximos passos

1. Implementar pipeline de Canteiro C (conforme especificação no DER e dicionário; checklist da seção 5 + validação contra Postgres real).
2. Lista Completa Sps.
3. Inventário do JB (Gabriel), percepção sobre polinizadores, mapas
   táteis do DEGEO.
4. API de consulta.
5. Fundação pro aplicativo mobile colaborativo (fase futura).
