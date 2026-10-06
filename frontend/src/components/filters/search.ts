/**
 * Filtros globais da área de dados, guardados na URL (search params) para serem
 * compartilháveis e reaproveitados por qualquer tela. Cada rota valida com `validateSearch`.
 *
 * Valor inválido na URL nunca derruba a página: cai no padrão (`catch`).
 */
import { z } from "zod";

import { dimensaoSchema, redeSchema, type Dimensao } from "@/lib/api/schemas";

const listaDeDimensoes = z.preprocess(
  // Aceita `?dimensao=presencial` (texto único) além da lista.
  (valor) => (typeof valor === "string" ? [valor] : valor),
  z.array(dimensaoSchema).transform((lista) => [...new Set(lista)]),
);

export const filtrosGlobaisSchema = z.object({
  /** Ausente = todas as redes. */
  rede: redeSchema.optional().catch(undefined),
  /** Ausente = todas as dimensões de oferta. Lista vazia = nenhuma selecionada. */
  dimensao: listaDeDimensoes.optional().catch(undefined),
});

export type FiltrosGlobais = z.infer<typeof filtrosGlobaisSchema>;

/** Dimensões selecionadas, na ordem de `disponiveis`. Sem filtro na URL = todas. */
export function dimensoesSelecionadas(
  filtros: Pick<FiltrosGlobais, "dimensao">,
  disponiveis: readonly Dimensao[],
): Dimensao[] {
  if (filtros.dimensao === undefined) return [...disponiveis];
  const marcadas = new Set(filtros.dimensao);
  return disponiveis.filter((slug) => marcadas.has(slug));
}

/** Alterna uma dimensão. Quando todas ficam marcadas, volta ao padrão (parâmetro ausente). */
export function alternarDimensao(
  filtros: Pick<FiltrosGlobais, "dimensao">,
  disponiveis: readonly Dimensao[],
  slug: Dimensao,
): Dimensao[] | undefined {
  const atuais = new Set(dimensoesSelecionadas(filtros, disponiveis));
  if (atuais.has(slug)) atuais.delete(slug);
  else atuais.add(slug);
  const proximas = disponiveis.filter((d) => atuais.has(d));
  return proximas.length === disponiveis.length ? undefined : proximas;
}
