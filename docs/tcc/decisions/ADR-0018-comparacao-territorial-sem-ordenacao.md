# ADR-0018 — Comparação territorial em lista fechada e sem ordenação das unidades
- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

A Fase 11 introduz a comparação entre unidades da Educação Superior. Três riscos foram
identificados na auditoria (`docs/data/raw/diagnostics/2026-10-07_comparacoes.csv`, 20 verificações):

- **A ordem depende do indicador.** Entre UFs, a ordem por matrículas e a ordem por matrículas por
  100 mil habitantes têm correlação de Spearman de 0,06; 15 de 27 UFs mudam cinco ou mais posições.
  SP é a 1ª em absoluto e a 8ª na razão; o DF é o 1º na razão e o 12º em absoluto. A população
  varia 64 vezes entre UFs e 13.929 vezes entre municípios com oferta.
- **As métricas vivem em grains e recortes distintos.** Métricas de IES (sede) e de cursos (oferta)
  não podem ser divididas entre si (IND-Q-03, IND-Q-06).
- **Bases municipais pequenas.** Dos 3.551 municípios com oferta, 1.271 têm de 1 a 99 matrículas
  (304 com 1 a 9) e 135 têm zero; 367 das 698 unidades de sede têm menos de 100 docentes.

## Decisão

1. **Só território × território, no mesmo nível** (região, UF ou município), de 2 a 5 unidades, com
   o Brasil como coluna de referência calculada pelas mesmas consultas.
2. **Lista fechada de 10 indicadores, em dois blocos separados:**
   - absolutos — IND-D-01 (IES) e IND-D-08 (docentes), pela sede; IND-D-02 (cursos, só presencial),
     IND-D-03, IND-D-04 e IND-D-05, pela oferta;
   - relativos — IND-R-01, IND-R-03 e IND-R-04, pela oferta; percentual de doutores do IND-R-12,
     pela sede.
   As dimensões são fixas (presencial + polo EAD). Cada linha declara recorte e dimensões.
3. **API e tela não ordenam nem classificam as unidades:** as colunas seguem a ordem escolhida pelo
   usuário. A comparação é lida dentro de cada linha, nunca entre linhas.
4. **Ausência não é zero.** IES igual a 0 é zero real (a tabela de IES é o universo); docentes,
   cursos e matrículas sem linha são nulos; razão com denominador zero é nula. Com rede fixada, a
   participação da rede privada "não se aplica".
5. **Nenhum JOIN `ies` × `cursos`** e nenhuma razão entre tabelas ou entre recortes.
6. **Base pequena no município gera aviso, não supressão:** nota quando a unidade tem menos de
   100 matrículas, menos de 100 docentes ou menos de 10 mil habitantes, com numerador e denominador
   sempre visíveis. O limiar de 100 é um critério de aviso, não um piso.

## Alternativas consideradas

- **Pública × privada e modalidade × modalidade como eixos de comparação:** descartadas como eixo;
  já existem como composições (Fases 8 e 9) e entram aqui como proporção por unidade (IND-R-03,
  IND-R-04) e como filtro de rede.
- **IES × IES:** descartada; a tabela de `/instituicoes` já cobre o caso e as métricas de uma IES
  vivem em dois grains (IND-Q-03).
- **Variação temporal:** descartada; só existe o ano de 2024 (IND-Q-04).
- **Ordenar ou ranquear as unidades:** descartada pela evidência de que a ordem se inverte conforme
  o indicador seja absoluto ou relativo.
- **Suprimir proporções municipais de base pequena**, como em perfil, financiamento e CINE
  ([ADR-0014](ADR-0014-razoes-por-vaga-e-bloqueio-municipal.md)): não adotada nesta fase; permanece
  em aberto.

## Consequências

- A comparação não cobre 2.580 das 10.227.266 matrículas (sem território); o total do Brasil nas
  definições da comparação é 10.224.686. O IND-R-04 exclui ainda o exterior e 41 matrículas de polo
  sem município.
- Novos indicadores na comparação exigem alteração explícita da lista, passando pelo critério da
  [ADR-0009](ADR-0009-criterio-de-admissibilidade-de-indicadores.md).
- Proporções municipais extremas permanecem visíveis (há município com 100% de EAD sobre
  4 matrículas), mitigadas apenas pelo aviso.

> A confirmar: manter só o aviso ou estender o bloqueio/piso da ADR-0014 às proporções municipais
> da comparação; e validar com o autor o limiar de 100 matrículas/docentes, definido pelo agente.

Detalhe operacional: seção "Comparações" de [API.md](../architecture/API.md) e subseção
"Comparação entre unidades territoriais" de [INDICADORES.md](../methodology/INDICADORES.md).
