# Conexão direta ao banco e confirmação das pendências da Fase 2

## Objetivo

Estabelecer conexão programática somente-leitura ao Big Data IESB a partir do repositório e verificar
contra o banco todos os achados que a auditoria da Fase 2 havia registrado como `A confirmar`
([ADR-0006](../decisions/ADR-0006-auditoria-sobre-extracoes-versionadas.md)).

## Trabalho realizado

Com as credenciais fornecidas pelo autor, foi criado `scripts/db/run_sql.py`: executor que lê o `.env`,
aplica as três travas de sessão da [ADR-0002](../decisions/ADR-0002-sessao-somente-leitura.md), aborta
se `default_transaction_read_only` não retornar `on`, bloqueia DDL/DML no cliente, grava cada result
set em CSV e nunca imprime host, usuário ou senha. `psycopg[binary]` 3.3.5 entra como primeira
dependência de produto no `pyproject.toml`.

Executados os scripts `06_auditoria_fase2.sql` e o novo `07_fase2_aprofundamento.sql`, com evidências
versionadas em `docs/data/raw/diagnostics/` conforme a
[ADR-0005](../decisions/ADR-0005-versionamento-das-evidencias-de-auditoria.md). Foram atualizados
`DATA_DICTIONARY.md` (tipos reais das 305 colunas, nulidade, sentinelas), `DATA_GRAIN.md`,
`JOIN_STRATEGY.md`, `CLAUDE.md` e `ENVIRONMENT.md`.

## Decisões técnicas/metodológicas

Duas afirmações da documentação estavam **erradas** e foram corrigidas:

1. **Não há padding em `co_municipio_ies`.** O tipo é `character(7)` e o comprimento é 7 no bruto e
   após `btrim()`. A exigência de `btrim()` e o bloqueio da Fase 3 registrados na ADR-0006 caem; o
   JOIN territorial direto é seguro. Padding real só em `nu_cep_ies` (`character(12)`), não usada.
2. **Não existe `NULL` nas tabelas do Censo.** `cursos` é `NOT NULL` nas 223 colunas; `ies` só admite
   em `qt_tec_total`, onde há 0. Os 459 `sg_ies` e 26 `nu_cep_ies` "vazios" são string vazia — o teste
   correto é `btrim(col) = ''`.

Confirmados no banco: chave natural de `cursos` (720.349 distintos), contaminação por
`'Cursos a distância'` em quatro colunas (11.778 linhas cada), `ds_rede` como ponte de rede
(ADR-0007), `qt_doc_total = qt_doc_exe`, permissões, e o recorte territorial da ADR-0004
(698 sede / 3.551 oferta / 0 órfãos).

O agente não cria nem lê o `.env`; o executor roda com sandbox desabilitada porque a sandbox estende a
negativa de leitura aos processos filhos — quem lê o arquivo é o processo Python, que não imprime os
valores.

## Problemas/limitações

- **`municipio` tem 5.599 linhas, mas só 5.571 municípios.** As outras 28 são sentinelas: 26
  `'Município Ignorado - <UF>'` (código terminado em `00000`; Rondônia não tem a sua), `9900000`
  (EXTERIOR, com coordenada de Paris) e `9999999` (Exterior ou EAD). Explica de uma vez as coordenadas
  fora do envelope do Brasil e o excedente de ~29 municípios. O Censo não referencia nenhuma sentinela
  (0 IES, 0 linhas de cursos), então o mapa não herda o problema — o denominador, sim.
  > A confirmar: se o denominador municipal do projeto adota 5.571 explicitamente.
  >
  > **Correção posterior — 2026-09-19 (Fase 4).** A contagem de 5.571 permanece correta, mas a
  > denominação usada acima ("5.571 municípios") não. Excluindo `2605459` restam 5.570:
  > Fernando de Noronha é distrito estadual de Pernambuco, não município. O universo é
  > **5.571 municípios e equivalentes**. A pendência acima foi fechada: o projeto adota 5.571
  > explicitamente como denominador — ver
  > [`../methodology/INDICADORES.md`](../methodology/INDICADORES.md) (IND-R-02).
- **`ibge_populacao_estimada` tem 50 pares `(ano, município)` duplicados**, todos com população
  divergente (até 100×: município 150680 em 2006, 276.074 vs 2.606), nos anos 2000–2009 e 2011–2020.
  2022, 2024, 2025 e 2026 estão limpos, mas todo JOIN deve filtrar o ano explicitamente.
  > A confirmar: qual valor é correto nos anos afetados (relevante só em série histórica, fora de escopo).
- **As 9 linhas de EAD sem território** são 9 cursos de 9 IES distintas, 41 matrículas, `qt_curso` = 0,
  todos com linhas de município válido em paralelo (291 no total). Filtrar `tp_dimensao` não as
  elimina; o filtro territorial descarta 41 de 10.227.266 matrículas — irrelevante numericamente, mas
  o total do mapa não fecha com o nacional e a diferença deve ser declarada.
- **A contaminação é estrutural na origem:** as oito colunas territoriais de `cursos` são
  `character varying(18)`, e `'Cursos a distância'` tem exatamente 18 caracteres — até `sg_uf`, que
  guardaria 2. Não é acidente de exportação.
- **Microrregião não é identificável nem pelo nome:** 65 códigos, 382 nomes, 383 pares
  `(co_uf_ies, co_microrregiao)`. Mesorregião fecha (15 códigos, 131 nomes, 131 pares).
- Percalços de ambiente: existia um **diretório** chamado `.env`, e a cópia do exemplo para dentro dele
  causou `PermissionError [Errno 13]` (conferir com `Get-Item .env`; `Mode` deve começar com `-`); o
  `uv` criou o `.venv` com Python 3.14.6, não 3.12.10 — funciona sob `requires-python = ">=3.12"`, e a
  documentação de ambiente foi corrigida.
- Nenhum JOIN executado: segue fora do escopo da Fase 2.

## Validação

`SELECT version()` retornou PostgreSQL 17.9, database `iesb`, usuário `data_iesb`, com
`default_transaction_read_only = on`. Script 06 produziu 305 + 29 linhas em dois blocos e o 07,
18 linhas; três CSV de evidência gravados. `ruff check` limpo em `run_sql.py`.

## Próximo passo

Fase 3 — validação de JOIN (skill `join-audit`), agora desbloqueada, começando por IES × `municipio` e
por `cursos` × `municipio` com o filtro territorial obrigatório.
