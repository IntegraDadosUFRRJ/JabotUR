-- Clean dos Espécimes do arboreto, lido e preenchido por clean_arboreto_specimens.py com str.format.
--
-- Numera as linhas de staging e normaliza os campos mecânicos
--   - family: trim; " - " placeholder usado nas linhas "sem identificação" e vira NULL
--   - sector: trim; normaliza os casos onde a planilha trouxe só o
--     número solto para o formato de código igual ao resto da coluna
--   - location_description / reproductive_status: trim, string vazia vira NULL
--
-- Resumo da query (CTEs encadeadas, cada passo lê só o anterior):
--   numbered/normalized: numeração e campos mecânicos acima;
--   parsed:   nome científico e número de registro pelos parsers Python, registrados
--             como funções registradas no DuckDB que devolvem STRUCT;
--   marked:   is_morphospecies;
--   SELECT final: morfo-espécie usa o nome normalizado como epíteto e fica sem gênero;
--             morfo-espécie e unparseable não reconciliam entre fontes (ADR-0003);
--             needs_review para status de nome fora da lista aceita ou registro
--             unparseable. Status NULL não é morfo-espécie nem unparseable (coalesce
--             com FALSE) e fica fora da lista aceita (coalesce com TRUE): nenhuma
--             flag sai NULL.
--
-- Placeholders, preenchidos pelo Python:
--   name_function / registration_function: nomes das funções registradas no DuckDB para os parsers;
--   status_* / registration_status_unparseable: valores de status, já como literais SQL.
-- Como o arquivo passa por str.format, uma chave literal (ex.: quantificador de regex)
-- precisa ser escrita dobrada.
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY CAST(_source_row AS INTEGER)) AS rn, * FROM df_input
),
normalized AS (
SELECT
    rn,
    _source_file,
    _source_sheet,
    _source_row,
    CASE
        WHEN trim(coalesce(family, '')) IN ('', '-') THEN NULL
        ELSE regexp_replace(trim(coalesce(family, '')), '^\s+|\s+$', '', 'g')
    END AS family,
    trim(coalesce(species_raw, '')) AS species_input,
    trim(coalesce(registration_number, '')) AS registration_number_input,
    CASE
        WHEN trim(coalesce(sector, '')) = '' THEN NULL
        WHEN regexp_matches(trim(coalesce(sector, '')), '^[0-9]+\.0$')
            THEN regexp_replace(trim(sector), '\.0$', '')
        ELSE trim(coalesce(sector, ''))
    END AS sector,
    CASE
        WHEN trim(coalesce(location_description, '')) = '' THEN NULL
        ELSE trim(coalesce(location_description, ''))
    END AS location_description,
    CASE
        WHEN trim(coalesce(reproductive_status, '')) = '' THEN NULL
        ELSE trim(coalesce(reproductive_status, ''))
    END AS reproductive_status
FROM numbered
),
parsed AS (
    SELECT
        *,
        {name_function}(species_input) AS name,
        {registration_function}(registration_number_input) AS registration
    FROM normalized
),
marked AS (
    SELECT *, coalesce(name.parse_status = {status_morphospecies}, FALSE) AS is_morphospecies
    FROM parsed
)
SELECT
    rn,
    _source_file,
    _source_sheet,
    _source_row,
    family,
    CASE WHEN is_morphospecies THEN NULL ELSE name.genus END AS genus,
    CASE WHEN is_morphospecies THEN name.name_normalized ELSE name.epithet END
        AS epithet,
    name.infraspecific AS infraspecific,
    name.author AS author,
    name.identification_qualifier AS identification_qualifier,
    name.name_raw AS name_raw,
    name.name_normalized AS name_normalized,
    name.parse_status AS parse_status,
    sector,
    location_description,
    reproductive_status,
    registration.registration_number AS registration_number,
    registration.registration_number_raw AS registration_number_raw,
    registration.registration_status AS registration_status,
    NOT (
        is_morphospecies
        OR coalesce(name.parse_status = {status_unparseable}, FALSE)
    ) AS reconcile_across_sources,
    coalesce(
        name.parse_status NOT IN ({status_ok}, {status_genus_only}, {status_morphospecies}),
        TRUE
    )
    OR coalesce(
        registration.registration_status = {registration_status_unparseable}, FALSE
    ) AS needs_review
FROM marked
ORDER BY rn
