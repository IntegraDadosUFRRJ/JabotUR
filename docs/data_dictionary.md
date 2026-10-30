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
| Autor | coluna própria (`Autor`) | embutido dentro de "Espécie" — por isso `transforms/nome_cientifico.py` existe só pro lado arboreto |
| Exemplo bruto | `O. albidum` (autor em coluna separada) | `Astronium urundeuva (M.Allemão) Engl.` |
| Identificador normalizado (ADR-0010) | `epithet` | `species_raw` (antes do parsing) |

## 2. Colunas por fonte (nome original -> coluna normalizada)

Legenda: [#] atenção a nomenclatura divergente entre fontes.

### SPP (briófitas)
| Original | Normalizado | Observação |
|---|---|---|
| Parcela | `parcela` (`plot` no ADR-0010) | fill-down; valores "1" a "5" e "aleat" |
| Amostra | `amostra` (`sample` no ADR-0010) | fill-down |
| StatusIdentificacao* | `identificacao` [#] | também aparece como "identificação" em outras fontes; ver seção 4 |
| Filo | `filo` (`phylum` no ADR-0010) | só existe pra briófitas (arboreto fica NULL (ADR-0004)) |
| Família | `familia` (`family` no ADR-0010) | |
| Gênero | `genero` (`genus` no ADR-0010) | |
| Espécie | `epithet` (`epiteto_especifico` legado) [#] | contém só o epíteto aqui (gênero abreviado removido no clean); contrasta com `species_raw` de Arboreto (ver ADR-0010 e seção 4) |
| Autor | `autor` (`author` no ADR-0010) | coluna própria |
| Forma de Vida | `forma_vida` (`life_form` no ADR-0010) | |
| Substrato | `substrato` (`substrate` no ADR-0010) | multivalorada (separada por transform); ver resíduo de "alt" na seção 3 |
| Observações | `observacao` [#] (`remark` no ADR-0010) | aparece como "observacoes" em código legado, `clean_SPP._to_duckdb_table` normaliza os dois nomes |

### Arboreto — Citações (Monografia Gabriel / Livro Pesquisas no JB / JABOT)
| Original | Normalizado | Observação |
|---|---|---|
| Família | `familia` (`family`) | fill-down |
| Espécie | `species_raw` -> parseada em `genus`/`epithet`/`infraspecific`/`author`/`identification_qualifier` | via `transforms/nome_cientifico.py` (ADR-0010) |
| Quant | `quantidade` (`quantity`) | |

### Arboreto — Espécimes
| Original                 | Normalizado                                      | Observação                               |
| --------------------------| --------------------------------------------------| ------------------------------------------|
| Família                  | `familia` (`family`)                             |                                          |
| Espécie                  | `species_raw` -> parseada igual citações         | via `transforms/nome_cientifico.py`      |
| N° de registro           | `numero_registro` (`registration_number`)        | ver regra do lacre azul, seção 4         |
| Setor                    | `setor` (`sector`)                                        |
| Descrição da localização | `descricao_localizacao` (`location_description`) | maioria NULL, nunca virar string `"N/A"` |
| Estado reprodutivo       | `estado_reprodutivo` (`reproductive_status`)     | valores confirmados: "Adulto"/"jovem"  |

### Arboreto — Canteiro C
| Original na Planilha | Normalizado (Inglês — ADR-0010) | Observação de Negócio / Regra de ETL |
|---|---|---|
| (sem cabeçalho, 1ª coluna) | `familia` (`family`) | renomeação posicional obrigatória; fill-down não aplicável |
| Gênero | `genero` (`genus`) | preenchido na fonte; validado no parsing taxonômico |
| Espécie | `species_raw` | string composta bruta com epíteto, infraespecífico e autor; parseada via `transforms/nome_cientifico.py` em `genero`, `epithet`, `infraspecific`, `author`, `identification_qualifier` |
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

**FILO** (só briófitas)
| id | nome | sigla |
|---|---|---|
| 1 | Hepáticas | H |
| 2 | Musgos | M |

**Substrato** (`SUBSTRATO_NOME_MAP` em `config.py`)
| Sigla | Nome |
|---|---|
| RZ | Raiz de árvore |
| S | Solo |
| TD | Tronco em decomposição |
| TV | Tronco vivo |
| A | Artificial |
| alt | amostragem aleatória _(anomalia legada; ver nota abaixo)_ |

> **Nota sobre a sigla "alt" em Substrato:** A entrada `"alt": "amostragem aleatória"` em `config.SUBSTRATO_NOME_MAP` é um resíduo histórico da interpretação inicial das legendas. "Amostragem aleatória" refere-se à metodologia de coleta da Parcela (`parcela = 'aleat'`), e não a uma superfície física de fixação de briófitas (substrato). Além disso, a rotina `transforms/substrato.py` converte tokens para maiúsculas (`key = token.upper()`), portanto a chave minúscula `"alt"` não é ativada em tempo de execução.

**StatusIdentificacao** (`IDENTIFICACAO_DESCRICAO_MAP`)
| Código | Descrição |
|---|---|
| 1 | Identificada |
| 2 | Parcialmente Identificada |
| 3 | Dúvida |

**Observações — abreviações expandidas** (`OBSERVACAO_REGEX_FIXES`)
| Abreviação | Expansão |
|---|---|
| acro | acrocárpico |
| pleuro | pleurocárpico |
| c. esp / c/esp | com esporófito |

**Parcelas — coordenadas** (`PARCELA_COORDENADAS`)
| Código | Coordenada |
|---|---|
| I / 1 | 22° 45' 54.2"S 43° 41' 31.1"O |
| II / 2 | 22° 45' 57.3"S 43° 41' 34"O |
| III / 3 | 22° 45' 54.3"S 43° 41' 33.7"O |
| IV / 4 | 22° 45' 54.9"S 43° 41' 34.5"O |
| V / 5 | 22° 45' 59.3"S 43° 41' 37.5"O — _não estava no CSV original, só no PDF;_ |
| aleat | NULL (coletas por amostragem aleatória fora de parcela fixa; 14 ocorrências em SPP) |

**Conservation status (IUCN)** — `NE`, `LC`, `VU`, `EN`, `NT`, `NA`. `NA` = "Not Applicable", valor semântico real (ver ADR-0005).

## 4. Regras de negócio entre fontes

- **Lacre azul**: qualquer número de registro **sem prefixo "RBRv"** é lacre azul, mesmo sem a palavra "AZUL" escrita. Quando os dois lacres (amarelo `RBRv...` e azul) existem na mesma linha, o azul prevalece (ver ADR-0009). Valores `"NA"` ou vazios no N° de registro devem ser convertidos para `NULL`.
- **Setor**: valores numéricos lidos como decimais pelo Excel (ex.: `"3.0"`, `"4.0"`) devem ser normalizados para suas strings inteiras equivalentes (`"3"`, `"4"`).
- **"na" em Grau de Ameaça** -> código IUCN `NA` (Not Applicable). Não é ausência de dado, é uma decisão que sobrepõe a leitura literal da planilha.
- **Domínio Fitogeográfico e Substrato** são campos multivalorados (separados por vírgula), sempre viram bridge table, nunca string crua na dimensão.
- **`identificacao`/`identificação`/`StatusIdentificacao*`**: mesmo conceito, três grafias diferentes entre fontes, cuidado ao integrar fonte nova que reuse esse campo.
- **Linhas de totais (Citações)**: a última linha de Monografia Gabriel e de Livro Pesquisas no JB é um somatório (família e espécie vazias, quantidade igual à soma das linhas anteriores da aba). É preservada no staging e no clean com `parse_status = "total_row"` e ignorada no load (ADR-0012). A aba JABOT não tem linha de totais.
- **Resolução da ambiguidade da coluna `especie` (`species_raw` vs `epithet`)**: Conforme padronizado pelo ADR-0010 para sanar a ambiguidade conceitual de nomenclatura entre fontes:
  - Nas fontes de Arboreto (Citações, Espécimes, Canteiro C e Lista Completa), a coluna de entrada na planilha traz uma string composta bruta (Gênero + Epíteto + Infraespecífico + Autor) e é mapeada na camada intermediária como `species_raw`. Essa coluna é então processada por `transforms/nome_cientifico.py`, que extrai `genus`, `epithet`, `infraspecific`, `author` e `identification_qualifier`.
  - Na fonte SPP (Briófitas), a coluna da planilha contém exclusivamente o epíteto específico (a abreviação de gênero pré-fixada, ex.: `"O. "`, é descartada no clean), sendo padronizada como `epithet` (ou `epiteto_especifico` no schema legado).
  - No banco de dados relacional final, ambas as fontes convergem perfeitamente para a dimensão compartilhada `species` (`species.epithet`).
- **Tratamento de `"aleat"` em Parcela (SPP)**: Na fonte SPP (Briófitas), exatamente 14 ocorrências biológicas possuem o valor textual `"aleat"` na coluna `Parcela`, indicando coletas realizadas por amostragem aleatória fora das parcelas fixas 1–5. O pipeline preserva esse valor no staging (`stg_spp_briofitas`) e no clean (`cln_spp_briofitas`) sem descartar linhas nem forçar para `NULL`, propagando o valor por fill-down. No carregamento (`scripts/load/load_SPP.py`), cria-se uma linha válida na dimensão `parcela` (ou `plot` no novo schema) com `codigo = 'aleat'` e coordenadas geográficas `NULL` (pois `config.PARCELA_COORDENADAS.get("aleat")` retorna `None`). As 14 ocorrências na tabela satélite `occurrence_bryophyte` recebem a chave estrangeira `id_parcela` apontando corretamente para esse registro. (A entrada `"alt": "amostragem aleatória"` em `SUBSTRATO_NOME_MAP` é um resíduo de confusão da legenda legada que diz respeito a esse mesmo método de amostragem de Parcela).
- **Localização em Canteiro C (`sector_location`) vs Espécimes (`location_description`)**:
  - Em Arboreto — Espécimes, a coluna `descricao_localizacao` (`location_description`) armazena descrições textuais livres de localização (ex.: "próximo à cerca"), mapeadas para `occurrence_arboretum.location_description`.
  - Em Arboreto — Canteiro C, a coluna "Localização Canteiro" armazena códigos estruturados de setor/canteiro (ex.: `"SCC1-4"`, `"S2C2"`, `"S2C4"`), que resolvem diretamente para a dimensão compartilhada `sector.name` (a mesma utilizada por Espécimes). Para refletir com exatidão essa semântica e evitar confusão entre conceitos, a coluna de Canteiro C é nomeada `sector_location`, e não `location_description`.

## 5. Pendências deste dicionário

- [ ] Preencher seção da Lista Completa Sps com mais detalhe quando essa fonte for iniciada
- [ ] Adicionar seção equivalente para a fonte nova, assim que definida
