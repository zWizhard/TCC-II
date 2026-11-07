/**
 * Cliente HTTP da API do Observatório. Somente GET, somente parâmetros enumerados.
 *
 * Três falhas distintas, para a interface poder dizer ao usuário o que aconteceu:
 *  - `ApiError`: a API respondeu com erro, no envelope `{"erro": {"codigo", "mensagem"}}`;
 *  - `ApiIndisponivelError`: não houve resposta (API fora do ar, rede, CORS);
 *  - `ApiContratoError`: houve resposta, mas fora do contrato validado por zod.
 */
import type { z } from "zod";

import { resolverDimensoes } from "./dimensoes";
import {
  catalogoRazoesSchema,
  catalogoSchema,
  envelopeErroSchema,
  malhaSchema,
  metadadosSchema,
  respostaComparacaoSchema,
  respostaComposicaoSchema,
  respostaCoropleticoSchema,
  respostaIndicadorSchema,
  respostaInstituicoesSchema,
  respostaMunicipiosSchema,
  respostaRazaoSchema,
  saudeSchema,
  type Agrupamento,
  type AreaCine,
  type BaseFluxo,
  type Categoria,
  type Dimensao,
  type Eixo,
  type Grau,
  type IndicadorInfo,
  type Malha,
  type Metadados,
  type Nivel,
  type NivelComparacao,
  type NivelMalha,
  type OrdemInstituicoes,
  type Organizacao,
  type RazaoInfo,
  type Recorte,
  type Rede,
  type Regiao,
  type RespostaComparacao,
  type RespostaComposicao,
  type RespostaCoropletico,
  type RespostaIndicador,
  type RespostaInstituicoes,
  type RespostaMunicipios,
  type RespostaRazao,
  type Saude,
} from "./schemas";

export const API_BASE_URL_PADRAO = "http://127.0.0.1:8000";

export function apiBaseUrl(): string {
  const configurada = import.meta.env.VITE_API_BASE_URL;
  const base = configurada && configurada.trim() !== "" ? configurada.trim() : API_BASE_URL_PADRAO;
  return base.replace(/\/+$/, "");
}

export class ApiError extends Error {
  readonly status: number;
  readonly codigo: string;
  readonly mensagem: string;

  constructor(status: number, codigo: string, mensagem: string) {
    super(mensagem);
    this.name = "ApiError";
    this.status = status;
    this.codigo = codigo;
    this.mensagem = mensagem;
  }
}

export class ApiIndisponivelError extends Error {
  constructor(options?: ErrorOptions) {
    super("API indisponível", options);
    this.name = "ApiIndisponivelError";
  }
}

export class ApiContratoError extends Error {
  readonly caminho: string;

  constructor(caminho: string, detalhe: string) {
    super(`Resposta fora do contrato em ${caminho}: ${detalhe}`);
    this.name = "ApiContratoError";
    this.caminho = caminho;
  }
}

export type OpcoesRequisicao = {
  signal?: AbortSignal | undefined;
};

function foiAbortada(erro: unknown, signal: AbortSignal | undefined): boolean {
  return signal?.aborted === true || (erro instanceof DOMException && erro.name === "AbortError");
}

async function lerJson(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json();
  } catch {
    return undefined;
  }
}

export async function getJson<S extends z.ZodTypeAny>(
  caminho: string,
  schema: S,
  parametros?: URLSearchParams,
  opcoes: OpcoesRequisicao = {},
): Promise<z.infer<S>> {
  const query = parametros?.toString();
  const url = `${apiBaseUrl()}${caminho}${query ? `?${query}` : ""}`;

  let resposta: Response;
  try {
    resposta = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      ...(opcoes.signal ? { signal: opcoes.signal } : {}),
    });
  } catch (erro) {
    // Cancelamento não é falha da API: o react-query precisa receber o AbortError original.
    if (foiAbortada(erro, opcoes.signal)) throw erro;
    throw new ApiIndisponivelError({ cause: erro });
  }

  const corpo = await lerJson(resposta);

  if (!resposta.ok) {
    const envelope = envelopeErroSchema.safeParse(corpo);
    if (envelope.success) {
      throw new ApiError(resposta.status, envelope.data.erro.codigo, envelope.data.erro.mensagem);
    }
    throw new ApiContratoError(caminho, `erro HTTP ${resposta.status} sem o envelope de erro`);
  }

  const validado = schema.safeParse(corpo);
  if (!validado.success) {
    const problemas = validado.error.issues
      .slice(0, 5)
      .map((i) => `${i.path.join(".") || "(raiz)"}: ${i.message}`)
      .join("; ");
    throw new ApiContratoError(caminho, problemas);
  }
  return validado.data as z.infer<S>;
}

export function obterSaude(opcoes?: OpcoesRequisicao): Promise<Saude> {
  return getJson("/api/health", saudeSchema, undefined, opcoes);
}

export function obterMetadados(opcoes?: OpcoesRequisicao): Promise<Metadados> {
  return getJson("/api/v1/metadados", metadadosSchema, undefined, opcoes);
}

export function listarIndicadores(opcoes?: OpcoesRequisicao): Promise<IndicadorInfo[]> {
  return getJson("/api/v1/indicadores", catalogoSchema, undefined, opcoes);
}

/** O que a tela escolhe. `recorte` não está aqui de propósito: ele vem do catálogo (ADR-0004). */
export type ConsultaIndicador = {
  nivel: Nivel;
  /** Dimensões selecionadas pelo usuário; ignoradas quando o indicador não exige dimensão. */
  dimensoes?: readonly Dimensao[] | undefined;
  rede?: Rede | undefined;
  categoria?: Categoria | undefined;
  organizacao?: Organizacao | undefined;
  /** Só é enviada nos níveis `regiao`, `uf` e `municipio`. */
  regiao?: Regiao | undefined;
  /** Só é enviada nos níveis `uf` e `municipio`. */
  uf?: string | undefined;
  /** Código IBGE de 7 dígitos; só é enviado no nível `municipio`. */
  municipio?: string | undefined;
  limite?: number | undefined;
};

/** Níveis em que a API aceita cada filtro territorial (`api/consultas.py`). */
const NIVEIS_DO_FILTRO = {
  regiao: ["regiao", "uf", "municipio"],
  uf: ["uf", "municipio"],
  municipio: ["municipio"],
} as const satisfies Record<string, readonly Nivel[]>;

/**
 * Monta a query string de `/api/v1/indicadores/{slug}`.
 *
 * - `recorte` é sempre o do indicador no catálogo;
 * - `dimensao` só é enviada quando `exige_dimensao`, já reduzida às admitidas no nível;
 * - `regiao`, `uf` e `municipio` só são enviados nos níveis em que a API os aceita.
 */
export function montarParametrosIndicador(
  indicador: IndicadorInfo,
  consulta: ConsultaIndicador,
): URLSearchParams {
  const parametros = new URLSearchParams();
  parametros.set("nivel", consulta.nivel);
  parametros.set("recorte", indicador.recorte);

  const { efetivas } = resolverDimensoes(indicador, consulta.nivel, consulta.dimensoes ?? []);
  for (const dimensao of efetivas) parametros.append("dimensao", dimensao);

  if (consulta.rede) parametros.set("rede", consulta.rede);
  if (consulta.categoria) parametros.set("categoria", consulta.categoria);
  if (consulta.organizacao) parametros.set("organizacao", consulta.organizacao);
  for (const filtro of ["regiao", "uf", "municipio"] as const) {
    const valor = consulta[filtro];
    const niveis: readonly Nivel[] = NIVEIS_DO_FILTRO[filtro];
    if (valor && niveis.includes(consulta.nivel)) parametros.set(filtro, valor);
  }
  if (consulta.limite !== undefined) parametros.set("limite", String(consulta.limite));
  return parametros;
}

export function consultarIndicador(
  indicador: IndicadorInfo,
  consulta: ConsultaIndicador,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaIndicador> {
  return getJson(
    `/api/v1/indicadores/${encodeURIComponent(indicador.slug)}`,
    respostaIndicadorSchema,
    montarParametrosIndicador(indicador, consulta),
    opcoes,
  );
}

/** Território já reduzido ao mais específico (ver `filtroDoEscopo`). */
type TerritorioConsulta = {
  regiao?: Regiao | undefined;
  uf?: string | undefined;
  /** Código IBGE de 7 dígitos. */
  municipio?: string | undefined;
};

type FiltrosInstitucionais = {
  rede?: Rede | undefined;
  categoria?: Categoria | undefined;
  organizacao?: Organizacao | undefined;
};

function acrescentarFiltros(
  parametros: URLSearchParams,
  consulta: FiltrosInstitucionais & TerritorioConsulta,
): void {
  for (const filtro of ["rede", "categoria", "organizacao", "regiao", "uf", "municipio"] as const) {
    const valor = consulta[filtro];
    if (valor) parametros.set(filtro, valor);
  }
}

/**
 * Composição de um indicador por um eixo categórico, no território selecionado. Aqui o nível
 * não é parâmetro: a API o deduz do filtro territorial mais específico.
 */
export type ConsultaComposicao = FiltrosInstitucionais &
  TerritorioConsulta & {
    eixo: Eixo;
    /** Nível do território selecionado; só decide quais dimensões são admitidas. */
    nivel: Nivel;
    dimensoes?: readonly Dimensao[] | undefined;
    /** Só indicadores de cursos. */
    area?: AreaCine | undefined;
    grau?: Grau | undefined;
    limite?: number | undefined;
  };

export function montarParametrosComposicao(
  indicador: IndicadorInfo,
  consulta: ConsultaComposicao,
): URLSearchParams {
  const parametros = new URLSearchParams();
  parametros.set("por", consulta.eixo);
  parametros.set("recorte", indicador.recorte);
  const { efetivas } = resolverDimensoes(indicador, consulta.nivel, consulta.dimensoes ?? []);
  for (const dimensao of efetivas) parametros.append("dimensao", dimensao);
  acrescentarFiltros(parametros, consulta);
  if (indicador.exige_dimensao) {
    if (consulta.area) parametros.set("area", consulta.area);
    if (consulta.grau) parametros.set("grau", consulta.grau);
  }
  if (consulta.limite !== undefined) parametros.set("limite", String(consulta.limite));
  return parametros;
}

export function consultarComposicao(
  indicador: IndicadorInfo,
  consulta: ConsultaComposicao,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaComposicao> {
  return getJson(
    `/api/v1/indicadores/${encodeURIComponent(indicador.slug)}/composicao`,
    respostaComposicaoSchema,
    montarParametrosComposicao(indicador, consulta),
    opcoes,
  );
}

/** Tabela detalhada de IES. O território filtra pela sede; as dimensões, as métricas de curso. */
export type ConsultaInstituicoes = FiltrosInstitucionais &
  TerritorioConsulta & {
    dimensoes: readonly Dimensao[];
    ordem?: OrdemInstituicoes | undefined;
    limite?: number | undefined;
    pagina?: number | undefined;
  };

export function montarParametrosInstituicoes(consulta: ConsultaInstituicoes): URLSearchParams {
  const parametros = new URLSearchParams();
  for (const dimensao of new Set(consulta.dimensoes)) parametros.append("dimensao", dimensao);
  acrescentarFiltros(parametros, consulta);
  if (consulta.ordem) parametros.set("ordem", consulta.ordem);
  if (consulta.limite !== undefined) parametros.set("limite", String(consulta.limite));
  if (consulta.pagina !== undefined) parametros.set("pagina", String(consulta.pagina));
  return parametros;
}

export function listarInstituicoes(
  consulta: ConsultaInstituicoes,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaInstituicoes> {
  return getJson(
    "/api/v1/instituicoes",
    respostaInstituicoesSchema,
    montarParametrosInstituicoes(consulta),
    opcoes,
  );
}

export function listarRazoes(opcoes?: OpcoesRequisicao): Promise<RazaoInfo[]> {
  return getJson("/api/v1/razoes", catalogoRazoesSchema, undefined, opcoes);
}

/**
 * Razão no território selecionado, opcionalmente comparada por um agrupamento. `dimensoes` já
 * vem resolvida (`resolverDimensoesRazao`): a API recusa dimensão em que a razão não existe.
 */
export type ConsultaRazao = FiltrosInstitucionais &
  TerritorioConsulta & {
    dimensoes: readonly Dimensao[];
    /** Só nas razões com `usa_base`. */
    base?: BaseFluxo | undefined;
    por?: Agrupamento | undefined;
    limite?: number | undefined;
  };

export function montarParametrosRazao(razao: RazaoInfo, consulta: ConsultaRazao): URLSearchParams {
  const parametros = new URLSearchParams();
  parametros.set("recorte", razao.recorte);
  for (const dimensao of new Set(consulta.dimensoes)) parametros.append("dimensao", dimensao);
  if (razao.usa_base && consulta.base) parametros.set("base", consulta.base);
  if (consulta.por) parametros.set("por", consulta.por);
  acrescentarFiltros(parametros, consulta);
  if (consulta.limite !== undefined) parametros.set("limite", String(consulta.limite));
  return parametros;
}

export function consultarRazao(
  razao: RazaoInfo,
  consulta: ConsultaRazao,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaRazao> {
  return getJson(
    `/api/v1/razoes/${encodeURIComponent(razao.slug)}`,
    respostaRazaoSchema,
    montarParametrosRazao(razao, consulta),
    opcoes,
  );
}

/**
 * Recorte do coroplético. É a ÚNICA chamada em que o recorte não vem do catálogo: IND-R-01
 * (matrículas por 100 mil habitantes) não tem endpoint de catálogo, a ficha só existe no recorte
 * de oferta e a API recusa qualquer outro. A resposta traz o recorte de volta, e é o da resposta
 * que a tela exibe.
 */
export const RECORTE_COROPLETICO: Recorte = "oferta";

/** Coroplético de IND-R-01. O território nunca inclui município: o mapa mostra a UF dele. */
export type ConsultaCoropletico = FiltrosInstitucionais & {
  /** Nível das unidades pintadas. */
  nivel: NivelMalha;
  /** Já reduzidas às que têm território (`resolverDimensoes`): a API recusa as demais. */
  dimensoes: readonly Dimensao[];
  regiao?: Regiao | undefined;
  uf?: string | undefined;
};

export function montarParametrosCoropletico(consulta: ConsultaCoropletico): URLSearchParams {
  const parametros = new URLSearchParams();
  parametros.set("nivel", consulta.nivel);
  parametros.set("recorte", RECORTE_COROPLETICO);
  for (const dimensao of new Set(consulta.dimensoes)) parametros.append("dimensao", dimensao);
  acrescentarFiltros(parametros, consulta);
  return parametros;
}

export function consultarCoropletico(
  consulta: ConsultaCoropletico,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaCoropletico> {
  return getJson(
    "/api/v1/mapa/coropletico",
    respostaCoropleticoSchema,
    montarParametrosCoropletico(consulta),
    opcoes,
  );
}

/**
 * Comparação lado a lado de unidades de um mesmo nível. Não há recorte nem dimensão a escolher:
 * a lista de indicadores é fechada e cada linha da resposta declara os seus.
 */
export type ConsultaComparacao = {
  nivel: NivelComparacao;
  /** Slugs de região, siglas de UF ou códigos IBGE, conforme o nível; a ordem é preservada. */
  unidades: readonly string[];
  /** Vale para todas as unidades. */
  rede?: Rede | undefined;
};

export function montarParametrosComparacao(consulta: ConsultaComparacao): URLSearchParams {
  const parametros = new URLSearchParams();
  parametros.set("nivel", consulta.nivel);
  for (const unidade of consulta.unidades) parametros.append("unidade", unidade);
  if (consulta.rede) parametros.set("rede", consulta.rede);
  return parametros;
}

export function consultarComparacao(
  consulta: ConsultaComparacao,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaComparacao> {
  return getJson(
    "/api/v1/comparacoes",
    respostaComparacaoSchema,
    montarParametrosComparacao(consulta),
    opcoes,
  );
}

/** Malha territorial do IBGE. A geometria não é validada feição a feição (ver `malhaSchema`). */
export async function obterMalha(nivel: NivelMalha, opcoes?: OpcoesRequisicao): Promise<Malha> {
  const casca = await getJson(
    `/api/v1/mapa/malha/${encodeURIComponent(nivel)}`,
    malhaSchema,
    undefined,
    opcoes,
  );
  return casca as Malha;
}

/** Municípios da UF presentes no Censo (sede de IES ou local de oferta), para o filtro. */
export function listarMunicipios(
  uf: string,
  opcoes?: OpcoesRequisicao,
): Promise<RespostaMunicipios> {
  return getJson(
    "/api/v1/territorios/municipios",
    respostaMunicipiosSchema,
    new URLSearchParams({ uf }),
    opcoes,
  );
}
