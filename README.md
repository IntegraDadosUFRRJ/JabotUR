# JabotUR

## Sobre

O JB-UFRRJ possui informações distribuídas em planilhas, sistemas e inventários fragmentados. Este repositorio contém o JabotUR que integra diferentes fontes de dados de pesquisa do Jardim Botânico da UFRRJ (JB-UFRRJ), como acervo de espécies, registros de campo e metadados de suporte, em um único fluxo ETL que produz tabelas normalizadas no PostgreSQL. Com isso ele busca reduzir retrabalho, melhorar a qualidade dos dados e preparar a base para análises e aplicações futuras de catalogação, mapeamento e pesquisa científica.


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
python scripts/init_postgres.py
```

5. Execute o pipeline completo:

```bash
python3 scripts/run_pipeline.py
```

### O que o pipeline gera

- `stg_spp_briofitas`: dados de staging carregados do Excel
- `cln_spp_briofitas`: dados limpos e normalizados
- tabelas finais normalizadas no PostgreSQL: `filo`, `familia`, `genero`, `autor`, `epiteto_especifico`, `forma_vida`, `parcela`, `substrato`, `identificacao`, `coleta`, `coleta_substrato`, `coleta_observacao`

## Help

- Entre em contato em davidson_wasserman@ufrrj.com | cassiolima@ufrrj.br | juliaprearo@ufrrj.br

### Membros

- Cássio Lima 
- Davidson Wasserman
- Julia Prearo
- Liliane Kunstmann


---

*Projeto de Iniciação Científica do Jardim Botânico da UFRRJ.*