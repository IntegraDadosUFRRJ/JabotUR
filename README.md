# JabotUR

## Sobre

O JB-UFRRJ possui informações distribuídas em planilhas, sistemas e inventários fragmentados. Este repositorio contém o JabotUR que integra diferentes fontes de dados de pesquisa do Jardim Botânico da UFRRJ (JB-UFRRJ), como acervo de espécies, registros de campo e metadados de suporte, em um único fluxo ETL que produz tabelas normalizadas no PostgreSQL. Com isso ele busca reduzir retrabalho, melhorar a qualidade dos dados e preparar a base para análises e aplicações futuras de catalogação, mapeamento e pesquisa científica.
No momento o pipeline realiza a integração de duas bases, sendo elas o levantamento de briófitas (SPP) e a diversidade florística do arboreto (por enquanto contendo somente a parte de registros do arboreto: Monografia Gabriel, Livro Pesquisas no JB e JABOT). 

## Requisitos para executar

- Python 3.10 ou superior
- PostgreSQL 14 ou superior

## Como começar

1. Clone o repositório:

```bash
git clone <url-do-repositorio>
cd jabotur
```

2. Crie um ambiente virtual e ative-o:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .venv\Scripts\activate     # Windows
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Crie o banco PostgreSQL:

```bash
python3 -m scripts.init_postgres
```

5. Execute o pipeline completo:

```bash
python3 -m scripts.run_pipeline
```

> `-m`: os módulos usam import relativo entre si, então rodar como script direto (`python3 scripts/run_pipeline.py`) falha com `ImportError`.

## Migrações do banco de dados

O diretório `migrations/` contém scripts SQL utilizados para atualizar
bancos PostgreSQL criados a partir de versões anteriores do projeto.

As migrações são necessárias quando um banco existente precisa ser
atualizado para acompanhar uma alteração no schema. Elas não fazem parte
da execução normal do pipeline em um banco criado do zero pela versão
atual do projeto.

### Banco novo

Para uma instalação nova, basta executar:

```bash
python3 -m scripts.init_postgres
python3 -m scripts.run_pipeline

### O que o pipeline gera

O pipeline processa cada fonte em camadas próprias de staging e clean, que convergem pro mesmo núcleo taxonômico na carga final:

- **Staging**:
  `stg_spp_briofitas`, `stg_arboreto_citations`
- **Clean** (normalizado, nada é descartado aqui, problemas de qualidade viram colunas como `parse_status`/`needs_review`):
  `cln_spp_briofitas`, `cln_arboreto_citations`
- **Tabelas finais normalizadas no PostgreSQL**:
  - núcleo taxonômico compartilhado entre fontes: `filo`, `familia`, `genero`, `autor`, `epiteto_especifico`
  - específicas de briófitas: `forma_vida`, `parcela`, `substrato`, `identificacao`, `observacao`, `occurrence`, `occurrence_bryophyte`, `coleta_substrato`, `coleta_observacao`
  - específicas do arboreto: `bibliographic_citation`

Schema completo esta documentado em `JabotUR_DER.md`.

## Help

- Entre em contato em davidson_wasserman@ufrrj.com | cassiolima@ufrrj.br | juliaprearo@ufrrj.br

### Membros

- Cássio Lima 
- Davidson Wasserman
- Julia Prearo
- Liliane Kunstmann


---

*Projeto de Iniciação Científica do Jardim Botânico da UFRRJ.*