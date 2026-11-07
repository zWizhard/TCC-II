import type { Dimensao, IndicadorInfo, Nivel, RazaoInfo } from "./schemas";

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

/**
 * Dimensões que uma razão admite entre as selecionadas. Além da regra territorial, cada razão só
 * existe onde numerador e denominador coexistem (`razao.dimensoes`); `fixa` restringe a consulta
 * a uma única dimensão, para as razões que não podem somar dimensões diferentes.
 */
export function resolverDimensoesRazao(
  razao: Pick<RazaoInfo, "dimensoes" | "dimensoes_territoriais">,
  nivel: Nivel,
  selecionadas: readonly Dimensao[],
  fixa?: Dimensao | undefined,
): Pick<DimensoesEfetivas, "efetivas" | "excluidas" | "consultavel"> {
  const admitidas = new Set<Dimensao>(
    nivel === "brasil"
      ? razao.dimensoes
      : razao.dimensoes.filter((d) => razao.dimensoes_territoriais.includes(d)),
  );
  const unicas = [...new Set(selecionadas)];
  const efetivas = unicas.filter((d) => admitidas.has(d) && (fixa === undefined || d === fixa));
  const excluidas = unicas.filter((d) => !efetivas.includes(d));
  return { efetivas, excluidas, consultavel: efetivas.length > 0 };
}
