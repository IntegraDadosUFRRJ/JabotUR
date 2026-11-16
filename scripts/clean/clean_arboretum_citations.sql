-- Clean das Citações do arboreto, lido e preenchido por clean_arboretum_citations.py com str.format.
--
-- Numera as linhas de staging na ordem da planilha (arquivo, aba, linha) e aplica
-- fill-down de family com last_value() IGNORE NULLS
-- (linhas sem family recebem o último valor, não-nulo, anterior).
-- A ordem vem do ORDER BY, não da entrada: o Postgres devolve as linhas em ordem física.
-- Normaliza family com trim + regex e prepara species_raw/quantity como
-- species_input/quantity_raw, aplicando trim e substituindo valores nulos por strings vazias
--
-- Resumo da query (CTEs encadeadas, cada passo lê só o anterior):
--   numbered: numera as linhas do staging (rn) na ordem da planilha;
--   typed:    guarda a família ORIGINAL (family_raw, antes do fill-down), faz o
--             fill-down de family, aplica trim em species_raw/quantity e faz o
--             TRY_CAST da quantidade para DOUBLE (inválido vira NULL);
--   checked:  quantidade finita; NaN/inf viram NULL. O TRY_CAST sozinho aceita
--             'nan'/'inf' como número; numa planilha de contagem eles são texto
--             inválido, como qualquer outro;
--   summed:   previous_quantity_sum = soma das quantidades das linhas ANTERIORES
--             da mesma aba, com ORDER BY explícito por _source_row inteiro
--             (NULL conta como 0);
--   flagged:  is_total_row = família original e espécie vazias, quantidade
--             preenchida e igual à soma anterior da aba (ADR-0012);
--   parsed:   nome científico pelo parser Python, função registrada no DuckDB que devolve STRUCT;
--   statused: parse_status final; total_row vence o status do parser. A quantidade
--             não entra aqui: ausente ou inválida, ela só marca needs_review;
--   marked:   is_morphospecies, calculado sobre o parse_status final;
--   SELECT final: morfo-espécie usa o nome normalizado como epíteto e fica sem gênero;
--             morfo-espécie, unparseable e total_row não reconciliam entre fontes;
--             needs_review para todo status fora da lista aceita e para toda
--             quantidade ausente ou inválida (quantity NULL; o valor original fica
--             no staging). parse_status NULL não é morfo-espécie nem unparseable
--             (coalesce com FALSE) e fica fora da lista aceita (coalesce com TRUE):
--             nenhuma flag sai NULL.
--
-- Placeholders, preenchidos pelo Python a partir do config.py e do parser:
--   staging: nome da view do staging (config.DUCKDB_STAGING_ALIAS);
--   source_file / source_sheet / source_row: colunas de linhagem (config.SOURCE_*_COL);
--   source_row_number: a linha de origem convertida para inteiro, no fill-down;
--   staging_order: lista de colunas da ordem da planilha, com a linha convertida para inteiro;
--     aparece no row_number().
--   family_raw_col: nome da coluna da família original; é constante do config.py porque
--     o Python lê a mesma coluna ao registrar a soma de controle.
--   parse_function: nome da função registrada no DuckDB para o parser de nome científico.
--   status_*: valores de parse_status, já como literais SQL.
-- Como o arquivo passa por str.format, uma chave literal (ex.: quantificador de regex)
-- precisa ser escrita dobrada.
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY {staging_order}) AS rn, * FROM {staging}
),
typed AS (
    SELECT
        rn,
        {source_file},
        {source_sheet},
        {source_row},
        trim(coalesce(family, '')) AS {family_raw_col},
        last_value(
            CASE
                WHEN trim(coalesce(family, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(family, '')), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS family,
        trim(coalesce(species_raw, '')) AS species_input,
        trim(coalesce(quantity, '')) AS quantity_raw,
        TRY_CAST(NULLIF(trim(coalesce(quantity, '')), '') AS DOUBLE) AS quantity_cast
    FROM numbered
),
checked AS (
    SELECT
        *,
        CASE WHEN isfinite(quantity_cast) THEN quantity_cast END AS quantity
    FROM typed
),
summed AS (
    SELECT
        *,
        coalesce(
            sum(quantity) OVER (
                PARTITION BY {source_file}, {source_sheet}
                ORDER BY {source_row_number}
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        ) AS previous_quantity_sum
    FROM checked
),
flagged AS (
SELECT
    rn,
    {source_file},
    {source_sheet},
    {source_row},
    {family_raw_col},
    family,
    species_input,
    quantity_raw,
    quantity,
    previous_quantity_sum,
    coalesce(
        {family_raw_col} = ''
        AND species_input = ''
        AND quantity IS NOT NULL
        AND quantity = previous_quantity_sum,
        FALSE
    ) AS is_total_row
FROM summed
),
parsed AS (
    SELECT *, {parse_function}(species_input) AS name FROM flagged
),
statused AS (
    SELECT
        *,
        CASE
            WHEN is_total_row THEN {status_total_row}
            ELSE name.parse_status
        END AS parse_status
    FROM parsed
),
marked AS (
    SELECT *, coalesce(parse_status = {status_morphospecies}, FALSE) AS is_morphospecies
    FROM statused
)
SELECT
    rn,
    {source_file},
    {source_sheet},
    {source_row},
    {family_raw_col},
    species_input,
    previous_quantity_sum,
    is_total_row,
    family,
    CASE WHEN is_morphospecies THEN NULL ELSE name.genus END AS genus,
    CASE WHEN is_morphospecies THEN name.name_normalized ELSE name.epithet END
        AS epithet,
    name.infraspecific AS infraspecific,
    name.author AS author,
    name.identification_qualifier AS identification_qualifier,
    quantity,
    name.name_raw AS name_raw,
    name.name_normalized AS name_normalized,
    parse_status,
    NOT (
        is_morphospecies
        OR is_total_row
        OR coalesce(parse_status = {status_unparseable}, FALSE)
    ) AS reconcile_across_sources,
    coalesce(
        parse_status NOT IN (
            {status_ok}, {status_genus_only}, {status_morphospecies}, {status_total_row}
        ),
        TRUE
    ) OR quantity IS NULL AS needs_review
FROM marked
ORDER BY rn
