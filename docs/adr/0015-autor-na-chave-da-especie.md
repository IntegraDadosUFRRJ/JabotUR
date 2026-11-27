# ADR-0015 — Autor continua na chave da espécie, sem flag de incerteza

**Data:** 10/10/2026 (atualizado em 12/11/2026)
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:** Mantém o autor na chave de espécie do ADR-0002; deixa registrada uma limitação conhecida com a reconciliação de gênero-só do ADR-0003.

---

## Contexto

O parser (`scripts/transforms/scientific_name.py`) só capturava o autor quando o nome tinha um rank infraespecífico (`var.`, `subsp.`, `f.`). Quando não tinha, o texto que sobrava depois do epíteto caía num ramo que atribuía `author = None`. A investigação de 10/10/2026 (somente leitura, em Citações, Espécimes e Canteiro C) mediu:

| Grupo | Linhas com autor no texto bruto | Autor nulo no resultado |
|---|---|---|
| Sem infraespecífico | 864 | 864 (100%) |
| Com infraespecífico | 14 | 0 |

A contagem segue o que o parser realmente faz. Quatro linhas `Genus sp.` (`Citrus sp.` duas vezes, `Pinus sp.` e `Annona sp.`) ficam de fora porque o parser as classifica como gênero-só (ADR-0003); uma regex direta de gênero + epíteto as contaria por engano, com epíteto "sp" e autor ".".

Isso contradiz o `processos_de_etl.md` §2.2 (*Astronium concinnum* Schott → autor Schott) e perde dado: a dimensão `author` quase não recebia autores vindos do arboreto.

No primeiro rascunho foi cogitado tirar o autor da chave da espécie por causa das 28 combinações (gênero, epíteto, infraespecífico) com mais de uma grafia de autor entre as fontes. Essa mudança de chave foi descartada: o autor continua fazendo parte da chave da espécie, como já estava no ADR-0002.

## Decisão

1. O parser passa a capturar o autor também em nomes sem infraespecífico: o texto que sobra depois do epíteto, sem espaços nas pontas, vira `author`. Continuam fora do escopo, como no ADR-0003: `spp.`, `sp. 1` e `sp.` seguido de autor (`Citrus sp. L.`).
2. O autor continua na chave da espécie, mantendo a chave `(id_genus, epithet, infraspecific, id_author)` e os índices únicos do ADR-0002.
3. **Sem flag de incerteza:** não é criada coluna de incerteza para o autor e não se usa `needs_review` por divergência de autor.
4. **Limitação conhecida (gênero-só entre SPP e arboreto):** o gênero-só do SPP leva o autor na chave e o do arboreto não, então o mesmo gênero vindo das duas fontes vira duas espécies diferentes no banco, contra a reconciliação do ADR-0003. Nenhum dado dispara isso hoje; vai virar uma issue separada depois do PR.

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Tirar o autor da chave da espécie (rascunho antigo) | Exigia mudar a chave e os índices do ADR-0002 e criar regra de contagem entre fontes no `taxonomy.py`. |
| Colocar flag de incerteza ou marcar `needs_review` | `needs_review` marca a linha para revisão sem dizer o motivo, e usá-lo para divergência de autor se misturaria com as pendências de identificação (ADR-0012 §3); criar outra flag mudaria o esquema sem uso agora. |
| Manter como estava (autor nulo sem infraespecífico) | Perde o autor de 864 linhas e contradiz o `processos_de_etl.md` §2.2. |
| Tratar já a diferença de gênero-só entre SPP e arboreto | Nenhum dado dispara isso hoje; fica para uma issue depois do PR. |

## Consequências

**Positivas:**
- O parser deixa de jogar fora o autor nas 864 linhas sem infraespecífico e passa a bater com o `processos_de_etl.md` §2.2.
- Não mexe nos índices únicos do ADR-0002 nem adiciona coluna nova no `schema.sql`.

**Negativas / trade-offs aceitos:**
- Gênero-só entre SPP e arboreto não reconcilia: como o SPP traz autor no gênero-só e o arboreto não, se o mesmo gênero aparecer como gênero-só nas duas fontes, vão ser criadas duas linhas em `species` em vez de uma só (contra o ADR-0003).
- Variantes de grafia de autor continuam separadas na chave. Nas 28 combinações levantadas em 10/10/2026 entre as fontes, 20 diferem só em espaço ou pontuação (`Raddi` / `Raddi.`), 3 são erro de digitação ou iniciais omitidas (`Altschu` / `Altschul`), 3 são forma incompleta (`Mart.` / `Mart. & Zucc.`) e 2 são conflito real (*Cassia fistula*: `L.` / `Benth.`; *Khaya grandifoliola*: `C.DC.` / `A. Juss.`). Elas entram como chaves diferentes enquanto não houver limpeza específica.

**Impacto no código existente:**
- Arquivos/tabelas afetados: `scripts/transforms/scientific_name.py`, testes e `docs/processos_de_etl.md` §2.2. Não muda o `schema.sql` (continua valendo a chave com `id_author` do ADR-0002).
- Precisa de migração? Não. Não há pasta `migrations/` (ver ADR-0014); no banco local, apagar e rodar o pipeline de novo para preencher os autores que antes ficavam nulos.
- É retroativo? Sim, passa a valer para todas as cargas que usam o parser (Citações, Espécimes, SPP e Canteiro C).
- Validação exigida: rodar os testes no banco `_test`, recriar o banco local e rodar o pipeline duas vezes seguidas mantendo as contagens iguais.

## Referências

- Issue/PR relacionado: issue sobre o gênero-só entre SPP e arboreto, a abrir depois do PR
- `docs/processos_de_etl.md` §2.2, `docs/panorama_tecnico_jabotur.md`
- ADR-0002, ADR-0003, ADR-0010, ADR-0012 e ADR-0014
