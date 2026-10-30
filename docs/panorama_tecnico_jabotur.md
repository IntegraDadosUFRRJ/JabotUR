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
  JABOT)
- **Arboreto — Espécimes**: as linhas originalmente ocultas no Excel de "Cássia Rosa" e "sem identificação" recebem `needs_review = True` (preservadas no clean mas puladas na criação de `occurrence` com log explícito). N° de registro: lacre azul prevalece sobre lacre amarelo. Dimensões novas: `sector` e `reproductive_status`.

### Especificado, não implementado

- **Arboreto — Canteiro C**: pipeline já mapeado estruturalmente no DER e ADRs (`species_status`, `conservation_status` com regra "na" -> código IUCN `NA` via ADR-0005, `phytogeographic_domain`), mas scripts de staging, clean e load ainda não implementados.

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

Os débitos técnicos ativos do projeto estão mapeados no painel de Issues do repositório no GitHub. Consulte as issues para visualizar os problemas conhecidos e as decisões de implementação.
## 7. Próximos passos

1. Implementar pipeline de Canteiro C (conforme especificação no DER e dicionário; checklist da seção 5 + validação contra Postgres real).
2. Lista Completa Sps.
3. Inventário do JB (Gabriel), percepção sobre polinizadores, mapas
   táteis do DEGEO.
4. API de consulta.
5. Fundação pro aplicativo mobile colaborativo (fase futura).
