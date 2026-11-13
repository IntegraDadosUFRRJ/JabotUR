-- Esquema das tabelas finais do JabotUR, aplicado por init_postgres().
-- Idempotente: só CREATE ... IF NOT EXISTS, sem DROP. Não migra banco antigo.
-- Chaves estrangeiras sem ON DELETE CASCADE: uma violação é achado a investigar.
-- Banco criado antes delas não ganha as FKs aqui; é preciso recriar o esquema.
-- Tabelas stg_* e cln_* ficam de fora: write_dataframe_to_postgres(mode="replace") as recria.

-- Núcleo taxonômico
CREATE TABLE IF NOT EXISTS phylum (
    id bigint PRIMARY KEY,
    name text
);

CREATE TABLE IF NOT EXISTS family (
    id bigint PRIMARY KEY,
    id_phylum bigint,
    name text,
    FOREIGN KEY (id_phylum) REFERENCES phylum (id)
);

CREATE TABLE IF NOT EXISTS genus (
    id bigint PRIMARY KEY,
    id_family bigint,
    name text,
    FOREIGN KEY (id_family) REFERENCES family (id)
);

CREATE TABLE IF NOT EXISTS author (
    id bigint PRIMARY KEY,
    name text
);

CREATE TABLE IF NOT EXISTS species (
    id bigint PRIMARY KEY,
    id_genus bigint,
    id_author bigint,
    epithet text,
    infraspecific text,
    FOREIGN KEY (id_genus) REFERENCES genus (id),
    FOREIGN KEY (id_author) REFERENCES author (id)
);

-- Índices únicos parciais por causa do infraspecific NULL (ADR-0002)
CREATE UNIQUE INDEX IF NOT EXISTS species_uniq_with_infra
ON species (id_genus, epithet, infraspecific, id_author)
WHERE infraspecific IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS species_uniq_without_infra
ON species (id_genus, epithet, id_author)
WHERE infraspecific IS NULL;

-- Dimensões das fontes
CREATE TABLE IF NOT EXISTS life_form (
    id bigint PRIMARY KEY,
    type text
);

CREATE TABLE IF NOT EXISTS plot (
    id bigint PRIMARY KEY,
    code text,
    coordinate text
);

CREATE TABLE IF NOT EXISTS identification_status (
    id bigint PRIMARY KEY,
    description text
);

CREATE TABLE IF NOT EXISTS substrate (
    id bigint PRIMARY KEY,
    name text,
    abbreviation text
);

CREATE TABLE IF NOT EXISTS remark (
    id bigint PRIMARY KEY,
    comment text
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
    FOREIGN KEY (id_species) REFERENCES species (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS occurrence_uniq_origin
ON occurrence (origin_file, COALESCE(origin_sheet, ''), origin_row);

CREATE TABLE IF NOT EXISTS occurrence_bryophyte (
    id bigint PRIMARY KEY,
    id_life_form bigint,
    id_identification_status bigint,
    id_plot bigint,
    sample bigint,
    FOREIGN KEY (id) REFERENCES occurrence (id),
    FOREIGN KEY (id_life_form) REFERENCES life_form (id),
    FOREIGN KEY (id_identification_status) REFERENCES identification_status (id),
    FOREIGN KEY (id_plot) REFERENCES plot (id)
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
CREATE TABLE IF NOT EXISTS occurrence_substrate (
    id_occurrence bigint,
    id_substrate bigint,
    PRIMARY KEY (id_occurrence, id_substrate),
    FOREIGN KEY (id_occurrence) REFERENCES occurrence_bryophyte (id),
    FOREIGN KEY (id_substrate) REFERENCES substrate (id)
);

CREATE TABLE IF NOT EXISTS occurrence_remark (
    id_occurrence bigint,
    id_remark bigint,
    PRIMARY KEY (id_occurrence, id_remark),
    FOREIGN KEY (id_occurrence) REFERENCES occurrence_bryophyte (id),
    FOREIGN KEY (id_remark) REFERENCES remark (id)
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
    FOREIGN KEY (id_species) REFERENCES species (id)
);
