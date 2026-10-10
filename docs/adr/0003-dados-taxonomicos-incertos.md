# ADR-0003 — Registro de dados taxonômicos incertos (gênero-só, "Genus sp.", morfo-espécie e unparseable)

**Data:** 09/08/2026 (atualizado em 05/10/2026)
**Status:** Aprovado
**Autor(es):** Davidson
**Relação com outras decisões:**
- Atualizado pelo **ADR-0010**: `epiteto_especifico` passa a ser `species`, `nome` passa a `epithet`, e `id_genero` passa a `id_genus`.
- Complementado pelo **ADR-0012**: linhas em branco que correspondem a somatórios de controle de Citações são `total_row` (`needs_review = False`), enquanto linhas ininteligíveis sem justificativa permanecem como `unparseable` (`needs_review = True`).

---

## Contexto

As planilhas de citação do arboreto (Monografia Gabriel, Livro Pesquisas no JB, JABOT) e de espécimes trazem registros que não seguem o padrão binomial completo "Gênero + epíteto específico + autor":

1. **Gênero só**: A planilha cita apenas o gênero botânico (ex.: "Handroanthus").
2. **Gênero com indicação indeterminada ("Genus sp.")**: A planilha cita o gênero acompanhado do marcador de indeterminação da espécie (ex.: "Citrus sp." ou "Eugenia sp").
3. **Morfo-espécie**: Registros classificados provisoriamente pelo coletor (ex.: "Morfo-Espécie 1"), sem identificação a nível de gênero ou espécie.
4. **Strings ininteligíveis ("Unparseable")**: Células com descrições livres, notas de campo ou textos corrompidos que falham no parser botânico (ex.: "Árvore grande com flor amarela").

A política central do projeto (`panorama_tecnico_jabotur.md`, §1) determina que nenhum dado seja descartado por incerteza. Era necessário definir a representação dessas quatro situações no schema relacional normalizado.

## Decisão

Todos os registros são preservados na camada clean e integrados na dimensão de espécies (`epiteto_especifico` / `species`), porém com semânticas distintas de reconciliação e preenchimento:

- **Gênero só e "Genus sp."**: Casos como "Handroanthus" ou "Citrus sp." são tratados puramente como Gênero-só (o sufixo "sp." ou "sp" é absorvido e ignorado). Possuem `id_genero` preenchido e `nome = NULL` (`epithet = NULL`). **Reconciliam normalmente** entre fontes via get-or-create, pois representam o mesmo táxon genérico.
- **Morfo-espécie**: Possuem `id_genero = NULL` e recebem como nome um identificador qualificado com a origem (`nome = "Morfo-Espécie 1 [aba#linha]"`). **Nunca reconciliam** entre fontes diferentes, visto que a numeração de morfo-espécies é puramente local à planilha de origem.
- **Unparseable**: Possuem `id_genero = NULL` e recebem como nome um placeholder qualificado com a origem (`nome = "Unparseable [aba#linha]"`). **Nunca reconciliam** entre fontes.

As sinalizações ocorrem na camada clean por meio das colunas de controle:
- `parse_status`: assume `genus_only`, `morphospecies` ou `unparseable` (além de `ok`).
- `reconcile_across_sources`: assume `True` para gênero-só e `False` para morfo-espécie e unparseable.
- `needs_review`: assume `False` para `ok`, `genus_only` e `morphospecies` (casos legítimos e esperados no arboreto), e `True` para `unparseable` (exigindo conferência humana com os botânicos).

## Alternativas consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Descartar registros incertos ou unparseable no staging | Viola a política fundamental de preservação total do dado bruto. |
| Cadastrar "sp." como um epíteto específico comum | Polui a dimensão de espécies com um pseudo-epíteto que colidiria entre todos os gêneros e mascararia consultas taxonômicas reais. |
| Reconciliar morfo-espécies pelo nome literal ("Morfo-Espécie 1") | Unificaria indevidamente espécimes de fontes distintas que usaram a mesma convenção numérica local para plantas completamente diferentes. |
| Criar lógica condicional complexa no get-or-create | Rejeitada em favor de embutir a origem `[aba#linha]` diretamente na string natural (`nome`), garantindo unicidade natural por construção sem exceções no SQL. |

## Consequências

**Positivas:**
- Preservação de 100% dos dados originais sem perda de linhagem.
- O get-or-create padrão continua simples e declarativo, sem condicionais de reconciliação no código SQL/Pandas.
- Gêneros idênticos se fundem adequadamente entre fontes, enquanto morfo-espécies e unparseable permanecem estritamente isoladas.

**Negativas / trade-offs aceitos:**
- A tabela `epiteto_especifico` (`species`) armazena linhas de morfo-espécie e unparseable que não representam espécies taxonômicas formais no sentido biológico estrito.
- Registros `unparseable` geram alertas em `needs_review = True`, requerendo acompanhamento botânico.

**Impacto no código existente:**
- Afeta `transforms/nome_cientifico.py`, `clean_arboreto_citations.py`, `clean_arboreto_specimens.py`, `load/taxonomy.py` e `load_arboreto_citations.py`.

## Referências

- ADR-0001, ADR-0002, ADR-0008, ADR-0010, ADR-0012
- `panorama_tecnico_jabotur.md`, §1 e §3
