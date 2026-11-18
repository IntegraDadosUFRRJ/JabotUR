# Processos de ETL — JabotUR

> Manter este arquivo como fonte única daqui pra frente,
> os PDFs originais ficam como referência histórica.
> Ligado a `ONBOARDING.md` (visão geral de convenções), `data_dictionary.md`
> (colunas e regras de negócio entre fontes) e `JabotUR_DER.md` (schema e
> ADRs), onde uma regra já está documentada em um desses, aqui só aponta
> pra ela, pra não duplicar e divergir com o tempo.

---

## 1. Fluxo geral: staging -> clean -> load

O pipeline mantém a origem do dado rastreável e organiza a limpeza em
camadas progressivas, cada uma com uma responsabilidade específica:

**Staging:** leitura das abas da planilha pelo `read_xlsx` do DuckDB com
`all_varchar = true` e `stop_at_empty = false` (`scripts/staging/xlsx_sheet.py`).
O staging troca inteiros exportados com decimal (`'1.0'` -> `'1'` via
`regexp_replace`), deixa de fora linhas que não têm nenhum dado nas colunas
mapeadas (`WHERE coalesce(...) IS NOT NULL`, `xlsx_sheet.py`) e
acrescenta a linhagem (`_source_file`, `_source_sheet`, `_source_row`) e
`_loaded_at`.

**Clean:** segunda camada de tabelas, recebendo o staging. Aqui sim
acontece transformação: limpeza de digitação, fill-down, normalização de
vocabulário, parsing de campos compostos. A transformação roda no DuckDB
(**ADR-0013**), que lê o staging do Postgres anexado, executa a query do
arquivo `.sql` de cada fonte (chamando os parsers Python registrados em
`scripts/clean/duckdb_parsers.py`) e grava a tabela `cln_*` direto no
Postgres com `db_utils.replace_table`. **Regra central: clean
nunca descarta linha.** Problema de qualidade de dado vira **coluna**
(`parse_status`, `needs_review`, `reconcile_across_sources`, conforme a
fonte), nunca uma linha removida ou um dataframe separado. Quem decide o
que fazer com a sinalização é a camada de load, não o clean.

**Load:** lê a tabela clean e resolve pras tabelas normalizadas finais no
Postgres. A resolução de chave natural (get-or-create) é feita inteiramente
em **Python puro** (`load/taxonomy.py`), não em SQL, um dict com tupla
como chave decide se uma família/gênero/autor/espécie já existe ou precisa
de um id novo. Isso é o que garante que a mesma espécie citada em fontes
diferentes resolva pro mesmo registro. A gravação usa o DuckDB anexado ao
Postgres (`db_utils.postgres_duckdb()`): `db_utils.replace_table` recria as
tabelas de staging e clean, e nos loads `db_utils.upsert_rows` (upsert por
`id` via `_upsert_by_id_statement`) grava dimensões e fatos e
`db_utils.insert_ignore_rows` grava tabelas associativas, tudo dentro de uma
única transação por fonte (`db_utils.transaction(con)`).
`db_utils.write_dataframe_to_postgres` agora aceita apenas `mode="replace"`
(default) e só é usada pelo Canteiro C (os modos `"upsert"` e
`"append_composite"` saíram).

Toda fonte nova segue essas três camadas, reaproveitando `taxonomy.py`
sempre que o conceito for compartilhado (família/gênero/autor/epíteto) e
só criando tabela/lógica nova para o que for exclusivo daquela fonte.

---

## 2. Regras de transformação por fonte

### 2.1 SPP (Briófitas)

| Coluna | Regra |
|---|---|
| Parcela | Fill-down; substituir "4*" por "4" (o asterisco é sufixo na planilha original) |
| Amostra | Fill-down |
| StatusIdentificacao | Significado em tabela externa, conforme legenda |
| Filo | Juntar sigla + nome completo |
| Família | Transpor os dados |
| Gênero | Transpor os dados |
| Espécie | Vira `epithet` (`transforms/epithet.py` remove a abreviação de gênero; separa `cf.`/`aff.` para `occurrence.identification_qualifier` conforme ADR-0006; se sobrar vazio, `sp` ou `sp.`, como em `G. sp.`, `G. sp` ou `G.`, devolve `None` e a espécie entra como gênero-só conforme ADR-0003) |
| Autor | Transpor os dados |
| Forma de Vida | Ausente -> NULL |
| Substrato | Fill-down; significado da sigla via legenda; multivalorado, separado por "+" |
| Observações | Conversões pontuais (`"poste de cimento"`/`"cimento de placa de pau brasil"` -> `"cimento"`, `"acro [fotos]"` -> `"acro"`); ausente -> NULL; multivalorado por ";" |

### 2.2 Arboreto — observações gerais sobre a coluna "Espécie"

A coluna de espécie do arboreto não segue um padrão único, o parser
(`transforms/scientific_name.py`) precisa cobrir, todos vistos em dados
reais:

- **Padrão simples**: `"Astronium concinnum Schott"` → Astronium(gênero) +
  concinnum(epíteto) + Schott(autor)
- **Infraespecífico antes do autor**: `"Anadenanthera colubrina var. cebil
  (Griseb.) Altschul"`, "var. cebil" logo após o epíteto, autor depois
- **Infraespecífico depois do autor**: `"Anadenanthera colubrina (Vell.)
  Brenan var. colubrina"` autor da espécie primeiro, "var. colubrina"
  depois (convenção botânica: a variedade autônima herda o autor da
  espécie)
- **Só gênero**: alguns registros têm só o gênero, sem epíteto,
  planilha incompleta na fonte
- **Gênero + "sp."**: `"Citrus sp."`, `"Eugenia sp"`, marcador de espécie
  indeterminada; tratado como gênero-só (ADR-0003). O escopo é só `sp.`/`sp`
  sem nenhum texto depois: `spp.`, `sp. 1` e `sp.` seguido de autor não estão
  cobertos
- **Morfo-espécie**: placeholder tipo `"Morfo-Espécie 1"` pra espécime
  ainda não identificado a nível de espécie/gênero
- **Qualificador de incerteza**: `"Handroanthus cf ochraceus (Cham.)
  Mattos"`, "cf"/"aff" entre gênero e epíteto, indicando identificação
  não confirmada

Ver `JabotUR_DER.md` (nota em `species`) pra decisão de produto
sobre como cada um desses casos é registrado hoje.

### 2.3 Arboreto — Lista Completa (SPS)

| Coluna | Regra |
|---|---|
| Família | Transpor os dados |
| Espécie | Script de parsing -> Gênero + Epíteto + Infraespecífico + Autor |
| Distribuição | Transpor dados (mapeia pra `species_status.origin`) |
| Grau de Ameaça | Transpor dados |
| Domínios Fitogeográficos | Multivalorado, separado por "," |
| Endemismo | Converter pra boolean |
| Distribuição geográfica | Multivalorado por ","; separar entre países e estados (com a conexão estado→país); menções que não decompõem em país/estado (regiões, áreas livres tipo "W. Indian Ocean") vão pra tabela separada (`species_geographic_area`) |

*(Ainda não implementado.)*

### 2.4 Arboreto — Espécimes

> **Nota sobre Extração e Linhas Ocultas:** O `read_xlsx` do DuckDB (`scripts/staging/xlsx_sheet.py`) lê todas as linhas da aba que tenham dado nas colunas mapeadas, inclusive linhas ocultas no Excel (se houver), gravando em `stg_arboretum_specimens` e `cln_arboretum_specimens`. Quando faltam dados botânicos ou há placeholders (ex.: "Cássia Rosa", "sem identificação"), as linhas recebem `needs_review = True` na camada clean e entram em `occurrence` com `id_species = NULL` durante o load (`scripts/load/load_arboretum_specimens.py`, linhas 80–90).

| Coluna | Regra |
|---|---|
| Família | Transpor os dados |
| Espécie | Script de parsing (mesmo do item 2.2) |
| N° de Registro | Identificar tipo de lacre (amarelo = prefixo "RBRv"; azul = só numeração). Quando os dois existirem na mesma linha, o azul prevalece por ser o mais recente. Ex.: `RBRv90000293 (LACRE AZUL 0015124)` -> mantém só o azul |
| Setor | Transpor os dados |
| Canteiro | Excluir coluna (sem dados na fonte) |
| Descrição da localização | Transpor; maioria NULL, tratar como NULL de verdade no load, nunca string `"N/A"` |
| Estado reprodutivo | Mesma regra acima, NULL de verdade; nunca criar uma linha `"N/A"` em `reproductive_status` via get-or-create |
| Procedência | Excluir coluna (sem dados na fonte) |
| ADICIONAR | Excluir coluna (sem dados na fonte) |


### 2.5 Arboreto — Canteiro C

> **Nota sobre Estrutura das Fontes (Excel):** "Espécimes" e "Canteiro C" são **abas do mesmo arquivo** Excel (`data/arboretum_floristic_diversity.xlsx`), e não a mesma planilha com filtros aplicados. Cada aba é processada por rotinas de extração independentes, respeitando as colunas e regras de negócio específicas de cada uma.

| Coluna | Regra |
|---|---|
| Família | Transpor os dados |
| Espécie | Script de parsing (mesmo do item 2.2) |
| Origem | Canonicalizar "Exótico"/"Exótica" para um valor único; `"na"`/vazio -> NULL |
| Domínio fitogeográfico | Multivalorado por vírgula; `"na"`/vazio -> nenhuma linha inserida na tabela associativa `species_domain` (ver ADR-0008), nunca criar um domínio "N/A" |
| Grau de Ameaça (Categoria CNCFlora) | Uppercase; `"na"`/vazio -> código IUCN real `NA` (ADR-0005), nunca NULL |
| Numeração lacre | Sem prefixo "RBRv" = lacre azul, mesmo sem a palavra "AZUL" escrita (ADR-0009) |
| Localização canteiro | "SCC1-4" e "S2C2"/"S2C4" são códigos legítimos (confirmados contra o Setor real de Espécimes), mapeados para o mesmo `sector` compartilhado |
| Altura (m) | Linhas 183, 184 e 185 têm erro de digitação que passa incólume pela conversão para número, forçar NULL nestas linhas e flagar o status |

*(Ainda não implementado.)*

### 2.6 Arboreto — Citações bibliográficas (Monografia Gabriel, Livro Pesquisas no JB, JABOT)

As 3 abas compartilham estrutura idêntica, um script parametrizado por
fonte em vez de três quase iguais.

| Coluna | Regra |
|---|---|
| Família | Fill-down |
| Espécie | Script de parsing (mesmo do item 2.2) |
| Quant | Converter para número (`TRY_CAST` + `isfinite`); quantidade ausente ou inválida vira `NULL` e só marca `needs_review = True`, sem mudar o `parse_status` do nome científico (`unparseable_quantidade` não é mais gravado; o valor bruto original se consulta no staging pela chave `_source_file`, `_source_sheet`, `_source_row`) |

**Linhas de totais.** Duas das três abas terminam em linha de somatório
(Monografia Gabriel e Livro Pesquisas no JB). O staging preserva todas as
linhas com dado nas colunas mapeadas (ADR-0012); o clean marca como
`parse_status = "total_row"` a linha com família original e espécie vazias
e quantidade igual à soma das linhas anteriores da mesma aba (soma acumulada
por aba, com ordem explícita), com `needs_review = False` e
`reconcile_across_sources = False`; o load a ignora com log, sem criar
citação. Linha vazia cuja quantidade não bate com a soma continua
`unparseable` (`needs_review = True`).


---

## 3. Pendências

- Canteiro C (já tem `stage_arboreto_canteiro_c.py` e `clean_arboreto_canteiro_c.py` em `scripts/`, faltando o load) e Lista Completa (Sps) do arboreto (ainda não iniciada).
- Limpador de nomes: ainda não integrado.
  Ponto de encaixe já definido: pré-processamento antes de
  `stage_arboretum_*`, substituindo a coluna "Espécie" bruta pela versão
  corrigida, sem mudar o resto do pipeline.
