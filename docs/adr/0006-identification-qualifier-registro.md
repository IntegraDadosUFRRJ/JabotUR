# ADR 0006 — `identification_qualifier` é atributo de registro, não de espécie

**Data:** 12/08/2026
**Status:** aprovada
**Autor(es):** Davidson

---

## Contexto

Nomes científicos do arboreto às vezes vêm com um qualificador de
incerteza de identificação "cf." ou "aff." (ex.: "Handroanthus cf.
chrysotrichus"), capturado por `scientific_name.py`. A dúvida de design
era onde essa informação deveria morar: em `species` (nível
espécie) ou em cada registro individual que cita/observa a espécie.

## Decisão

`identification_qualifier` fica no **registro** (`bibliographic_citation` e `occurrence`, populado por Citações, Espécimes e também pelo SPP, onde `transforms/epithet.py` tira `cf.`/`aff.` do epíteto e `load_spp_bryophytes.py` grava o qualificador na ocorrência; Canteiro C usará a mesma coluna), nunca em `species`. Corresponde ao `identificationQualifier` do Darwin Core, que é por natureza um atributo de identificação individual, não da espécie em si.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Guardar o qualificador em `species` | Rejeitada: a incerteza é sobre *esta identificação específica*, não uma propriedade da espécie. Uma citação futura da mesma espécie sem qualificador não deve herdar a incerteza de uma citação anterior, o que aconteceria se o qualificador fosse atributo de espécie e todas as citações apontassem pra mesma linha de `species`. |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- A coluna vive em `occurrence` (tabela-base), não em `occurrence_arboretum`
  nem em nenhuma satélite, qualquer fonte com identificação incerta se
  beneficia da coluna estar no nível comum, sem duplicar por sub-tipo.
- Confirmado em código: `clean_arboretum_specimens.py` produz
  `identification_qualifier` usando `transforms/scientific_name.py` (que
  foi atualizado com `_GENUS_SP_RE`, prioridade do autor infraespecífico
  e exportação de `QUALIFIER_PATTERN` e `normalize_qualifier`), e
  `load_spp_bryophytes.py` também preenche
  `occurrence.identification_qualifier` via `transforms/epithet.py`.
- `bibliographic_citation.identification_qualifier` continua existindo em
  paralelo, é uma coluna própria dessa tabela, não uma FK pra
  `occurrence`, porque `bibliographic_citation` não é sub-tipo de
  `occurrence` (não representa espécime físico).

## Referências

- `panorama_tecnico_jabotur.md`

---
