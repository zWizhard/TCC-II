# Configuração do ambiente de desenvolvimento assistido

## Objetivo

Estruturar o repositório do TCC-II — até então completamente vazio — como ambiente de trabalho
assistido por IA, estabelecendo as regras operacionais, a documentação base e os mecanismos de
proteção que serão usados ao longo de todo o desenvolvimento. Nenhuma funcionalidade do produto
foi implementada nesta etapa.

## Trabalho realizado

Criado `CLAUDE.md` como memória operacional curta: escopo (exclusivamente Educação Superior),
arquitetura pretendida, regra de não inventar schema, postura read-only no banco, workflow e
critérios para interromper e consultar o autor.

Configurados cinco subagentes (`data-engineer`, `frontend-geospatial`, `ai-data-analyst`,
`reviewer`, `tcc-documentarian`) e seis skills (`schema-audit`, `join-audit`, `analytics-feature`,
`geospatial-feature`, `text-to-sql`, `release-check`), além de quatro hooks de proteção e do
`.gitignore`.

Estruturada a documentação em `docs/`: mapa de navegação, levantamento do ambiente da máquina,
arquitetura do Analista IA, e os três documentos de dados (`DATA_DICTIONARY`, `DATA_GRAIN`,
`JOIN_STRATEGY`) — todos deliberadamente vazios e marcados como *A confirmar*.

## Decisões técnicas/metodológicas

**Documentação em camadas.** `CLAUDE.md` permanece mínimo e é carregado em toda sessão; o detalhe
fica em `docs/` e só é lido quando a tarefa o exigir. A motivação é o custo acumulado de contexto
ao longo de muitas sessões de desenvolvimento.

**Hooks em Python**, não em shell, por portabilidade no ambiente Windows/PowerShell do autor.
O hook de encerramento é estritamente consultivo — sempre retorna sucesso e apenas emite mensagem —
com salvaguarda adicional de `stop_hook_active`, de modo que não pode gerar laço de execução.

**O subagente revisor recebeu somente ferramentas de leitura**, para que a revisão independente não
se converta em alteração silenciosa do que deveria estar apenas sendo avaliado.

**Nenhuma documentação de dados foi preenchida por suposição.** Os três arquivos de `docs/data/`
registram o procedimento obrigatório — prova de grain por `COUNT(*)` versus `COUNT(DISTINCT chave)`,
e validação de JOIN por linhas antes/depois, duplicações, chaves órfãs e métrica de controle — mas
nenhuma tabela real, por ainda não haver acesso ao banco. Registrou-se também o cuidado de definir
se o grain territorial da IES é a sede ou o local de oferta, pois a escolha altera a resposta de
"quantas IES tem o município X".

## Validação

Escrita a suíte de regressão `.claude/hooks/_selftest.py`, com 46 casos cobrindo tanto o que os
hooks devem bloquear quanto o que não podem bloquear — falso positivo em hook é mais custoso que
falso negativo, por travar trabalho legítimo em toda sessão. Todos passam.

Dois defeitos reais foram encontrados **pelo teste** e corrigidos: arquivos Python com BOM UTF-8
eram falsamente reportados como erro de sintaxe (corrigido com leitura em `utf-8-sig`); e o detector
de segredos, por usar limite de palavra, não reconhecia `DB_PASSWORD`, já que o sublinhado é
caractere de palavra (corrigido com *lookarounds*). Verificou-se ainda que nenhum arquivo do próprio
projeto dispara falso positivo, e que o hook de encerramento executa em 0,04 s.

## Problemas/limitações

O ambiente carece de **git**, **Node/npm** e **Ollama**; sem git não há histórico nem proteção
contra perda de trabalho. Decidiu-se instalar o git imediatamente e adiar Node e Ollama até que
frontend e Analista IA entrem em pauta.

O repositório está dentro do OneDrive, com risco de conflito de sincronização em `.git`, `.venv` e
`node_modules`. Decidiu-se **movê-lo para fora do OneDrive**, com o GitHub assumindo o papel de
backup — execução pendente, por ser ação manual do autor.

Durante a configuração, a regra de negação `Read(./.env.*)` acabou alcançando o próprio
`.env.example`, impedindo sua criação. Corrigida por regras explícitas para `.env`, `.env.local`,
`.env.development` e `.env.production`; o arquivo de exemplo foi então criado, sem valores reais.
A proteção efetiva permanece no hook `protect_secrets.py`, que bloqueia leitura e escrita de
arquivos de credenciais e rejeita um `.env.example` que contenha valor aparentemente real.

O hardware levantado (RTX 2070 SUPER com 8 GB de VRAM, 32 GB de RAM) limita o LLM local à faixa de
7–8 bilhões de parâmetros em quantização Q4/Q5.

> A confirmar: tecnologia, acesso e existência de usuário somente-leitura no Big Data IESB.

## Próximo passo

Instalar o git, mover o repositório para fora do OneDrive e inicializar o versionamento;
em seguida, confirmar a tecnologia e o acesso ao Big Data IESB para executar a primeira
auditoria de schema.
