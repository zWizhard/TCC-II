---
name: join-audit
description: Validar um JOIN entre tabelas do Censo antes e depois de executá-lo — grains, chave, cardinalidade, pré-agregação, linhas antes/depois, duplicações e impacto nas métricas. Use sempre que um JOIN influenciar um número apresentado.
---

# join-audit

Um JOIN não está correto só porque executou. Ele está correto quando a cardinalidade foi provada
e as métricas não inflaram.

## Antes do JOIN

1. **Grain de A** e **grain de B**, cada um em uma frase. Se algum for "a confirmar", rode
   `schema-audit` antes — não prossiga.
2. **Chave** — use a chave oficial (código IBGE municipal, código IES, código curso).
   Nunca faça JOIN por **nome textual** de município quando existir chave oficial confiável:
   acento, grafia e homônimos entre UFs produzem perda e duplicação silenciosas.
   Se a chave for composta (ex.: ano + código), o JOIN usa **todas** as partes.
3. **Cardinalidade esperada** — 1:1, 1:N ou N:N. Declare antes e verifique:
   contagem de linhas por chave em cada lado; a chave é única onde você acha que é?
4. **Pré-agregação** — se o lado N carrega a métrica e você quer o grain do lado 1,
   agregue **antes** do JOIN. Somar depois de um fan-out é a causa mais comum de número inflado.
5. **Domínio das chaves** — chaves de A ausentes em B e vice-versa. Anti-join nos dois sentidos.
   Isso antecipa o que um INNER JOIN vai descartar em silêncio.

## Depois do JOIN

- **Linhas antes vs. depois.** Aumentou? Houve fan-out — era esperado?
- **Duplicações** — `COUNT(*)` vs `COUNT(DISTINCT <chave do grain alvo>)` no resultado.
- **Nulos introduzidos** pelo LEFT JOIN, e o efeito deles em `SUM`, `AVG` e denominadores.
- **Métricas** — compare um total do resultado com o mesmo total calculado direto na tabela de
  origem. Se divergirem, o JOIN está errado até prova em contrário.
- **Tipo da chave** — string vs inteiro, zeros à esquerda, espaços. Um match silenciosamente vazio
  costuma ser tipo incompatível, não ausência de dado.

## Saída

Registre em `docs/data/JOIN_STRATEGY.md`: tabelas, chave, cardinalidade provada, se houve
pré-agregação, os números de validação e as armadilhas encontradas.

Se algum número não fechar, **não** apresente o resultado como válido — reporte a divergência.

## Encerramento

Chame `tcc-documentarian` se a estratégia de JOIN for uma decisão metodológica nova.
