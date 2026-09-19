# ADR-0007 — Comparação de rede entre IES e cursos via `ies.ds_rede`

- **Data:** 2026-09-05
- **Status:** Aceita

## Contexto

A dimensão rede administrativa (pública/privada) é transversal a praticamente todo indicador do
projeto, mas as duas tabelas a expressam de forma incompatível: `inep_educacao_superior_ies.tp_rede`
é código (`'1'`/`'2'`) e `inep_educacao_superior_cursos.tp_rede` é rótulo (`Pública`/`Privada`).
Comparar as colunas diretamente produz zero correspondências sem gerar erro.

A auditoria da Fase 2 identificou a coluna `ies.ds_rede`, até então não documentada: mapeamento 1:1
com `ies.tp_rede` (`1` → `Pública`, 317 IES; `2` → `Privada`, 2.244 IES), usando exatamente os mesmos
rótulos de `cursos.tp_rede`.

## Decisão

Adotar `ies.ds_rede` ↔ `cursos.tp_rede` como pareamento canônico da dimensão rede em filtros,
agrupamentos, JOINs e na camada semântica do Analista IA. Nenhuma tradução manual de `1`/`2` deve ser
escrita em consulta, indicador ou prompt.

A ressalva metodológica anterior permanece válida e deve acompanhar todo indicador por rede:
`Pública` inclui as 28 IES de categoria "Especial", logo não é sinônimo estrito de rede pública.

## Alternativas consideradas

- **`CASE` de tradução em cada consulta.** Funciona, mas replica a mesma regra em vários pontos e
  qualquer omissão passa silenciosa; foi a origem do risco que esta ADR elimina.
- **Coluna derivada na camada DuckDB.** Redundante: `ds_rede` já existe na origem e a derivação
  acrescentaria um passo de ETL a manter sincronizado.
- **Normalizar tudo para código na camada analítica.** Exigiria converter `cursos.tp_rede`, a tabela
  de 720.349 linhas, para ganhar apenas compactação de rótulo.

## Consequências

- Comparações de rede entre as duas tabelas deixam de depender de convenção implícita.
- `ies.tp_rede` continua útil para leitura de código, mas não deve ser usada em comparação
  entre tabelas.
- A camada semântica do Analista IA deve expor um único conceito "rede" mapeado a `ds_rede`/`tp_rede`
  conforme a tabela consultada, com a ressalva das IES "Especial" registrada na definição do
  indicador.
- `docs/data/DATA_DICTIONARY.md` passa a documentar `ds_rede`; a incompatibilidade original segue
  registrada como armadilha conhecida.

## Desfecho da verificação (2026-09-05)

O mapeamento foi confirmado diretamente no banco, e não apenas nas extrações: `ies.ds_rede` mantém a
correspondência 1:1 com `ies.tp_rede` (`1` → `Pública`, 317 IES; `2` → `Privada`, 2.244 IES) e o
domínio de `cursos.tp_rede` é exatamente `Privada` | `Pública`. Nenhum rótulo divergente, acentuação
alternativa ou categoria adicional. A decisão permanece **Aceita**, sem alteração. Detalhes no devlog
[Conexão direta ao banco e confirmação das pendências da Fase 2](../devlog/2026-09-05_conexao-direta-e-confirmacao-da-fase-2.md).
