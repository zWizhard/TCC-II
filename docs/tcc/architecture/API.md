# API do Observatório — backend FastAPI (Fases 5, 7, 8 e 9)

Implementada em **2026-09-26**; filtros territoriais e institucionais em **2026-10-06** (Fase 7). Serve ao dashboard e ao mapa os indicadores diretos
do Bloco A — e, desde a Fase 8 (2026-10-06), as composições deles por eixo categórico — de [`../methodology/INDICADORES.md`](../methodology/INDICADORES.md), lidos do DuckDB
local ([ADR-0003](../decisions/ADR-0003-camada-analitica-local-duckdb.md)).

```
.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
.venv/Scripts/python.exe -m pytest          # 256 testes; os de dados pulam se o .duckdb faltar
```

Documentação interativa em `/docs` (OpenAPI gerado pelo FastAPI).

## Estrutura

| Arquivo | Papel |
|---|---|
| `api/config.py` | `Settings` (pydantic-settings), **só variáveis de ambiente** — a API não lê o `.env` |
| `api/db.py` | conexão DuckDB somente-leitura e travada; timeout por consulta |
| `api/indicadores.py` | catálogo fechado: tabela, expressão, recorte e dimensões válidas por indicador |
| `api/consultas.py` | validação metodológica dos parâmetros + SQL de agregação |
| `api/analises.py` | composições por eixo e tabela de IES (Fase 8) |
| `api/fluxo.py` | razões de Matrículas e Fluxo: IND-R-08, R-09, R-10 e R-11 (Fase 9) |
| `api/mapas.py` | coroplético de IND-R-01 (JOIN com a população) e malha territorial (Fase 10) |
| `api/comparacoes.py` | unidades territoriais lado a lado, absolutos e relativos (Fase 11) |
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
| `/api/v1/metadados` | ano, fonte, **data de extração** (do `ETL_MANIFEST.json`), recortes, níveis, dimensões de oferta (com a modalidade de cada uma), regiões, UFs (nome e região), categorias administrativas (com a rede) e organizações acadêmicas |
| `/api/v1/indicadores` | catálogo: código da ficha, unidade, recorte, dimensões territorializáveis, limitações |
| `/api/v1/indicadores/{slug}` | valores agregados |
| `/api/v1/territorios/municipios?uf=` | municípios da UF presentes no Censo (sede de IES ou local de oferta), para o filtro de município |
| `/api/v1/indicadores/{slug}/composicao?por=` | um indicador direto decomposto por um eixo categórico, com a participação de cada categoria (Fase 8) |
| `/api/v1/instituicoes` | tabela paginada de IES: atributos, pessoal e oferta de cada instituição (Fase 8) |
| `/api/v1/razoes` | catálogo das razões: ficha, unidade, dimensões admitidas, limitações (Fase 9) |
| `/api/v1/razoes/{slug}` | uma razão no território selecionado, com numerador, denominador e comparação por agrupamento (Fase 9) |

Parâmetros de `/api/v1/indicadores/{slug}` — todos enumerados, exceto `municipio`, que é validado por expressão regular e entra como parâmetro vinculado; nenhum texto livre:

| Parâmetro | Valores | Regra |
|---|---|---|
| `nivel` | `brasil` · `regiao` · `uf` · `municipio` | obrigatório |
| `recorte` | `sede` · `oferta` | **obrigatório e explícito** (ADR-0004); tem de coincidir com a ficha |
| `dimensao` | `presencial` · `ead_polo` · `ead_nacional` · `ead_exterior` (repetível) | obrigatória em indicador de cursos, proibida em indicador de IES |
| `rede` | `publica` · `privada` | `ies.ds_rede` ↔ `cursos.tp_rede` (ADR-0007) |
| `categoria` | 6 valores de `tp_categoria_administrativa` | incoerente com `rede` → 422 |
| `organizacao` | 5 valores de `tp_organizacao_academica` | — |
| `regiao` | `norte` · `nordeste` · `sudeste` · `sul` · `centro_oeste` | níveis `regiao`, `uf` e `municipio` |
| `uf` | as 27 siglas | níveis `uf` e `municipio`; incoerente com `regiao` → 422 |
| `municipio` | código IBGE, `^[0-9]{7}$` | só no nível `municipio` |
| `limite` | 1–6000 (padrão 6000) | `total` e `unidades` são calculados antes do limite; `truncado` declara o corte |

Slugs: `ies` (D-01), `cursos` (D-02), `matriculas` (D-03), `ingressantes` (D-04),
`concluintes` (D-05), `vagas` (D-06), `inscricoes` (D-07), `docentes` (D-08), `tecnicos` (D-09).

**Filtro territorial vale do seu nível para baixo.** O valor de um território é a consulta no
nível do próprio território: `nivel=uf&uf=SP` devolve a linha de SP; `nivel=municipio&uf=SP`,
os municípios de SP. Não existe `nivel=brasil` com filtro territorial — a linha sairia rotulada
"Brasil" com o valor de uma UF.

## Análises de Instituições e Cursos (Fase 8, 2026-10-06)

Em `api/analises.py`, com as mesmas garantias de `consultas.py` (fragmentos fixos, valores
vinculados, `validar()` reaproveitada).

**`/api/v1/indicadores/{slug}/composicao`** — parâmetros: `por` (obrigatório), `recorte`,
`dimensao`, `rede`, `categoria`, `organizacao`, `regiao`, `uf`, `municipio`, `area`, `grau`,
`limite` (1–400). Não há `nivel`: o território é o do filtro mais específico, e as regras de
dimensão são as desse nível. Sem filtro territorial, o total inclui a parcela sem município.

| `por` | Vale para | Ficha |
|---|---|---|
| `rede` · `categoria` · `organizacao` | indicadores de IES e de cursos | IND-R-03 (rede) |
| `dimensao` | cursos — `tp_dimensao`, não `tp_modalidade_ensino` | IND-R-04 |
| `grau` | cursos — `Não aplicável` permanece no denominador | IND-R-05 |
| `area` · `rotulo_cine` | cursos — 11 áreas gerais e 353 rótulos CINE | IND-R-06 |
| `titulacao` | só `docentes` — cinco colunas que particionam `qt_doc_total` | IND-R-12 |

`participacao` = `valor / total × 100`, calculada no servidor sobre **todas** as categorias, antes
do `limite`; nula se o total for zero. `area` (11 valores) e `grau` (4) também são filtros, só em
indicadores de cursos; as listas saem em `/metadados` (`areas_cine`, `graus`).

**`/api/v1/instituicoes`** — parâmetros: `dimensao` (obrigatória), `rede`, `categoria`,
`organizacao`, `regiao`, `uf`, `municipio`, `ordem` (`matriculas` · `cursos` · `ingressantes` ·
`concluintes` · `docentes` · `tecnicos` · `nome`), `limite` (1–100, padrão 25), `pagina`.
Devolve `totais` (somas sobre todas as IES filtradas, antes da paginação) e `paginas`. **Com filtro
territorial, os totais de cursos, matrículas, ingressantes e concluintes são nulos**: somar a
oferta de toda a IES sob o território da sede fabricaria um número que não é o de IND-D-03 (as
IES com sede no PR somam mais de 3× as matrículas ofertadas no PR).

Regras próprias destas rotas:

- **Único JOIN entre `ies` e `cursos` da API**, sempre com `cursos` pré-agregada por `co_ies`
  (1:1, 0 órfãos, somas preservadas — [`JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md#ies--cursos-pré-agregada-por-ies-fase-8-2026-10-06)).
  Docentes e técnicos vêm da tabela de IES e não dependem de `dimensao`.
- **Na tabela de IES o território é o da sede**, e as métricas de curso são o total da instituição
  em qualquer local de oferta. IES sem linha nas dimensões escolhidas devolvem **nulo**, não zero.
- **Recortes CINE não são servidos no nível municipal** (`por=area|rotulo_cine` ou filtro `area`
  com `municipio` → 422). É um **bloqueio provisório por nível, não um piso de supressão**: o DF
  tem um único município de oferta e `uf=DF` devolve a mesma composição; UF × rótulo CINE tem
  741 células de 1 a 9 matrículas (medido pelo reviewer em 2026-10-06). A decisão do piso
  continua pendente em INDICADORES.md.
- **`por=dimensao` só declara IND-R-04 com as dimensões inteiras do nível.** Com dimensão
  pré-filtrada, ou em indicador que no território só existe no presencial, `ficha` é nula e uma
  nota o diz.
- **Zeros estruturais são declarados em `notas`**: sem presencial nem "somente a nível Brasil"
  não há marcador de curso; só com esta última não há matrícula.
- **Nenhuma razão entre docentes e matrículas** (IND-Q-03), nem entre concluintes e ingressantes
  (IND-Q-01). Turno e situação não são eixos: o primeiro ainda não tem ficha, o segundo não
  existe como coluna.

## Matrículas e Fluxo (Fase 9, 2026-10-07)

Auditoria prévia em `scripts/analise/auditar_fluxo.py` (45 testes sobre o DuckDB; saída em
`docs/data/raw/diagnostics/2026-10-07_fluxo.csv`).

**Perfil e tipo de vaga — novos valores de `por` em `/indicadores/{slug}/composicao`.** São
decomposições **por colunas** (como `titulacao`), devolvidas na ordem natural, não por valor:

| `por` | Vale para | Ficha |
|---|---|---|
| `sexo` · `cor_raca` · `faixa_etaria` · `nacionalidade` · `procedencia_escolar` | `matriculas`, `ingressantes`, `concluintes` | IND-R-07 |
| `tipo_ingresso` | só `ingressantes` — vaga nova, remanescente, programa especial, outra forma | sem ficha própria (IND-D-04) |

**`/api/v1/razoes/{slug}`** — parâmetros: `recorte` (sempre `oferta`), `dimensao` (obrigatória),
`base` (`matriculas` · `ingressantes` · `concluintes`; obrigatória em R-08/R-09, proibida nas
outras), `por` (opcional: `regiao` · `uf` · `municipio` · `rede` · `categoria` · `organizacao` ·
`dimensao` · `grau` · `area`), filtros institucionais e territoriais, `limite`.

| Slug | Ficha | Numerador ÷ denominador | Dimensões admitidas |
|---|---|---|---|
| `financiamento` | IND-R-08 | `qt_<base>_financ` ÷ `qt_<base>` × 100 | presencial, polo, exterior |
| `reserva_vagas` | IND-R-09 | `qt_<base>_reserva_vaga` ÷ `qt_<base>` × 100 | presencial, polo, exterior |
| `ingressantes_por_vaga` | IND-R-10 | `qt_ing` ÷ `qt_vg_total` | **só presencial** |
| `inscricoes_por_vaga` | IND-R-11 | `qt_inscrito_total` ÷ `qt_vg_total` | **uma** de presencial ou `ead_nacional` (esta só no nível Brasil) |

A resposta traz `geral` (numerador, denominador e valor no território dos filtros — não depende
de `por`) e `linhas` (um grupo por linha, com os mesmos três campos). Numerador e denominador são
somados **nas mesmas linhas de `cursos`** e só então divididos, em Python.

Regras próprias:

- **Denominador zero devolve `valor` nulo**, nunca zero: 60 municípios têm curso presencial e
  nenhuma vaga, e ali a razão não se aplica.
- **`por` territorial define o nível das linhas**, e os filtros seguem a regra "do seu nível para
  baixo" (`por=uf&regiao=sul` → as 3 UFs do Sul; `por=regiao&uf=DF` → 422).
- **Sem filtro territorial, `geral` inclui os registros sem município e as linhas por território
  não** (41 matrículas de polo); uma nota o declara. Com filtro, os dois descrevem o mesmo conjunto.
- **Bloqueio municipal provisório** para o perfil (IND-R-07) e para R-08/R-09 — 304 municípios
  têm de 1 a 9 matrículas e o piso de supressão continua pendente. **É bloqueio por nível, não
  piso:** UF com filtros de categoria, organização, área e grau ainda devolve células de 1 a 9
  vínculos (378 em matrículas). R-10 e R-11 são servidos por
  município (não descrevem atributo de pessoa).
- **Nota de rede:** em comparação que não seja por rede ou categoria, sem filtro de rede, a
  resposta avisa que as diferenças refletem em grande parte a composição pública/privada.
- **`por=dimensao` só em R-08/R-09**; R-10 e R-11 nunca somam nem comparam dimensões numa resposta.
- **Não existe** razão entre concluintes, ingressantes e matrículas (IND-Q-01), nem endpoint para
  `qt_sit_*` (IND-Q-02); os tipos de financiamento e de reserva (IND-Q-08/09) e os tipos de
  processo seletivo (não fecham com `qt_ing`) não são eixos.

## Mapa (Fase 10, 2026-10-07)

Auditoria prévia em `scripts/analise/auditar_mapas.py` (27 verificações; saída em
`docs/data/raw/diagnostics/2026-10-07_mapas.csv`). Lógica em `api/mapas.py`.

| Rota | Retorno |
|---|---|
| `/api/v1/mapa/malha/{nivel}` | GeoJSON do IBGE como baixado (`nivel` = `uf` · `municipio`); chave `properties.codarea`, texto |
| `/api/v1/mapa/coropletico` | IND-R-01 (matrículas por 100 mil habitantes) por UF ou município, com as classes da legenda |

**Pontos e mapa de calor não têm rota própria:** usam `/indicadores/{slug}?nivel=municipio`, que
já devolve uma linha por município com a coordenada de `municipio`. Não existe coordenada por IES
— o ponto é o município de sede (2.561 IES em 698 pontos).

**`/mapa/coropletico`** — parâmetros: `nivel` (`uf` · `municipio`, obrigatório), `recorte`
(sempre `oferta`), `dimensao` (obrigatória; só `presencial` e `ead_polo`), `rede`, `categoria`,
`organizacao`, `regiao`, `uf`, `municipio`, `classes` (3–7, padrão 5). A resposta traz `geral`
(valor do território dos filtros), `unidades` / `com_registro` / `sem_registro`, `classes`
(`indice`, `minimo` e `maximo` observados, `unidades`) e uma linha por unidade **do território**,
com `numerador`, `denominador`, `valor` e `classe`.

Regras próprias:

- **O universo é `municipio` (5.571 unidades), não `cursos`.** Unidade sem linha de oferta sai com
  numerador, valor e classe **nulos** (2.020); unidade com linha e zero matrícula sai com **zero**
  (135). Se nenhuma unidade do recorte tem registro, `geral` também é nulo.
- **Único JOIN com a população:** `cursos` pré-agregada → `municipio` (7 dígitos) →
  `ibge_populacao_estimada` (6 dígitos, `ano = '2024'`), 1:1 nos dois passos
  ([`JOIN_STRATEGY.md`](../../data/JOIN_STRATEGY.md)).
- **No nível UF o denominador é reagregado** — população de todas as unidades da UF, com ou sem
  oferta —, nunca a média das razões municipais.
- **Classes por quantis, calculadas no servidor** sobre as unidades com valor; empates fundem
  classes (podem vir menos que as pedidas). Os limites mudam com os filtros, e uma nota o diz.
- **Filtro institucional só restringe o numerador**; o denominador continua a população total.
- **Município tem de pertencer à UF e à região informadas**, e ser unidade real: sentinela ou
  código inexistente → 422. (O indicador direto devolve lista vazia nesses casos; aqui a unidade
  sairia como "sem registro", o que é falso.)
- **Notas com números do próprio recorte:** quantas unidades com registro têm menos de 10 mil
  habitantes, e quantas matrículas de polo ficaram sem município.
- **Malha:** arquivo escolhido por enum (nunca por texto da requisição), `Cache-Control` de um
  dia, 503 `malha_indisponivel` se faltar — a mensagem não expõe caminho. Baixar com
  `scripts/etl/baixar_malha_ibge.py`; versão identificada por hash em
  `data/reference/malha/MANIFEST.json`. **Edição (ano) da malha v4: A confirmar.**
- **Gzip em toda resposta acima de 1 KB** (`GZipMiddleware`). Medido: malha municipal 3,9 MB →
  1,08 MB; coroplético municipal do país 667 KB → 140 KB (~65 ms); matrículas por município
  378 KB → 92 KB; IES por município de sede 73 KB → 18 KB. Por isso não há consulta por bbox.

## Comparações (Fase 11, 2026-10-07)

Auditoria prévia em `scripts/analise/auditar_comparacoes.py` (20 verificações; saída em
`docs/data/raw/diagnostics/2026-10-07_comparacoes.csv`). Lógica em `api/comparacoes.py`.

| Rota | Retorno |
|---|---|
| `/api/v1/comparacoes` | de 2 a 5 unidades territoriais do mesmo nível, lado a lado, mais o Brasil como referência |

Parâmetros: `nivel` (`regiao` · `uf` · `municipio`, obrigatório), `unidade` (repetido, 2 a 5:
slug da região, sigla da UF ou código IBGE de 7 dígitos, conforme o nível) e `rede` (opcional,
vale para todas as unidades). **Não há `recorte`, `dimensao` nem indicador a escolher:** a lista é
fechada, e cada linha da resposta declara `recorte`, `dimensoes`, `tipo`, numerador, denominador e
limitações.

| Tipo | Indicadores | Recorte |
|---|---|---|
| `absoluto` | IND-D-01 IES · IND-D-08 docentes | sede |
| `absoluto` | IND-D-02 cursos (só presencial) · IND-D-03 matrículas · IND-D-04 ingressantes · IND-D-05 concluintes | oferta |
| `relativo` | IND-R-01 matrículas por 100 mil hab. · IND-R-03 participação da rede privada · IND-R-04 participação da EAD (as duas sobre matrículas) | oferta |
| `relativo` | IND-R-12 docentes com doutorado | sede |

Regras próprias:

- **Mesmas definições para todas as colunas:** as unidades e o Brasil (`referencia`) passam pelas
  mesmas consultas. A referência de um indicador relativo é a razão das somas, nunca a média das
  razões; as cinco regiões somam a referência em numerador e denominador (testado).
- **Dimensões fixas: presencial + polo EAD**, as únicas com território. Por isso a referência
  nacional de matrículas é 10.224.686, e a participação da EAD é 50,73% (exclui o exterior).
- **Nível único:** unidade de outro nível → 422 (uma sigla de UF num pedido de regiões, por
  exemplo). Município tem de ser unidade real de `municipio`: sentinela ou inexistente → 422.
- **A API não ordena nem classifica:** as unidades voltam na ordem pedida. Entre as UFs, a ordem
  por matrículas e a ordem por matrículas por 100 mil habitantes têm correlação de postos de 0,06
  (15 das 27 mudam cinco posições ou mais).
- **Ausência ≠ zero:** IES = 0 é zero real (a tabela de IES é o universo); docentes, cursos e
  matrículas saem **nulos** sem linha na base; razão com denominador zero ou ausente é nula.
- **Com `rede` fixada**, a participação da rede privada vem com `nao_se_aplica` (seria 0% ou
  100%) e o denominador de IND-R-01 continua sendo a população total.
- **Nenhum JOIN entre IES e cursos e nenhuma razão entre as duas tabelas** (IND-Q-03) ou entre os
  dois recortes (IND-Q-06): compara-se entre unidades, dentro de uma linha.
- **Notas com números da seleção:** razão entre a maior e a menor população, quantas unidades têm
  menos de 10 mil habitantes, menos de 100 matrículas ou menos de 100 docentes (aviso de leitura —
  nada é suprimido; o piso de supressão segue pendente). Notas fixas declaram as dimensões e a
  perda territorial (2.580 de 10.227.266 matrículas) e que ingressantes e concluintes não se
  dividem; com `rede` fixada, que célula vazia é "sem registro dessa rede", não "sem oferta".

**Não servido, por decisão:** IES × IES (a tabela de `/instituicoes` já as lista; as métricas de
uma IES vivem em dois grains), modalidade × modalidade e pública × privada como colunas (já são
composições em `/indicadores/{slug}/composicao`; aqui entram como proporção por unidade e como
filtro), IND-R-08 a R-11 (comparadas por território em `/razoes/{slug}?por=`) e qualquer variação
temporal (IND-Q-04).

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
- **Categoria administrativa e organização acadêmica** são atributos da IES: os rótulos são
  idênticos em `ies` e `cursos` e constantes por IES (0 divergências nas 2.561, conferido em
  teste). Filtrar `cursos` por eles equivale a filtrar pela instituição, sem JOIN.
- **Modalidade** (`tp_modalidade_ensino`) é função de `tp_dimensao` e não é parâmetro: a
  correspondência sai em `/metadados` e o cliente a traduz em `dimensao`.
- **Com filtro territorial, `valor_sem_territorio` é nulo** — a parcela sem município não
  pertence a território algum.
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
  filtros, o limite e 28 combinações recusadas. Na Fase 7: partição do total por categoria
  administrativa e por organização acadêmica (IES e matrículas), fechamento
  região = UFs = municípios para as cinco regiões, e a lista de municípios (3.551 distintos,
  698 com sede).
- `scripts/dev/capturar_fixtures_frontend.py` regrava as fixtures de teste do frontend a partir
  das respostas reais; rodar quando o contrato mudar.
- `tests/test_analises.py` (Fase 8) confere cada composição contra os números de controle e
  contra o indicador direto do mesmo território (UF, região e município); a partição do total por
  área e por grau; a titulação docente fechando com IND-D-08 nas 27 UFs; e a tabela de IES
  percorrida página a página — 2.561 instituições distintas cujas colunas somam os totais
  nacionais. Também 24 combinações recusadas, a ponte de rede (`ds_rede` ↔ `tp_rede`) e a paginação sem
  duplicatas com nulos e empates.
- `tests/test_fluxo.py` (Fase 9) confere a partição exata dos cinco perfis nas três bases, os
  seis percentuais de controle de R-08/R-09, as razões por vaga (0,3277 · 1,7061 · 0,3800), o
  fechamento das linhas com o valor geral em todos os agrupamentos, a razão nula sem denominador
  e as combinações recusadas (EAD em R-10, soma de dimensões em R-11, município em R-08/R-09 e
  no perfil).
- `tests/test_mapas.py` (Fase 10) confere o universo de 5.571 unidades, a preservação das somas
  no JOIN com a população (10.224.686 / 212.583.750), ausência ≠ zero (2.020 e 135), o numerador
  igual a IND-D-03 município a município, a reagregação do denominador por UF, os quantis
  (partição, faixas sem sobreposição, casos de borda), as notas com números do recorte, as
  recusas (inclusive município fora da UF e sentinela) e a malha: 1:1 com as linhas, hash do
  manifesto, gzip, nível só por enum e 503 sem caminho. **Os testes de malha são pulados se
  `data/reference/malha/` faltar.**
- `tests/test_comparacoes.py` (Fase 11) confere que as cinco regiões somam a referência nacional
  (absolutos, numeradores e denominadores), os quatro valores relativos do Brasil contra as
  fichas, o recorte e as dimensões declarados por linha, a ordem pedida preservada, a partição
  por rede, ausência ≠ zero num município sem sede de IES, Brasília = DF coluna a coluna, a
  divergência entre a ordem absoluta e a relativa das UFs e 12 recusas.
- `tests/test_seguranca.py` testa as travas da conexão (escrita, arquivo, ATTACH, SET, INSTALL),
  o timeout, a coerência entre os literais do catálogo e o dado, `POST → 405`, o slug não ecoado
  e a base ausente ou corrompida.

## Limitações desta etapa

- Do Bloco B faltam IND-R-02 (cobertura territorial) e IND-R-13 (concentração territorial).
  IND-R-01 é servido desde a Fase 10, só nos níveis UF e município.
- Nenhum cache HTTP. As consultas levam de 5 a 45 ms, então ainda não é necessário.
- `/docs` e `/openapi.json` ficam expostos. Para uso local no TCC é aceitável; fora disso,
  desligar no `FastAPI(docs_url=None, ...)`.
- `pyproject.toml` silencia a depreciação do `httpx` no `TestClient` do Starlette 1.x. O
  substituto sugerido (`httpx2`) não está no índice do uv em 2026-09-26; reavaliar na próxima
  atualização de dependências.
