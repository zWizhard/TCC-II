# ADR-0012 — Semântica dos filtros territoriais da API

- **Data:** 2026-10-06
- **Status:** Aceita

## Contexto

Até a Fase 5, o endpoint `/api/v1/indicadores/{slug}` devolvia os indicadores diretos por nível
(Brasil, região, UF, município) sem seleção de um território específico
([ADR-0010](ADR-0010-api-de-catalogo-fechado.md)). A Fase 7 introduziu os filtros `regiao`, `uf` e
`municipio` para que a Visão Geral mostre os indicadores de um território escolhido e a sua
distribuição no nível imediatamente inferior.

Era preciso definir como um filtro territorial se combina com o parâmetro `nivel`. Uma combinação
sem regra permitiria respostas rotuladas com um território e calculadas sobre outro — erro que não
gera falha de execução.

## Decisão

1. **O filtro territorial vale do seu nível para baixo.** O valor de um território é a consulta no
   nível do próprio território: `nivel=uf&uf=SP` devolve uma linha.
2. **Não existe `nivel=brasil` com filtro territorial**, pois a linha sairia rotulada "Brasil" com o
   valor de uma UF.
3. **Combinações incoerentes são recusadas com 422 e o motivo declarado**: UF fora da região
   informada; categoria administrativa fora da rede informada.
4. **Com filtro territorial, `valor_sem_territorio` é nulo.**
5. O bloco `Filtros` da resposta declara todos os filtros aplicados.

O recorte territorial (sede ou local de oferta) continua obrigatório, conforme a
[ADR-0004](ADR-0004-recorte-territorial-duplo.md).

## Alternativas consideradas

- **Filtro territorial livre em qualquer nível.** Rejeitada: admite linhas cujo rótulo não
  corresponde ao universo calculado (caso do item 2).

## Consequências

- O frontend obtém o valor do território selecionado consultando o nível do próprio território, e a
  distribuição consultando o nível seguinte com o mesmo filtro.
- Onze novas combinações recusadas passaram a ser cobertas por teste; o fechamento
  região = UFs = municípios é verificado nas 5 regiões.
- **Assimetria conhecida, não corrigida:** `uf` + `municipio` incoerentes devolvem 200 com resultado
  vazio, e não 422. Para que isso não produza número sob a UF errada, o frontend envia o município
  sempre acompanhado da UF.

Contrato detalhado em [API.md](../architecture/API.md).
