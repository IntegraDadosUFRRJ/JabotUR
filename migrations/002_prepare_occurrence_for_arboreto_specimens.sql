-- Migração necessária antes de executar
-- load_arboreto_specimens.py em um banco criado
-- a partir de uma versão anterior do schema.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'occurrence'
          AND column_name = 'id_especie'
    ) THEN
        ALTER TABLE occurrence
        RENAME COLUMN id_especie TO id_species;
    END IF;
END $$;

ALTER TABLE occurrence
ADD COLUMN IF NOT EXISTS basis_of_record varchar;

ALTER TABLE occurrence
ADD COLUMN IF NOT EXISTS origin_sheet varchar;

ALTER TABLE occurrence
ADD COLUMN IF NOT EXISTS identification_qualifier varchar;

-- Backfill dos registros existentes do SPP.
UPDATE occurrence
SET basis_of_record = 'PreservedSpecimen'
WHERE basis_of_record IS NULL;

DROP INDEX IF EXISTS occurrence_uniq_origin;

CREATE UNIQUE INDEX occurrence_uniq_origin
ON occurrence (
    origin_file,
    COALESCE(origin_sheet, ''),
    origin_row
);