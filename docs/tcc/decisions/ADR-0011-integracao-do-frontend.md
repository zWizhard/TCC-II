# ADR-0011 — Integração do frontend ao repositório oficial

- **Data:** 2026-10-06
- **Status:** Aceita

## Contexto

O frontend foi prototipado no Lovable, em repositório próprio (`github.com/zWizhard/tcc-2`), só com
conteúdo ilustrativo (placeholders, sem números) e textos que sugeriam série temporal. A API da Fase 5
([ADR-0010](ADR-0010-api-de-catalogo-fechado.md)) já servia os indicadores diretos, e era preciso
definir onde o frontend passa a viver, com que stack e como se relaciona com a API.

## Decisão

1. **Fonte oficial:** o repositório TCC-II. O código foi copiado (commit `79a737d`) para `frontend/`,
   sem histórico; o repositório do Lovable passa a ser referência visual.
2. **Stack mantida** como veio: TanStack Start/Router, React 19, TypeScript strict, Tailwind 4,
   shadcn/ui, TanStack Query, Recharts, Zod e Vitest. Nenhuma dependência trocada.
3. **Acesso à API por uma única porta** (`src/lib/api/`), com contrato zod espelhando
   `api/schemas.py`. O `recorte` vem sempre do catálogo.
4. **Estado dos filtros na URL**, em search params validados com zod; valor inválido cai no padrão.
5. **Consultas no navegador** com `useQuery`, sem loaders SSR; `staleTime` de 1 h e nova tentativa
   apenas para falha de rede.
6. **Landing ilustrativa separada dos dados reais:** `/` não consulta a API e é rotulada como
   demonstrativa; dado real só em `/painel`.
7. **O frontend não calcula** indicador derivado nem percentual: exibe apenas valores da API.

## Alternativas consideradas

- **Git subtree do repositório do Lovable:** descartado em favor da cópia simples; mudanças futuras
  no Lovable são trazidas manualmente.
- **Loaders SSR para as consultas:** descartados porque a API é local.
- **Estado dos filtros em memória:** descartado por não ser compartilhável nem reaproveitável por
  telas futuras.
- **Lista fixa de KPIs no código:** descartada; os KPIs são gerados a partir do catálogo da API.

## Consequências

- Não há sincronização automática com o Lovable.
- O contrato zod precisa acompanhar `api/schemas.py`; divergência aparece como erro de contrato.
- A landing funciona com a API fora do ar, mas mantém elementos ilustrativos enquanto não houver
  endpoint equivalente.
- Indicador novo no catálogo aparece no painel sem alteração de código.
- O build herdado mira Cloudflare Workers; o alvo de implantação permanece em aberto.
- Os módulos `lovable-error-reporting.ts` e `error-capture.ts` foram mantidos; fora do editor do
  Lovable não enviam dados.
