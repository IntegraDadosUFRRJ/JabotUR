# ADR-0011 — Origem do dado (lineage) em tabela própria, com `id_lineage` nos fatos

**Data:** 05/10/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** substitui em parte o ADR-0007 (chave de idempotência de `bibliographic_citation`) e a menção a `origin_*` no ADR-0001; depende do ADR-0010 (a tabela nasce em inglês)

---

## Contexto

`occurrence` e `bibliographic_citation` guardam `origin_file`, `origin_sheet` e
`origin_row` em cada linha. Poucos arquivos e abas alimentam centenas de linhas,
então o mesmo nome de arquivo se repete em série nas tabelas-fato.

Essas colunas também são a chave de idempotência dos fatos (ADR-0007 para
citações; o mesmo padrão em `occurrence`). Já as colunas `_source_file`,
`_source_sheet` e `_source_row` das camadas staging e clean são efêmeras
(recriadas em modo `replace`) e servem de ordenação do fill-down; elas não fazem
parte desta decisão.

## Decisão

1. Nova tabela `lineage` (`id` sequencial, `origin_file`, `origin_sheet`,
   `origin_row`), com **uma linha por linha de origem que gera um fato**.
   `origin_sheet` continua nullable (SPP antigo: 1 arquivo = 1 aba).
2. `occurrence` e `bibliographic_citation` **removem** `origin_file`,
   `origin_sheet` e `origin_row` e ganham `id_lineage` (FK), com índice único em
   cada tabela-fato (uma linha de origem gera no máximo um fato). `id_lineage` é
   nullable, para registros que no futuro não venham de planilha (app
   colaborativo); a unicidade só vale quando ele existe.
3. Chave natural de `lineage`: `(origin_file, origin_sheet, origin_row)`, com dois
   índices únicos parciais no padrão do ADR-0002 (com e sem `origin_sheet`). Se o
   Postgres do projeto for 15 ou superior, `UNIQUE NULLS NOT DISTINCT` resolve com
   um índice só.
4. Idempotência: o loader resolve-ou-cria a linha de `lineage` pela chave natural
   (`_merge_ids`) e depois o fato por `id_lineage` ("já existe fato com esse
   `id_lineage`?"), no lugar de comparar três strings.
5. Só linhas que geram fato ganham `lineage`. Linhas ignoradas (por exemplo
   `total_row`, ADR-0012, ou espécie não resolvida) continuam rastreáveis pelas
   colunas `_source_*` das tabelas `cln_*`.
6. Staging e clean não mudam. A tabela é populada na camada **load**, antes dos
   fatos, em módulo novo (`load/lineage.py`), nos moldes de
   `species_attributes.py`, para não ampliar `taxonomy.py`.
7. Opcional: views de leitura (`occurrence_with_lineage`,
   `bibliographic_citation_with_lineage`) que devolvem as colunas de origem sem
   JOIN manual, para quem consulta o banco direto.

## Alternativas consideradas

| Alternativa                                                                                                | Motivo da rejeição                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------| --------------------------------------------------------------------------------------------------------------------------------------------------------|
| Manter as colunas nos fatos                                                                                | Contraria a decisão de organizar o banco e mantém a repetição.                                                                                         |
| Lineage também em staging/clean                                                                            | Essas tabelas são efêmeras (`replace`) e usam `_source_row` na ordenação do fill-down.                                                                 |
| Normalizar também arquivo e aba numa tabela `source` (a `lineage` guardaria só `id_source` e `origin_row`) | Adiada: tiraria o nome do arquivo repetido de dentro da própria `lineage`, e como os fatos só têm `id_lineage`, pode ser feita depois sem mexer neles. |

## Consequências

**Positivas:**
- As tabelas-fato ficam enxutas: um inteiro no lugar de três colunas.
- A chave de idempotência dos fatos vira um id único (`id_lineage`).
- Consultar "tudo que veio desta aba" é uma junção simples (ou a view).

**Negativas / trade-offs aceitos:**
- O nome do arquivo ainda se repete dentro de `lineage` (uma linha por linha de origem); a tabela `source` acima resolve isso se virar incômodo.
- Ler a origem completa de um fato exige JOIN (a view mitiga).
- Todo loader muda: SPP, citações, espécimes e, nascendo já no padrão novo, Canteiro C e Inventário.

**Impacto no código existente:**
- Arquivos/tabelas afetados: migration nova, `config.py`, `load/lineage.py` (novo), `load_SPP.py`, `load_arboreto_citations.py`, `load_arboreto_specimens.py`, DER (inclusive blocos `Dep`), `data_dictionary.md`, `processos_de_etl.md` §1 (a frase "a lineage não fica em tabela separada" deixa de valer), nota de remissão nos ADRs 0001 e 0007.
- Precisa de migração? Sim. No banco local, descartável, basta reconstruir (o pipeline é idempotente). Se existir banco compartilhado: criar `lineage` a partir dos `DISTINCT origin_file, origin_sheet, origin_row` de `occurrence` e `bibliographic_citation`, preencher `id_lineage` por junção, e só então remover as colunas antigas.
- É retroativo? Sim, afeta todas as fontes carregadas, sem perda de dado.
- Ordem: implementação depois do ADR-0010 (renomeação), do refactor `resolve_species_id()` e da segregação build/load, para não editar os loaders três vezes.

## Referências

- ADR-0001, ADR-0002, ADR-0007, ADR-0010, ADR-0012
