// JabotUR: DER 
// Tabelas e colunas já existentes permanecem em português, enquanto as tabelas 
// e colunas novas possuirão nomenclatura em inglês, por padronização internacional 
// e para evitar problemas de acentuação/unicode em identificadores de banco


// Tabelas originais(Briófitas-SPP) 
Table filo {
  id id [pk]
  nome varchar
}

Table familia {
  id id [pk]
  id_filo int [ref: > filo.id]
  nome varchar
}

Table genero {
  id id [pk]
  id_familia int [ref: > familia.id]
  nome varchar
}

Table epiteto_especifico {
  id id [pk]
  id_genero int [ref: > genero.id]
  id_autor int [ref: > autor.id]
  nome varchar
  infraespecifico varchar  // Nullable. Ex.: "var. cebil". Preencher só quando existir no nome científico de origem.
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

// Registro de ocorrência (substitui a antiga tabela "coleta")
// Motivo: mais extensível — uma fonte extra só adiciona uma
// nova occurrence_<fonte>, sem repetir as colunas comuns.

Table occurrence {
  id id [pk]
  id_species int [ref: > epiteto_especifico.id]
  basis_of_record varchar  
  origin_file varchar
  origin_row varchar
}

Table occurrence_bryophyte {
  id id [pk, ref: - occurrence.id]
  id_forma int [ref: > forma_vida.id]
  id_identificacao int [ref: > identificacao.id]
  id_parcela int [ref: > parcela.id]
  amostra int
}

Table occurrence_arboretum {
  id id [pk, ref: - occurrence.id]
  id_reproductive_status int [ref: > reproductive_status.id]
  id_sector int [ref: > sector.id]
  registration_number varchar
  location_description varchar  
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

// === Atributos de nível-espécie, esses não irão variar por ocorrência e/ou registro ===

Table species_status {
  id_species int [pk, ref: - epiteto_especifico.id]
  origin varchar         
  is_endemic boolean
  id_conservation_status int [ref: > conservation_status.id]
}

Table conservation_status {
  id id [pk]
  code varchar(2)
}

Table phytogeographic_domain {
  id id [pk]
  name varchar
}

Table species_domain {
  id_species int [ref: > epiteto_especifico.id]
  id_domain int [ref: > phytogeographic_domain.id]
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
  id_country int [ref: > country.id]
}

Table species_country {
  id_species int [ref: > epiteto_especifico.id]
  id_country int [ref: > country.id]

  indexes {
    (id_species, id_country) [pk]
  }
}

Table species_state {
  id_species int [ref: > epiteto_especifico.id]
  id_state int [ref: > state.id]

  indexes {
    (id_species, id_state) [pk]
  }
}

Table species_geographic_area {
  id id [pk]
  id_species int [ref: > epiteto_especifico.id]
  description varchar
  // texto livre para menções de "distribuição geográfica" que não decompõem em país/estado
  // ex.: "W. Indian Ocean", "Kênia até Moçambique", "Tropical & Subtropical Asia to Pacific"
}

// Citações bibliográficas (Monografia Gabriel / Livro Pesquisas / JABOT)
// Não representam espécime físico, só a contagem de registros 
Table bibliographic_citation {
  id id [pk]
  id_species int [ref: > epiteto_especifico.id]
  source varchar   
  quantity int
}