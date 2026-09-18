# ADR 0003 — Registro de dados taxonômicos incertos (gênero-só / morfo-espécie)

**Data:** 09/08/2026
**Status:** aprovada (temporária: ver "Consequências")
**Autor(es):** Davidson

---

## Contexto

As planilhas de citação do arboreto (Monografia Gabriel, Livro Pesquisas no
JB, JABOT) trazem registros que não seguem o padrão binomial completo
"Gênero + epíteto + autor":

- **Gênero só** (ex.: planilha só diz "Handroanthus", sem epíteto).
- **Morfo-espécie** (ex.: "Morfo-Espécie 1"), usada quando o espécime não
  foi identificado a nível de gênero/espécie.

A política geral do projeto (ver `panorama_tecnico_jabotur.md`,
seção 1) é registrar tudo, nunca descartar por incerteza de dado, decisão
já tomada antes desta, aqui só se aplica ao caso concreto de taxonomia.

## Decisão

Ambos os casos são registrados em `epiteto_especifico`, não descartados,
mas com semânticas de reconciliação diferentes:

- **Gênero só**: `id_genero` preenchido, `nome=NULL`. **Reconcilia**
  normalmente entre fontes via get-or-create — é o mesmo conceito
  taxonômico independente da fonte. Confirmado em produção: 4 citações
  "Handroanthus" no JABOT resolvem pro mesmo `id_species`.
- **Morfo-espécie**: `id_genero=NULL`, `nome="Morfo-Espécie 1 [aba#linha]"`
  — origem embutida no nome pelo `load_arboreto_citations.prepare()`.
  **Nunca reconcilia** entre fontes, porque a numeração ("Morfo-Espécie 1",
  "Morfo-Espécie 2"...) é local a cada planilha/levantamento — duas fontes
  com "Morfo-Espécie 1" não são necessariamente o mesmo espécime.

`clean_arboreto_citations.py` sinaliza os dois casos via `parse_status`
(`PARSE_STATUS_GENUS_ONLY` / `PARSE_STATUS_MORPHOSPECIES`) e a coluna
`reconcile_across_sources` (False só para morfo-espécie).

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Descartar esses registros até o pytaxon chegar | rejeitada, viola a política central do projeto de nunca descartar por incerteza. |
| **Caso especial em `taxonomy.py` pra impedir reconciliação de morfo-espécie** | rejeitada em favor de embutir a origem na própria chave natural (`nome`), que já garante chave sempre distinta sem lógica condicional extra no get-or-create. |


## Consequências

**Positivas / Negativas / Impacto no código existente:**
- Ambos os casos aparecem em `epiteto_especifico` com `needs_review=True`
  seria redundante a nível de espécie, a sinalização de revisão vive na
  camada clean (`needs_review` em `cln_arboreto_citations`), não na
  dimensão final.
## Referências

- `panorama_tecnico_jabotur.md`

---
