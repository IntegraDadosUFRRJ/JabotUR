// =========================================================================
// JabotUR — DER consolidado
// Convenção (ADR-0010): a regra antiga "não retroativo" foi revogada.
// Todas as tabelas, colunas e índices das fontes integradas usam
// nomenclatura em inglês/Darwin Core.
//
// Justificativas de decisão de arquitetura vivem em docs/adr/ (ADR = numerado,
// com contexto/alternativas/consequências), não neste arquivo, aqui só
// referência curta. Ver CONTRIBUTING.md para o padrão de ADR.
//
// Nota sobre `>?` nos Refs: nenhuma coluna de FK aqui tem `not null`
// explícito, e várias são legitimamente nullable por decisão de negócio
// (ADR-0003, ADR-0004, ADR-0008 etc.) — `>?` é o operador do dbdiagram
// pra "referencia se houver valor, mas pode ser NULL" (o `>` puro exige
// que a FK sempre aponte pra uma linha existente).
//
// Este arquivo tem duas partes: o schema (Table/Ref) e, ao final, a seção
// de lineage (Dep) mostrando como o dado flui de staging até as tabelas
// normalizadas, por fonte.
//
// NOTA DE AUDITORIA (Realidade de Implementação em schema.sql/config.py vs DER Alvo):
// O DER consolida o modelo conceitual e relacional alvo do JabotUR. No esquema atual
// (`scripts/db/schema.sql` e `scripts/config.py`), estão implementadas as tabelas:
// `phylum`, `family`, `genus`, `species`, `author`, `identification_status`, `life_form`,
// `plot`, `remark`, `substrate`, `occurrence_remark`, `occurrence_substrate`, `occurrence`,
// `occurrence_bryophyte`, `occurrence_arboretum`, `reproductive_status`, `sector` e
// `bibliographic_citation` (cobrindo SPP, Arboreto — Citações e Arboreto — Espécimes).
// As demais tabelas constam neste DER como especificação alvo:
//   - Arboreto — Canteiro C (staging/clean já no repositório; falta o load): `species_status`, `conservation_status`, `phytogeographic_domain`, `species_domain`;
//   - Arboreto — Lista Completa Sps (recebido, integração não iniciada): `country`, `state`, `species_country`, `species_state`, `species_geographic_area`.
// Da mesma forma, tabelas de staging/clean para Canteiro C constam como stubs de modelagem para o lineage.
// =========================================================================


// -------------------------------------------------------------------------
// Núcleo taxonômico e dimensões de Briófitas (schema.sql)
// -------------------------------------------------------------------------

Table phylum {
  id bigint [pk]
  name text
}

Table family {
  id bigint [pk]
  id_phylum bigint [ref: >? phylum.id]  // nullable para famílias de origem arboreto (ver ADR-0004)
  name text
}

Table genus {
  id bigint [pk]
  id_family bigint [ref: >? family.id]
  name text
}

Table species {
  id bigint [pk]
  id_genus bigint [ref: >? genus.id]  // NULL para morfo-espécie (ver ADR-0003)
  id_author bigint [ref: >? author.id]
  epithet text  // NULL para "gênero só" (ver ADR-0003)
  infraspecific text  // nullable, ex.: "var. cebil". Unicidade: ver ADR-0002 (índices parciais em scripts/db/schema.sql)
}

Table author {
  id bigint [pk]
  name text
}

Table identification_status {
  id bigint [pk]
  description text
}

Table life_form {
  id bigint [pk]
  type text
}

Table plot {
  id bigint [pk]
  code text
  coordinate text
}

Table remark {
  id bigint [pk]
  comment text
}

Table substrate {
  id bigint [pk]
  name text
  abbreviation text
}

// occurrence_remark / occurrence_substrate: renomeadas de coleta_* pelo ADR-0010.
// Alvo da referência é occurrence_bryophyte.id (ver `scripts/db/schema.sql`).
Table occurrence_remark {
  id_occurrence bigint [ref: > occurrence_bryophyte.id]
  id_remark bigint [ref: > remark.id]

  indexes {
    (id_occurrence, id_remark) [pk]
  }
}

Table occurrence_substrate {
  id_occurrence bigint [ref: > occurrence_bryophyte.id]
  id_substrate bigint [ref: > substrate.id]

  indexes {
    (id_occurrence, id_substrate) [pk]
  }
}


// NOVO: registro de ocorrência (substitui a antiga tabela `coleta`)
// Padrão super-tipo/sub-tipo, ver ADR-0001 para contexto e alternativas.

Table occurrence {
  id bigint [pk]
  id_species bigint [ref: >? species.id]  // nullable para ocorrências de Espécimes sem identificação (load_arboretum_specimens.py)
  basis_of_record text  // 'PreservedSpecimen' (SPP), 'LivingSpecimen' (arboreto)
  identification_qualifier text  // "cf."/"aff." (ver ADR-0006)
  origin_file text
  origin_sheet text  // nullable: NULL pras linhas do SPP (1 arquivo = 1 aba lá); obrigatório a partir do arboreto, mesmo motivo do ADR-0007
  origin_row bigint

  note: 'Auditoria de implementação vs DER: o carregador do SPP (`load_spp_bryophytes.py`) preenche `basis_of_record` e `identification_qualifier` (e não preenche `origin_sheet`); o de Espécimes (`load_arboretum_specimens.py`) preenche os três e grava `id_species = NULL` quando a ocorrência vem sem gênero e sem epíteto. A população ou externalização do lineage está prevista conforme ADR-0011.'
}

Table occurrence_bryophyte {
  id bigint [pk, ref: - occurrence.id]
  id_life_form bigint [ref: >? life_form.id]
  id_identification_status bigint [ref: >? identification_status.id]
  id_plot bigint [ref: >? plot.id]
  sample bigint
}

Table occurrence_arboretum {
  id bigint [pk, ref: - occurrence.id]
  id_reproductive_status bigint [ref: >? reproductive_status.id]  // NULL na FK se ausente, nunca linha "N/A" (ver ADR-0008)
  id_sector bigint [ref: >? sector.id]
  registration_number text
  location_description text  // ausente -> NULL, não string "N/A" (ver ADR-0008)
  height_m double precision
}

Table reproductive_status {
  id bigint [pk]
  name text
}

Table sector {
  id bigint [pk]
  name text
}


// NOVO — atributos de nível-espécie (não variam por ocorrência/registro)

Table species_status {
  id_species int [pk, ref: - species.id]
  origin varchar  // 'Nativa', etc. Ausente -> NULL, não "N/A" (ver ADR-0008)
  is_endemic boolean
  id_conservation_status int [ref: >? conservation_status.id]
}

Table conservation_status {
  id id [pk]
  code varchar(2)  // NE, LC, VU, EN, NT, NA, códigos IUCN padrão. "NA" = valor real "Not Applicable", não placeholder de ausência (ver ADR-0005)
}

Table phytogeographic_domain {
  id id [pk]
  name varchar
}

Table species_domain {
  id_species int [ref: >? species.id]
  id_domain int [ref: >? phytogeographic_domain.id]  // ausente -> nenhuma linha inserida, nunca domínio "N/A" (ver ADR-0008)

  indexes {
    (id_species, id_domain) [pk]
  }
}

Table country {
  id id [pk]
  name varchar
}

Table state {
  id id [pk]
  name varchar
  id_country int [ref: >? country.id]
}

Table species_country {
  id_species int [ref: >? species.id]
  id_country int [ref: >? country.id]

  indexes {
    (id_species, id_country) [pk]
  }
}

Table species_state {
  id_species int [ref: >? species.id]
  id_state int [ref: >? state.id]

  indexes {
    (id_species, id_state) [pk]
  }
}

Table species_geographic_area {
  id id [pk]
  id_species int [ref: >? species.id]
  description varchar
  // Texto livre pra menções de distribuição que não decompõem em país/estado,
  // ex.: "W. Indian Ocean", "Tropical & Subtropical Asia to Pacific"
  // (fonte: Processos_de_ETL_Arboreto — Lista Completa Sps)
}


// NOVO: citações bibliográficas (Monografia Gabriel / Livro Pesquisas / JABOT)
// Não representam espécime físico, só contagem de ocorrência em fonte.

Table bibliographic_citation {
  id bigint [pk]
  id_species bigint [ref: >? species.id]
  source text  // 'Monografia Gabriel', 'Livro Pesquisas no JB', 'JABOT'
  quantity bigint
  identification_qualifier text  // ver ADR-0006
  origin_file text
  origin_sheet text
  origin_row bigint
  // Chave de idempotência: (origin_file, origin_sheet, origin_row) (ver ADR-0007)
}


// -------------------------------------------------------------------------
// STAGING / CLEAN — stubs mínimos, só pra permitir o lineage abaixo.
// dbdiagram exige que toda tabela referenciada em Dep exista como Table
// no documento. Estes NÃO são o schema completo de staging/clean (que
// vive no código real, stage_*.py/clean_*.py), só as colunas citadas
// nos blocos Dep, pra não duplicar/desatualizar schema aqui.
// -------------------------------------------------------------------------

Table stg_spp_bryophytes {
  plot varchar
  sample varchar
  identification_status varchar
  phylum varchar
  family varchar
  genus varchar
  epithet varchar
  author varchar
  life_form varchar
  substrate varchar
  remark varchar
}

Table cln_spp_bryophytes {
  phylum varchar
  family varchar
  genus varchar
  epithet varchar
  author varchar
  life_form varchar
  plot varchar
  sample varchar
  identification_status int
  substrate varchar
  remarks varchar
}

Table stg_arboretum_citations {
  family varchar
  species_raw varchar
  quantity varchar
}

Table cln_arboretum_citations {
  family varchar
  genus varchar
  epithet varchar
  infraspecific varchar
  author varchar
  identification_qualifier varchar
  quantity double precision
}

Table stg_arboretum_specimens {
  family varchar
  species_raw varchar
  registration_number varchar
  sector varchar
  location_description varchar
  reproductive_status varchar
}

Table cln_arboretum_specimens {
  family varchar
  genus varchar
  epithet varchar
  infraspecific varchar
  author varchar
  identification_qualifier varchar
  sector varchar
  location_description varchar
  reproductive_status varchar
  registration_number varchar

  note: 'confirmado contra clean_arboretum_specimens.py real — scientific_name.py atualizado para Genus sp. e autor infraespecífico; registration_number via transforms/registration_number.py'
}

Table stg_arboreto_canteiro_c {
  familia varchar
  especie varchar
  origem varchar
  grau_ameaca varchar
  dominio_fitogeografico varchar
  numeracao_lacre varchar
  localizacao_canteiro varchar
  altura_m varchar
}

Table cln_arboreto_canteiro_c {
  familia varchar
  genero varchar
  epiteto_especifico varchar
  infraespecifico varchar
  autor varchar
  origem varchar
  grau_ameaca varchar
  dominio_fitogeografico varchar
  numeracao_lacre varchar
  localizacao_canteiro varchar
  altura_m numeric

}


// =========================================================================
// LINEAGE (Dep): como o dado flui de staging até as tabelas normalizadas.
// Visão separada do schema (Ref) de propósito: aqui o objetivo é responder
// "de onde vem esse número/nome", não "como as tabelas se relacionam".
//
// Regras do dbdiagram pra Dep (importante pra quem for editar isto depois):
//   - Cada bloco `Dep nome { ... }` só pode ter edges apontando pro MESMO
//     destino, por isso os blocos abaixo são organizados por tabela-alvo,
//     não por fonte (o que deixa a reconciliação entre fontes mais visível,
//     de quebra).
//   - Um bloco não pode misturar edge de tabela inteira (A -> B) com edge
//     de coluna (A.col -> B.col), por isso os vínculos de tabela inteira
//     usam a forma solta `Dep: A -> B [note: '...']`, fora de blocos.
//
// SPP, arboreto-citações e Espécimes: refletem o pipeline como está em produção/
// validado. Canteiro C: pipeline já mapeado estruturalmente,
// nomes de tabela/coluna de staging/clean fixados de acordo com o dicionário de dados.
// =========================================================================

// --- staging -> clean (por fonte) ---

Dep: stg_spp_bryophytes -> cln_spp_bryophytes [note: 'DuckDB: fill-down de plot/sample/substrate via last_value() IGNORE NULLS; normalização de remarks; cast de identification_status pra inteiro']
Dep: stg_arboretum_citations -> cln_arboretum_citations [note: 'DuckDB: fill-down de family via last_value() IGNORE NULLS; parsing de scientific_name.py em Python registrado no DuckDB; cast de quantity; marca parse_status = total_row (família original em family_raw, soma acumulada por aba com ORDER BY explícito; ADR-0012)']
Dep: stg_arboretum_specimens -> cln_arboretum_specimens [note: 'resolve N° de Registro preferindo lacre azul quando lacre amarelo e azul coexistem (ver ADR-0009)']
Dep: stg_arboreto_canteiro_c -> cln_arboreto_canteiro_c [note: 'normaliza Origem; multivalora Domínio fitogeográfico por vírgula; Grau de Ameaça uppercase e "na" -> código IUCN NA (ADR-0005); resolve lacre azul sobre amarelo (ADR-0009); mapeia setor S2C2/S2C4 para sector; NULL nas linhas de altura com erro (183, 184, 185)']

// --- clean -> dimensões de taxonomia (agrupado por destino, mostra reconciliação entre fontes) ---

Dep phylum_lineage {
  cln_spp_bryophytes.phylum -> phylum.name

  note: 'expand: sigla M/H -> nome completo. Arboreto não popula phylum diretamente (fica NULL ADR-0004)'
}

Dep family_lineage {
  cln_spp_bryophytes.family -> family.name
  cln_arboretum_citations.family -> family.name
  cln_arboretum_specimens.family -> family.name
  cln_arboreto_canteiro_c.familia -> family.name

  note: 'get-or-create por nome; id_phylum fica NULL para toda linha de origem arboreto (ADR-0004)'
}

Dep genus_lineage {
  cln_spp_bryophytes.genus -> genus.name
  cln_arboretum_citations.genus -> genus.name
  cln_arboretum_specimens.genus -> genus.name
  cln_arboreto_canteiro_c.genero -> genus.name

  note: 'arboreto extrai genus via parsing de scientific_name.py; NULL para morfo-espécie (ADR-0003)'
}

Dep species_lineage {
  cln_spp_bryophytes.epithet -> species.epithet
  cln_arboretum_citations.epithet -> species.epithet
  cln_arboretum_specimens.epithet -> species.epithet
  cln_arboreto_canteiro_c.epiteto_especifico -> species.epithet

  note: 'get-or-create por (id_genus, epithet, infraspecific, id_author); SPP nunca tem infraspecific; morfo-espécie/gênero-só não seguem o binomial completo (ADR-0003)'
}

Dep author_lineage {
  cln_spp_bryophytes.author -> author.name
  cln_arboretum_citations.author -> author.name
  cln_arboretum_specimens.author -> author.name
  cln_arboreto_canteiro_c.autor -> author.name
}

// --- clean -> dimensões exclusivas de uma única fonte ---

Dep life_form_lineage {
  cln_spp_bryophytes.life_form -> life_form.type
}

Dep plot_lineage {
  cln_spp_bryophytes.plot -> plot.code
}

Dep identification_status_lineage {
  cln_spp_bryophytes.identification_status -> identification_status.id
}

Dep substrate_lineage {
  cln_spp_bryophytes.substrate -> substrate.name

  note: 'expand_multivalued: célula pode listar mais de um substrato'
}

Dep remark_lineage {
  cln_spp_bryophytes.remarks -> remark.comment

  note: 'split_multivalued'
}

Dep sector_lineage {
  cln_arboretum_specimens.sector -> sector.name
  cln_arboreto_canteiro_c.localizacao_canteiro -> sector.name

  note: 'SCC1-4 e S2C2/S2C4 de Canteiro C vão para o mesmo sector compartilhado com Espécimes'
}

Dep reproductive_status_lineage {
  cln_arboretum_specimens.reproductive_status -> reproductive_status.name

  note: 'ausente -> NULL na FK, nunca linha N/A criada (ADR-0008)'
}

Dep conservation_status_lineage {
  cln_arboreto_canteiro_c.grau_ameaca -> conservation_status.code

  note: 'ADR-0005: "na" mapeia pro código IUCN real NA, não NULL'
}

Dep species_status_lineage {
  cln_arboreto_canteiro_c.origem -> species_status.origin

  note: 'canonicalizar Exótico/Exótica; "na" ou ausente -> NULL, não "N/A" (ADR-0008)'
}

Dep species_domain_lineage {
  cln_arboreto_canteiro_c.dominio_fitogeografico -> species_domain.id_domain

  note: 'multi-valorado por vírgula; "na" ou ausente -> nenhuma linha em species_domain (ADR-0008)'
}

Dep occurrence_identification_qualifier_lineage {
  cln_arboretum_specimens.identification_qualifier -> occurrence.identification_qualifier
  cln_spp_bryophytes.epithet -> occurrence.identification_qualifier

  note: 'ADR-0006: Espécimes e SPP (via transforms/epithet.py) preenchem occurrence.identification_qualifier'
}

Dep occurrence_arboretum_registration_lineage {
  cln_arboretum_specimens.registration_number -> occurrence_arboretum.registration_number
  cln_arboreto_canteiro_c.numeracao_lacre -> occurrence_arboretum.registration_number

  note: 'transforms/registration_number.py: lacre azul preferido sobre lacre amarelo (RBRv...) quando ambos existem (ver ADR-0009)'
}

Dep occurrence_arboretum_height_lineage {
  cln_arboreto_canteiro_c.altura_m -> occurrence_arboretum.height_m

  note: 'linhas 183, 184 e 185 forçadas para NULL devido a erro de digitação'
}

Dep occurrence_arboretum_location_lineage {
  cln_arboretum_specimens.location_description -> occurrence_arboretum.location_description

  note: 'ausente -> NULL, não "N/A" (ADR-0008)'
}

Dep bibliographic_citation_lineage {
  cln_arboretum_citations.quantity -> bibliographic_citation.quantity
  cln_arboretum_citations.identification_qualifier -> bibliographic_citation.identification_qualifier

  note: 'chave de idempotência (origin_file, origin_sheet, origin_row) não mostrada aqui por ser metadado de linhagem, não valor de negócio (ver ADR-0007)'
}

// --- clean -> occurrence e satélites (vínculo de tabela inteira: natural key composta, não 1 coluna) ---

Dep: cln_spp_bryophytes -> occurrence [note: 'get-or-create por (origin_file=_source_file, origin_row=_source_row); basis_of_record fixo = PreservedSpecimen']
Dep: cln_arboretum_specimens -> occurrence [note: 'basis_of_record fixo = LivingSpecimen']
Dep: cln_arboreto_canteiro_c -> occurrence [note: 'basis_of_record fixo = LivingSpecimen']

Dep: occurrence -> occurrence_bryophyte [note: '1:1, colunas exclusivas de briófita']
Dep: occurrence -> occurrence_arboretum [note: '1:1, populado por Espécimes e Canteiro C']
Dep: occurrence -> occurrence_substrate
Dep: occurrence -> occurrence_remark
