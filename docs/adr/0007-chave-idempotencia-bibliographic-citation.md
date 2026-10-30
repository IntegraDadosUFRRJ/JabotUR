# ADR 0007 — Chave de idempotência composta para `bibliographic_citation`

**Data:** 12/08/2026
**Status:** aprovada
**Autor(es):** Davidson

---

## Contexto

`load_arboreto_citations.py` precisa de uma chave natural estável pra
get-or-create de cada citação, rodar o pipeline de novo não pode duplicar
registros. As 3 abas de citação (Monografia Gabriel, Livro Pesquisas no
JB, JABOT) vivem no mesmo arquivo `.xlsx`, e a numeração de linha
(`_source_row`) **reinicia em cada aba**.

## Decisão

A chave de idempotência é a tupla `(origin_file, origin_sheet, origin_row)`
— `origin_file` sozinho não basta, porque duas citações de abas diferentes
podem ter o mesmo `origin_row` (ex.: linha 5 de "JABOT" e linha 5 de
"Monografia Gabriel" são registros diferentes, não o mesmo).

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| `(origin_file, origin_row)` | rejeitada: colide entre abas diferentes do mesmo arquivo, já que a numeração de linha reinicia por aba. |
| Numeração global contínua entre as abas antes do staging | rejeitada por adicionar uma etapa de transformação artificial só pra evitar guardar uma coluna extra (`origin_sheet`), que já é natural de se ter (rastreia de qual aba/fonte a citação veio, útil por si só pra `source` em `bibliographic_citation`). |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- `origin_sheet` é obrigatória em `bibliographic_citation`, diferente de
  `occurrence` (SPP), onde é NULL pras linhas antigas, lá um arquivo
  corresponde a uma aba só, então o problema não existe.
- Qualquer fonte nova que reaproveite o padrão "múltiplas abas no mesmo
  arquivo com numeração de linha reiniciando" deve seguir a mesma
  composição de chave, não assumir que `(origin_file, origin_row)` basta.

## Referências

- `panorama_tecnico_jabotur.md`

---
