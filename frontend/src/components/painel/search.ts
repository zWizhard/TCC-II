import { z } from "zod";

import { filtrosGlobaisSchema } from "@/components/filters/search";

/** Níveis oferecidos na distribuição territorial desta tela (município fica para o mapa). */
export const NIVEIS_DISTRIBUICAO = ["regiao", "uf"] as const;
export type NivelDistribuicao = (typeof NIVEIS_DISTRIBUICAO)[number];
export const NIVEL_DISTRIBUICAO_PADRAO: NivelDistribuicao = "regiao";

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
