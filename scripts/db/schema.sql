-- Esquema das tabelas finais do JabotUR, aplicado por init_postgres().
-- Idempotente: só CREATE ... IF NOT EXISTS, sem DROP. Não migra banco antigo.
-- Sem chaves estrangeiras por enquanto (entram depois da suíte de invariantes).
-- Tabelas stg_* e cln_* ficam de fora: write_dataframe_to_postgres(mode="replace") as recria.

-- Núcleo taxonômico
CREATE TABLE IF NOT EXISTS filo (
    id bigint PRIMARY KEY,
    nome text
);

CREATE TABLE IF NOT EXISTS familia (
    id bigint PRIMARY KEY,
    id_filo bigint,
    nome text
);

CREATE TABLE IF NOT EXISTS genero (
    id bigint PRIMARY KEY,
    id_familia bigint,
    nome text
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
    infraespecifico text
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
    identification_qualifier text
);

CREATE UNIQUE INDEX IF NOT EXISTS occurrence_uniq_origin
ON occurrence (origin_file, COALESCE(origin_sheet, ''), origin_row);

CREATE TABLE IF NOT EXISTS occurrence_bryophyte (
    id bigint PRIMARY KEY,
    id_forma bigint,
    id_identificacao bigint,
    id_parcela bigint,
    amostra bigint
);

CREATE TABLE IF NOT EXISTS occurrence_arboretum (
    id bigint PRIMARY KEY,
    id_reproductive_status bigint,
    id_sector bigint,
    registration_number text,
    location_description text,
    height_m double precision
);

-- Associativas (sem id; PK composta)
CREATE TABLE IF NOT EXISTS coleta_substrato (
    id_briofita bigint,
    id_substrato bigint,
    PRIMARY KEY (id_briofita, id_substrato)
);

CREATE TABLE IF NOT EXISTS coleta_observacao (
    id_briofita bigint,
    id_observacao bigint,
    PRIMARY KEY (id_briofita, id_observacao)
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
    origin_row bigint
);
