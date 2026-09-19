---
name: analytics-feature
description: Implementar um indicador ou análise de ponta a ponta — dados, cálculo, endpoint de API, UI e teste. Use quando a tarefa for entregar uma métrica ou visão analítica nova da Educação Superior.
---

# analytics-feature

Fluxo: **dados → cálculo → API → UI → teste**. Nenhuma etapa é pulada; se uma não se aplica, diga por quê.

## 1. Dados

O schema das tabelas envolvidas está verificado? Se não, `schema-audit` primeiro.
Há JOIN no caminho? `join-audit` antes de confiar no número.

## 2. Definição do indicador (antes do código)

Escreva, e só então implemente:

- **Definição** — o que mede, em uma frase, sem jargão ambíguo.
- **Fórmula** — numerador e denominador explícitos.
- **Unidade** — contagem, %, razão, por 100 mil habitantes...
- **Grain** — a que nível se aplica (município-ano? IES-ano? curso-ano?).
- **Fonte** — tabela(s) e colunas reais.
- **Pressupostos** — o que se assume verdadeiro para o número fazer sentido.
- **Limitações** — o que ele **não** mede.

Nome honesto. Não chame de "taxa" o que é contagem, nem de "densidade" o que é razão bruta.
Correlação não vira causalidade no rótulo nem no texto da UI.

## 3. Cálculo

Em SQL ou Python — **nunca** no LLM. Cuidados recorrentes:
divisão por zero; denominador nulo ou ausente; média de médias (quase sempre errada — agregue os
componentes); municípios sem ocorrência (zero real vs. linha ausente — decida e documente qual usar);
comparação entre anos com quebra metodológica do Censo.

## 4. API

Endpoint FastAPI com response model Pydantic. Filtros como parâmetros validados, não interpolação.
`LIMIT` e timeout definidos. Conexão read-only.

## 5. UI

Componente React + TypeScript. Estados de carregamento, vazio e erro. Unidade e período visíveis.
A definição do indicador acessível ao usuário (tooltip ou nota) — um número sem definição é
inutilizável academicamente.

## 6. Teste

Um teste de cálculo com valores conhecidos (inclusive o caso-limite: denominador zero, série vazia).
Um teste do contrato do endpoint. Proporcional ao risco — não busque cobertura por cobertura.

## Encerramento

Registre a definição do indicador em `docs/data/` ou `docs/tcc/methodology/` e chame
`tcc-documentarian` com handoff compacto.
