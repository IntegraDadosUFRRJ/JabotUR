# Dicionário de Dados — JabotUR

> Consolida `Dicionario_Colunas_em_Comum.pdf`, `Legendas_Tabela_Briófitas.pdf` e
> `Formas_de_Registro_em_Comum_entre_as_Bases.pdf`. Manter este arquivo como fonte
> única daqui pra frente, os PDFs originais ficam como referência histórica.
> Ligado a `JabotUR_DER.md` (schema) e ao `panorama_tecnico_jabotur.md` (decisões).

---

## 1. Núcleo taxonômico comum a todas as fontes

Toda planilha de origem segue, no mínimo: **Família, Gênero, Epíteto Específico**.
`Infraespecífico` (ex.: `var.`) nem sempre tem coluna própria, mas o conceito existe
em todas, indica "derivação" de outro táxon.

**Diferença estrutural crítica entre os dois grupos de fontes:**

| | Briófitas (SPP) | Arboreto (todas as abas — JB) |
|---|---|---|
| Coluna "Espécie" contém | só o epíteto (gênero abreviado: `O. albidum`) | string única sem separador: Gênero + Epíteto + Infraespecífico + **Autor** |
| Autor | coluna própria (`Autor`) | embutido dentro de "Espécie" — por isso `transforms/scientific_name.py` existe só pro lado arboreto |
| Exemplo bruto | `O. albidum` (autor em coluna separada) | `Astronium urundeuva (M.Allemão) Engl.` |
| Identificador normalizado (ADR-0010) | `epithet` | `species_raw` (antes do parsing) |

**Tipos no banco (`scripts/db/schema.sql`) e `id_species` nulo:** nas tabelas finais, identificadores (`id`), chaves estrangeiras (`id_*`), `sample`, `quantity` e `origin_row` são `bigint`; textos são `text`; `height_m` é `double precision`. Em `occurrence`, a coluna `id_species` aceita `NULL` para registrar ocorrências de Espécimes sem identificação botânica (`load_arboretum_specimens.py`, linhas 80–90) e, futuramente, árvores mortas do Inventário.

## 2. Colunas por fonte (nome original -> coluna normalizada)

Legenda: [#] atenção a nomenclatura divergente entre fontes.

### SPP (briófitas)
| Original | Normalizado | Observação |
|---|---|---|
| Parcela | `plot` | fill-down; valores "1" a "5" e "aleat" |
| Amostra | `sample` | fill-down |
| StatusIdentificacao* | `identification_status` [#] | também aparece como "identificação" em outras fontes; ver seção 4 |
| Filo | `phylum` | só existe pra briófitas (arboreto fica NULL (ADR-0004)) |
| Família | `family` | |
| Gênero | `genus` | |
| Espécie | `epithet` [#] | `transforms/epithet.py` remove a abreviação de gênero, tira `cf.`/`aff.` para `occurrence.identification_qualifier` (ADR-0006) e converte vazio, `sp` ou `sp.` (`G. sp.`, `G. sp`, `G.`) em `None` (gênero-só, ADR-0003); contrasta com `species_raw` do arboreto |
| Autor | `author` | coluna própria |
| Forma de Vida | `life_form` | |
| Substrato | `substrate` | multivalorada (separada por `transforms/substrate.py`); ver nota sobre "alt" na seção 3 |
| Observações | `remark` (staging) / `remarks` (clean) [#] | mapeada por `SPP_COLUMN_MAP` para `remark` no staging e gravada como `remarks` em `clean_spp_bryophytes.sql` |

### Arboreto — Citações (Monografia Gabriel / Livro Pesquisas no JB / JABOT)
| Original | Normalizado | Observação |
|---|---|---|
| Família | `family` | fill-down |
| Espécie | `species_raw` -> parseada em `genus`/`epithet`/`infraspecific`/`author`/`identification_qualifier` | via `transforms/scientific_name.py` (ADR-0010) |
| Quant | `quantity` | |

### Arboreto — Espécimes
| Original                 | Normalizado                                      | Observação                               |
| --------------------------| --------------------------------------------------| ------------------------------------------|
| Família                  | `family`                                         |                                          |
| Espécie                  | `species_raw` -> parseada igual citações         | via `transforms/scientific_name.py`      |
| N° de registro           | `registration_number`                            | ver regra do lacre azul, seção 4         |
| Setor                    | `sector`                                         |                                          |
| Descrição da localização | `location_description`                           | maioria NULL, nunca virar string `"N/A"` |
| Estado reprodutivo       | `reproductive_status`                            | valores confirmados: "Adulto"/"jovem"  |

### Arboreto — Canteiro C
| Original na Planilha | Normalizado (Inglês — ADR-0010) | Observação de Negócio / Regra de ETL |
|---|---|---|
| (sem cabeçalho, 1ª coluna) | `familia` (`family`) | renomeação posicional obrigatória; fill-down não aplicável |
| Gênero | `genero` (`genus`) | preenchido na fonte; validado no parsing taxonômico |
| Espécie | `species_raw` | string composta bruta com epíteto, infraespecífico e autor; parseada via `transforms/scientific_name.py` em `genero`, `epithet`, `infraspecific`, `author`, `identification_qualifier` |
| Autor | embutido em `species_raw` | extraído pelo parser botânico |
| Origem | `origin` [#] | variante de grafia "Exótico"/"Exótica", canonizar pra "Exótica"; `"na"`/vazio -> NULL. Mapeia para `species_status.origin` |
| Domínio Fitogeográfico | `phytogeographic_domain` | multivalorada (vírgula); `"na"`/vazio -> nenhuma linha na tabela associativa `species_domain` (ADR-0008) |
| Grau de Ameaça | `conservation_status` | código IUCN em maiúsculas; `"na"`/vazio -> código IUCN real `NA` (Not Applicable, ADR-0005), nunca NULL. Mapeia para `conservation_status.code` |
| Numeração Lacre | `registration_number` | lacre azul prevalece sobre amarelo (RBRv); sem prefixo = lacre azul (ADR-0009). Mapeia para `occurrence_arboretum.registration_number` |
| Localização Canteiro | `sector_location` | códigos de setor/canteiro (ex.: "SCC1-4", "S2C2", "S2C4"); mapeados para a dimensão compartilhada `sector.name` (não confundir com `location_description` de Espécimes) |
| Altura (m) | `height_m` | conversão para número; linhas 183, 184 e 185 possuem erros de digitação e são forçadas para NULL. Mapeia para `occurrence_arboretum.height_m` |

### Arboreto — Lista Completa Sps (não iniciado)
| Original | Normalizado (Inglês — ADR-0010) | Observação |
|---|---|---|
| Família / Gênero / Espécie / Autor | `familia` (`family`) / `genero` (`genus`) / `species_raw` / `author` | igual às demais fontes de Arboreto |
| Distribuição | -> `species_country`/`species_state`/`species_geographic_area` | sem padrão fixo, mistura estado, país, continente e frases livres tipo "Kênia até Moçambique", "W. Indian Ocean", "Tropical & Subtropical Asia to Pacific"; decompor quando possível, cair em `species_geographic_area.description` (texto livre) quando não |
| Domínios Fitogeográfico | `phytogeographic_domain` | igual Canteiro C |
| Grau de Ameaça | `conservation_status` | igual Canteiro C | |

## 3. Legendas de código (valores controlados)

**FILO** (`PHYLUM_NAME_MAP` em `config.py`, só briófitas; o `id` em `phylum` vem da ordem do get-or-create)
| sigla | nome |
|---|---|
| H | Hepáticas |
| M | Musgos |

**Substrato** (`SUBSTRATE_NAME_MAP` em `config.py`)
| Sigla | Nome |
|---|---|
| RZ | Raiz de árvore |
| S | Solo |
| TD | Tronco em decomposição |
| TV | Tronco vivo |
| A | Artificial |

> **Nota sobre a sigla "alt" em Substrato:** A entrada `"alt": "amostragem aleatória"` que antes existia em `SUBSTRATO_NOME_MAP` **foi removida** de `config.SUBSTRATE_NAME_MAP`. "Amostragem aleatória" refere-se à metodologia de coleta da Parcela (`plot = 'aleat'`), não a uma superfície física de fixação de briófitas (substrato). O módulo agora se chama `transforms/substrate.py` (e converte tokens para maiúsculas com `key = token.upper()`).

**StatusIdentificacao** (`IDENTIFICATION_STATUS_DESCRIPTION_MAP`)
| Código | Descrição |
|---|---|
| 1 | Identificada |
| 2 | Parcialmente Identificada |
| 3 | Dúvida |

**Observações — abreviações expandidas** (`REMARK_REGEX_FIXES`)
| Abreviação | Expansão |
|---|---|
| acro | acrocárpico |
| pleuro | pleurocárpico |
| c. esp / c/esp | com esporófito |

**Parcelas — coordenadas** (`PLOT_COORDINATES`)
| Código | Coordenada |
|---|---|
| I / 1 | 22° 45' 54.2"S 43° 41' 31.1"O |
| II / 2 | 22° 45' 57.3"S 43° 41' 34"O |
| III / 3 | 22° 45' 54.3"S 43° 41' 33.7"O |
| IV / 4 | 22° 45' 54.9"S 43° 41' 34.5"O |
| V / 5 | 22° 45' 59.3"S 43° 41' 37.5"O — _não estava no CSV original, só no PDF;_ |
| aleat | NULL (coletas por amostragem aleatória fora de parcela fixa) |

**Conservation status (IUCN)** — `NE`, `LC`, `VU`, `EN`, `NT`, `NA`. `NA` = "Not Applicable", valor semântico real (ver ADR-0005).

## 4. Regras de negócio entre fontes

- **Lacre azul**: qualquer número de registro **sem prefixo "RBRv"** é lacre azul, mesmo sem a palavra "AZUL" escrita. Quando os dois lacres (amarelo `RBRv...` e azul) existem na mesma linha, o azul prevalece (ver ADR-0009). Valores `"NA"` ou vazios no N° de registro devem ser convertidos para `NULL`.
- **Setor**: valores numéricos lidos como decimais pelo Excel (ex.: `"3.0"`, `"4.0"`) devem ser normalizados para suas strings inteiras equivalentes (`"3"`, `"4"`).
- **"na" em Grau de Ameaça** -> código IUCN `NA` (Not Applicable). Não é ausência de dado, é uma decisão que sobrepõe a leitura literal da planilha.
- **Domínio Fitogeográfico e Substrato** são campos multivalorados (separados por vírgula), sempre viram bridge table, nunca string crua na dimensão.
- **`identificacao`/`identificação`/`StatusIdentificacao*`**: mesmo conceito, três grafias diferentes entre fontes, cuidado ao integrar fonte nova que reuse esse campo.
- **Linhas de totais (Citações)**: a última linha de Monografia Gabriel e de Livro Pesquisas no JB é um somatório (família e espécie vazias, quantidade igual à soma das linhas anteriores da aba). É preservada no staging e no clean com `parse_status = "total_row"` e ignorada no load (ADR-0012). A aba JABOT não tem linha de totais.
- **Resolução da ambiguidade da coluna `especie` (`species_raw` vs `epithet`)**: Conforme padronizado pelo ADR-0010 para sanar a ambiguidade conceitual de nomenclatura entre fontes:
  - Nas fontes de Arboreto (Citações, Espécimes, Canteiro C e Lista Completa), a coluna de entrada na planilha traz uma string composta bruta (Gênero + Epíteto + Infraespecífico + Autor) e é mapeada na camada intermediária como `species_raw`. Essa coluna é então processada por `transforms/scientific_name.py`, que extrai `genus`, `epithet`, `infraspecific`, `author` e `identification_qualifier`.
  - Na fonte SPP (Briófitas), a coluna da planilha contém exclusivamente o epíteto específico (a abreviação de gênero pré-fixada, ex.: `"O. "`, é descartada no clean), sendo padronizada como `epithet` (ou `epiteto_especifico` no schema legado).
  - No banco de dados relacional final, ambas as fontes convergem perfeitamente para a dimensão compartilhada `species` (`species.epithet`).
- **Tratamento de `"aleat"` em Parcela (SPP)**: Na fonte SPP (Briófitas), ocorrências coletadas por amostragem aleatória fora das parcelas fixas 1–5 trazem o valor textual `"aleat"` na coluna `Parcela`. O pipeline preserva esse valor no staging (`stg_spp_bryophytes`) e no clean (`cln_spp_bryophytes`) sem descartar linhas nem forçar para `NULL`, propagando o valor por fill-down. No carregamento (`scripts/load/load_spp_bryophytes.py`), cria-se uma linha válida na dimensão `plot` com `code = 'aleat'` e coordenadas geográficas `NULL` (pois `config.PLOT_COORDINATES.get("aleat")` retorna `None`). Essas ocorrências na tabela satélite `occurrence_bryophyte` recebem a chave estrangeira `id_plot` apontando para esse registro. (A entrada `"alt": "amostragem aleatória"`, que antes ficava em `SUBSTRATE_NAME_MAP`, era um resíduo da legenda antiga sobre esse mesmo método de amostragem de Parcela e já saiu de `config.py`).
- **Localização em Canteiro C (`sector_location`) vs Espécimes (`location_description`)**:
  - Em Arboreto — Espécimes, a coluna `descricao_localizacao` (`location_description`) armazena descrições textuais livres de localização (ex.: "próximo à cerca"), mapeadas para `occurrence_arboretum.location_description`.
  - Em Arboreto — Canteiro C, a coluna "Localização Canteiro" armazena códigos estruturados de setor/canteiro (ex.: `"SCC1-4"`, `"S2C2"`, `"S2C4"`), que resolvem diretamente para a dimensão compartilhada `sector.name` (a mesma utilizada por Espécimes). Para refletir com exatidão essa semântica e evitar confusão entre conceitos, a coluna de Canteiro C é nomeada `sector_location`, e não `location_description`.

## 5. Pendências deste dicionário

- [ ] Preencher seção da Lista Completa Sps com mais detalhe quando essa fonte for iniciada
- [ ] Adicionar seção equivalente para a fonte nova, assim que definida
