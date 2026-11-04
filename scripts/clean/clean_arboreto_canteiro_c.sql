SELECT 
    *,
    -- Limpeza e padronização da Família
    CASE 
        WHEN TRIM("Família") IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
        ELSE TRIM("Família")
    END AS family_clean,

    -- Limpeza e padronização da Espécie
    CASE 
        WHEN TRIM("Espécie") IN ('na', 'NA', 'sem id', 'SEM ID') THEN NULL 
        ELSE TRIM("Espécie")
    END AS species_clean,

    -- Padronização da Origem
    CASE 
        WHEN LOWER(TRIM("Origem")) IN ('exótico', 'exótica') THEN 'Exótica'
        WHEN LOWER(TRIM("Origem")) IN ('na', 'sem id') THEN NULL
        ELSE TRIM("Origem")
    END AS origin_clean,

    -- Padronização do Domínio Fitogeográfico
    CASE 
        WHEN LOWER(TRIM("Domínio fitogeográfico")) IN ('na', 'sem id') THEN NULL
        ELSE TRIM("Domínio fitogeográfico")
    END AS domain_clean,

    -- Padronização CNCFlora
    CASE 
        WHEN LOWER(TRIM("Categoria CNCFlora")) = 'na' THEN 'NA'
        ELSE UPPER(TRIM("Categoria CNCFlora"))
    END AS cncflora_clean,

    -- Conversão de Altura para metros
    CASE 
        WHEN TRY_CAST(REPLACE(CAST("Altura (m)" AS VARCHAR), ',', '.') AS DOUBLE) IN (15124, 15125) THEN NULL
        WHEN TRY_CAST(REPLACE(CAST("Altura (m)" AS VARCHAR), ',', '.') AS DOUBLE) IS NOT NULL THEN TRY_CAST(REPLACE(CAST("Altura (m)" AS VARCHAR), ',', '.') AS DOUBLE)
        ELSE NULL 
    END AS height_m_clean,

    -- Marcação de linhas que necessitam de revisão
    CASE 
        WHEN "Espécie" IS NULL 
            OR TRIM("Espécie") IN ('na', 'NA', 'sem id', 'SEM ID')
            OR ("Altura (m)" IS NOT NULL AND TRY_CAST(REPLACE(CAST("Altura (m)" AS VARCHAR), ',', '.') AS DOUBLE) IS NULL)
            OR TRY_CAST(REPLACE(CAST("Altura (m)" AS VARCHAR), ',', '.') AS DOUBLE) IN (15124, 15125)
        THEN TRUE 
        ELSE FALSE 
    END AS needs_review,

    -- Timestamp
    CURRENT_TIMESTAMP AS _cleaned_at

FROM stg_canteiro_c