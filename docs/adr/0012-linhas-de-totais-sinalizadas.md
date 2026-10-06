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

2. **Linhas Ocultas / Filtradas pelo Usuário (Espécimes e Canteiro C):**
   A biblioteca `openpyxl` (utilizada pelo `pandas.read_excel`) lê integralmente todas as linhas da planilha, ignorando se estão visualmente ocultas ou filtradas no Excel.
   - Na aba Espécimes, das 376 linhas brutas carregadas no staging, **84 correspondem a linhas originalmente ocultas no Excel**. Dessas 84 linhas, **82 não possuem setor preenchido**, e 10 possuem nomes populares ou placeholders ("Cássia Rosa" ×4, "sem identificação" ×6).
   - Tentar filtrar linhas pelo estado de visibilidade visual do Excel na extração introduz dependência frágil de propriedades de exibição gráfica do software cliente.

## Decisão

1. **O Staging preserva integralmente todas as linhas:**
   - O comando `iloc[:-1]` é permanentemente removido de `stage_arboreto_citations.py` (totalizando 336 linhas staged).
   - O leitor de `openpyxl` extrai todas as linhas da planilha, visíveis ou ocultas (376 linhas em Espécimes).

2. **A camada Clean classifica e sinaliza declarativamente:**
   - **Totais de Citações:** Identificados quando família e espécie são vazias e a quantidade coincide exatamente com a soma das linhas anteriores da aba. Recebem `parse_status = "total_row"` e `needs_review = False`. A soma de controle é validada e registrada no log. Linhas vazias que não batem com a soma permanecem como `unparseable` e `needs_review = True`.
   - **Linhas Ocultas de Espécimes:** Preservadas em `cln_arboreto_specimens` com todas as suas colunas (incluindo `sector = NULL` quando ausente). Registros com nomes populares ou placeholders recebem `needs_review = True` e `parse_status` correspondente.

3. **A camada Load decide a inserção nos fatos com log explícito:**
   - Linhas com `parse_status = "total_row"` são ignoradas pelo loader de Citações, sem gerar registros em `bibliographic_citation`.
   - Registros de Espécimes com pendência de identificação (`needs_review = True` / espécie não resolvida) são pulados na criação de `occurrence`, com emissão de log informativo por linha. Registros ocultos que contêm identificação botânica válida e consistente são carregados normalmente.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter `iloc[:-1]` no staging de Citações | Descarte silencioso que eliminou uma citação legítima da aba JABOT. |
| Inspecionar flags de linha oculta (`ws.row_dimensions[row].hidden`) no openpyxl | Acopla a lógica de extração a configurações de visualização do Excel; ignora espécimes válidos que possam ter sido ocultados acidentalmente por filtros salvos pelo usuário. |
| Descartar linhas de totais ou ocultas direto no staging | Viola o princípio de que staging é o espelho fiel do dado bruto sem transformação. |

## Consequências

**Positivas:**
- Rastreabilidade total: 100% das linhas do arquivo Excel entram no staging e no clean.
- A linha de totais é aproveitada como validação de integridade matemática por aba.
- Nenhuma citação ou espécime legítimo é perdido por filtros de interface gráfica.
- Contagens de citações passam a bater exatamente: 336 staged, 336 cleaned, 334 citações carregadas no banco e 2 linhas de totais ignoradas.

**Negativas / trade-offs aceitos:**
- Introdução do novo status `total_row` e verificação de soma por aba no clean.
- Necessidade de log explícito na camada de load ao ignorar linhas não registráveis.

## Referências

- ADR-0001, ADR-0003, ADR-0008, ADR-0010, ADR-0011
- `panorama_tecnico_jabotur.md` §1 e §3
- `processos_de_etl.md` §2.4, §2.5 e §2.6
