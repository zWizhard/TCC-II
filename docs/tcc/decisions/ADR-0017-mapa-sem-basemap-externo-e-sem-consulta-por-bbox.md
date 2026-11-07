# ADR-0017 — Mapa sem basemap de terceiros e sem consulta por bbox/zoom

- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

Mapas web costumam depender de um serviço de tiles para o fundo e de consultas refeitas a cada
movimento (por caixa envolvente e nível de zoom) para limitar o volume trafegado. O projeto tem
orçamento zero, precisa funcionar na defesa sem depender de rede externa e trabalha com um conjunto
de dados estático e pequeno.

## Decisão

1. **Sem tiles nem basemap de terceiros.** O fundo do mapa é a malha de UFs
   ([ADR-0016](ADR-0016-malha-territorial-ibge-v4.md)). Os rótulos usam os glifos locais do
   MapLibre 6 (TinySDF), sem servidor de fontes.
2. **Sem consulta por bbox/zoom.** Cada modo carrega de uma vez os dados do território definido
   pelos filtros. O volume é contido por agregação no servidor (698 municípios de sede em vez de
   2.561 IES), clustering no cliente e restrição ao território filtrado.
3. O coroplético é pintado por `feature-state`: a geometria não é reenviada quando o filtro muda.
4. A malha municipal é baixada apenas no coroplético municipal e mantida em cache.

Tamanhos medidos das respostas (sem compressão → com gzip):

| Resposta | Bruto | gzip |
|---|---|---|
| Malha municipal | 3,9 MB | 1,08 MB |
| Coroplético municipal do país | 667 KB | 140 KB (~65 ms) |
| Matrículas por município | 378 KB | 92 KB |
| IES por sede | 73 KB | 18 KB |

## Alternativas consideradas

- **Basemap de serviço externo (tiles):** descartado por criar dependência de terceiro, contrariar o
  orçamento zero e impedir o uso offline.
- **Consulta por bbox/zoom a cada movimento:** descartada; com os volumes medidos, apenas
  acrescentaria latência.
- **Servidor de fontes para rótulos:** descartado em favor dos glifos locais.

## Consequências

- O mapa funciona sem acesso à internet, apenas com a API local.
- O fundo não traz referências cartográficas além dos limites de UF (sem vias, relevo ou
  hidrografia).
- A primeira abertura do coroplético municipal tem o custo de 1,08 MB da malha.
- A decisão pressupõe o volume atual (um único ano, 5.571 municípios); um crescimento relevante dos
  dados exigiria reavaliação.
- Não foi verificado o desempenho com GPU real nem em celular real; a renderização foi conferida em
  Edge headless com WebGL por software.
