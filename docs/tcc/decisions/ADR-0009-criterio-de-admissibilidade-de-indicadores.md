# ADR-0009 — Critério de admissibilidade de indicadores

- **Data:** 2026-09-19
- **Status:** Aceita

## Contexto

A Fase 4 formalizou os indicadores da plataforma. A auditoria de suporte
(98 verificações sobre a cópia DuckDB local, evidências em
[`raw/diagnostics/2026-09-19_familias_metricas.csv`](../../data/raw/diagnostics/2026-09-19_familias_metricas.csv)
e [`_semantica_metricas.csv`](../../data/raw/diagnostics/2026-09-19_semantica_metricas.csv))
mostrou que a diferença entre um indicador correto e um indicador errado, nesta base, **não
aparece na execução**. Três casos concretos:

1. **Dimensão de oferta.** `SUM(qt_mat)` vale 10.227.266, 5.037.875 ou 5.186.852 conforme quais
   valores de `tp_dimensao` entram na conta. Vaga e matrícula de EAD **nem sequer coexistem na
   mesma dimensão**: as 18,6 milhões de vagas a distância estão numa dimensão sem território,
   onde `qt_mat` é zero. Qualquer padrão silencioso responderia a uma pergunta que o leitor não
   fez.
2. **Decomposições que não fecham.** As subcolunas de financiamento excedem o total em 78.502
   matrículas, e os 12 subtipos de reserva de vagas somam 1.116.988 contra 648.225 — divergindo
   nos dois sentidos. Apresentadas como fatias de um todo, produzem percentual acima de 100%.
   Já as seis decomposições do corpo docente e as cinco de perfil do estudante particionam o
   total com **zero** linhas divergentes. O comportamento não é previsível pelo nome da coluna:
   só o teste distingue.
3. **Taxas de fluxo.** Só existe o Censo de 2024. Concluintes e ingressantes do mesmo ano são
   coortes distintas, e situações de vínculo (`qt_sit_*`) excedem as matrículas em 267.780
   linhas. Uma razão entre essas colunas executa sem erro e é lida como taxa de conclusão ou de
   evasão.

O que falta não é mais documentação de dados — é um **critério declarado** que decida, antes da
implementação, se um número pode ser publicado.

## Decisão

Um indicador só é publicável na plataforma se satisfizer as três condições abaixo. O critério
vale para o dashboard, o mapa, as exportações e o Analista IA, sem exceção.

**1. Dimensão de oferta explícita.** `tp_dimensao` é dimensão obrigatória e **não tem padrão
universal**. A interface expõe um seletor de primeira classe, com a dimensão corrente sempre
visível; todo indicador de curso declara sob quais dimensões foi calculado; a camada semântica
trata a dimensão como obrigatória e **um QueryPlan que a omita é inválido**. Quando a dimensão
altera o resultado e a pergunta em linguagem natural é ambígua, o Analista IA **pergunta**.
Esta regra é gêmea da [ADR-0004](ADR-0004-recorte-territorial-duplo.md), que já faz o mesmo com
o recorte territorial: os dois eixos são declarados, nunca assumidos.

**2. Composição só sobre decomposição provada.** Um percentual, uma fatia de gráfico ou uma
composição só podem ser publicados se as partes **particionarem exatamente** o total — soma
igual em todas as linhas, verificada e registrada em evidência versionada. Família que se
sobrepõe, ou que deixa resíduo, é publicável **apenas como agregado**, e sua decomposição vai
para a quarentena. O teste é pré-requisito de implementação, não etapa de validação posterior.

**3. Nenhuma taxa que pressuponha coorte.** Com um único ano, nenhum indicador pode relacionar
entrada e saída como se acompanhasse uma turma. Isso veda taxa de conclusão, taxa de evasão,
taxa de sucesso, eficiência e qualquer métrica de evolução — inclusive no vocabulário da UI e
nas respostas do Analista IA. O bloqueio é de nomenclatura **e** de cálculo: renomear não
libera, e calcular sem nomear também não.

Indicador que falha em qualquer das três vai para o bloco de **quarentena** de
[`../methodology/INDICADORES.md`](../methodology/INDICADORES.md), com o motivo técnico
registrado — a recusa fica auditável e não reaparece por engano.

## Alternativas consideradas

**Fixar um padrão para `tp_dimensao`** (só presencial, ou o total). Simplificaria tudo, e foi
rejeitada pelo mesmo motivo que a ADR-0004 rejeitou fixar o recorte: transformaria uma
característica real do dado numa decisão invisível de implementação. "Presencial" apagaria
metade das matrículas do país; "total" somaria oferta física, polo, agregado nacional e oferta
no exterior num único número sem significado.

**Validar as decomposições só na revisão do resultado.** Rejeitada: o percentual acima de 100%
aparece na tela antes de alguém revisar, e a correção depois custa mais que o teste antes.

**Publicar taxas de fluxo com ressalva textual.** Rejeitada: a ressalva não sobrevive ao
compartilhamento de um print, de uma exportação ou de uma frase do Analista IA. Com coorte
ausente, o número não é impreciso — é outro número.

## Consequências

O conjunto de indicadores fica menor e defensável. Dois candidatos saíram do bloco derivado para
a quarentena por efeito direto da regra 2 (composição do financiamento por tipo; composição da
reserva de vagas por subtipo), e quatro tiveram o escopo reduzido pela regra 1 — vagas e
inscrições não são territorializáveis em EAD, e a razão ingressantes/vagas passou a ser
exclusivamente presencial.

O custo é real: mais um eixo obrigatório na camada semântica e na interface, um teste de
fechamento antes de cada nova composição, e um vocabulário controlado que o Analista IA precisa
respeitar. Em troca, nenhum número publicado depende de um pressuposto que ninguém verificou.

A regra 2 tem efeito acumulativo: cada família de colunas auditada e aprovada amplia o que a
plataforma pode mostrar, e a evidência fica versionada
([ADR-0005](ADR-0005-versionamento-das-evidencias-de-auditoria.md)). Famílias ainda não testadas
— forma de ingresso, PARFOR, apoio social, mobilidade acadêmica — não estão proibidas, estão
pendentes.

## Referências

- [`../methodology/INDICADORES.md`](../methodology/INDICADORES.md) — as fichas e a quarentena
- [ADR-0004](ADR-0004-recorte-territorial-duplo.md) — o eixo territorial, regra gêmea da nº 1
- [ADR-0003](ADR-0003-camada-analitica-local-duckdb.md) — camada onde a auditoria rodou
- [`../../data/DATA_GRAIN.md`](../../data/DATA_GRAIN.md) — grain e `tp_dimensao`
- [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) — validação do QueryPlan
