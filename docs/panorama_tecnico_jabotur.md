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

- **Python 3.12**, ambiente virtual `.venv`; **pandas** em todas as
  camadas; **DuckDB** só como motor efêmero em memória dentro do
  `transform()` da camada clean, nunca persiste nada; **PostgreSQL**
  como único armazenamento persistente (staging, clean, tabelas finais),
  via SQLAlchemy + `psycopg2`; **openpyxl** (via `pandas.read_excel`)
  pras planilhas de origem, sempre com `dtype=str`.

## 3. Estado atual do pipeline, por fonte

### Pronto e em produção (validado contra Postgres real)

- **SPP (briófitas)** — completo.
- **Arboreto — Citações** (Monografia Gabriel, Livro Pesquisas no JB,
  JABOT): 333 linhas staged, 333 registráveis (316 "ok" + 12
  morfo-espécie + 5 gênero-só), 0 skip no load.
- **Arboreto — Espécimes**: 376 staged, 366 com `parse_status="ok"`; 10
  em `needs_review` (nome popular/placeholder: "Cássia Rosa" ×4, "sem
  identificação" ×6, linhas originalmente ocultas no Excel), preservadas
  em `cln_arboreto_specimens` mas puladas na criação de `occurrence`, com
  log explícito por linha. N° de registro: 197 NULL (195 vazias + 2
  "NA"), 157 lacre amarelo, 22 lacre azul (11 só + 11 combinado, azul
  sempre prevalece), 0 `unparseable`. Dimensões novas: `sector` (25
  valores), `reproductive_status` (2: "Adulto"/"jovem"). `occurrence`:
  366 linhas; `occurrence_arboretum`: 366 satélites.

### Em desenvolvimento, aguardando validação contra Postgres real

- **Arboreto — Canteiro C**: `species_status`, `conservation_status`
  (regra "na" -> código IUCN `NA`, ADR-0005), `phytogeographic_domain`.

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
  `stage_arboreto_*`, sem mudar o resto do pipeline.

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

- **Nomenclatura**: tabelas/colunas já existentes (SPP) em português, não
  retroativo; novas seguem inglês/Darwin Core.
- **Convenção de arquivo**: `stage_<fonte>.py` / `clean_<fonte>.py` /
  `load_<fonte>.py`.
- **Lineage com prefixo `_`** (`_source_file` etc.) precisa de alias sem
  underscore antes de `itertuples()`, pandas renomeia colunas com
  underscore inicial pra posicionais, colidindo com o namedtuple.
- **Nada de literal hardcoded fora de `config.py`**, nomes de coluna,
  tabela, aba.
- **Comentário-resumo obrigatório** em toda query DuckDB com mais de
  ~15 linhas ou que combine mais de uma técnica.
- **Função de entrada de módulo não se chama `run()`**, nome
  descritivo (`populate_normalized_tables()`).
- **Organização de pastas**: `docs/adr/`, `docs/der/`,`.github/` (CODEOWNERS + PR template); `data/`
  continua sendo a cópia operacional que o pipeline lê, a submissão
  original do pesquisador fica no Drive, como prova de proveniência.

## 5. Checklist obrigatório de bug (qualquer `build_occurrence*`/`build_bibliographic_citation*` novo)

1. Toda tupla-chave de espécie passa cada campo por
   `taxonomy._none_if_nan()`, `NaN` vindo do Postgres não bate com
   `None` mesmo dentro de tupla, quebra `dict.get` silenciosamente.
2. O guard `if id_especie is None: continue` vem **antes** de montar
   `natural_key`/dar append na linha, removê-lo grava `id_species=NULL`
   sem erro nem log.

**Status confirmado contra o código real:** SPP, Arboreto — Citações,
Arboreto — Espécimes.

## 6. Débito técnico conhecido

**Prioridade Alta (Bug/Integridade):**
- **Bug de Determinismo no Fill-Down do DuckDB:** Nas camadas `clean_`, as *Window Functions* que fazem `fill-down` (`last_value(... IGNORE NULLS) OVER ()`) não possuem `ORDER BY`. Por conta do paralelismo do DuckDB, a ordem de processamento das linhas não é garantida. Isso cria o risco de misturar a herança de parcelas ou substratos de uma linha para outra. É necessário adicionar `ORDER BY _source_file, CAST(_source_row AS INTEGER)` dentro das cláusulas `OVER()`.

**Prioridade Média (Refatorações Arquiteturais e Código):**
- **Extração de Queries SQL (DuckDB):** Remover as queries cruas inseridas como *strings* no meio dos arquivos Python (em `clean_SPP.py` e `clean_arboreto_citations.py`) e transacioná-las para arquivos `.sql` independentes numa pasta `queries/` para facilitar a manutenção.
- **Segregação de Responsabilidades nos Loaders:** Atualmente, as funções principais de `load_<fonte>.py` fazem todo o processamento de tabelas satélite (`prepare`, `build_*`) embutido na transação física do banco de dados (`write_dataframe_to_postgres`). Isso impede a testabilidade unitária e exige o banco rodando só para validar a transformação. Os arquivos precisam ser quebrados em dois papéis distintos.
- **Reuso de Regras em `taxonomy.py` (DRY):**
  - **Resolução de `id_species`:** Extrair a validação redundante e a criação das tuplas taxonômicas dos loaders e delegar para uma helper em `taxonomy.resolve_species_id(row, epiteto_ids)`.
  - **Loop de Idempotência:** O gerenciamento do dicionário `existing_keys_to_id` com o incremento manual do `next_id` repete o trabalho que o módulo taxonômico já implementa perfeitamente através da `taxonomy._merge_ids()`. Substituir as ocorrências locais pela chamada importada.
- **Testes Automatizados de Idempotência:** Criar testes simulando o reprocessamento sucessivo do pipeline para garantir que os registros não sejam duplicados e contadores de tabelas-fato permaneçam imutáveis.

- **Externalização da Tabela de Lineage:** Remover as strings de `origin_file`, `origin_sheet` e `origin_row` das tabelas de fato (`occurrence`, `bibliographic_citation`) e movê-las para uma tabela de suporte (`lineage`). A motivação principal é manter a tabela de fato enxuta (limpeza semântica e visual do banco), evitando repetição literal de strings com nomes de arquivos em cada linha da dimensão. **Ajuste no Pipeline:** As funções de load/build exigirão um passo extra de resolver-ou-criar a linha de lineage primeiro, a fim de extrair seu ID para ser usado como Foreign Key na tabela fato.
## 7. Próximos passos

1. Finalizar Canteiro C (checklist da seção 5 + validar contra Postgres
   real).
2. Lista Completa Sps.
3. Inventário do JB (Gabriel), percepção sobre polinizadores, mapas
   táteis do DEGEO.
4. API de consulta.
5. Fundação pro aplicativo mobile colaborativo (fase futura).
