# Fase 13 — Analista IA e Text-to-SQL (backend)

## Objetivo

Implementar no backend o pipeline Pergunta → camada semântica → QueryPlan (Pydantic) → validação →
SQL gerado pelo backend → validação AST → DuckDB somente-leitura → análise em Python → spec de
visualização, sem que SQL produzido pelo LLM chegue ao banco.

## Trabalho realizado

- Pacote `api/analista/` (`plano`, `validacao`, `sql`, `validador_sql`, `llm`, `analise`,
  `visualizacao`, `pipeline`, `rotas`) e endpoint `POST /api/v1/analista/perguntas` (corpo
  `{pergunta}`). As respostas são HTTP 200 com `situacao` ∈ respondida, requer_esclarecimento,
  recusada, nao_mapeada, nao_suportada, pergunta_invalida, plano_invalido.
- `api/config.py` (provedor, URL e modelo do Ollama — vazio por padrão —, prazo, teto de tokens e
  de linhas), `api/erros.py` (ModeloIndisponivel e ModeloOcupado 503, RespostaDoModeloInvalida 502,
  SqlRejeitado e ConsultaFalhou 500) e `api/main.py` (roteador, provedor em `app.state`, CORS com
  GET e POST).
- `api/semantica/texto.py` e `recuperacao.py`: número no formato brasileiro como token único,
  `numeros_citados` com papel (limiar, limite, município, sem papel), `ordem`, remoção de `<`/`>`
  do texto do usuário e ids de regra fora do prompt.
- Dependências: `sqlglot>=30.21.0,<31` e `httpx` como dependência de produto.
- Escopo v1: 11 métricas diretas e as razões `ingressantes_por_vaga` e `inscricoes_por_vaga`, sem
  JOIN, com quebra por nível territorial e por dimensão categórica enumerada. Saem como
  `nao_suportada`: composições, decomposições, rótulo CINE, `matriculas_por_100_mil_habitantes`,
  `financiamento`, `reserva_vagas` e medidas de IES e de cursos na mesma pergunta.

A descrição dos módulos e do QueryPlan está em
[`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md).

## Decisões técnicas/metodológicas

A decisão estruturante está na
[ADR-0020](../decisions/ADR-0020-queryplan-fechado-validado-contra-o-contexto.md): o LLM apenas
escolhe identificadores de um plano fechado, validado contra a camada semântica e contra o contexto
determinístico da pergunta; o SQL é montado pelo backend e passa por validador AST em allowlist;
explicação e análise são determinísticas.

Decisões complementares: dimensão de oferta não citada leva a esclarecimento (sem padrão); o nível
territorial é derivado do contexto; sem modelo configurado, a API responde 503 explicado sem
tentar a rede; um semáforo limita o LLM a uma chamada simultânea.

## Validação

- 425 testes do Analista; suíte completa com 1021 aprovados (eram 596). `ruff check`,
  `ruff format --check` e `mypy api` limpos, reexecutados pelo agente principal.
- Revisão adversarial: nenhum achado crítico e cinco importantes, todos corrigidos com teste de
  regressão — alias liberando coluna não exposta (I-1); nome de CTE dando acesso a views de sistema
  do DuckDB (I-2); JOIN e produto cartesiano aceitos (I-3); números "100.000" e "1,5" partidos em
  dois tokens e número sem papel (I-4); operador, direção, subconjunto de métricas e quebras livres
  (I-5). I-1 a I-3 não eram alcançáveis pelo gerador: eram falhas de defesa em profundidade.
- Achados menores M-1 a M-9 corrigidos, M-5 (prazo total) e M-6 (semáforo configurável)
  parcialmente; M-10 ficou fora.
- Em oito planos, os números coincidiram com os de `consultar_indicador`; controles nacionais
  10.227.266 matrículas e 45.776 cursos.

## Problemas/limitações

- O pipeline nunca foi exercitado com modelo real (Ollama ausente): aderência ao JSON Schema, taxa
  de plano inválido e robustez a injeção com LLM real são desconhecidas.
- As correções da revisão não passaram por segunda rodada do revisor.
- O frontend não consome o endpoint e a spec de visualização não tem intérprete no cliente.
- Sem autenticação nem limite de taxa: uso local e de demonstração.
- Município apenas por código IBGE, sem nome nas linhas.
- "Com menos X" vira esclarecimento e "no máximo N" é termo não mapeado; união e negação seguem não
  representadas; "top N" sai com `truncado=true`.
- Cobertura das combinações métrica × dimensão conferida por amostra, não exaustiva.
- "Técnicos" não é mapeado em "docentes e técnicos" (M-10).

> A confirmar: base de `financiamento` e `reserva_vagas` no plano, dimensão de oferta padrão e os
> 21 sinônimos `proposto` — decisões pendentes do autor.

## Próximo passo

Instalar o Ollama, escolher o modelo por teste empírico e medir a aderência ao QueryPlan;
submeter as correções a nova revisão; integrar o endpoint ao frontend.
