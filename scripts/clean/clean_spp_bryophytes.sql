-- Clean do SPP (briófitas), lido e preenchido por clean_spp_bryophytes.py com str.format.
--
-- Numera as linhas de staging na ordem da planilha (arquivo, linha) e aplica fill-down com
-- last_value() IGNORE NULLS em plot/sample/substrate, que valem para um bloco de linhas
-- (linhas em branco recebem o último valor, não-nulo, anterior).
-- A ordem vem do ORDER BY, não da entrada: o Postgres devolve as linhas em ordem física.
-- Normaliza (trim + regex) os campos taxonômicos/metadados, converte
-- identification_status pra INT e monta a coluna de observações.
--
-- Placeholders, preenchidos pelo Python a partir do config.py:
--   staging: nome da view do staging (config.DUCKDB_STAGING_ALIAS);
--   source_file / source_row: colunas de linhagem (config.SOURCE_*_COL);
--   staging_order: lista de colunas da ordem da planilha, com a linha convertida para inteiro;
--     aparece no row_number() e no ORDER BY final.
--   remark_expression: expressão CASE inteira da coluna de observações, com uma
--     regexp_replace encadeada para cada correção da lista de regex de observação.
-- Como o arquivo passa por str.format, uma chave literal (ex.: quantificador de regex)
-- precisa ser escrita dobrada.
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY {staging_order}) AS rn, * FROM {staging}
), filled AS (
    SELECT
        rn,
        {source_file},
        {source_row},
        last_value(
            CASE
                WHEN trim(coalesce(plot, '')) = '' THEN NULL
                ELSE regexp_replace(regexp_replace(trim(coalesce(plot, '')), '^\s+|\s+$', '', 'g'), '4\*', '4')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS plot,
        last_value(
            CASE
                WHEN trim(coalesce(sample, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(sample, '')), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS sample,
        last_value(
            CASE
                WHEN trim(coalesce(substrate, '')) = '' THEN NULL
                ELSE regexp_replace(regexp_replace(trim(coalesce(substrate, '')), '\s+', ' ', 'g'), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS substrate,
        -- forma de vida é da coleta, não do bloco: sem fill-down, vazio fica NULL
        CASE
            WHEN trim(coalesce(life_form, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(life_form, '')), '^\s+|\s+$', '', 'g')
        END AS life_form,
        {remark_expression} AS remarks,
        CASE
            WHEN trim(coalesce(identification_status, '')) = '' THEN NULL
            ELSE CAST(trim(coalesce(identification_status, '')) AS INTEGER)
        END AS identification_status,
        CASE
            WHEN trim(coalesce(phylum, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(phylum, '')), '^\s+|\s+$', '', 'g')
        END AS phylum,
        CASE
            WHEN trim(coalesce(family, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(family, '')), '^\s+|\s+$', '', 'g')
        END AS family,
        CASE
            WHEN trim(coalesce(genus, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(genus, '')), '^\s+|\s+$', '', 'g')
        END AS genus,
        CASE
            WHEN trim(coalesce(epithet, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(epithet, '')), '^\s+|\s+$', '', 'g')
        END AS epithet,
        CASE
            WHEN trim(coalesce(author, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(author, '')), '^\s+|\s+$', '', 'g')
        END AS author
    FROM numbered
)
SELECT
    {source_file},
    {source_row},
    -- texto que a normalização deixou vazio vira NULL, não string vazia
    NULLIF(plot, '') AS plot,
    sample,
    substrate,
    life_form,
    NULLIF(remarks, '') AS remarks,
    identification_status,
    phylum,
    family,
    genus,
    epithet,
    author,
    CURRENT_TIMESTAMP AS _cleaned_at
FROM filled
ORDER BY {staging_order}
