import { z } from "zod";

import { filtrosGlobaisSchema } from "@/components/filters/search";
import {
  agrupamentoSchema,
  areaCineSchema,
  baseFluxoSchema,
  grauSchema,
  ordemInstituicoesSchema,
  type Agrupamento,
  type BaseFluxo,
} from "@/lib/api/schemas";

/** Indicadores da tabela de IES que podem ser decompostos em `/instituicoes`. */
export const METRICAS_INSTITUICOES = ["ies", "docentes", "tecnicos"] as const;
export type MetricaInstituicoes = (typeof METRICAS_INSTITUICOES)[number];
export const METRICA_INSTITUICOES_PADRAO: MetricaInstituicoes = "ies";

/** IES por página na tabela detalhada. */
export const LIMITE_INSTITUICOES = 25;

/** Search params de `/instituicoes`: filtros globais + métrica das composições + tabela. */
export const instituicoesSearchSchema = filtrosGlobaisSchema.extend({
  /** Ausente = contagem de IES. */
  metrica: z.enum(METRICAS_INSTITUICOES).optional().catch(undefined),
  /** Ausente = matrículas (a ordem padrão da API). */
  ordem: ordemInstituicoesSchema.optional().catch(undefined),
  /** Ausente = primeira página. */
  pagina: z.number().int().min(2).max(3000).optional().catch(undefined),
});

export type InstituicoesSearch = z.infer<typeof instituicoesSearchSchema>;

export function validarInstituicoesSearch(search: Record<string, unknown>): InstituicoesSearch {
  return instituicoesSearchSchema.parse(search);
}

/** Indicador decomposto em `/cursos` quando a URL não escolhe outro. */
export const METRICA_CURSOS_PADRAO = "matriculas";

/** Rótulos CINE exibidos no ranking; total e participação consideram todos. */
export const LIMITE_ROTULOS = 20;

/** Search params de `/cursos`: filtros globais + indicador + recortes de área e grau. */
export const cursosSearchSchema = filtrosGlobaisSchema.extend({
  /** Slug de um indicador da tabela de cursos. Ausente ou desconhecido = matrículas. */
  metrica: z
    .string()
    .regex(/^[a-z0-9_-]{1,40}$/)
    .optional()
    .catch(undefined),
  /** Ausente = todas as áreas gerais CINE. */
  area: areaCineSchema.optional().catch(undefined),
  /** Ausente = todos os graus acadêmicos. */
  grau: grauSchema.optional().catch(undefined),
});

export type CursosSearch = z.infer<typeof cursosSearchSchema>;

export function validarCursosSearch(search: Record<string, unknown>): CursosSearch {
  return cursosSearchSchema.parse(search);
}

/** Base do perfil e das participações em `/matriculas` quando a URL não escolhe outra. */
export const BASE_FLUXO_PADRAO: BaseFluxo = "matriculas";
/** Comparação das razões em `/matriculas` quando a URL não escolhe outra. */
export const COMPARACAO_PADRAO: Agrupamento = "rede";

/** Rótulo de cada comparação das razões. */
export const ROTULO_AGRUPAMENTO: Record<Agrupamento, string> = {
  rede: "Rede",
  categoria: "Categoria administrativa",
  organizacao: "Organização acadêmica",
  dimensao: "Dimensão de oferta",
  grau: "Grau acadêmico",
  area: "Área geral (CINE)",
  regiao: "Região",
  uf: "UF",
  municipio: "Município",
};

/** Search params de `/matriculas`: filtros globais + base de fluxo + comparação das razões. */
export const matriculasSearchSchema = filtrosGlobaisSchema.extend({
  /** Ausente = matrículas. */
  base: baseFluxoSchema.optional().catch(undefined),
  /** Ausente = por rede. */
  comparar: agrupamentoSchema.optional().catch(undefined),
});

export type MatriculasSearch = z.infer<typeof matriculasSearchSchema>;

export function validarMatriculasSearch(search: Record<string, unknown>): MatriculasSearch {
  return matriculasSearchSchema.parse(search);
}
