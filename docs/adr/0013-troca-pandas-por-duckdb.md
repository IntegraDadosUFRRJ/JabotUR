# ADR-0013 — Troca do pandas pelo DuckDB

**Data:** 12/11/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** Complementa o ADR-0012 §1 quanto ao descarte de linhas vazias nas colunas mapeadas e ao fim do uso de openpyxl na leitura (a nota de revisão fica no próprio ADR-0012 §1); preserva a regra do ADR-0008 (conversão de placeholders em NULL no clean); mantém o pandas apenas no Canteiro C (Refs #19, não Closes #19).

---

## Contexto

A leitura das planilhas Excel, o staging e a escrita no Postgres com pandas estavam deixando a execução do pipeline lenta, além de passar todos os dados por DataFrames em memória no Python. Por direção da orientadora e pelo ganho de velocidade com o `ATTACH` (que lê e grava direto no Postgres sem passar as linhas pelo Python), foi definida a troca do pandas pelo DuckDB.

O `CONTRIBUTING.md` pede ADR antes de PR de código, e este PR é a maior mudança de stack do repositório. Além disso, o spike e a implementação em `scripts/staging/xlsx_sheet.py` e `scripts/db/db_utils.py` mostraram diferenças de comportamento entre as duas ferramentas que precisam ficar explicadas:

1. **Inferência de tipos e células de texto em coluna numérica (`read_xlsx`):**
   - Na leitura padrão (`all_varchar = false`, `ignore_errors = false`), o DuckDB infere o tipo de cada coluna pelas primeiras linhas. Se a coluna começa com número e tem um texto mais abaixo (ex.: `4*` em Parcela de Briófitas), ele toma a coluna por numérica e falha a leitura inteira quando chega no texto. No spike, isso quebrava Espécimes, Canteiro C e SPP.
   - Com `ignore_errors = true`, a leitura não aborta, mas a célula inválida vira NULL sem aviso, perdendo o dado em silêncio.
   - Com `all_varchar = true`, nenhum dos dois acontece: tudo entra como texto (`VARCHAR`), e a conversão e a sinalização do que não converte (`parse_status`, `needs_review`) ficam no clean.

2. **Inteiros salvos como `.0` pelo Google Sheets:**
   Quando uma planilha é exportada do Google Sheets para `.xlsx`, os números inteiros ficam gravados no XML interno como ponto flutuante (`1.0`). Como usamos `all_varchar = true`, o DuckDB converte esse float interno direto para texto e devolve `'1.0'` em vez de `'1'`. Se `'1.0'` fosse gravado no staging, a busca de coordenadas da parcela em `config.PLOT_COORDINATES` (`'1'`..`'5'`) falharia e o `int('1.0')` no load daria `ValueError`.

3. **Cálculo de `_source_row`, linhas em branco e topo da planilha:**
   - O padrão do `read_xlsx` é `stop_at_empty = true`. Com ele, as linhas depois da primeira linha em branco no meio da aba nem são emitidas pelo leitor, perdendo registros em silêncio.
   - O `row_number() OVER ()` não serve para numerar o `_source_row` porque, sem `ORDER BY`, a ordem no SQL não é garantida. Além disso, se o `row_number()` fosse aplicado depois de filtrar as linhas vazias, uma linha em branco na linha 5 faria a linha 6 do Excel receber o número 5.
   - Sem um `range` fixo, o `read_xlsx` também pula linhas vazias no topo antes do cabeçalho sem avisar. Se alguém colocasse uma linha vazia na linha 1 e o cabeçalho ficasse na linha 2, a conta do `_source_row` ficaria atrasada em todas as linhas da aba.

**Outras diferenças medidas no spike:**

| O que muda | Antes (pandas / openpyxl) | Agora (DuckDB) |
|---|---|---|
| Strings `'NA'`, `'N/A'`, `'NULL'`, `'None'` | Viravam nulo (`NaN`) já na leitura do pandas | Com `all_varchar = true`, entram como texto no staging (`'NA'` de texto em Espécimes deixa de virar `NULL` na leitura); a conversão para `NULL` fica a cargo do clean (ADR-0008); hoje ele cobre os casos que as planilhas atuais trazem (ver Decisão, item 1) |
| Espaço final no cabeçalho | Continuava no nome da coluna se não tratasse | `read_xlsx` tira o espaço final do cabeçalho sozinho |
| Leitura do Postgres | `read_sql` via SQLAlchemy/psycopg | `ATTACH` lê igual ao pandas, sem passar pelo Python |
| Upsert por `id` com `id` repetido | Ficava com a última linha sem avisar | Levanta `ValueError` antes de gravar (`_raise_if_duplicated_id`) |
| Escrita com `replace` | Tipagem pelo DataFrame | Cria colunas `VARCHAR`, e `HUGEINT` vira `DOUBLE` |
| Ordem dos ids | Ordem `en_US.utf8` | `ORDER BY` do DuckDB, em ordem binária |
| Rede / extensões | Pacotes Python locais | Extensões (`excel`, `postgres`) pedem rede uma vez por versão do DuckDB |

**Tempo medido:** o pipeline completo em `jabotur_test` passou de 3,10 s / 3,55 s (duas medições, com pandas) para 2,19 s / 2,23 s (duas medições, com DuckDB). Depois da troca nos loads, a medição intercalada com o estado anterior deu cerca de 2,0 s contra 2,1 s. São medições simples sobre as planilhas atuais, que indicam a ordem de grandeza e não um benchmark.

## Decisão

DuckDB entra no lugar do pandas, menos no staging e no clean do Canteiro C (`scripts/staging/stage_arboreto_canteiro_c.py` e `scripts/clean/clean_arboreto_canteiro_c.py`), onde o pandas continua por enquanto (Refs #19, não Closes #19).

1. **`read_xlsx` só com `all_varchar = true` e nunca com `ignore_errors`:** strings que o pandas convertia sozinho em `NaN` na leitura (`'NA'`, `'N/A'`, `'NULL'` e `'None'`) passam a ficar como texto no staging — inclusive o `'NA'` de texto em Espécimes, que antes sumia na entrada. O staging não decide o que é ausência: a conversão para `NULL` é do clean. Hoje o clean de Espécimes converte o vazio (e `'-'` em `family`) e o parser do número de registro trata `'NA'`; a cobertura de outros placeholders em colunas de dimensão (como `'N/A'` em `reproductive_status`, ADR-0008) fica para uma issue depois do PR, e nenhuma planilha atual traz esse caso.

2. **Staging o mais fiel possível à fonte (complementando o ADR-0012 §1):** o staging não limpa dado de negócio, mas faz dois cortes estruturais:
   - Tira o `.0` exato de números inteiros usando `regexp_replace("Coluna", '^(-?\d+)\.0$', '\1')`. A regex casa do início (`^`) ao fim (`$`) só com inteiro seguido de `.0` exato: valores como `2.5`, `2.00` e o lacre `RBRv...` passam intactos. Como o `all_varchar = true` transforma tudo em texto logo na entrada, o SQL não tem como saber se a célula era originalmente um número (`1` salvo como `1.0`) ou um texto `"3.0"` digitado à mão. Esse risco é controlado pelo teste `NoTextIntegerFloatCellsTests` em `tests/test_staging_duckdb.py`, que abre as planilhas reais com openpyxl e confere que não existe nenhuma célula do tipo `str` nesse formato `N.0`.
   - Descarta linhas sem dado nas colunas mapeadas com `WHERE coalesce(<colunas mapeadas>) IS NOT NULL`. Como a subquery só busca as colunas do `column_map`, se uma linha tiver dado apenas numa coluna não mapeada (como `Canteiro`, `Procedência` ou `ADICIONAR` em Espécimes, que hoje estão todas vazias), ela sai no filtro. Isso complementa o ADR-0012 §1, que dizia que 100% das linhas do Excel entravam no staging e ainda falava que o leitor era o openpyxl (a nota de revisão fica no próprio ADR-0012 §1).

3. **Cálculo de `_source_row` com `WITH ORDINALITY` e `stop_at_empty = false`:**
   - O `WITH ORDINALITY` anexa ao `read_xlsx` uma coluna `ordinality` numerando cada linha emitida a partir de 1, na posição física em que ela sai da planilha. Como `header = true` consome a linha 1 como cabeçalho, a primeira linha de dados (`ordinality = 1`) é a linha 2 do Excel, então `ordinality + 1` dá o número exato da linha na lateral do Excel.
   - A fórmula `ordinality + 1` só vale se nenhuma linha for pulada antes, então `stop_at_empty = false` é pré-condição do cálculo. Com ele, a linha em branco é emitida como linha de NULLs, ganha número na subquery interna (com `ORDER BY ordinality`) e sai depois no `WHERE` externo, deixando o buraco certo na numeração (ex.: `[2, 3, 4, 6]` quando a linha 5 está vazia).

4. **Verificação do cabeçalho na linha 1 (`_check_header_in_first_row`):** antes de ler a aba, o `xlsx_sheet.py` descobre quantas colunas a tabela tem (`width`) rodando `DESCRIBE SELECT * FROM read_xlsx(...)` e depois lê `range = 'A1:<Letra>1'` com `header = false`. Se `coalesce(*COLUMNS(*))` voltar `None`, levanta `ValueError`. O range vai só até a largura achada (`A1:<width>1`) em vez de `1:1` porque o `.xlsx` suporta até 16.384 colunas (A até XFD), e `1:1` materializaria todas elas à toa. Se a tabela começar deslocada para a direita com as primeiras colunas vazias, `A1:<width>1` também lê `None` e falha.

5. **Transação por load e no `write_staging` (`replace_table`):** em `scripts/db/db_utils.py`, cada load e cada `replace_table` roda dentro de um único `BEGIN ... COMMIT` com `ROLLBACK` se der erro. No staging, o `CREATE OR REPLACE TABLE pg.public.<tabela> AS <query>` lê as abas enquanto executa (em Citações, são três abas num `UNION ALL BY NAME`). Se a leitura falhar no meio (por exemplo, na última aba), o `ROLLBACK` desfaz a troca e sobra a tabela anterior inteira no Postgres.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter o pandas em todo o pipeline | Lento e passa todos os dados pelo Python (DataFrames em memória e SQLAlchemy/psycopg). O DuckDB é mais rápido e, com o `ATTACH`, lê e grava no Postgres direto pelo motor SQL sem passar as linhas pelo Python (decisão tomada com a orientadora em 12/11/2026). |
| `read_xlsx` no padrão ou com `ignore_errors = true` | O padrão parava com erro nas colunas mistas de Espécimes, Canteiro C e SPP; o `ignore_errors` transforma a célula inválida em NULL sem avisar. |
| Numerar `_source_row` com `row_number() OVER ()` ou manter `stop_at_empty = true` | `stop_at_empty = true` perde todas as linhas abaixo da primeira linha em branco; `row_number()` sem `ORDER BY` não garante ordem e, depois do `WHERE`, atrasa a numeração das linhas seguintes. |
| Validar a linha 1 com `range = '1:1'` | Carrega 16.384 colunas na memória para cada aba sem necessidade; `A1:<width>1` já resolve e pega deslocamento. |

## Consequências

**Positivas:**
- Leitura e carga mais rápidas, com o `ATTACH` trafegando os dados direto entre o DuckDB e o Postgres sem passar pelo Python (ver "Tempo medido" no Contexto).
- Célula de texto em coluna numérica não derruba o staging nem vira `NULL` escondido, e `'NA'` em Espécimes não é mais apagado para nulo na leitura bruta (a conversão para `NULL` fica no clean, conforme o ADR-0008).
- Upsert por `id` com `id` repetido no mesmo lote agora levanta `ValueError` antes de gravar (`_raise_if_duplicated_id`) em vez de sobrescrever em silêncio, e erro de leitura no staging não apaga a tabela que já estava no banco.
- O `_source_row` bate com a linha real do Excel mesmo quando há linhas em branco no meio da planilha.

**Negativas / trade-offs aceitos:**
- O `replace_table` não pode ser chamado dentro de `transaction()`, porque ele já abre a própria transação e o DuckDB não aninha transações.
- Sem o openpyxl no SQL não dá para saber se `"3.0"` veio de número ou de texto; a proteção disso depende de rodar o teste `NoTextIntegerFloatCellsTests` sobre as planilhas.
- A ordem dos ids gerados muda porque o `ORDER BY` do DuckDB usa ordem binária (antes era `en_US.utf8`).
- As extensões do DuckDB pedem rede uma vez a cada versão nova instalada.
- O openpyxl continua nos requisitos por causa dos testes, e o pandas continua até fechar a issue #19.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `scripts/staging/xlsx_sheet.py`, `scripts/staging/stage_arboretum_specimens.py`, `scripts/staging/stage_arboretum_citations.py`, `scripts/staging/stage_spp_bryophytes.py`, `scripts/db/db_utils.py`, `tests/test_staging_duckdb.py`, `tests/test_db_utils_duckdb.py`, `docs/processos_de_etl.md`, `docs/panorama_tecnico_jabotur.md` e ADR-0012 (`docs/adr/0012-linhas-de-totais-sinalizadas.md`).
- Esquema: no staging, o replace cria as colunas como `VARCHAR` e transforma `HUGEINT` em `DOUBLE`; nas tabelas finais vale o `schema.sql` (ver ADR-0014).
- Precisa de migração? Não. Não há arquivo em `migrations/` (a pasta sai no ADR-0014); no banco local, apagar e rodar o pipeline do zero.
- É retroativo? Sim, muda o staging e a carga de Citações, Espécimes e SPP; Canteiro C não muda agora.
- Validação exigida: rodar `unittest` em `tests/test_staging_duckdb.py` e `tests/test_db_utils_duckdb.py` no banco `_test`, recriar o banco local e rodar o pipeline duas vezes seguidas conferindo que as contagens permanecem iguais.

## Referências

- Issue/PR relacionado: Issue #19 (Refs #19)
- Trecho do `panorama_tecnico_jabotur.md` ou DER afetado: `docs/panorama_tecnico_jabotur.md` (camada de staging e stack), `docs/processos_de_etl.md`, `CONTRIBUTING.md`, ADR-0008, ADR-0012 (`docs/adr/0012-linhas-de-totais-sinalizadas.md`) e ADR-0014
