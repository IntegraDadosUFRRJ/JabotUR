# ADR-001 — Occurrence como super-tipo/sub-tipo, substituindo `coleta`

**Data:** 08/08/2026
**Status:** Aprovado
**Autor(es):** Davidson

---

## Contexto

A tabela original `coleta` (briófitas) guardava tudo num único registro:
espécie + metadados de coleta específicos de briófita (forma de vida,
parcela, amostra, identificação). Ao integrar o arboreto, que tem seus
próprios metadados de ocorrência (setor, número de registro, estado
reprodutivo) sem nenhuma sobreposição real com os de briófita, ficou
claro que replicar o padrão de `coleta` criaria uma tabela paralela por
fonte, cada uma duplicando as colunas comuns (`id_species`,
`origin_file`, `origin_row`).

## Decisão

Adotado o padrão super-tipo/sub-tipo: `occurrence` (tabela base, com
`id_species`, `basis_of_record`, `identification_qualifier`,
`origin_file`/`origin_sheet`/`origin_row`) + tabelas satélite
`occurrence_bryophyte` e `occurrence_arboretum`, cada uma só com o que é
exclusivo daquela fonte.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Tabelas paralelas (`registro_briofita`, `registro_arboreto`), cada uma com colunas completas | Duplica `id_species`/`origin_file`/`origin_row` em cada tabela nova; uma 3ª fonte exigiria repetir esse conjunto de novo, sem ganho real |
| Uma única tabela `occurrence` com todas as colunas de todas as fontes (largas, muitas NULL) | Cresce sem controle a cada fonte nova; mistura semântica de campos que não se aplicam entre fontes |

## Consequências

**Positivas:**
- Uma 3ª fonte só adiciona `occurrence_<fonte>` nova, sem tocar nas
  demais nem repetir colunas comuns.
- `identification_qualifier` pôde ser promovido para `occurrence` (nível
  registro) de forma natural quando Espécimes precisou dele, sem migrar
  schema de novo.

**Negativas / trade-offs aceitos:**
- Toda leitura que precisa dos dados completos de uma ocorrência exige
  JOIN entre `occurrence` e a satélite correta, aceito, dado que as
  queries são majoritariamente por fonte de qualquer forma.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `load_SPP.py` (removida chamada a
  `build_coleta`), `load_arboreto_citations.py`,
  `load_arboreto_specimens.py`, `JabotUR_DER.md`.
- Migração de dados: sim, de `coleta` pra `occurrence` +
  `occurrence_bryophyte` (1 linha antiga -> 1 linha em cada tabela nova).
- É retroativo: sim, para os dados de SPP já carregados.

## Referências

- `panorama_tecnico_jabotur.md`, seção 4 ("Super-tipo/sub-tipo pra
  registro de ocorrência")
- `JabotUR_DER.md`, comentário acima de `Table occurrence`

---
