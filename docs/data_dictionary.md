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

## 2. Colunas por fonte (nome original -> coluna normalizada)

Legenda: [#] atenção a nomenclatura divergente entre fontes.

### SPP (briófitas)
| Original | Normalizado | Observação |
|---|---|---|
| Parcela | `parcela` | fill-down; ver seção 4 |
| Amostra | `amostra` | fill-down |
| StatusIdentificacao* | `identificacao` [#] | também aparece como "identificação" em outras fontes; ver seção 4 |
| Filo | `filo` | só existe pra briófitas(arboreto fica NULL (ADR-0004)) |
| Família | `familia` | |
| Gênero | `genero` | |
| Espécie | `epiteto_especifico` [#] | contém só o epíteto aqui, mas em arboreto é "Espécie" = string completa, mesmo nome de coluna, semântica diferente |
| Autor | `autor` | coluna própria |
| Forma de Vida | `forma_vida` | |
| Substrato | `substrato` | multivalorada (separada por transform) |
| Observações | `observacao` [#] | aparece como "observacoes" em código legado, `clean_SPP._to_duckdb_table` normaliza os dois nomes |

### Arboreto — Citações (Monografia Gabriel / Livro Pesquisas no JB / JABOT)
| Original | Normalizado | Observação |
|---|---|---|
| Família | `familia` | fill-down |
| Espécie | `especie` (raw) -> parseada em `genero`/`epiteto_especifico`/`infraespecifico`/`autor`/`identification_qualifier` | via `transforms/nome_cientifico.py` |
| Quant | `quantidade` | |

### Arboreto — Espécimes
| Original | Normalizado | Observação |
|---|---|---|
| Família | `familia` | |
| Espécie | `especie` (raw) -> parseada igual citações | |
| N° de registro | `numero_registro` | ver regra do lacre azul, seção 4 |
| Setor | `setor` | 25 valores distintos confirmados |
| Descrição da localização | `descricao_localizacao` | maioria NULL, nunca virar string `"N/A"` |
| Estado reprodutivo | `estado_reprodutivo` | 2 valores confirmados: "Adulto"/"jovem" |

### Arboreto — Canteiro C
| Original | Normalizado | Observação |
|---|---|---|
| (sem cabeçalho, 1ª coluna) | `familia` | renomeação posicional obrigatória |
| Gênero | `genero` | |
| Espécie | `especie` (raw) -> parseada | |
| Autor | embutido em `especie` | mesmo padrão arboreto |
| Origem | `origin` [#] | variante de grafia "Exótico"/"Exótica", canonizar pra "Exótica" |
| Domínio Fitogeográfico | `phytogeographic_domain` | multivalorada (vírgula) |
| Grau de Ameaça | -> `conservation_status.code` | "na" mapeia pro código IUCN real `NA`, não NULL (ver ADR) |
| Numeração Lacre | `registration_number` | mesma regra de lacre azul de Espécimes |
| Localização Canteiro | `location_description` | |

### Arboreto — Lista Completa Sps (não iniciado)
| Original | Normalizado | Observação |
|---|---|---|
| Família / Gênero / Espécie / Autor | igual às demais | |
| Distribuição | -> `species_country`/`species_state`/`species_geographic_area` | sem padrão fixo, mistura estado, país, continente e frases livres tipo "Kênia até Moçambique", "W. Indian Ocean", "Tropical & Subtropical Asia to Pacific"; decompor quando possível, cair em `species_geographic_area.description` (texto livre) quando não |
| Domínios Fitogeográfico | igual Canteiro C | |
| Grau de Ameaça | igual Canteiro C | |

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
| alt | amostragem aleatória |

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

**Conservation status (IUCN)** — `NE`, `LC`, `VU`, `EN`, `NT`, `NA`. `NA` = "Not Applicable", valor semântico real (ver ADR-0005).

## 4. Regras de negócio entre fontes

- **Lacre azul**: qualquer número de registro **sem prefixo "RBRv"** é lacre azul, mesmo sem a palavra "AZUL" escrita. Quando os dois lacres (amarelo `RBRv...` e azul) existem na mesma linha, o azul prevalece (ver ADR-0009).
- **"na" em Grau de Ameaça** -> código IUCN `NA` (Not Applicable). Não é ausência de dado, é uma DER que sobrepõe a leitura literal da planilha.
- **Domínio Fitogeográfico e Substrato** são campos multivalorados (separados por vírgula), sempre viram bridge table, nunca string crua na dimensão.
- **`identificacao`/`identificação`/`StatusIdentificacao*`**: mesmo conceito, três grafias diferentes entre fontes, cuidado ao integrar fonte nova que reuse esse campo.
- **`epiteto_especifico` como nome de coluna existe em fontes diferentes com semântica ligeiramente diferente** (SPP = só epíteto; arboreto pré-parsing = string completa), só depois do parsing os dois convergem pra mesma semântica na tabela final.

## 5. Pendências deste dicionário

- [ ] Preencher seção da Lista Completa Sps com mais detalhe quando essa fonte for iniciada
- [ ] Adicionar seção equivalente para a fonte nova, assim que definida
