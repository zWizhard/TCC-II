# ADR-0019 — Camada semântica declarativa em Python, recuperação por léxico e prompt sem schema

- **Data:** 2026-10-07
- **Status:** Aceita

## Contexto

O Analista IA precisa traduzir perguntas em linguagem natural para conceitos da base do Censo da
Educação Superior 2024 sem inventar tabela, coluna, categoria ou métrica. O projeto tem orçamento
zero, o Ollama não está instalado e os literais e expressões dos indicadores já existem, validados,
em `api/indicadores.py`. As ambiguidades centrais alteram o resultado em ordens de grandeza
(por exemplo, 2.561 IES contra 206 com organização acadêmica "Universidade").

## Decisão

1. **Fonte da verdade em Python.** A camada (`api/semantica/`) é um conjunto de modelos Pydantic
   imutáveis (`frozen`, `extra=forbid`), exportável como JSON e com JSON Schema. Literais,
   expressões, recortes e limitações são **derivados** de `api/indicadores.py`, não redigitados. A
   importação do pacote falha se houver referência pendente.
2. **Recuperação determinística por léxico**, sem LLM: n-gramas normalizados, maior casamento
   primeiro. Devolve apenas os itens casados e o fecho de dependências (entidade e grain, dimensões
   obrigatórias, regras aplicáveis), além de ambiguidades disparadas, recusas e termos não
   reconhecidos. Termo não mapeado é rejeição explícita. O resultado declara uma situação: vazia,
   pergunta longa, recusada, termo não mapeado, requer esclarecimento, lugar não resolvido, sem
   métrica ou pronta.
3. **O schema bruto não é enviado ao LLM.** `para_prompt()` não contém expressão SQL, nome de
   coluna, tabela física, predicado nem relacionamento; o modelo escolherá apenas identificadores.
   O detalhe técnico fica em `para_dict()`, de uso do backend. A pergunta é limitada a 500
   caracteres, o prompt a 16.000, e a pergunta entra delimitada e rotulada como dado não confiável.
4. **Recusa de razões é estrutural.** Duas medidas ligadas por conector de razão só são aceitas se
   o par for uma razão do catálogo, na ordem numerador/denominador.

## Alternativas consideradas

- **YAML como fonte da verdade:** descartado por exigir dependência nova e criar uma segunda cópia
  dos literais já presentes no catálogo de indicadores.
- **Recuperação por embeddings:** descartada porque o Ollama está ausente, o orçamento é zero e o
  resultado não seria determinístico nem testável.

## Consequências

- O prompt típico tem cerca de 6 KB, contra 243 KB da camada exportada.
- O comportamento é integralmente testável sem modelo: 250 testes, 198 deles sem a base.
- A cobertura lexical depende de sinônimos mantidos à mão; 67 deles têm status `proposto` e
  aguardam confirmação do autor.
- Paráfrases fora do léxico resultam em "termo não mapeado", não em resposta aproximada; há falsos
  positivos seguros conhecidos (ver o
  [devlog da Fase 12](../devlog/2026-10-07_fase-12-camada-semantica.md)).
- Operadores e limiares são apenas detectados, negação leva a esclarecimento e não há resolução de
  município ou curso por nome; a interpretação fica para o QueryPlan (Fase 13), que será validado
  contra esta camada.
