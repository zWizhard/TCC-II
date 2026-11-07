import { z } from "zod";

import {
  nivelComparacaoSchema,
  redeSchema,
  REGIOES,
  type NivelComparacao,
  type UFInfo,
} from "@/lib/api/schemas";

/** Limites de `/api/v1/comparacoes` (`api/comparacoes.py`). */
export const MIN_UNIDADES = 2;
export const MAX_UNIDADES = 5;
export const NIVEL_PADRAO: NivelComparacao = "regiao";

/**
 * Search params de `/comparar`. As unidades ficam numa lista separada por vírgulas
 * (`?nivel=uf&u=SP,DF,RR`): a ordem da URL é a ordem das colunas.
 */
export const compararSearchSchema = z.object({
  /** Ausente = região. */
  nivel: nivelComparacaoSchema.optional().catch(undefined),
  /** Ausente = padrão do nível (as cinco regiões; nos demais, nenhuma unidade). */
  u: z
    .preprocess(
      // O roteador lê `?u=3550308` (um único código) como número.
      (valor) => (typeof valor === "number" ? String(valor) : valor),
      z.string().regex(/^[A-Za-z0-9_,]{0,80}$/),
    )
    .optional()
    .catch(undefined),
  /** Ausente = todas as redes. */
  rede: redeSchema.optional().catch(undefined),
});

export type CompararSearch = z.infer<typeof compararSearchSchema>;

export function validarCompararSearch(search: Record<string, unknown>): CompararSearch {
  return compararSearchSchema.parse(search);
}

const CODIGO_MUNICIPIO = /^[0-9]{7}$/;

/**
 * Unidades da URL que são válidas no nível, sem repetição e até o limite, na ordem da URL. Nível
 * e unidades nunca se misturam: uma sigla de UF num pedido de regiões é descartada.
 */
export function unidadesDaBusca(
  search: Pick<CompararSearch, "nivel" | "u">,
  ufs: ReadonlyArray<Pick<UFInfo, "sigla">>,
): string[] {
  const nivel = search.nivel ?? NIVEL_PADRAO;
  if (search.u === undefined) return nivel === "regiao" ? [...REGIOES] : [];
  const regioes: readonly string[] = REGIOES;
  const valida = (unidade: string) =>
    nivel === "regiao"
      ? regioes.includes(unidade)
      : nivel === "uf"
        ? ufs.some((u) => u.sigla === unidade)
        : CODIGO_MUNICIPIO.test(unidade);
  return [...new Set(search.u.split(",").filter(valida))].slice(0, MAX_UNIDADES);
}
