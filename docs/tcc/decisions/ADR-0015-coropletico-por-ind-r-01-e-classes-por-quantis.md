# ADR-0015 — Coroplético pelo IND-R-01 com classes por quantis

- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

O mapa coroplético da rota `/mapa` pinta polígonos de UF ou de município. A área do polígono não
guarda relação com a população, de modo que uma contagem bruta de matrículas reproduziria no mapa
apenas o tamanho demográfico das unidades. Além disso, a distribuição municipal do indicador é
fortemente assimétrica: mediana de 1.173 contra máximo de 30.106 matrículas por 100 mil habitantes
(p20 235, p80 3.763). Das 5.571 unidades de `municipio`, apenas 3.551 têm linha de oferta.

## Decisão

1. O coroplético representa o **IND-R-01** (matrículas por 100 mil habitantes, recorte de oferta,
   com as dimensões presencial/polo declaradas), nunca contagem bruta. Ficha em
   [INDICADORES.md](../methodology/INDICADORES.md).
2. O universo são as **5.571 unidades** de `municipio`, não as 3.551 com oferta. Unidade sem linha
   de oferta recebe valor **nulo** (2.020), distinto do zero real (135), e é desenhada em cinza
   hachurado com item próprio na legenda.
3. No nível UF o denominador é reagregado: população de todas as unidades da UF.
4. As classes são definidas por **quantis** (5 por padrão, entre 3 e 7), calculadas no servidor
   sobre as unidades com valor, com mínimo e máximo observados em cada classe. Empates fundem classes.
5. O nível das unidades (UF ou município) é escolha explícita do leitor, nunca troca automática por
   zoom.

## Alternativas consideradas

- **Contagem bruta de matrículas:** descartada por refletir o tamanho da população, não a oferta
  relativa.
- **Intervalos iguais:** descartados; com a assimetria medida, cerca de 95% das unidades ficariam na
  primeira cor.
- **Quebras naturais (Jenks):** descartadas por não trazerem ganho claro e terem pior
  reprodutibilidade.
- **Universo restrito às unidades com oferta:** descartado por omitir do mapa a ausência de oferta.
- **Troca automática de nível por zoom:** descartada por alterar a escala de cores sem aviso.

## Consequências

- A classe superior é larga no nível municipal (3.763 a 30.106), o que é declarado na legenda.
- As cores não são comparáveis entre mapas com filtros diferentes, pois os quantis são recalculados
  a cada resposta; a legenda também o declara.
- O indicador compara matrícula no local de oferta com habitante no local de residência: não é taxa
  de escolarização e é instável em município pequeno (757 unidades com oferta têm menos de 10 mil
  habitantes).
- Categoria administrativa e organização acadêmica são aceitas como filtros por serem atributos
  constantes por IES e restringirem apenas o numerador.
