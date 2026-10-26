# ADR 0005 — `conservation_status.code = 'NA'` é código real do IUCN, não placeholder de dado ausente

**Data:** 08/08/2026
**Status:** aprovada
**Autor(es):** Davidson

---

## Contexto

A coluna "Grau de Ameaça" do Canteiro C ("Rosa dos Ventos") usa os códigos
padrão do IUCN (NE, LC, VU, EN, NT, NA). O valor "na" (minúsculo, às vezes
vazio) aparece na planilha. À primeira vista parece dado ausente, mas
"NA" no IUCN significa **"Not Applicable"**, um valor semântico real
(ex.: espécie exótica/cultivada, pra qual avaliação de ameaça não se
aplica), não "não sei"/"não preenchido".

## Decisão

"na"/vazio na coluna "Grau de Ameaça" mapeia para o código IUCN real `NA`
em `conservation_status`, quando fizer sentido semântico, não para NULL
na FK.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| **Mapear "na" para NULL na FK** (tratar como qualquer outro campo ausente) | Rejeitada porque perde informação real: "Not Applicable" é uma classificação válida do IUCN, diferente de "não avaliado" (que seria o código NE) ou de dado simplesmente não coletado. |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- Esta é a **única exceção deliberada** à regra geral do projeto de "NULL
  de verdade, quase sempre" (ver ADR-0008, que cobre os demais campos do
  Canteiro C/Espécimes). Documentar isso explicitamente evita que alguém
  "corrija" o mapeamento no futuro achando que é um bug.

## Referências

- `panorama_tecnico_jabotur.md`

---
