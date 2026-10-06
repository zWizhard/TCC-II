import type { Dimensao, IndicadorInfo, Nivel } from "./schemas";

export type DimensoesEfetivas = {
  /** `false` quando o indicador não usa dimensão de oferta (indicadores da tabela de IES). */
  aplicavel: boolean;
  /** Dimensões que serão de fato enviadas à API, na ordem em que foram selecionadas. */
  efetivas: Dimensao[];
  /** Dimensões selecionadas que o indicador não admite neste nível (não territorializáveis). */
  excluidas: Dimensao[];
  /** `false` quando o indicador exige dimensão e nenhuma das selecionadas é admitida. */
  consultavel: boolean;
};

/**
 * Resolve quais dimensões de oferta podem ser enviadas para um indicador em um nível.
 *
 * Regra da API (`docs/tcc/architecture/API.md`): no nível `brasil` valem as quatro dimensões; nos
 * níveis territoriais só as de `indicador.dimensoes_territoriais`. Enviar outra devolve 422.
 * A interface usa `excluidas` para declarar o corte ao usuário em vez de receber o erro.
 */
export function resolverDimensoes(
  indicador: Pick<IndicadorInfo, "exige_dimensao" | "dimensoes_territoriais">,
  nivel: Nivel,
  selecionadas: readonly Dimensao[],
): DimensoesEfetivas {
  if (!indicador.exige_dimensao) {
    return { aplicavel: false, efetivas: [], excluidas: [], consultavel: true };
  }

  const unicas = [...new Set(selecionadas)];
  if (nivel === "brasil") {
    return { aplicavel: true, efetivas: unicas, excluidas: [], consultavel: unicas.length > 0 };
  }

  const admitidas = new Set<Dimensao>(indicador.dimensoes_territoriais);
  const efetivas = unicas.filter((d) => admitidas.has(d));
  const excluidas = unicas.filter((d) => !admitidas.has(d));
  return { aplicavel: true, efetivas, excluidas, consultavel: efetivas.length > 0 };
}
