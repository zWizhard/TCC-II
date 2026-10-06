# API do Observatório — backend FastAPI (Fase 5)

Implementada em **2026-09-26**. Serve ao dashboard e ao mapa **apenas** os indicadores diretos
do Bloco A de [`../methodology/INDICADORES.md`](../methodology/INDICADORES.md), lidos do DuckDB
local ([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)).

```
.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
.venv/Scripts/python.exe -m pytest          # 70 testes; os de dados pulam se o .duckdb faltar
```

Documentação interativa em `/docs` (OpenAPI gerado pelo FastAPI).

## Estrutura

| Arquivo | Papel |
|---|---|
| `api/config.py` | `Settings` (pydantic-settings), **só variáveis de ambiente** — a API não lê o `.env` |
| `api/db.py` | conexão DuckDB somente-leitura e travada; timeout por consulta |
| `api/indicadores.py` | catálogo fechado: tabela, expressão, recorte e dimensões válidas por indicador |
| `api/consultas.py` | validação metodológica dos parâmetros + SQL de agregação |
| `api/schemas.py` | modelos de resposta (Pydantic) |
| `api/rotas.py` | endpoints |
| `api/erros.py` | erros de domínio e envelope único `{"erro": {"codigo", "mensagem"}}` |
| `api/main.py` | *app factory*, CORS, log de requisição, ciclo de vida da conexão |

Sem ORM nem SQLAlchemy: são nove agregações fixas sobre um arquivo embarcado, e o SQL explícito
é o que se audita. Sem camada de repositório: `consultas.py` é a única porta para o banco.

## Endpoints (somente `GET`)

| Rota | Retorno |
|---|---|
| `/api/health` | estado da API e da camada analítica |
| `/api/v1/metadados` | ano, fonte, **data de extração** (do `ETL_MANIFEST.json`), recortes, níveis, dimensões de oferta |
| `/api/v1/indicadores` | catálogo: código da ficha, unidade, recorte, dimensões territorializáveis, limitações |
| `/api/v1/indicadores/{slug}` | valores agregados |

Parâmetros de `/api/v1/indicadores/{slug}` — todos enumerados, nenhum texto livre:

| Parâmetro | Valores | Regra |
|---|---|---|
| `nivel` | `brasil` · `regiao` · `uf` · `municipio` | obrigatório |
| `recorte` | `sede` · `oferta` | **obrigatório e explícito** (ADR-0004); tem de coincidir com a ficha |
| `dimensao` | `presencial` · `ead_polo` · `ead_nacional` · `ead_exterior` (repetível) | obrigatória em indicador de cursos, proibida em indicador de IES |
| `rede` | `publica` · `privada` | `ies.ds_rede` ↔ `cursos.tp_rede` (ADR-0007) |
| `uf` | as 27 siglas | só no nível `municipio` |
| `limite` | 1–6000 (padrão 6000) | `total` e `unidades` são calculados antes do limite; `truncado` declara o corte |

Slugs: `ies` (D-01), `cursos` (D-02), `matriculas` (D-03), `ingressantes` (D-04),
`concluintes` (D-05), `vagas` (D-06), `inscricoes` (D-07), `docentes` (D-08), `tecnicos` (D-09).

## Regras metodológicas aplicadas no servidor

Combinações que a metodologia não admite devolvem **422 com o motivo** — não um número errado:

- **Dimensões sem território fora do nível `brasil`.** `ead_nacional` e `ead_exterior` não têm
  município em nenhuma linha. `cursos`, `vagas` e `inscricoes` só existem territorializados no
  **presencial** (são zero em todo polo EAD); matrículas, ingressos e concluintes admitem
  presencial e polo.
- **Recorte coerente com a ficha:** IES, docentes e técnicos → `sede`; métricas de cursos → `oferta`.
- **Filtro de 7 dígitos em `co_municipio`** em todo nível territorial de cursos. Ele limpa as oito
  colunas contaminadas, que o estão nas mesmas linhas.
- **Métrica de IES agrega-se só na tabela de IES**; nenhuma consulta junta IES com cursos.
- **Mapa municipal:** a consulta pré-agrega (uma linha por código) e só então faz o JOIN N:1 com
  `municipio`, apenas para obter as coordenadas. Auditoria em
  [`../../data/JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md#joins-validados).
- **Perda territorial declarada** (regra 8): `valor_sem_territorio` traz a parcela sem município.
  Matrículas, todas as dimensões, nível `brasil`: 10.227.266, dos quais 2.580 sem território.
- **Rede Pública** (regra 7): com `rede=publica`, `notas` avisa que ela inclui as 28 IES Especial.

## Segurança

- **Nenhuma consulta livre.** O cliente escolhe entre enums, e o SQL é montado só com fragmentos
  fixos do catálogo; valores entram como parâmetros nomeados do DuckDB.
- **Conexão travada**, verificada em teste: `read_only=True`, `enable_external_access=False`
  (sem `read_csv`, sem `COPY TO`), autoload/autoinstall de extensões desligados, `memory_limit`
  de 1 GB e `lock_configuration=True`, que impede qualquer `SET` posterior. Timeout de 10 s via
  `interrupt()`. Os testes exigem a **mensagem** de cada recusa, não um erro qualquer.
- ⚠️ **`CREATE TEMP TABLE` é aceito** mesmo com `read_only=True`, porque a tabela temporária vive
  fora do arquivo. Hoje não há SQL livre, então o risco não é explorável. **Pendência para o
  Analista IA:** o validador AST precisa recusar `CREATE` por conta própria.
- **Sem credencial no processo.** O PostgreSQL do IESB nunca é acessado pela API; as credenciais
  continuam restritas ao ETL.
- Os erros não expõem SQL, caminho de arquivo nem stack trace, e o slug recebido não é ecoado.
  O detalhe vai para o log, onde o path é gravado com `repr`, para que nenhuma quebra de linha
  forje entrada. Todo erro, inclusive 404 e 405, usa o mesmo envelope.
- CORS restrito a `API_CORS_ORIGINS` e ao método `GET`.
- Se a base estiver ausente, ilegível ou travada, a API sobe mesmo assim: `/api/health` informa
  `indisponivel` e as consultas devolvem 503. **No Windows, o ETL (`pg_to_duckdb.py`) não
  consegue gravar enquanto a API mantém o arquivo aberto:** pare a API antes de regerar a base.

## Testes

- `tests/test_indicadores.py` confere as somas de controle nacionais dos nove indicadores e o
  fechamento dos níveis região e UF com o total territorializável. Também cobre o mapa municipal
  (3.551 e 698 unidades, com coordenadas), os indicadores de IES em todos os níveis, os
  filtros, o limite e 18 combinações recusadas.
- `tests/test_seguranca.py` testa as travas da conexão (escrita, arquivo, ATTACH, SET, INSTALL),
  o timeout, a coerência entre os literais do catálogo e o dado, `POST → 405`, o slug não ecoado
  e a base ausente ou corrompida.

## Limitações desta etapa

- Só indicadores diretos (Bloco A). Os derivados do Bloco B (razões, composições) ficam para depois.
  O IND-R-01 exige o JOIN com população, e o IND-R-02 exige o denominador de 5.571 unidades.
- Nenhum cache HTTP. As consultas levam de 5 a 45 ms, então ainda não é necessário.
- `/docs` e `/openapi.json` ficam expostos. Para uso local no TCC é aceitável; fora disso,
  desligar no `FastAPI(docs_url=None, ...)`.
- `pyproject.toml` silencia a depreciação do `httpx` no `TestClient` do Starlette 1.x. O
  substituto sugerido (`httpx2`) não está no índice do uv em 2026-09-26; reavaliar na próxima
  atualização de dependências.
