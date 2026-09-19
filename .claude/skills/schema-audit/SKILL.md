---
name: schema-audit
description: Descobrir e documentar o schema real de uma tabela do Big Data IESB — colunas, tipos, grain, chaves, nulos, cardinalidade, período e categorias. Use antes de escrever qualquer SQL produtivo sobre uma tabela ainda não verificada.
---

# schema-audit

Objetivo: transformar "acho que a tabela tem" em fato documentado. Nada aqui é suposição.

## Antes de começar

Confirme que o acesso ao banco existe. Se não houver conexão configurada, **pare e peça ao usuário** —
não escreva um dicionário de dados especulativo.

## Passos

1. **Localizar** — schema e nome real da tabela. Anote-os exatamente como aparecem no catálogo.
2. **Estrutura** — colunas, tipos, nullability, particionamento/ordenação se o motor expuser.
3. **Volume e período** — contagem total; valores mín./máx. da coluna de ano; contagem por ano
   (revela anos faltantes e quebras de série do Censo).
4. **Grain** — enuncie em uma frase: "uma linha = ___". Prove:
   `COUNT(*)` vs `COUNT(DISTINCT <chave candidata>)`. Se diferirem, o grain não é o que você pensou.
5. **Chaves** — candidatas a chave primária e estrangeiras. Priorize códigos oficiais
   (IBGE municipal, código IES, código curso) sobre nomes textuais.
6. **Nulos** — proporção de nulos nas colunas que o projeto vai usar. Nulo em chave é bloqueante.
7. **Categorias** — para colunas categóricas (Categoria Administrativa, Organização Acadêmica,
   Modalidade, Grau, Turno, Situação): valores distintos + frequência. Registre o **código** e o
   **rótulo oficial**, não uma tradução sua.
8. **Cardinalidade** — nº de distintos nas colunas que entrarão em JOIN ou GROUP BY.

## Armadilhas de método (já custaram erro neste projeto)

- **Nunca use `row.get(coluna, "")` numa auditoria.** Coluna inexistente vira valor vazio e você
  documenta "100% nulo" sobre uma coluna que só tem outro nome. Acesse por chave direta e deixe
  estourar `KeyError`, ou compare a lista de colunas antes. *(Ocorrido em 2026-09-05:
  `in_capital` não existe na tabela de IES — lá é `in_capital_ies`, e tem dado.)*
- **Colunas homônimas entre tabelas podem ter codificação diferente.** No Censo 2024, `tp_rede`
  é código `'1'/'2'` em IES e rótulo `Pública`/`Privada` em cursos.
- **Coluna com nome de código pode conter texto.** `co_municipio` tem 11.778 linhas com o literal
  `'Cursos a distância'`. Verifique o formato, não confie no nome.
- **Não conclua semântica de métrica por aritmética plausível.** Antes de somar uma coluna
  replicada em várias linhas, inspecione linhas reais do mesmo grupo para ver se o valor
  se repete (replicado) ou varia (distribuído). São conclusões opostas.

## Cuidados de execução

Toda consulta exploratória com `LIMIT` e, quando existir, filtro de partição.
`COUNT(DISTINCT)` sobre tabela grande é caro — avise o usuário antes de rodar.
Se uma consulta puder varrer a tabela inteira, diga isso antes de executá-la.

## Saída

Atualize `docs/data/DATA_DICTIONARY.md` (por tabela: finalidade, grain, chave, colunas relevantes,
tipos, período, categorias, nulos, cardinalidade, relacionamentos, problemas conhecidos)
e `docs/data/DATA_GRAIN.md` (uma linha por tabela com o grain enunciado e como foi provado).

Documente **somente o verificado**. O resto fica como `A confirmar`.
Não cole o schema inteiro — só o que o projeto usa.

## Encerramento

Chame `tcc-documentarian` com um handoff compacto se o resultado mudar a metodologia
ou revelar limitação relevante dos dados.
