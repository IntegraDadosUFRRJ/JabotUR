# ADR-0002 — Índices únicos parciais em vez de sentinela para `infraspecific`

**Data:** 11/08/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** O padrão arquitetural de índices parciais aqui definido é reutilizado pelo **ADR-0011** para a tabela `lineage`. `id_author` continua nos dois índices parciais porque o autor permanece na chave da espécie (conforme o ADR de autor na chave da espécie).

---

## Contexto

`species` precisa de unicidade por
`(id_genus, epithet, infraspecific, id_author)`, mas `infraspecific` é
nullable, a maioria dos táxons não tem infraespecífico. No Postgres,
`NULL != NULL`, então uma constraint única direta sobre essas 4 colunas
não bloqueia duplicatas quando `infraspecific IS NULL` (cada `NULL`
conta como distinto do outro).

## Decisão

Dois índices únicos parciais em vez de um valor sentinela
(ex.: string vazia `''`) para representar "sem infraespecífico":

```sql
CREATE UNIQUE INDEX species_uniq_with_infra
ON species (id_genus, epithet, infraspecific, id_author)
WHERE infraspecific IS NOT NULL;

CREATE UNIQUE INDEX species_uniq_without_infra
ON species (id_genus, epithet, id_author)
WHERE infraspecific IS NULL;
```

O lookup real de get-or-create continua em Python (`load/taxonomy.py`,
via `_none_if_nan` + tupla como chave de dict), os índices são
cinto-e-suspensório a nível de banco, não o mecanismo principal de
resolução.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Constraint única direta nas 4 colunas, sem tratamento de NULL | Não bloqueia duplicata alguma quando `infraspecific IS NULL`, que é o caso mais comum |

## Consequências

**Positivas:**
- `NULL` continua significando "sem infraespecífico" de forma limpa,
  sem sentinela artificial se propagando por queries e relatórios.
- Alinhado com a política geral do projeto de "NULL de verdade,
  quase sempre".

**Negativas / trade-offs aceitos:**
- Upsert (`ON CONFLICT`) precisa tratar os dois arbiter indexes
  separadamente em `db_utils.py`, mais complexo que um `ON CONFLICT`
  único.
- *(Nota de revisão)* O upsert em `scripts/db/db_utils.py` (`upsert_rows` via `_upsert_by_id_statement`) agora é sempre por `id` (`ON CONFLICT (id)`), não pelos índices parciais. O get-or-create resolve os ids em Python (`scripts/load/taxonomy.py`) e os dois índices parciais em `species` ficam no banco só para barrar duplicatas.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `species` (schema),
  `db_utils.write_dataframe_to_postgres`, `load/taxonomy.py`.
- Precisa de migração: sim, `migrations/001_add_infraespecifico.sql`
  (adiciona a coluna + cria os dois índices).
- É retroativo: sim, aplicado antes do primeiro load de arboreto,
  citations rodou sobre o schema já migrado.
- *(Nota de revisão)* `db_utils.write_dataframe_to_postgres` ficou restrita ao Canteiro C (os loads usam `db_utils.upsert_rows`). Os índices parciais agora nascem direto em `scripts/db/schema.sql`, e a pasta `migrations/` (`migrations/001_add_infraespecifico.sql`) saiu porque o banco é recriado do `schema.sql`.

## Referências

- `migrations/001_add_infraespecifico.sql` (Apêndice do
  `panorama_tecnico_jabotur.md`) *(Nota de revisão: os índices hoje vivem em `scripts/db/schema.sql`)*
- `JabotUR_DER.md`, comentário acima de `Table species`

---

