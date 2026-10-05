# ADR-0010 — Nomenclatura em inglês também para as tabelas e colunas já existentes

**Data:** 05/10/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** revoga a regra "não retroativo" de nomenclatura
(`ONBOARDING.md` §3, `CONTRIBUTING.md` §3, `panorama_tecnico_jabotur.md` §4 e
cabeçalho do `JabotUR_DER.md`).

---

## Contexto

No início, a regra era: tabelas e colunas **novas** seguem inglês/Darwin
Core, e as **já existentes** (SPP) continuam em português, sem renomear. Isso
deixou o schema com dois vocabulários convivendo:

- `familia` -> `genero` -> `epiteto_especifico` ao lado de `species_status`,
  `occurrence` e `sector`;
- FKs que misturam `id_familia` e `id_species`, sendo que `id_species`
  aponta para uma tabela chamada `epiteto_especifico` (o nome da FK não bate
  com o nome da tabela);
- `coleta_substrato.id_briofita` e `coleta_observacao.id_briofita`
  apontam para `occurrence.id`, não para uma briófita (nome desatualizado
  desde o ADR-0001, que aposentou a tabela `coleta`).

O motivo prático de ordem: o rascunho de normalização do Inventário do Gabriel
(`[Normal] Gabriel.docx`) já propõe tabelas `family`, `genus` e `species`,
que colidem com `familia`, `genero` e `epiteto_especifico`. Resolver a
nomenclatura antes de integrar essa fonte evita criar um terceiro vocabulário.

O custo é o menor possível agora: quatro fontes carregadas, pipeline
idempotente, e uma regra de projeto que já manda manter todo literal em
`config.py`.

## Decisão

1. **Todos os identificadores do schema normalizado** (tabelas, colunas,
   índices e constraints nomeadas) passam para inglês, conforme a tabela de
   equivalência do Anexo A.
2. **A convenção de FK continua `id_<entidade>`** (ex.: `id_species`,
   `id_sector`), que já é usada por todas as tabelas em inglês. Não migramos
   para `<entidade>_id` neste ADR.
3. **As camadas `stg_`/`cln_` também são renomeadas** nos nomes de tabela e
   de coluna que o projeto controla (Anexo B). Os **cabeçalhos originais das
   planilhas** (chaves dos mapas de colunas em `config.py`) não mudam, porque
   são dado externo.
4. **Valores de dado não mudam.** "Adulto"/"jovem", "Hepáticas", "Exótica",
   "Morfo-Espécie 1 [aba#linha]" e afins continuam como estão: a decisão é
   sobre identificadores, não sobre conteúdo. Escopo confirmado com a orientadora
   em 02/10/2026: os dados se mantêm como vieram, só o banco muda.
5. **Fora de escopo:** nomes de variáveis e funções Python (ex.:
   `id_especie` em loaders) e nomes de arquivo (`clean_SPP.py`). Podem ser
   ajustados de forma oportunista, sem exigência neste ADR.
6. **Execução em PR dedicado, só de renomeação.** Nenhum bugfix ou mudança de
   comportamento entra junto, para que o diff seja revisável como mecânico.
   O ADR é aprovado antes de o PR de código ser aberto.
7. **Regra daqui em diante, sem exceção:** toda tabela, coluna ou índice novo
   nasce em inglês.
8. **Ordem de execução:** o PR de código entra depois das correções de
   parser/staging (Etapa 1) e da entrada da branch de Espécimes na `main`
   (para o diff renomear um arquivo só uma vez), e antes dos refactors
   estruturais. A tabela `lineage` do ADR-0011 já nasce com nomes em inglês.

## Alternativas consideradas

| Alternativa                                                        | Motivo da rejeição                                                                                                                                                                                                                          |
| --------------------------------------------------------------------| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Manter o schema bilíngue (regra "não retroativo")                  | Mantém FKs com nome diferente da tabela alvo (`id_species` → `epiteto_especifico`).                                                                                                                                                         |
| Renomear só o schema final e deixar `stg_`/`cln_` em português     | Deixaria `cln_*.familia → family.name`, um mapeamento inconsistente. O custo de renomear essas camadas é baixo, porque elas são recriadas em modo `replace`.                                                                                |
| Renomear depois de integrar o Inventário                           | Cada loader novo escreveria nomes que serão removidos, e o rascunho do Gabriel (`family`, `genus`, `species`) colidiria com as tabelas existentes.                                                                                          |
| Chamar a tabela de `taxon` em vez de `species`                     | Exigiria renomear `id_species` em 7 tabelas que já estão em inglês (`occurrence`, `species_status`, `species_domain`, `species_country`, `species_state`, `species_geographic_area`, `bibliographic_citation`), ampliando o diff sem ganho. |
| Migrar a convenção de FK para `<entidade>_id` junto com a tradução | Mistura dois tipos de mudança no mesmo PR e contradiz todas as tabelas já em inglês. Se desejado, fica para um ADR próprio.                                                                                                                 |

## Consequências

**Positivas:**
- Um só vocabulário no banco, no código, no DER e na documentação.
- `id_species` passa a apontar para `species.id`, e `id_briofita` deixa de
  apontar para algo que não é briófita.
- Termos alinhados com Darwin Core (`phylum`, `family`, `genus`) e com o
  rascunho do Inventário.
- Onboarding mais simples: a regra de nomenclatura vira uma só.

**Negativas / trade-offs aceitos:**
- Diff grande e mecânico, com risco de conflito em branches abertas (em
  especial Canteiro C), que devem ser rebaseadas ou nascer já com os nomes
  novos.
- `species` guarda também as linhas "gênero-só" e "morfo-espécie" do
  ADR-0003, e `species.epithet` guarda o placeholder de morfo-espécie. O nome
  é um pouco mais estreito que o conteúdo; aceito por coerência com
  `id_species` e com o Darwin Core.
- ADRs antigos citam os nomes anteriores (0002, 0003, 0004). Eles **não são
  reescritos** (registro histórico); recebem uma nota no topo remetendo a
  este ADR.
- Relatórios e histórico de git continuam com os nomes antigos.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `config.py`, `db/db_utils.py`, `load/taxonomy.py`
  (todos sob CODEOWNERS), `load_*.py`, `clean_*.py` (queries DuckDB),
  `scripts/init_postgres`, migrations, `JabotUR_DER.md`, `data_dictionary.md`,
  `processos_de_etl.md`, `panorama_tecnico_jabotur.md`, `ONBOARDING.md`,
  `CONTRIBUTING.md`.
- Precisa de migração? **Sim**
- É retroativo? Sim, afeta o schema de todas as fontes já carregadas, mas os
  dados são preservados.
- Verificação exigida no PR: contagem de linhas por tabela antes e depois
  iguais; pipeline completo rodado duas vezes sem alterar contagens
  (idempotência); `grep` dos nomes antigos nas áreas em escopo sem
  ocorrências; consulta de sobras (constraints, índices e sequences com nome
  antigo) no script da migration.

## Referências

- ADR-0001 (super-tipo `occurrence`), ADR-0002 (índices parciais), ADR-0003
  (gênero-só/morfo-espécie), ADR-0004 (`filo` NULL), ADR-0006
  (`identification_qualifier`)
- `[Normal] Gabriel.docx` (rascunho do Inventário com nomes em inglês)
- `JabotUR_DER.md`, `data_dictionary.md`, `processos_de_etl.md`

---

## Anexo A — Equivalência do schema normalizado

> Levantada a partir do `JabotUR_DER.md`. Conferir contra o `config.py` e o
> DDL real antes do PR (um `grep` por cada nome antigo fecha a lista).

**Tabelas**

| Antigo | Novo | Observação |
|---|---|---|
| `filo` | `phylum` | termo do Darwin Core (`phylum`) |
| `familia` | `family` | |
| `genero` | `genus` | |
| `epiteto_especifico` | `species` | alvo das FKs `id_species` já existentes |
| `autor` | `author` | |
| `identificacao` | `identification_status` | evita confusão com `identification_qualifier` (ADR-0006) |
| `forma_vida` | `life_form` | |
| `parcela` | `plot` | |
| `observacao` | `remark` | alinhado a `occurrenceRemarks`; `observation` colide com o sentido usual de ocorrência |
| `substrato` | `substrate` | |
| `coleta_observacao` | `occurrence_remark` | "coleta" não existe mais desde o ADR-0001 |
| `coleta_substrato` | `occurrence_substrate` | idem |

**Colunas**

| Tabela (nome novo) | Antigo → Novo |
|---|---|
| `phylum` | `nome` → `name` |
| `family` | `id_filo` → `id_phylum`; `nome` → `name` |
| `genus` | `id_familia` → `id_family`; `nome` → `name` |
| `species` | `id_genero` → `id_genus`; `id_autor` → `id_author`; `nome` → `epithet`; `infraespecifico` → `infraspecific` |
| `author` | `nome` → `name` |
| `identification_status` | `descricao` → `description` |
| `life_form` | `tipo` → `type` |
| `plot` | `codigo` → `code`; `coordenada` → `coordinate` |
| `remark` | `comentario` → `comment` |
| `substrate` | `nome` → `name`; `sigla` → `abbreviation` (`code` já é usado pelos códigos IUCN) |
| `occurrence_remark` | `id_briofita` → `id_occurrence`; `id_observacao` → `id_remark` |
| `occurrence_substrate` | `id_briofita` → `id_occurrence`; `id_substrato` → `id_substrate` |
| `occurrence_bryophyte` | `id_forma` → `id_life_form`; `id_identificacao` → `id_identification_status`; `id_parcela` → `id_plot`; `amostra` → `sample` |

`id_briofita` → `id_occurrence` não é tradução literal: corrige um nome que
ficou errado desde o ADR-0001 (a coluna referencia `occurrence.id`).

**Índices**

| Antigo | Novo |
|---|---|
| `epiteto_uniq_com_infra` | `species_uniq_with_infra` |
| `epiteto_uniq_sem_infra` | `species_uniq_without_infra` |

## Anexo B — Camadas `stg_`/`cln_` (proposta, a confirmar com `grep` em `config.py`)

**Tabelas:** `stg_spp_briofitas` → `stg_spp_bryophytes` e
`cln_spp_briofitas` → `cln_spp_bryophytes`. As demais (`*_arboreto_citations`,
`*_arboreto_specimens`, `*_arboreto_canteiro_c`) já têm nome em inglês.

**Colunas recorrentes**

| Antigo | Novo |
|---|---|
| `familia` | `family` |
| `genero` | `genus` |
| `epiteto_especifico` | `epithet` |
| `infraespecifico` | `infraspecific` |
| `autor` | `author` |
| `filo` | `phylum` |
| `parcela` / `amostra` | `plot` / `sample` |
| `status_identificacao` / `identificacao` | `identification_status` |
| `forma_vida` | `life_form` |
| `substrato` | `substrate` |
| `observacoes` / `observacao` | `remarks` / `remark` |
| `quantidade` | `quantity` |
| `setor` | `sector` |
| `descricao_localizacao` | `location_description` |
| `estado_reprodutivo` | `reproductive_status` |
| `numero_registro` | `registration_number` |
| `origem` | `origin` |
| `dominio_fitogeografico` | `phytogeographic_domain` |
| `altura_m` | `height_m` |

**A decidir na issue (ambíguo ou em desenvolvimento):**
- `especie`: nas fontes de arboreto guarda o nome completo bruto (antes do
  parsing) e em SPP guarda só o epíteto. Sugestão: `species_raw` no arboreto e
  `epithet` em SPP, para não repetir a ambiguidade que o dicionário de dados já
  aponta.
- `grau_ameaca` → `conservation_status` ou `threat_category`, e
  `numeracao_lacre` / `localizacao_canteiro`: pertencem ao Canteiro C, que está
  em desenvolvimento.
