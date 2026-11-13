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
--   flagged:  is_total_row = família original e espécie vazias, quantidade
--             preenchida e igual à soma anterior da aba (ADR-0012);
--   parsed:   nome científico pelo parser Python, função registrada no DuckDB que devolve STRUCT;
--   statused: parse_status final; total_row vence unparseable_quantidade, que vence o
--             status do parser;
--   marked:   is_morphospecies, calculado sobre o parse_status final;
--   SELECT final: morfo-espécie usa o nome normalizado como epíteto e fica sem gênero;
--             morfo-espécie, unparseable e total_row não reconciliam entre fontes;
--             needs_review para todo status fora da lista aceita. As comparações com
--             parse_status tratam NULL como "não é", como fazia o pandas.
--
-- Placeholders, preenchidos pelo Python a partir do config.py e do parser:
--   staging_order: lista de colunas da ordem da planilha, com a linha convertida para inteiro;
--     aparece no row_number().
--   family_raw_col: nome da coluna da família original; é constante do config.py porque
--     o Python lê a mesma coluna ao registrar a soma de controle.
--   parse_function: nome da função registrada no DuckDB para o parser de nome científico.
--   status_*: valores de parse_status, já como literais SQL.
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
),
flagged AS (
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
),
parsed AS (
    SELECT *, {parse_function}(especie_raw) AS name FROM flagged
),
statused AS (
    SELECT
        *,
        CASE
            WHEN is_total_row THEN {status_total_row}
            WHEN quantidade IS NULL THEN {status_unparseable_quantidade}
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
    _source_file,
    _source_sheet,
    _source_row,
    {family_raw_col},
    especie_raw,
    previous_quantity_sum,
    is_total_row,
    familia,
    CASE WHEN is_morphospecies THEN NULL ELSE name.genero END AS genero,
    CASE WHEN is_morphospecies THEN name.nome_normalizado ELSE name.epiteto_especifico END
        AS epiteto_especifico,
    name.infraespecifico AS infraespecifico,
    name.autor AS autor,
    name.identification_qualifier AS identification_qualifier,
    quantidade,
    name.nome_raw AS nome_raw,
    name.nome_normalizado AS nome_normalizado,
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
    ) AS needs_review
FROM marked
ORDER BY rn
