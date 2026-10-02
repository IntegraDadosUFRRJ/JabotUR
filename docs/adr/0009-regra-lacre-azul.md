# ADR-0009 — Preferência e identificação implícita do Lacre Azul

**Data:** 22/07/2026
**Status:** Aprovado
**Autor(es):** Davidson

---

## Contexto

Nas planilhas do arboreto (tanto Espécimes quanto Canteiro C), o campo de "N° de registro" ou "Numeração Lacre" pode conter diferentes formatos de identificação física da planta. Existem lacres amarelos (que possuem o prefixo "RBRv", ex: "RBRv 12345") e lacres azuis.
Ocasionalmente, o lacre azul aparece digitado apenas como um número, sem conter a palavra explícita "AZUL". Além disso, em alguns casos os dados originais trazem a anotação dos dois lacres simultaneamente na mesma célula/linha. A falta de uma regra clara resultava em ambiguidade de como extrair a identificação canônica do registro.

## Decisão

Qualquer número de registro que não possua o prefixo "RBRv" (case-insensitive) é tacitamente considerado um lacre azul, mesmo na ausência da palavra. Quando um mesmo registro apresentar simultaneamente um lacre amarelo ("RBRv...") e um azul, o lacre azul sempre tem preferência e será o valor limpo final guardado em `registration_number`.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter os dois números concatenados | Quebra a pesquisa e a semântica de dimensão relacional; um espécime no banco deve ter um identificador canônico primário extraído. |
| Tratar números sem prefixo como "Desconhecido" ou NULL | Perda substancial de dados reais, contrariando a política de não descartar dados, visto que foi validado pelo JB-UFRRJ que a ausência de RBRv implica lacre azul neste contexto. |

## Consequências

**Positivas:**
- Consistência ao carregar múltiplas fontes do arboreto: Canteiro C e Espécimes utilizam a mesma lógica para tratar a coluna (via `transforms/registration_number.py`).

**Negativas / trade-offs aceitos:**
- Se futuramente o Jardim Botânico criar um terceiro tipo de lacre sem prefixo, a premissa de exclusão ("não é RBRv = é azul") dará falso positivo e a função `registration_number.py` precisará de revisão.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `scripts/transforms/registration_number.py` e a tabela `occurrence_arboretum`.
- Precisa de migração? não
- É retroativo? Sim, afeta todos os dados da fonte Espécimes.

## Referências

- Trecho do `panorama_tecnico_jabotur.md` ou DER afetado: DER em `occurrence_arboretum_registration_lineage` e dicionário de dados Seção 4.

---
