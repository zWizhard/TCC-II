import { z } from "zod";

import { filtrosGlobaisSchema, type Escopo } from "@/components/filters/search";
import { nivelMalhaSchema, type NivelMalha, type Regiao } from "@/lib/api/schemas";

/** Os três modos do mapa de `/mapa`. */
export const MODOS_MAPA = ["coropletico", "pontos", "calor"] as const;
export type ModoMapa = (typeof MODOS_MAPA)[number];
export const MODO_PADRAO: ModoMapa = "coropletico";

export const ROTULO_MODO: Record<ModoMapa, string> = {
  coropletico: "Coroplético",
  pontos: "Municípios de sede",
  calor: "Mapa de calor",
};

/**
 * Indicadores diretos que o mapa de calor oferece: os que fazem sentido somados por município.
 * Recorte e dimensões de cada um vêm do catálogo da API; slug ausente do catálogo não é oferecido.
 */
export const METRICAS_CALOR = ["matriculas", "ingressantes", "concluintes", "ies", "docentes"];
export const METRICA_CALOR_PADRAO = "matriculas";

/** Indicador do modo de pontos: IES por município de sede (IND-D-01). */
export const INDICADOR_PONTOS = "ies";

/** Unidades por página na tabela que acompanha o mapa. */
export const LIMITE_TABELA = 25;
/** IES listadas no painel do município selecionado; a lista completa fica em `/instituicoes`. */
export const LIMITE_IES_DO_MUNICIPIO = 10;

/** Search params de `/mapa`: filtros globais + modo, unidade do coroplético e métrica do calor. */
export const mapaSearchSchema = filtrosGlobaisSchema.extend({
  /** Ausente = coroplético. */
  modo: z.enum(MODOS_MAPA).optional().catch(undefined),
  /** Unidade pintada no coroplético. Ausente = a padrão do território (`unidadePadrao`). */
  unidade: nivelMalhaSchema.optional().catch(undefined),
  /** Slug do indicador do mapa de calor. Ausente ou desconhecido = matrículas. */
  metrica: z
    .string()
    .regex(/^[a-z0-9_-]{1,40}$/)
    .optional()
    .catch(undefined),
});

export type MapaSearch = z.infer<typeof mapaSearchSchema>;

export function validarMapaSearch(search: Record<string, unknown>): MapaSearch {
  return mapaSearchSchema.parse(search);
}

/**
 * Unidade do coroplético quando a URL não escolhe: UFs no Brasil inteiro, municípios dentro de
 * uma região ou UF. A troca é sempre uma escolha (ou uma mudança de território), nunca efeito do
 * zoom: as classes são quantis do recorte, e mudar de unidade muda a escala de cores.
 */
export function unidadePadrao(escopo: Escopo): NivelMalha {
  return escopo.nivel === "brasil" ? "uf" : "municipio";
}

/**
 * Território consultado pelo mapa. Com um município selecionado, o mapa NÃO se reduz a ele: os
 * dados continuam sendo os da UF, e o município é só destacado e enquadrado.
 */
export function territorioDoMapa(escopo: Escopo): {
  regiao?: Regiao;
  uf?: string;
} {
  switch (escopo.nivel) {
    case "brasil":
      return {};
    case "regiao":
      return { regiao: escopo.regiao };
    case "uf":
    case "municipio":
      return { uf: escopo.uf };
  }
}

/** Nome do território consultado pelo mapa (a UF, quando há município selecionado). */
export function nomeDoTerritorioDoMapa(
  escopo: Escopo,
  ufs: ReadonlyArray<{ sigla: string; nome: string }>,
): string {
  if (escopo.nivel !== "municipio") return escopo.nome;
  return ufs.find((u) => u.sigla === escopo.uf)?.nome ?? escopo.uf;
}

/**
 * Identidade do território na URL. O enquadramento do mapa reage só a ela: mover ou aproximar o
 * mapa não escreve na URL, e por isso não há laço entre filtros e mapa.
 */
export function chaveDoTerritorio(escopo: Escopo): string {
  switch (escopo.nivel) {
    case "brasil":
      return "brasil";
    case "regiao":
      return `regiao:${escopo.regiao}`;
    case "uf":
      return `uf:${escopo.uf}`;
    case "municipio":
      return `municipio:${escopo.municipio}`;
  }
}
