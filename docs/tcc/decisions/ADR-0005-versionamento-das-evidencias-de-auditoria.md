# ADR-0005 — Versionamento das evidências de auditoria de dados

- **Data:** 2026-09-05
- **Status:** Aceita

## Contexto

As auditorias de schema, grain e desempenho realizadas em 2026-09-05 produziram quatro arquivos CSV
de diagnóstico em `docs/data/raw/diagnostics/` (~20 KB no total). São eles que sustentam as
afirmações registradas em `docs/data/` e nos devlogs — grain das tabelas, tipos reais, ausência de
índices, contaminação de `co_municipio`.

O `.gitignore` original excluía todo CSV (`*.csv`) e todo o conteúdo de `**/data/raw/`, regra criada
para manter fora do repositório as extrações brutas do Censo 2024 (560 MB e 1,2 MB). O efeito
colateral era que as evidências de auditoria também ficavam invisíveis no repositório remoto: um
leitor do TCC — orientador, banca ou terceiro — teria de aceitar os números por confiança, sem poder
verificá-los.

Havia ainda um defeito técnico na regra: `**/data/raw/` com barra final exclui o diretório, e o git
não reinclui arquivo contido em diretório excluído, de modo que nenhuma exceção funcionaria.

## Decisão

Versionar as evidências de auditoria e continuar ignorando os dados brutos.

O padrão passa a ser `**/data/raw/*` (sem barra final), com `*.csv` declarado antes das exceções e
uma exceção explícita para `docs/data/raw/diagnostics/*.csv`. Os CSVs do Censo permanecem ignorados.
`docs/data/raw/**` recebe `linguist-generated` no `.gitattributes`, para não poluir as estatísticas
de linguagem do repositório.

## Alternativas consideradas

- **Manter tudo ignorado.** Repositório mais enxuto, mas os resultados da auditoria ficariam sem
  prova pública e a reprodutibilidade dependeria de acesso ao banco institucional.
- **Versionar também os brutos do Censo.** Rejeitada: 560 MB excedem o limite prático do GitHub,
  tornariam o clone inviável e não acrescentam nada que o script de extração não reproduza.
- **Converter as evidências em tabelas Markdown dentro da documentação.** Legível, porém transcrição
  manual é sujeita a erro e perde o artefato original gerado pela consulta.

## Consequências

- As afirmações quantitativas do TCC passam a ser verificáveis a partir do repositório, sem acesso
  ao banco.
- Toda evidência de auditoria futura deve ser gravada em `docs/data/raw/diagnostics/` para ser
  versionada automaticamente; arquivo colocado fora desse diretório continuará ignorado.
- É preciso confirmar, antes de cada commit de diagnóstico, que o CSV não contém host, usuário ou
  qualquer credencial do banco. A varredura realizada em 2026-09-05 não encontrou segredos.
- O repositório cresce de forma controlada: o commit inicial candidato ficou em 192,5 KB.
