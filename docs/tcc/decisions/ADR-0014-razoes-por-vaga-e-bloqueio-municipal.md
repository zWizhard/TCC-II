# ADR-0014 — Razões por vaga restritas a uma dimensão de oferta e bloqueio municipal para atributos de pessoa

- **Data:** 2026-10-07
- **Status:** Aceita (o bloqueio municipal de IND-R-08/R-09 aguarda confirmação do autor)

## Contexto

A Fase 9 passou a servir razões entre contagens de `cursos` (IND-R-10, ingressantes por vaga;
IND-R-11, inscrições por vaga) e composições por atributos de pessoa (perfil IND-R-07,
financiamento IND-R-08, reserva de vagas IND-R-09). A auditoria de 2026-10-07
(`scripts/analise/auditar_fluxo.py`) mostrou três condições que produzem número errado sem erro
de execução:

- Vagas e ingressos não coexistem em todas as dimensões de oferta: nas linhas de polo EAD com
  território as vagas são zero, e na dimensão "somente a nível Brasil" os ingressos são zero.
- 60 municípios têm curso presencial e nenhuma vaga.
- 304 municípios têm de 1 a 9 matrículas e 792 têm de 1 a 9 concluintes; o piso de supressão da
  plataforma ainda não foi definido.

## Decisão

1. **IND-R-10 aceita somente a dimensão presencial.** O nome é "Ingressantes por vaga ofertada".
2. **IND-R-11 aceita exatamente uma dimensão por resposta** — presencial ou EAD nacional, esta
   apenas no nível Brasil. As duas nunca são somadas nem comparadas na mesma resposta.
3. **Numerador e denominador são somados nas mesmas linhas de `cursos`** e divididos em Python.
4. **Denominador zero resulta em valor nulo** ("não se aplica"), nunca em zero.
5. **Perfil, IND-R-08 e IND-R-09 não são servidos no nível municipal.** Trata-se de bloqueio por
   nível, não de piso de supressão.

## Alternativas consideradas

- **Somar as dimensões de oferta numa razão única.** Rejeitada: numerador e denominador viriam de
  conjuntos de linhas distintos.
- **Nomear IND-R-10 "taxa de ocupação" e IND-R-11 "candidatos por vaga".** Rejeitadas: o Censo
  conta ingressos e inscrições, não ocupação de vagas nem pessoas candidatas.
- **Devolver zero quando não há vagas.** Rejeitada: confunde ausência de denominador com razão nula.
- **Servir atributos de pessoa no município, conforme as fichas de IND-R-08/R-09.** Preterida até
  existir piso de supressão, dada a quantidade de municípios com contagens de 1 a 9.

## Consequências

- Não há razão por vaga para a oferta EAD em nível subnacional, nem valor único que reúna
  presencial e EAD.
- O cartão da interface declara as dimensões excluídas do cálculo.
- A granularidade efetiva de IND-R-08/R-09 fica mais restrita que a registrada nas fichas de
  [INDICADORES.md](../methodology/INDICADORES.md); a divergência depende de confirmação do autor.
- O bloqueio municipal não elimina células pequenas em outros níveis: UF × categoria já devolve
  células de 1 vínculo. A definição do piso (N) segue pendente e pode levar à revisão do item 5.
- Relaciona-se com a [ADR-0004](ADR-0004-recorte-territorial-duplo.md) (recorte territorial) e a
  [ADR-0009](ADR-0009-criterio-de-admissibilidade-de-indicadores.md) (admissibilidade de indicadores).
