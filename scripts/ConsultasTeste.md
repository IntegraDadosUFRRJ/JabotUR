## Criação de uma view para a cadeia de joins taxonomicos:

```
CREATE VIEW vw_taxonomia AS
SELECT
    e.id AS id_especie,
    f.nome AS filo,
    fa.nome AS familia,
    g.nome AS genero,
    e.nome AS especie,
    a.nome AS autor,
    g.nome || ' ' || e.nome || ' ' || a.nome AS nome_cientifico
FROM especie e
JOIN genero g
    ON e.id_genero = g.id
JOIN familia fa
    ON g.id_familia = fa.id
JOIN filo f
    ON fa.id_filo = f.id
JOIN autor a
    ON e.id_autor = a.id;
```
## Nome Cientifico Completo

```
SELECT
    id_especie,
    nome_cientifico
FROM vw_taxonomia
ORDER BY nome_cientifico;
```

## Taxonomia Completa(individuo especifico)

```
SELECT
    filo,
    familia,
    genero,
    especie,
    autor,
    nome_cientifico
FROM vw_taxonomia
WHERE id_especie = 1; <!-- ou pelo nome "WHERE especie = 'nome';"-->
```

## Informações sobre uma coleta

```
SELECT
    c.id,
    c.amostra,

    t.nome_cientifico,
    t.genero,
    t.familia,
    t.filo,

    fv.tipo AS forma_vida,
    i.descricao AS identificacao,
    p.coordenada

FROM coleta c

JOIN vw_taxonomia t
    ON c.id_especie = t.id_especie

JOIN forma_vida fv
    ON c.id_forma = fv.id

JOIN identificacao i
    ON c.id_identificacao = i.id

JOIN parcela p
    ON c.id_parcela = p.id;
```

## Especies de uma Familia

```
SELECT
    nome_cientifico
FROM vw_taxonomia
WHERE familia = 'Lejeuneaceae'
ORDER BY genero, especie;
```

## Especies de um Genero

```
SELECT
    nome_cientifico
FROM vw_taxonomia
WHERE genero = 'Cheilolejeunea'
ORDER BY especie;
```

## Quantidade de Coletas por Especie

```
SELECT
    t.nome_cientifico,
    COUNT(*) AS coletas

FROM coleta c

JOIN vw_taxonomia t
    ON c.id_especie = t.id_especie

GROUP BY
    t.nome_cientifico

ORDER BY
    coletas DESC;
```

## Especies em cada Parcela

```
SELECT
    p.coordenada,
    t.nome_cientifico

FROM coleta c

JOIN parcela p
    ON c.id_parcela = p.id

JOIN vw_taxonomia t
    ON c.id_especie = t.id_especie

ORDER BY
    p.coordenada,
    t.nome_cientifico;
```

## Substratos de uma Coleta
```
SELECT
    c.id,
    s.nome,
    s.sigla

FROM coleta c

JOIN briofita_substrato bs
    ON c.id = bs.id_briofita

JOIN substrato s
    ON bs.id_substrato = s.id

WHERE c.id = 15;
```

## relatorio de uma Coleta

```
SELECT
    c.id,
    c.amostra,

    t.nome_cientifico,
    t.familia,
    t.filo,

    fv.tipo AS forma_vida,
    i.descricao AS identificacao,
    p.coordenada

FROM coleta c

JOIN vw_taxonomia t
    ON c.id_especie = t.id_especie

JOIN forma_vida fv
    ON c.id_forma = fv.id

JOIN identificacao i
    ON c.id_identificacao = i.id

JOIN parcela p
    ON c.id_parcela = p.id

ORDER BY
    c.id;
```