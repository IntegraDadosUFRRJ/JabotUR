# ADR-0014 — Esquema explícito, FKs e banco de teste

**Data:** 12/11/2026
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** Junta no `schema.sql` o que foi definido no ADR-0002 (índices parciais) e no ADR-0010 (nomes em inglês); transforma as migrações 001 e 002 em histórico no git.

---

## Contexto

A definição das tabelas estava dividida entre o código de inicialização e os arquivos soltos na pasta `migrations/` (001 e 002). Para saber como o banco estava de verdade, era preciso olhar mais de um lugar e somar as migrações de cabeça.

Além disso:
- As tabelas não tinham as chaves estrangeiras (FKs) declaradas como constraint no banco, o que deixava passar registro órfão sem o Postgres reclamar.
- Nada impedia os testes de rodarem no banco principal (`jabotur`) e apagarem os dados locais por engano.

## Decisão

1. **`schema.sql` como fonte única:** todo o esquema do banco fica escrito num único arquivo, `scripts/db/schema.sql`, que o `init_postgres` aplica direto.
2. **Saída da pasta `migrations/`:** o que estava nas migrações 001 e 002 já entrou no `schema.sql`. Elas viram histórico no git e a pasta `migrations/` deixa de existir.
3. **FKs como constraint de tabela, sem `ON DELETE CASCADE`:** todas as ligações entre tabelas passam a ter `FOREIGN KEY` no `schema.sql`.
4. **Falha de FK é achado, não motivo para tirar a FK:** se algum load ou teste quebrar por violação de FK, isso mostra um erro nos dados ou na ordem de carga que precisa ser consertado, e nunca resolvido tirando a constraint.
5. **Banco de teste e trava no nome:** o `init_postgres` cria o banco indicado por `POSTGRES_DB`; os testes que gravam no banco só rodam se o nome terminar em `_test` e `require_test_database()` recusa qualquer outro.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Continuar com a pasta `migrations/` (001, 002, ...) | Como o banco ainda é recriado do zero pelo pipeline, espalhar o esquema em vários arquivos só dificulta a leitura do que está valendo. |
| Colocar `ON DELETE CASCADE` nas FKs | Apagaria linhas filhas sem avisar quando uma linha pai saísse, escondendo erro de carga ou de teste. |
| Tirar ou não pôr FK onde desse erro na carga | Esconde problema real do pipeline ou da planilha; o banco tem que barrar. |
| Rodar os testes no mesmo banco, dependendo de lembrar de trocar `POSTGRES_DB` | Um comando de teste rodado sem trocar o banco apagaria as tabelas do banco de trabalho. |

## Consequências

**Positivas:**
- Dá para ver todas as tabelas, índices e FKs do projeto abrindo apenas o `schema.sql`.
- O próprio Postgres barra na hora um load que tente gravar um id que não existe na tabela pai.
- Os testes não correm mais o risco de limpar o banco `jabotur` por acidente.

**Negativas / trade-offs aceitos:**
- Sem arquivos de migração ativos, qualquer mudança no `schema.sql` pede apagar o banco local, rodar o `init_postgres` e carregar o pipeline de novo.
- Nos loads e na limpeza dos testes, as tabelas precisam ser preenchidas e limpas respeitando a ordem das FKs, porque não há `ON DELETE CASCADE`.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `scripts/db/schema.sql`, `scripts/db/init_postgres.py`, `scripts/db/db_utils.py`, remoção da pasta `migrations/` (001 e 002), `tests/test_db_utils_duckdb.py`, `docs/data_dictionary.md`, `docs/panorama_tecnico_jabotur.md` e DER. Todas as tabelas e constraints de FK ficam unificadas no `schema.sql`.
- Precisa de migração? Não. Não há mais pasta `migrations/`: rodar o `init_postgres` para aplicar o `schema.sql` no banco indicado por `POSTGRES_DB` e rodar o pipeline em seguida. Como o `schema.sql` só cria o que não existe, um banco local que já tem o esquema antigo precisa ser apagado antes; o `jabotur_test` é recriado pela própria suíte.
- É retroativo? Sim, vale para todas as tabelas do banco.
- Validação exigida: rodar o `init_postgres` do zero; rodar a suíte no `jabotur_test`; conferir que os testes de banco não rodam (ou recusam) num banco sem `_test` no final; rodar o pipeline duas vezes sem erro de FK e mantendo as mesmas contagens.

## Referências

- `docs/panorama_tecnico_jabotur.md` (esquema, FKs e banco de teste), `docs/data_dictionary.md`, DER e `CONTRIBUTING.md`
- ADR-0002, ADR-0010 e ADR-0013
