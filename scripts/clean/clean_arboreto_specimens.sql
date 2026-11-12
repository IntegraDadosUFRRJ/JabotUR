-- Clean dos Espécimes do arboreto, lido e executado sem alteração por clean_arboreto_specimens.py
-- (sem placeholders).
--
-- Numera as linhas de staging e normaliza os campos mecânicos
--   - familia: trim; " - " placeholder usado nas linhas "sem identificação" e vira NULL
--   - setor: trim; normaliza os casos onde a planilha trouxe só o
--     número solto para o formato de código igual ao resto da coluna
--   - descricao_localizacao / estado_reprodutivo: trim, string vazia vira NULL
WITH numbered AS (
    SELECT row_number() OVER (ORDER BY CAST(_source_row AS INTEGER)) AS rn, * FROM df_input
)
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
ORDER BY rn
