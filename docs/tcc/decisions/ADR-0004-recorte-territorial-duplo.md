# ADR-0004 — Recorte territorial explícito: sede da IES e local de oferta

- **Data:** 2026-09-05
- **Status:** Aceita

## Contexto

A pergunta "quantas instituições de ensino superior há no município X" admite duas respostas
igualmente defensáveis, e a auditoria de 2026-09-05 mediu a distância entre elas:

| Recorte | Fonte | Municípios | O que responde |
|---|---|---|---|
| **Sede da IES** | `ies.co_municipio_ies` | **698** | onde a instituição está fisicamente instalada |
| **Local de oferta** | `cursos.co_municipio` | **3.551** | onde o ensino superior é acessível, incluindo polos de EAD |

São **2.853 municípios** com oferta sem sediar nenhuma instituição — praticamente todos, polos de
educação a distância. Nenhum município com sede está ausente da tabela de cursos.

A diferença é de aproximadamente cinco vezes. Escolher um recorte em silêncio produziria um mapa
que responde a uma pergunta que o leitor não fez, e a escolha ficaria invisível na interface.

## Decisão

A plataforma **não escolhe**: expõe o recorte como **controle explícito de primeira classe**,
com os dois modos disponíveis e o modo corrente sempre visível.

Consequências de projeto:

- todo indicador territorial declara o recorte sob o qual foi calculado;
- toda exportação e todo texto gerado pelo Analista IA carregam essa declaração;
- a camada semântica trata o recorte como **dimensão obrigatória** de qualquer consulta territorial,
  e um QueryPlan que a omita é inválido;
- quando a pergunta em linguagem natural for ambígua quanto ao recorte e a resposta mudar conforme
  a escolha, o Analista IA **pergunta** em vez de assumir.

O recorte por sede é o **padrão inicial** da interface, por ser a leitura mais conservadora e a que
corresponde à noção corrente de "instituição instalada no município". Trata-se de um padrão, não de
uma preferência metodológica: nenhum dos dois recortes é tido como mais correto.

## Alternativas consideradas

**Adotar apenas a sede.** Simples e conservador, mas apagaria o fenômeno mais expressivo do Censo
2024 — a educação a distância responde por 93,5% das linhas da tabela de cursos, e o acesso via polo
alcança cinco vezes mais municípios.

**Adotar apenas o local de oferta.** Retrataria melhor o acesso, mas equipara campus físico a polo
de EAD, o que distorce qualquer leitura sobre instalação de infraestrutura acadêmica.

Ambas foram rejeitadas pelo mesmo motivo: transformam uma ambiguidade real do dado numa decisão
oculta de implementação.

## Consequências

A ambiguidade deixa de ser limitação e passa a ser **resultado** do trabalho: a comparação entre os
dois recortes é, em si, um achado sobre a interiorização do ensino superior brasileiro e material
direto para a discussão do TCC.

O custo é maior complexidade em toda a cadeia — dois caminhos de agregação, rotulagem obrigatória
nos indicadores, e um eixo adicional na camada semântica. A interface ganha um controle que precisa
ser compreensível sem exigir que o usuário conheça a estrutura do Censo.

Há risco de comparação indevida entre números de recortes diferentes; a rotulagem obrigatória existe
para mitigá-lo, e comparações entre recortes devem ser bloqueadas ou explicitamente sinalizadas.

## Referências

- [`../../data/DATA_GRAIN.md`](../../data/DATA_GRAIN.md) — grain territorial e as contagens
- [`../../data/JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md) — chaves e cardinalidade
- [`../architecture/AI_ANALYST.md`](../architecture/AI_ANALYST.md) — tratamento de ambiguidade
