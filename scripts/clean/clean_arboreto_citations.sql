-- Clean das Citações do arboreto, lido e preenchido por clean_arboreto_citations.py com str.format.
--
-- Numera as linhas de staging na ordem da planilha (arquivo, aba, linha) e aplica
-- fill-down de familia com last_value() IGNORE NULLS
-- (linhas sem familia recebem o último valor, não-nulo, anterior).
-- A ordem vem do ORDER BY, não da entrada: o Postgres devolve as linhas em ordem física.
-- Normaliza familia com trim + regex e prepara especie/quantidade como
-- campos *_raw, aplicando trim e substituindo valores nulos por strings vazias
--
-- Resumo da query (CTEs encadeadas, cada passo lê só o anterior):
--   numbered: numera as linhas do staging (rn) na ordem da planilha;
--   typed:    guarda a família ORIGINAL (family_raw, antes do fill-down), faz o
--             fill-down de familia, aplica trim em especie/quantidade e faz o
--             TRY_CAST da quantidade para DOUBLE (inválido vira NULL);
--   checked:  quantidade finita; NaN/inf viram NULL. Divergência deliberada do
--             TRY_CAST puro, que aceita 'nan'/'inf', para manter o mesmo
--             comportamento do antigo pd.to_numeric(errors="coerce") + isna();
--   summed:   previous_quantity_sum = soma das quantidades das linhas ANTERIORES
--             da mesma aba, com ORDER BY explícito por _source_row inteiro
--             (NULL conta como 0);
--   SELECT final: is_total_row = família original e espécie vazias, quantidade
--             preenchida e igual à soma anterior da aba (ADR-0012).
--
-- Placeholders, preenchidos pelo Python a partir do config.py:
--   staging_order: lista de colunas da ordem da planilha, com a linha convertida para inteiro;
--     aparece no row_number().
--   family_raw_col: nome da coluna da família original; é constante do config.py porque
--     o Python lê a mesma coluna ao registrar a soma de controle.
-- Como o arquivo passa por str.format, uma chave literal (ex.: quantificador de regex)
-- precisa ser escrita dobrada.
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY {staging_order}) AS rn, * FROM df_input
),
typed AS (
    SELECT
        rn,
        _source_file,
        _source_sheet,
        _source_row,
        trim(coalesce(familia, '')) AS {family_raw_col},
        last_value(
            CASE
                WHEN trim(coalesce(familia, '')) = '' THEN NULL
                ELSE regexp_replace(trim(coalesce(familia, '')), '^\s+|\s+$', '', 'g')
            END IGNORE NULLS
        ) OVER (ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS familia,
        trim(coalesce(especie, '')) AS especie_raw,
        trim(coalesce(quantidade, '')) AS quantidade_raw,
        TRY_CAST(NULLIF(trim(coalesce(quantidade, '')), '') AS DOUBLE) AS quantidade_cast
    FROM numbered
),
checked AS (
    SELECT
        *,
        CASE WHEN isfinite(quantidade_cast) THEN quantidade_cast END AS quantidade
    FROM typed
),
summed AS (
    SELECT
        *,
        coalesce(
            sum(quantidade) OVER (
                PARTITION BY _source_file, _source_sheet
                ORDER BY CAST(_source_row AS INTEGER)
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ),
            0
        ) AS previous_quantity_sum
    FROM checked
)
SELECT
    rn,
    _source_file,
    _source_sheet,
    _source_row,
    {family_raw_col},
    familia,
    especie_raw,
    quantidade_raw,
    quantidade,
    previous_quantity_sum,
    coalesce(
        {family_raw_col} = ''
        AND especie_raw = ''
        AND quantidade IS NOT NULL
        AND quantidade = previous_quantity_sum,
        FALSE
    ) AS is_total_row
FROM summed
ORDER BY rn
