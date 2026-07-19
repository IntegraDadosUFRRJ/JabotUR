Table taxon_voucher {
  id id [pk]
  id_voucher int [ref: > voucher.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_referencia {
  id id [pk]
  id_referencia int [ref: > referencia.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_formasdevida {
  id id [pk]
  id_formasdevida int [ref: > formas_de_vida.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_substratos {
  id id [pk]
  id_substratos int [ref: > substratos.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_distr_regional {
  id id [pk]
  id_distr_regional int [ref: > distr_regional.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_distr_uf {
  id id [pk]
  id_distr_uf int [ref: > distr_uf.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_dom_fitogeografico {
  id id [pk]
  id_dom_fitogeografico int [ref: > dom_fitogeografico.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_vegetacao {
  id id [pk]
  id_vegetacao int [ref: > vegetacao.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_tem_como_sinonimo {
  id id [pk]
  id_tem_como_sionimo int [ref: > tem_como_sinonimo.id]
  id_taxon int [ref: > taxon.id]
}

Table taxon_e_sinonimo_de {
  id id [pk]
  id_e_sinonimo_de int [ref: > e_sinonimo_de.id]
  id_taxon int [ref: > taxon.id]
}

Table rank {
  id id [pk]
  tipo varchar
}

Table filo {
  id id [pk]
  nome varchar
  sigla varchar(1)
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

Table especie {
  id id [pk]
  id_genero int [ref: > genero.id]
  nome varchar
}

Table autor {
  id id [pk]
  nome varchar
}

Table subespecie {
  id id [primary key]
  id_especie int [ref: > especie.id]
  nome varchar
}

Table variedade {
  id id [primary key]
  id_especie int [ref: > especie.id]
  nome varchar
}

Table obra_original {
  id id [pk]
  id_especie int [ref: > especie.id]
  obra varchar
}

Table origem {
  id id [pk]
  descricao varchar
}

Table voucher {
  id id [pk]
  titulo varchar
}

Table referencia {
  id id [pk]
  titulo varchar 
  tipo varchar
}

Table formas_de_vida {
  id id [pk]
  tipo varchar
}

Table substratos {
  id id [pk]
  nome varchar
}

Table distr_regional {
  id id [pk]
  regiao varchar
}

Table distr_uf {
  id id [pk]
  estado varchar
  sigla varchar(2)
}

Table dom_fitogeografico {
  id id [pk]
  dominio varchar
}

Table vegetacao {
  id id [pk]
  tipo varchar
}

Table tem_como_sinonimo {
  id id [pk]
  tipo varchar
  sinonimo varchar
}

Table e_sinonimo_de {
  id id [pk]
  tipo varchar
  sinonimo varchar
}

Table usuario {
  id id [pk]
  usuario varchar
}

Table taxon {
  id id [pk]
  id_origem int [ref: > origem.id]
  id_rank int [ref: > rank.id]
  id_especie int [ref: > especie.id]
  id_subespecie int [ref: > subespecie.id]
  id_variedade int [ref: > variedade.id]
  id_autor int [ref: > autor.id]
  autoria int [ref: > usuario.id]
  usuario_update int [ref: > usuario.id]
  registro varchar 
  status varchar
  origem varchar
  endemica boolean
  ocorre_no_brasil boolean
  data_update datetime
  citacao varchar
}