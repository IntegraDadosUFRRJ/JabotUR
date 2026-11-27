# ADR-0012 — Preservação e sinalização de linhas de totais e linhas ocultas do Excel

**Data:** 05/10/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** Consolida a diretriz "staging é dado bruto sem perdas" e "clean nunca descarta registros" (`panorama_tecnico_jabotur.md` §1); complementa ADR-0003 e ADR-0008.

---

## Contexto

Planilhas legadas de Excel frequentemente contêm linhas que não representam espécimes individuais diretos, apresentando-se em duas formas principais:

1. **Linhas de Totais (Citações):**
   O staging de Citações continha a instrução `df = df.iloc[:-1]`, que removia a última linha de cada aba sem analisar o conteúdo. A investigação de 02/10/2026 revelou que:
   - Em *Monografia Gabriel* e *Livro Pesquisas no JB*, as últimas linhas eram de fato somatórios (362 e 212 espécimes), com família e espécie em branco.
   - Na aba *JABOT*, a última linha era um espécime botânico real (*Citharexylum myrianthum*, quantidade 4), descartado inadvertidamente pelo corte cego.

2. **Linhas Ocultas / Filtradas pelo Usuário (Espécimes):**
   O leitor `read_xlsx` do DuckDB (`scripts/staging/xlsx_sheet.py`, que substituiu o `openpyxl` / `pandas.read_excel` conforme o **ADR-0013**) lê todas as linhas da planilha, visíveis ou ocultas no Excel (o Canteiro C não tem linhas ocultas e não passa por `xlsx_sheet.py`).
   - Na versão anterior da aba Espécimes havia linhas originalmente ocultas no Excel sem setor preenchido e linhas com nomes populares ou placeholders ("Cássia Rosa", "sem identificação"); a planilha atual (`data/arboretum_floristic_diversity.xlsx`) não traz mais linhas ocultas, mas o `read_xlsx` continua lendo linhas ocultas se existirem.
   - Tentar filtrar linhas pelo estado de visibilidade do Excel na extração acoplaria a leitura a propriedades visuais do arquivo.

## Decisão

1. **O Staging preserva todas as linhas que têm dado nas colunas mapeadas:**
   - O corte `iloc[:-1]` foi removido de `stage_arboretum_citations.py` (antigo `stage_arboreto_citations.py`).
   - O `read_xlsx` do DuckDB em `scripts/staging/xlsx_sheet.py` (com `all_varchar = true` e `stop_at_empty = false`) extrai todas as linhas visíveis ou ocultas da aba.
   - *(Nota de revisão)* Linha sem nenhum dado **nas colunas mapeadas** pelo `column_map` não é registro e não entra no staging: o filtro em `scripts/staging/xlsx_sheet.py` é `WHERE coalesce(<colunas mapeadas>) IS NOT NULL`. Se uma linha tiver valor apenas em coluna fora do `column_map` (como `Canteiro`, `Procedência` ou `ADICIONAR` em Espécimes), ela também fica de fora.

2. **A camada Clean classifica e sinaliza declarativamente:**
   - **Totais de Citações:** Identificados quando a família **original** (antes do fill-down, preservada em `family_raw`) e a espécie são vazias e a quantidade coincide exatamente com a soma das linhas anteriores da mesma aba (soma acumulada por aba, com `ORDER BY` explícito, calculada na própria query DuckDB do clean). Recebem `parse_status = "total_row"`, `needs_review = False` e `reconcile_across_sources = False` (a linha não representa um táxon). A soma de controle é validada e registrada no log, por aba. Linhas vazias que não batem com a soma permanecem como `unparseable` e `needs_review = True`.
   - **Linhas Ocultas de Espécimes:** Preservadas em `cln_arboretum_specimens` com todas as suas colunas (incluindo `sector = NULL` quando ausente). Registros com nomes populares ou placeholders recebem `needs_review = True` e `parse_status` correspondente.

3. **A camada Load decide a inserção nos fatos com log explícito:**
   - Linhas com `parse_status = "total_row"` são ignoradas pelo loader de Citações, sem gerar registros em `bibliographic_citation`.
   - *(Nota de revisão)* Linhas de Espécimes com pendência de identificação (sem gênero e sem epíteto, marcadas com `needs_review = True` no clean, como "sem identificação" e nomes populares que caem em `unparseable`) **não são puladas**: elas entram em `occurrence` com `id_species = NULL` (`scripts/load/load_arboretum_specimens.py`). As demais linhas com `needs_review = True` (que têm gênero ou epíteto) também são carregadas normalmente e permanecem sinalizadas em `cln_arboretum_specimens`.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter `iloc[:-1]` no staging de Citações | Descarte silencioso que eliminou uma citação legítima da aba JABOT. |
| Inspecionar flags de linha oculta (`ws.row_dimensions[row].hidden`) no openpyxl | Acopla a lógica de extração a configurações de visualização do Excel; ignora espécimes válidos que possam ter sido ocultados acidentalmente por filtros salvos pelo usuário. |
| Descartar linhas de totais ou ocultas direto no staging | Viola o princípio de que staging é o espelho fiel do dado bruto sem transformação. |

## Consequências

**Positivas:**
- Rastreabilidade total: todas as linhas com dado nas colunas mapeadas entram no staging e no clean.
- A linha de totais é aproveitada como validação de integridade matemática por aba.
- Nenhuma citação ou espécime legítimo é perdido por filtros de interface gráfica.
- As contagens de citações entre staging, clean e banco batem descontando as linhas de totais e as linhas sem espécie, que o load de Citações ignora com log (`load_arboretum_citations.py`).

**Negativas / trade-offs aceitos:**
- Introdução do novo status `total_row` e verificação de soma por aba no clean.
- Necessidade de log explícito na camada de load ao ignorar linhas não registráveis.

## Referências

- ADR-0001, ADR-0003, ADR-0008, ADR-0010, ADR-0011
- `panorama_tecnico_jabotur.md` §1 e §3
- `processos_de_etl.md` §2.4, §2.5 e §2.6
