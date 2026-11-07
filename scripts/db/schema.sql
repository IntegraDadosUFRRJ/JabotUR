-- Esquema das tabelas finais do JabotUR, aplicado por init_postgres().
-- Idempotente: só CREATE ... IF NOT EXISTS, sem DROP. Não migra banco antigo.
-- Chaves estrangeiras sem ON DELETE CASCADE: uma violação é achado a investigar.
-- Banco criado antes delas não ganha as FKs aqui; é preciso recriar o esquema.
-- Tabelas stg_* e cln_* ficam de fora: write_dataframe_to_postgres(mode="replace") as recria.

-- Núcleo taxonômico
CREATE TABLE IF NOT EXISTS filo (
    id bigint PRIMARY KEY,
    nome text
);

CREATE TABLE IF NOT EXISTS familia (
    id bigint PRIMARY KEY,
    id_filo bigint,
    nome text,
    FOREIGN KEY (id_filo) REFERENCES filo (id)
);

CREATE TABLE IF NOT EXISTS genero (
    id bigint PRIMARY KEY,
    id_familia bigint,
    nome text,
    FOREIGN KEY (id_familia) REFERENCES familia (id)
);

CREATE TABLE IF NOT EXISTS autor (
    id bigint PRIMARY KEY,
    nome text
);

CREATE TABLE IF NOT EXISTS epiteto_especifico (
    id bigint PRIMARY KEY,
    id_genero bigint,
    id_autor bigint,
    nome text,
    infraespecifico text,
    FOREIGN KEY (id_genero) REFERENCES genero (id),
    FOREIGN KEY (id_autor) REFERENCES autor (id)
);

-- Índices únicos parciais por causa do infraespecifico NULL (ADR-0002)
CREATE UNIQUE INDEX IF NOT EXISTS epiteto_uniq_com_infra
ON epiteto_especifico (id_genero, nome, infraespecifico, id_autor)
WHERE infraespecifico IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS epiteto_uniq_sem_infra
ON epiteto_especifico (id_genero, nome, id_autor)
WHERE infraespecifico IS NULL;

-- Dimensões das fontes
CREATE TABLE IF NOT EXISTS forma_vida (
    id bigint PRIMARY KEY,
    tipo text
);

CREATE TABLE IF NOT EXISTS parcela (
    id bigint PRIMARY KEY,
    codigo text,
    coordenada text
);

CREATE TABLE IF NOT EXISTS identificacao (
    id bigint PRIMARY KEY,
    descricao text
);

CREATE TABLE IF NOT EXISTS substrato (
    id bigint PRIMARY KEY,
    nome text,
    sigla text
);

CREATE TABLE IF NOT EXISTS observacao (
    id bigint PRIMARY KEY,
    comentario text
);

CREATE TABLE IF NOT EXISTS sector (
    id bigint PRIMARY KEY,
    name text
);

CREATE TABLE IF NOT EXISTS reproductive_status (
    id bigint PRIMARY KEY,
    name text
);

-- Ocorrência (base) e satélites
-- id_species aceita NULL: ocorrência de Espécimes sem identificação (decisão de 30/10)
CREATE TABLE IF NOT EXISTS occurrence (
    id bigint PRIMARY KEY,
    id_species bigint,
    basis_of_record text,
    origin_file text,
    origin_row bigint,
    origin_sheet text,
    identification_qualifier text,
    FOREIGN KEY (id_species) REFERENCES epiteto_especifico (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS occurrence_uniq_origin
ON occurrence (origin_file, COALESCE(origin_sheet, ''), origin_row);

CREATE TABLE IF NOT EXISTS occurrence_bryophyte (
    id bigint PRIMARY KEY,
    id_forma bigint,
    id_identificacao bigint,
    id_parcela bigint,
    amostra bigint,
    FOREIGN KEY (id) REFERENCES occurrence (id),
    FOREIGN KEY (id_forma) REFERENCES forma_vida (id),
    FOREIGN KEY (id_identificacao) REFERENCES identificacao (id),
    FOREIGN KEY (id_parcela) REFERENCES parcela (id)
);

CREATE TABLE IF NOT EXISTS occurrence_arboretum (
    id bigint PRIMARY KEY,
    id_reproductive_status bigint,
    id_sector bigint,
    registration_number text,
    location_description text,
    height_m double precision,
    FOREIGN KEY (id) REFERENCES occurrence (id),
    FOREIGN KEY (id_reproductive_status) REFERENCES reproductive_status (id),
    FOREIGN KEY (id_sector) REFERENCES sector (id)
);

-- Associativas (sem id; PK composta)
CREATE TABLE IF NOT EXISTS coleta_substrato (
    id_briofita bigint,
    id_substrato bigint,
    PRIMARY KEY (id_briofita, id_substrato),
    FOREIGN KEY (id_briofita) REFERENCES occurrence_bryophyte (id),
    FOREIGN KEY (id_substrato) REFERENCES substrato (id)
);

CREATE TABLE IF NOT EXISTS coleta_observacao (
    id_briofita bigint,
    id_observacao bigint,
    PRIMARY KEY (id_briofita, id_observacao),
    FOREIGN KEY (id_briofita) REFERENCES occurrence_bryophyte (id),
    FOREIGN KEY (id_observacao) REFERENCES observacao (id)
);

-- Citações bibliográficas
CREATE TABLE IF NOT EXISTS bibliographic_citation (
    id bigint PRIMARY KEY,
    id_species bigint,
    source text,
    quantity bigint,
    identification_qualifier text,
    origin_file text,
    origin_sheet text,
    origin_row bigint,
    FOREIGN KEY (id_species) REFERENCES epiteto_especifico (id)
);
