# ADR-0004 — `phylum` NULL para famílias de origem arboreto

**Data:** 08/08/2026
**Status:** aprovada (revisitar quando virar bloqueio real)
**Autor(es):** Davidson

---

## Contexto

`family.id_phylum` referencia `phylum`, preenchido corretamente para todas as
famílias de origem SPP (briófitas: Musgos/Hepáticas, via
`PHYLUM_NAME_MAP`). O arboreto, porém, abrange mais de uma divisão
taxonômica real, por exemplo, Pinaceae é gimnosperma enquanto a maior
parte das famílias do arboreto é angiosperma. Não existe um valor único de
`phylum` aplicável a "família de origem arboreto" como grupo.

## Decisão

`family.id_phylum` fica `NULL` para famílias que entram via arboreto, em vez
de forçar um valor incorreto ou um placeholder genérico. Popular
corretamente exigiria pesquisa taxonômica família a família, que não é o
foco atual do projeto.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| **Criar um `phylum` genérico tipo "Arboreto" ou "Angiospermas/Gimnospermas (não classificado)"** | Rejeitada por misturar uma categoria administrativa (de onde veio o dado) dentro de uma dimensão que deveria representar taxonomia real (divisão biológica). |
| **Pesquisar e preencher `phylum` corretamente família por família antes de integrar o arboreto** | Rejeitada por não ser bloqueante para o objetivo atual (reconciliação de espécies entre fontes); adiada até virar necessidade real. |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- Qualquer query que agrupe ou filtre por `phylum` vai naturalmente excluir
  ou agrupar como NULL as famílias de origem arboreto, até esta decisão
  ser revisitada.
- Revisitar quando: uma nova fonte depender de `phylum` preenchido, ou uma
  análise específica precisar agrupar/filtrar por divisão taxonômica das
  famílias do arboreto.

## Referências

- `panorama_tecnico_jabotur.md`

---
