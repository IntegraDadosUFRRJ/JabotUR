-- Clean dos Espécimes do arboreto, lido e preenchido por clean_arboreto_specimens.py com str.format.
--
-- Numera as linhas de staging e normaliza os campos mecânicos
--   - familia: trim; " - " placeholder usado nas linhas "sem identificação" e vira NULL
--   - setor: trim; normaliza os casos onde a planilha trouxe só o
--     número solto para o formato de código igual ao resto da coluna
--   - descricao_localizacao / estado_reprodutivo: trim, string vazia vira NULL
--
-- Resumo da query (CTEs encadeadas, cada passo lê só o anterior):
--   numbered/normalized: numeração e campos mecânicos acima;
--   parsed:   nome científico e número de registro pelos parsers Python, registrados
--             como funções registradas no DuckDB que devolvem STRUCT;
--   marked:   is_morphospecies;
--   SELECT final: morfo-espécie usa o nome normalizado como epíteto e fica sem gênero;
--             morfo-espécie e unparseable não reconciliam entre fontes (ADR-0003);
--             needs_review para status de nome fora da lista aceita ou registro
--             unparseable. As comparações com status tratam NULL como "não é", como
--             fazia o pandas.
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
        WHEN trim(coalesce(familia, '')) IN ('', '-') THEN NULL
        ELSE regexp_replace(trim(coalesce(familia, '')), '^\s+|\s+$', '', 'g')
    END AS familia,
    trim(coalesce(especie, '')) AS especie_raw,
    trim(coalesce(numero_registro, '')) AS numero_registro_raw,
    CASE
        WHEN trim(coalesce(setor, '')) = '' THEN NULL
        WHEN regexp_matches(trim(coalesce(setor, '')), '^[0-9]+\.0$')
            THEN regexp_replace(trim(setor), '\.0$', '')
        ELSE trim(coalesce(setor, ''))
    END AS setor,
    CASE
        WHEN trim(coalesce(descricao_localizacao, '')) = '' THEN NULL
        ELSE trim(coalesce(descricao_localizacao, ''))
    END AS descricao_localizacao,
    CASE
        WHEN trim(coalesce(estado_reprodutivo, '')) = '' THEN NULL
        ELSE trim(coalesce(estado_reprodutivo, ''))
    END AS estado_reprodutivo
FROM numbered
),
parsed AS (
    SELECT
        *,
        {name_function}(especie_raw) AS name,
        {registration_function}(numero_registro_raw) AS registration
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
    familia,
    CASE WHEN is_morphospecies THEN NULL ELSE name.genero END AS genero,
    CASE WHEN is_morphospecies THEN name.nome_normalizado ELSE name.epiteto_especifico END
        AS epiteto_especifico,
    name.infraespecifico AS infraespecifico,
    name.autor AS autor,
    name.identification_qualifier AS identification_qualifier,
    name.nome_raw AS nome_raw,
    name.nome_normalizado AS nome_normalizado,
    name.parse_status AS parse_status,
    setor,
    descricao_localizacao,
    estado_reprodutivo,
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
