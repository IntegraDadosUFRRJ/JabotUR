-- Clean do SPP (briófitas), lido e preenchido por clean_SPP.py com str.format.
--
-- Numera as linhas de staging na ordem da planilha (arquivo, linha) e aplica fill-down com
-- last_value() IGNORE NULLS em parcela/amostra/substrato, que valem para um bloco de linhas
-- (linhas em branco recebem o último valor, não-nulo, anterior).
-- A ordem vem do ORDER BY, não da entrada: o Postgres devolve as linhas em ordem física.
-- Normaliza (trim + regex) os campos taxonômicos/metadados, converte
-- status_identificacao pra INT e monta a coluna de observações.
--
-- Placeholders, preenchidos pelo Python a partir do config.py:
--   staging_order: lista de colunas da ordem da planilha, com a linha convertida para inteiro;
--     aparece no row_number() e no ORDER BY final.
--   observation_expression: expressão CASE inteira da coluna de observações, com uma
--     regexp_replace encadeada para cada correção da lista de regex de observação.
-- Como o arquivo passa por str.format, uma chave literal (ex.: quantificador de regex)
-- precisa ser escrita dobrada.
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY {staging_order}) AS rn, * FROM df_input
), filled AS (
    SELECT
        rn,
        _source_file,
        _source_row,
        last_value(
            CASE
                WHEN trim(coalesce(parcela, '')) = '' THEN NULL
                ELSE regexp_replace(regexp_replace(trim(coalesce(parcela, '')), '^\s+|\s+$', '', 'g'), '4\*', '4')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS parcela,
        last_value(
            CASE
                WHEN trim(coalesce(amostra, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(amostra, '')), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS amostra,
        last_value(
            CASE
                WHEN trim(coalesce(substrato, '')) = '' THEN NULL
                ELSE regexp_replace(regexp_replace(trim(coalesce(substrato, '')), '\s+', ' ', 'g'), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS substrato,
        -- forma de vida é da coleta, não do bloco: sem fill-down, vazio fica NULL
        CASE
            WHEN trim(coalesce(forma_vida, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(forma_vida, '')), '^\s+|\s+$', '', 'g')
        END AS forma_vida,
        {observation_expression} AS observacoes,
        CASE
            WHEN trim(coalesce(identificacao, '')) = '' THEN NULL
            ELSE CAST(trim(coalesce(identificacao, '')) AS INTEGER)
        END AS status_identificacao,
        CASE
            WHEN trim(coalesce(filo, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(filo, '')), '^\s+|\s+$', '', 'g')
        END AS filo,
        CASE
            WHEN trim(coalesce(familia, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(familia, '')), '^\s+|\s+$', '', 'g')
        END AS familia,
        CASE
            WHEN trim(coalesce(genero, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(genero, '')), '^\s+|\s+$', '', 'g')
        END AS genero,
        CASE
            WHEN trim(coalesce(epiteto_especifico, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(epiteto_especifico, '')), '^\s+|\s+$', '', 'g')
        END AS especie,
        CASE
            WHEN trim(coalesce(autor, '')) = '' THEN NULL
            ELSE regexp_replace(trim(coalesce(autor, '')), '^\s+|\s+$', '', 'g')
        END AS autor
    FROM numbered
)
SELECT
    _source_file,
    _source_row,
    -- texto que a normalização deixou vazio vira NULL, não string vazia
    NULLIF(parcela, '') AS parcela,
    amostra,
    substrato,
    forma_vida,
    NULLIF(observacoes, '') AS observacoes,
    status_identificacao,
    filo,
    familia,
    genero,
    especie,
    autor,
    CURRENT_TIMESTAMP AS _cleaned_at
FROM filled
ORDER BY {staging_order}
