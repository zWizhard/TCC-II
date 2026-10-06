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
  catalogoSchema,
  envelopeErroSchema,
  metadadosSchema,
  respostaIndicadorSchema,
  saudeSchema,
  type Dimensao,
  type IndicadorInfo,
  type Metadados,
  type Nivel,
  type Rede,
  type RespostaIndicador,
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
  /** Só é enviada no nível `municipio`. */
  uf?: string | undefined;
  limite?: number | undefined;
};

/**
 * Monta a query string de `/api/v1/indicadores/{slug}`.
 *
 * - `recorte` é sempre o do indicador no catálogo;
 * - `dimensao` só é enviada quando `exige_dimensao`, já reduzida às admitidas no nível;
 * - `uf` só é enviada no nível `municipio`.
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
  if (consulta.uf && consulta.nivel === "municipio") parametros.set("uf", consulta.uf);
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
