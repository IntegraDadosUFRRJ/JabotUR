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

**Staging:** carga bruta, sem transformação nenhuma. A planilha é lida e
gravada quase inalterada direto no PostgreSQL. O único acréscimo aqui é lineage: 
arquivo de origem, aba e linha (`_source_file`/`_source_sheet`/`_source_row`), 
que acompanha o dado até a tabela final.

**Clean:** segunda camada de tabelas, recebendo o staging. Aqui sim
acontece transformação: limpeza de digitação, fill-down, normalização de
vocabulário, parsing de campos compostos. A transformação roda em DuckDB
(motor SQL efêmero, só em memória, nunca persiste nada por conta própria)
dentro da função `transform()` de cada fonte. **Regra central: clean
nunca descarta linha.** Problema de qualidade de dado vira **coluna**
(`parse_status`, `needs_review`, `reconcile_across_sources`, conforme a
fonte), nunca uma linha removida ou um dataframe separado. Quem decide o
que fazer com a sinalização é a camada de load, não o clean.

**Load:** lê a tabela clean e resolve pras tabelas normalizadas finais no
Postgres. A resolução de chave natural (get-or-create) é feita inteiramente
em **Python puro** (`load/taxonomy.py`), não em SQL, um dict com tupla
como chave decide se uma família/gênero/autor/espécie já existe ou precisa
de um id novo. Isso é o que garante que a mesma espécie citada em fontes
diferentes resolva pro mesmo registro. A gravação em si usa
`db_utils.write_dataframe_to_postgres` com um modo explícito por
tipo de tabela: `"replace"` pra staging/clean, `"upsert"` por `id` pra
dimensões/fatos, `"append_composite"` pra tabelas associativas.

Toda fonte nova segue essas três camadas, reaproveitando `taxonomy.py`
sempre que o conceito for compartilhado (família/gênero/autor/epíteto) e
só criando tabela/lógica nova para o que for exclusivo daquela fonte.

---

## 2. Regras de transformação por fonte

### 2.1 SPP (Briófitas)

| Coluna | Regra |
|---|---|
| Parcela | Fill-down; remover "\*4" e substituir por "4" |
| Amostra | Fill-down |
| StatusIdentificacao | Significado em tabela externa, conforme legenda |
| Filo | Juntar sigla + nome completo |
| Família | Transpor os dados |
| Gênero | Transpor os dados |
| Espécie | Vira `epiteto_especifico` remover a abreviação de gênero que a planilha traz embutida, sobra só o epíteto |
| Autor | Transpor os dados |
| Forma de Vida | Ausente -> NULL |
| Substrato | Fill-down; significado da sigla via legenda; multivalorado, separado por "+" |
| Observações | Conversões pontuais (`"poste de cimento"`/`"cimento de placa de pau brasil"` -> `"cimento"`, `"acro [fotos]"` -> `"acro"`); ausente -> `"sem observações registradas"`; multivalorado por ";" |

### 2.2 Arboreto — observações gerais sobre a coluna "Espécie"

A coluna de espécie do arboreto não segue um padrão único, o parser
(`transforms/nome_cientifico.py`) precisa cobrir, todos vistos em dados
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
- **Morfo-espécie**: placeholder tipo `"Morfo-Espécie 1"` pra espécime
  ainda não identificado a nível de espécie/gênero
- **Qualificador de incerteza**: `"Handroanthus cf ochraceus (Cham.)
  Mattos"`, "cf"/"aff" entre gênero e epíteto, indicando identificação
  não confirmada

Ver `JabotUR_DER.md` (nota em `epiteto_especifico`) pra decisão de produto
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

> **Nota importante sobre Extração (Excel):** A biblioteca `openpyxl` lê nativamente as linhas ocultas/filtradas das planilhas Excel. Isso é relevante para a fonte do Arboreto (Espécimes e Canteiro C estão na mesma planilha com filtros aplicados), exigindo que a extração limpe o que não pertence à aba/visão desejada.

| Coluna | Regra |
|---|---|
| Família | Transpor os dados |
| Espécie | Script de parsing (mesmo do item 2.2) |
| Origem | Canonicalizar "Exótico"/"Exótica" para um valor único; `"na"`/vazio -> NULL |
| Domínio fitogeográfico | Multivalorado por vírgula; `"na"`/vazio -> nenhuma linha inserida na tabela associativa `species_domain` (ver ADR-0008), nunca criar um domínio "N/A" |
| Grau de Ameaça (Categoria CNCFlora) | Uppercase; `"na"`/vazio -> código IUCN real `NA` (ADR-0005), nunca NULL |
| Numeração lacre | Sem prefixo "RBRv" = lacre azul, mesmo sem a palavra "AZUL" escrita (ADR-0009) |
| Localização canteiro | "SCC1-4" e "S2C2"/"S2C4" são códigos legítimos (confirmados contra o Setor real de Espécimes), mapeados para o mesmo `sector` compartilhado |
| Altura (m) | Linhas 183, 184 e 185 têm erro de digitação que passa incólume pela coerção numérica, forçar NULL nestas linhas e flagar o status |

*(Ainda não implementado.)*

### 2.6 Arboreto — Citações bibliográficas (Monografia Gabriel, Livro Pesquisas no JB, JABOT)

As 3 abas compartilham estrutura idêntica, um script parametrizado por
fonte em vez de três quase iguais.

| Coluna | Regra |
|---|---|
| Família | Fill-down |
| Espécie | Script de parsing (mesmo do item 2.2) |
| Quant | Transpor os dados |


---

## 3. Pendências

- Canteiro C e Lista Completa (Sps) do arboreto: staging/clean/load ainda não integrados/escritos.
- Limpador de nomes: ainda não integrado.
  Ponto de encaixe já definido: pré-processamento antes de
  `stage_arboreto_*`, substituindo a coluna "Espécie" bruta pela versão
  corrigida, sem mudar o resto do pipeline.
- Testes automatizados: adiados até o schema do arboreto estabilizar.
