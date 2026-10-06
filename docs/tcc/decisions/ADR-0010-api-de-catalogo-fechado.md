# ADR-0010 — API de catálogo fechado sobre a camada analítica
- **Data:** 2026-09-26
- **Status:** Aceita

## Contexto

O dashboard e o mapa precisam de um backend que sirva os indicadores validados na Fase 4
([INDICADORES.md](../methodology/INDICADORES.md), [ADR-0009](ADR-0009-criterio-de-admissibilidade-de-indicadores.md)).
Os dados do Censo permitem produzir números errados sem erro de execução: recorte territorial
omitido ([ADR-0004](ADR-0004-recorte-territorial-duplo.md)), `tp_dimensao` ignorada, linhas
`'Cursos a distância'` agregadas como território, métricas de IES somadas após JOIN com cursos,
rede comparada por códigos crus ([ADR-0007](ADR-0007-comparacao-de-rede-via-ds-rede.md)).
Um backend que aceitasse consultas arbitrárias exporia essas armadilhas ao cliente.

## Decisão

1. A API consulta **somente** o DuckDB local ([ADR-0003](ADR-0003-camada-analitica-local-duckdb.md));
   nunca o PostgreSQL. Não lê `.env` e não mantém credencial em processo.
2. **Catálogo fechado** de nove indicadores diretos (IND-D-01..09) em `api/indicadores.py`.
   O cliente escolhe apenas enums: indicador, nível (brasil/regiao/uf/municipio), recorte,
   dimensão, rede, UF e `limite` (≤ 6000). O SQL é montado a partir de fragmentos fixos com
   parâmetros nomeados.
3. **Regras metodológicas impostas no servidor**, com 422 explicativo: recorte obrigatório e
   coerente com a ficha (IES/docentes/técnicos = sede; cursos = oferta); `tp_dimensao` obrigatória
   em cursos e proibida em IES; dimensões EAD nacional/exterior só no nível brasil; cursos, vagas e
   inscrições territorializados só no presencial; filtro de 7 dígitos em todo nível territorial de
   cursos; IES nunca combinada com cursos; mapa municipal pré-agrega e depois faz JOIN N:1 com
   `municipio` só para coordenadas; `valor_sem_territorio` declara a perda (regra 8); `notas`
   informa que Pública inclui as 28 IES Especial.
4. **Conexão DuckDB travada:** `read_only`, `enable_external_access=false`, autoload/autoinstall
   desligados, `memory_limit` 1 GB, `lock_configuration=true`, timeout de 10 s via `interrupt()`.

Detalhe operacional em [API.md](../architecture/API.md).

## Alternativas consideradas

- **Endpoint SQL genérico / consulta livre:** rejeitada por segurança e por permitir números
  metodologicamente inválidos.
- **ORM/SQLAlchemy com camada de repositório:** rejeitada; não agrega valor a agregações fixas
  sobre arquivo embarcado, e o SQL explícito é o artefato auditado.
- **Um endpoint por indicador × nível:** rejeitada por proliferação de rotas.
- **Consultar o PostgreSQL diretamente:** rejeitada pela ADR-0003.

## Consequências

- Todo número servido corresponde a uma ficha de INDICADORES.md e a uma combinação admitida;
  combinações inválidas são recusadas com explicação, e não calculadas.
- Novo indicador exige inclusão explícita no catálogo, com suas regras e testes.
- A superfície de ataque restringe-se a enums validados; `CREATE TEMP TABLE`, aceito pelo DuckDB
  mesmo em `read_only`, não é alcançável hoje, mas deve ser bloqueado pelo validador AST do
  Analista IA.
- A API mantém a base aberta; no Windows, o ETL exige que a API seja parada antes de regravar.
