import { z } from "zod";

import { filtrosGlobaisSchema, type Escopo } from "@/components/filters/search";
import type { Regiao } from "@/lib/api/schemas";

/** Níveis oferecidos na distribuição territorial desta tela (município fica para o mapa). */
export const NIVEIS_DISTRIBUICAO = ["regiao", "uf"] as const;
export type NivelDistribuicao = (typeof NIVEIS_DISTRIBUICAO)[number];
export const NIVEL_DISTRIBUICAO_PADRAO: NivelDistribuicao = "regiao";

/** Municípios exibidos quando o território é uma UF; o total considera todos. */
export const LIMITE_MUNICIPIOS = 20;

export type NivelDetalhe = NivelDistribuicao | "municipio";

export type Detalhe = {
  nivel: NivelDetalhe;
  regiao?: Regiao;
  uf?: string;
  limite?: number;
};

/**
 * Nível em que o território selecionado é detalhado: sempre o imediatamente abaixo dele.
 * No Brasil o usuário escolhe entre região e UF; no município não há nível inferior.
 */
export function detalheDoEscopo(
  escopo: Escopo,
  nivelBrasil: NivelDistribuicao | undefined,
): Detalhe | null {
  switch (escopo.nivel) {
    case "brasil":
      return { nivel: nivelBrasil ?? NIVEL_DISTRIBUICAO_PADRAO };
    case "regiao":
      return { nivel: "uf", regiao: escopo.regiao };
    case "uf":
      return { nivel: "municipio", uf: escopo.uf, limite: LIMITE_MUNICIPIOS };
    case "municipio":
      return null;
  }
}

/** Search params de `/painel`: filtros globais + estado da distribuição territorial. */
export const painelSearchSchema = filtrosGlobaisSchema.extend({
  /** Slug do indicador da distribuição. Ausente ou desconhecido = primeiro do catálogo. */
  indicador: z
    .string()
    .regex(/^[a-z0-9_-]{1,40}$/)
    .optional()
    .catch(undefined),
  /** Ausente = região. */
  nivel: z.enum(NIVEIS_DISTRIBUICAO).optional().catch(undefined),
});

export type PainelSearch = z.infer<typeof painelSearchSchema>;

export function validarPainelSearch(search: Record<string, unknown>): PainelSearch {
  return painelSearchSchema.parse(search);
}
