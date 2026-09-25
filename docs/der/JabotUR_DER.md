// =========================================================================
// JabotUR — DER consolidado
// Convenção: tabelas/colunas já existentes permanecem em português (não
// retroativo). Tabelas e colunas NOVAS a partir desta revisão seguem
// nomenclatura em inglês, por padronização internacional (Darwin Core-like)
// e para evitar problemas de acentuação/unicode em identificadores de banco.
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
// =========================================================================


// -------------------------------------------------------------------------
// ORIGINAL — Briófitas (sem alterações estruturais, exceto onde marcado)
// -------------------------------------------------------------------------

Table filo {
  id id [pk]
  nome varchar
}

Table familia {
  id id [pk]
  id_filo int [ref: >? filo.id]  // nullable para famílias de origem arboreto(ver ADR-0004)
  nome varchar
}

Table genero {
  id id [pk]
  id_familia int [ref: >? familia.id]
  nome varchar
}

Table epiteto_especifico {
  id id [pk]
  id_genero int [ref: >? genero.id]  // NULL para morfo-espécie(ver ADR-0003)
  id_autor int [ref: >? autor.id]
  nome varchar  // NULL para "gênero só"(ver ADR-0003)
  infraespecifico varchar  // nullable, ex.: "var. cebil". Unicidade: ver ADR-0002 (índices parciais, migrations/001)
}

Table autor {
  id id [pk]
  nome varchar
}

Table identificacao {
  id id [pk]
  descricao varchar
}

Table forma_vida {
  id id [pk]
  tipo varchar
}

Table parcela {
  id id [pk]
  codigo varchar
  coordenada varchar
}

Table observacao {
  id id [pk]
  comentario varchar
}

Table substrato {
  id id [pk]
  nome varchar
  sigla varchar(3)
}

// coleta_observacao / coleta_substrato: nomes e colunas mantidos como estão
// (não retroativo). Alvo da referência é occurrence, não a antiga coleta
// (ver ADR-0001) hoje só populado para occurrences de briófita.
Table coleta_observacao {
  id_briofita int [ref: > occurrence.id]
  id_observacao int [ref: > observacao.id]

  indexes {
    (id_briofita, id_observacao) [pk]
  }
}

Table coleta_substrato {
  id_briofita int [ref: > occurrence.id]
  id_substrato int [ref: > substrato.id]

  indexes {
    (id_briofita, id_substrato) [pk]
  }
}


// NOVO: registro de ocorrência (substitui a antiga tabela `coleta`)
// Padrão super-tipo/sub-tipo, ver ADR-0001 para contexto e alternativas.

Table occurrence {
  id id [pk]
  id_species int [ref: >? epiteto_especifico.id]
  basis_of_record varchar  // 'PreservedSpecimen' (SPP), 'LivingSpecimen' (arboreto)
  identification_qualifier varchar  // "cf."/"aff."(ver ADR-0006)
  origin_file varchar
  origin_sheet varchar  // nullable: NULL pras linhas antigas do SPP (1 arquivo = 1 aba lá); obrigatório a partir do arboreto,mesmo motivo do ADR-0007
  origin_row varchar
}

Table occurrence_bryophyte {
  id id [pk, ref: - occurrence.id]
  id_forma int [ref: >? forma_vida.id]
  id_identificacao int [ref: >? identificacao.id]
  id_parcela int [ref: >? parcela.id]
  amostra int
}

Table occurrence_arboretum {
  id id [pk, ref: - occurrence.id]
  id_reproductive_status int [ref: >? reproductive_status.id]  // NULL na FK se ausente, nunca linha "N/A"(ver ADR-0008)
  id_sector int [ref: >? sector.id]
  registration_number varchar
  location_description varchar  // ausente -> NULL, não string "N/A"(ver ADR-0008)
  height_m numeric
}

Table reproductive_status {
  id id [pk]
  name varchar
}

Table sector {
  id id [pk]
  name varchar
}


// NOVO — atributos de nível-espécie (não variam por ocorrência/registro)

Table species_status {
  id_species int [pk, ref: - epiteto_especifico.id]
  origin varchar  // 'Nativa', etc. Ausente -> NULL, não "N/A" (ver ADR-0008)
  is_endemic boolean
  id_conservation_status int [ref: >? conservation_status.id]
}

Table conservation_status {
  id id [pk]
  code varchar(2)  // NE, LC, VU, EN, NT, NA, códigos IUCN padrão. "NA" = valor real "Not Applicable", não placeholder de ausência(ver ADR-0005)
}

Table phytogeographic_domain {
  id id [pk]
  name varchar
}

Table species_domain {
  id_species int [ref: >? epiteto_especifico.id]
  id_domain int [ref: >? phytogeographic_domain.id]  // ausente -> nenhuma linha inserida, nunca domínio "N/A"(ver ADR-0008)

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
  id_species int [ref: >? epiteto_especifico.id]
  id_country int [ref: >? country.id]

  indexes {
    (id_species, id_country) [pk]
  }
}

Table species_state {
  id_species int [ref: >? epiteto_especifico.id]
  id_state int [ref: >? state.id]

  indexes {
    (id_species, id_state) [pk]
  }
}

Table species_geographic_area {
  id id [pk]
  id_species int [ref: >? epiteto_especifico.id]
  description varchar
  // Texto livre pra menções de distribuição que não decompõem em país/estado,
  // ex.: "W. Indian Ocean", "Tropical & Subtropical Asia to Pacific"
  // (fonte: Processos_de_ETL_Arboreto — Lista Completa Sps)
}


// NOVO: citações bibliográficas (Monografia Gabriel / Livro Pesquisas / JABOT)
// Não representam espécime físico, só contagem de ocorrência em fonte.

Table bibliographic_citation {
  id id [pk]
  id_species int [ref: >? epiteto_especifico.id]
  source varchar  // 'Monografia Gabriel', 'Livro Pesquisas no JB', 'JABOT'
  quantity int
  identification_qualifier varchar  // ver ADR-0006
  origin_file varchar
  origin_sheet varchar
  origin_row varchar
  // Chave de idempotência: (origin_file, origin_sheet, origin_row) (ver ADR-0007)
}


// -------------------------------------------------------------------------
// STAGING / CLEAN — stubs mínimos, só pra permitir o lineage abaixo.
// dbdiagram exige que toda tabela referenciada em Dep exista como Table
// no documento. Estes NÃO são o schema completo de staging/clean (que
// vive no código real, stage_*.py/clean_*.py), só as colunas citadas
// nos blocos Dep, pra não duplicar/desatualizar schema aqui.
// -------------------------------------------------------------------------

Table stg_spp_briofitas {
  parcela varchar
  amostra varchar
  identificacao varchar
  filo varchar
  familia varchar
  genero varchar
  epiteto_especifico varchar
  autor varchar
  forma_vida varchar
  substrato varchar
  observacao varchar
}

Table cln_spp_briofitas {
  filo varchar
  familia varchar
  genero varchar
  especie varchar
  autor varchar
  forma_vida varchar
  parcela varchar
  status_identificacao varchar
  substrato varchar
  observacoes varchar
}

Table stg_arboreto_citations {
  familia varchar
  especie varchar
  quantidade varchar
}

Table cln_arboreto_citations {
  familia varchar
  genero varchar
  epiteto_especifico varchar
  infraespecifico varchar
  autor varchar
  identification_qualifier varchar
  quantidade varchar
}

Table stg_arboreto_specimens {
  familia varchar
  especie varchar
  numero_registro varchar
  setor varchar
  descricao_localizacao varchar
  estado_reprodutivo varchar
}

Table cln_arboreto_specimens {
  familia varchar
  genero varchar
  epiteto_especifico varchar
  infraespecifico varchar
  autor varchar
  identification_qualifier varchar
  setor varchar
  descricao_localizacao varchar
  estado_reprodutivo varchar
  registration_number varchar

  note: 'confirmado contra clean_arboreto_specimens.py real — nome_cientifico.py reaproveitado sem modificação; registration_number via transforms/registration_number.py'
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

Dep: stg_spp_briofitas -> cln_spp_briofitas [note: 'DuckDB: fill-down de parcela/amostra/substrato/forma_vida via last_value() IGNORE NULLS; normalização de observações; cast de status_identificacao pra inteiro']
Dep: stg_arboreto_citations -> cln_arboreto_citations [note: 'DuckDB: fill-down de familia via last_value() IGNORE NULLS; parsing de nome_cientifico.py em Python puro; cast de quantidade']
Dep: stg_arboreto_specimens -> cln_arboreto_specimens [note: 'fill-down de familia; resolve N° de Registro preferindo lacre azul quando lacre amarelo e azul coexistem (ver ADR-0009)']
Dep: stg_arboreto_canteiro_c -> cln_arboreto_canteiro_c [note: 'normaliza Origem; multivalora Domínio fitogeográfico por vírgula; Grau de Ameaça uppercase e "na" -> código IUCN NA (ADR-0005); resolve lacre azul sobre amarelo (ADR-0009); mapeia setor S2C2/S2C4 para sector; NULL nas linhas de altura com erro (183, 184, 185)']

// --- clean -> dimensões de taxonomia (agrupado por destino, mostra reconciliação entre fontes) ---

Dep filo_lineage {
  cln_spp_briofitas.filo -> filo.nome

  note: 'expand: sigla M/H -> nome completo. Arboreto não popula filo diretamente (fica NULL ADR-0004)'
}

Dep familia_lineage {
  cln_spp_briofitas.familia -> familia.nome
  cln_arboreto_citations.familia -> familia.nome
  cln_arboreto_specimens.familia -> familia.nome
  cln_arboreto_canteiro_c.familia -> familia.nome

  note: 'get-or-create por nome; id_filo fica NULL para toda linha de origem arboreto(ADR-0004)'
}

Dep genero_lineage {
  cln_spp_briofitas.genero -> genero.nome
  cln_arboreto_citations.genero -> genero.nome
  cln_arboreto_specimens.genero -> genero.nome
  cln_arboreto_canteiro_c.genero -> genero.nome

  note: 'arboreto extrai genero via parsing de nome_cientifico.py; NULL para morfo-espécie(ADR-0003)'
}

Dep epiteto_especifico_lineage {
  cln_spp_briofitas.especie -> epiteto_especifico.nome
  cln_arboreto_citations.epiteto_especifico -> epiteto_especifico.nome
  cln_arboreto_specimens.epiteto_especifico -> epiteto_especifico.nome
  cln_arboreto_canteiro_c.epiteto_especifico -> epiteto_especifico.nome

  note: 'get-or-create por (id_genero, nome, infraespecifico, id_autor); SPP nunca tem infraespecifico; morfo-espécie/gênero-só não seguem o binomial completo(ADR-0003)'
}

Dep autor_lineage {
  cln_spp_briofitas.autor -> autor.nome
  cln_arboreto_citations.autor -> autor.nome
  cln_arboreto_specimens.autor -> autor.nome
  cln_arboreto_canteiro_c.autor -> autor.nome
}

// --- clean -> dimensões exclusivas de uma única fonte ---

Dep forma_vida_lineage {
  cln_spp_briofitas.forma_vida -> forma_vida.tipo
}

Dep parcela_lineage {
  cln_spp_briofitas.parcela -> parcela.codigo
}

Dep identificacao_lineage {
  cln_spp_briofitas.status_identificacao -> identificacao.id
}

Dep substrato_lineage {
  cln_spp_briofitas.substrato -> substrato.nome

  note: 'expand_multivalued: célula pode listar mais de um substrato'
}

Dep observacao_lineage {
  cln_spp_briofitas.observacoes -> observacao.comentario

  note: 'split_multivalued'
}

Dep sector_lineage {
  cln_arboreto_specimens.setor -> sector.name
  cln_arboreto_canteiro_c.localizacao_canteiro -> sector.name

  note: 'SCC1-4 e S2C2/S2C4 de Canteiro C vão para o mesmo sector compartilhado com Espécimes'
}

Dep reproductive_status_lineage {
  cln_arboreto_specimens.estado_reprodutivo -> reproductive_status.name

  note: 'ausente -> NULL na FK, nunca linha N/A criada(ADR-0008)'
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
  cln_arboreto_specimens.identification_qualifier -> occurrence.identification_qualifier

  note: 'ADR-0006: Espécimes é a 1ª fonte occurrence_arboretum-based com qualificador de identificação real (não mais hipotético)'
}

Dep occurrence_arboretum_registration_lineage {
  cln_arboreto_specimens.registration_number -> occurrence_arboretum.registration_number
  cln_arboreto_canteiro_c.numeracao_lacre -> occurrence_arboretum.registration_number

  note: 'transforms/registration_number.py: lacre azul preferido sobre lacre amarelo (RBRv...) quando ambos existem (ver ADR-0009)'
}

Dep occurrence_arboretum_height_lineage {
  cln_arboreto_canteiro_c.altura_m -> occurrence_arboretum.height_m

  note: 'linhas 183, 184 e 185 forçadas para NULL devido a erro de digitação'
}

Dep occurrence_arboretum_location_lineage {
  cln_arboreto_specimens.descricao_localizacao -> occurrence_arboretum.location_description

  note: 'ausente -> NULL, não "N/A"(ADR-0008)'
}

Dep bibliographic_citation_lineage {
  cln_arboreto_citations.quantidade -> bibliographic_citation.quantity
  cln_arboreto_citations.identification_qualifier -> bibliographic_citation.identification_qualifier

  note: 'chave de idempotência (origin_file, origin_sheet, origin_row) não mostrada aqui por ser metadado de linhagem, não valor de negócio(ver ADR-0007)'
}

// --- clean -> occurrence e satélites (vínculo de tabela inteira: natural key composta, não 1 coluna) ---

Dep: cln_spp_briofitas -> occurrence [note: 'get-or-create por (origin_file=_source_file, origin_row=_source_row); basis_of_record fixo = PreservedSpecimen']
Dep: cln_arboreto_specimens -> occurrence [note: 'basis_of_record fixo = LivingSpecimen']
Dep: cln_arboreto_canteiro_c -> occurrence [note: 'basis_of_record fixo = LivingSpecimen']

Dep: occurrence -> occurrence_bryophyte [note: '1:1, colunas exclusivas de briófita']
Dep: occurrence -> occurrence_arboretum [note: '1:1, populado por Espécimes e Canteiro C']
Dep: occurrence -> coleta_substrato
Dep: occurrence -> coleta_observacao
