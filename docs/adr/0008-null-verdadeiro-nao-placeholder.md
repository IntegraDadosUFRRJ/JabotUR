# ADR 0008 — Dado ausente vira NULL verdadeiro, nunca uma linha "N/A" criada via get-or-create

**Data:** 12/08/2026
**Status:** aprovada
**Autor(es):** Davidson

---

## Contexto

Várias colunas de Espécimes e Canteiro C costumam vir vazias ou com "N/A"/
"na" na planilha original: `Descrição da localização`, `Estado
reprodutivo` (Espécimes maioria NULL), `Domínio fitogeográfico`
(Canteiro C quando ausente), entre outras que apontam pra dimensões via
get-or-create (`reproductive_status`, `phytogeographic_domain`).

Um get-or-create ingênuo, se receber a string literal "N/A" ou "na" como
entrada, criaria uma linha real nessas dimensões com esse valor poluindo, por exemplo, `reproductive_status` com uma categoria
"N/A" que não é um estado reprodutivo de verdade, só ausência de dado.

## Decisão

Dado ausente vira **NULL de verdade** na FK (`occurrence_arboretum.
id_reproductive_status`, `location_description`) ou **nenhuma linha
inserida** na tabela associativa (`species_domain`), nunca uma linha
sentinela "N/A"/"na" criada via get-or-create.

Esta é a regra geral do projeto ("NULL de verdade, quase sempre"). A única
exceção deliberada é `conservation_status.code = 'NA'`, que é um código
real do IUCN, não um placeholder (ver ADR-0005 para o raciocínio
específico desse caso.)

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| **Deixar o get-or-create tratar "N/A"/"na" como qualquer outro valor** | rejeitada: cria uma linha de dimensão falsa (ex.: `reproductive_status` com uma entrada "N/A"), que qualquer análise futura (contagem de estados reprodutivos, por exemplo) teria que saber filtrar manualmente. |
| Usar string vazia em vez de NULL | rejeitada pelo mesmo motivo geral do ADR-0002: NULL de verdade é semanticamente mais correto e evita tratamento especial de string vazia espalhado pelo código de leitura. |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- A etapa `clean_*` de cada fonte precisa normalizar explicitamente "N/A"/
  "na"/vazio para `None`/NaN **antes** de a etapa `load_*` fazer
  get-or-create, não pode confiar que o get-or-create vai filtrar isso
  sozinho.
- Ao adicionar uma nova coluna com esse padrão (planilha nova, dimensão
  nova via get-or-create), checar explicitamente se "N/A"/"na"/vazio
  precisa desse tratamento antes do load, e se algum desses casos na
  verdade é um código semântico real (como em ADR-0005) em vez de dado
  ausente.

## Referências

- `panorama_tecnico_jabotur.md`

---
