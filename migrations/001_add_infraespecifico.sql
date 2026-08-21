-- Migração necessária antes de executar
-- load_arboreto_citations.py pela primeira vez
-- contra um PostgreSQL que já possua a versão anterior do schema.
--
-- A coluna infraespecifico é necessária para que a dimensão
-- epiteto_especifico possa ser carregada corretamente.

ALTER TABLE epiteto_especifico
ADD COLUMN IF NOT EXISTS infraespecifico varchar;

-- Índices únicos parciais para tratar corretamente os casos
-- em que infraespecifico é NULL.

DROP INDEX IF EXISTS epiteto_uniq_com_infra;
DROP INDEX IF EXISTS epiteto_uniq_sem_infra;

CREATE UNIQUE INDEX epiteto_uniq_com_infra
ON epiteto_especifico
(id_genero, nome, infraespecifico, id_autor)
WHERE infraespecifico IS NOT NULL;

CREATE UNIQUE INDEX epiteto_uniq_sem_infra
ON epiteto_especifico
(id_genero, nome, id_autor)
WHERE infraespecifico IS NULL;