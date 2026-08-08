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

Table coleta_observacao {
  id_briofita int [ref: > coleta.id]
  id_observacao int [ref: > observacao.id]

  indexes {
    (id_briofita, id_observacao) [pk]
  }
}

Table observacao {
  id id [pk]
  comentario varchar
}

Table coleta_substrato {
  id_briofita int [ref: > coleta.id]
  id_substrato int [ref: > substrato.id]

  indexes {
    (id_briofita, id_substrato) [pk]
  }
}

Table substrato {
  id id [pk]
  nome varchar
  sigla varchar(3)
}

Table coleta {
  id id [pk]
  id_especie int [ref: > epiteto_especifico.id] 
  id_forma int [ref: > forma_vida.id]
  id_identificacao int [ref: > identificacao.id]
  id_parcela int [ref: > parcela.id]
  origin_file varchar
  origin_row varchar
  amostra int
}
