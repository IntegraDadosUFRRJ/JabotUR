# ADR-002 — Índices únicos parciais em vez de sentinela para `infraespecifico`

**Data:** 11/08/2026
**Status:** Aprovado
**Autor(es):** Davidson

---

## Contexto

`epiteto_especifico` precisa de unicidade por
`(id_genero, nome, infraespecifico, id_autor)`, mas `infraespecifico` é
nullable, a maioria dos táxons não tem infraespecífico. No Postgres,
`NULL != NULL`, então uma constraint única direta sobre essas 4 colunas
não bloqueia duplicatas quando `infraespecifico IS NULL` (cada `NULL`
conta como distinto do outro).

## Decisão

Dois índices únicos parciais em vez de um valor sentinela
(ex.: string vazia `''`) para representar "sem infraespecífico":

```sql
CREATE UNIQUE INDEX epiteto_uniq_com_infra
ON epiteto_especifico (id_genero, nome, infraespecifico, id_autor)
WHERE infraespecifico IS NOT NULL;

CREATE UNIQUE INDEX epiteto_uniq_sem_infra
ON epiteto_especifico (id_genero, nome, id_autor)
WHERE infraespecifico IS NULL;
```

O lookup real de get-or-create continua em Python (`load/taxonomy.py`,
via `_none_if_nan` + tupla como chave de dict), os índices são
cinto-e-suspensório a nível de banco, não o mecanismo principal de
resolução.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Constraint única direta nas 4 colunas, sem tratamento de NULL | Não bloqueia duplicata alguma quando `infraespecifico IS NULL`, que é o caso mais comum |

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

**Impacto no código existente:**
- Arquivos/tabelas afetados: `epiteto_especifico` (schema),
  `db_utils.write_dataframe_to_postgres`, `load/taxonomy.py`.
- Precisa de migração: sim, `migrations/001_add_infraespecifico.sql`
  (adiciona a coluna + cria os dois índices).
- É retroativo: sim, aplicado antes do primeiro load de arboreto,
  citations rodou sobre o schema já migrado.

## Referências

- `migrations/001_add_infraespecifico.sql` (Apêndice do
  `panorama_tecnico_jabotur.md`)
- `JabotUR_DER.md`, comentário acima de `Table epiteto_especifico`

---

