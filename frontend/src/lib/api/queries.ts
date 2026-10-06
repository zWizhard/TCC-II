import { QueryClient, queryOptions } from "@tanstack/react-query";

import {
  ApiIndisponivelError,
  consultarIndicador,
  listarIndicadores,
  montarParametrosIndicador,
  obterMetadados,
  obterSaude,
  type ConsultaIndicador,
} from "./client";
import { resolverDimensoes } from "./dimensoes";
import type { IndicadorInfo } from "./schemas";

const UMA_HORA = 60 * 60 * 1000;

/**
 * O dado é estático (Censo 2024, uma única extração): não há por que revalidar a cada foco.
 * Só falha de rede é repetida, e uma única vez — 4xx/5xx com envelope e resposta fora do
 * contrato são determinísticos, repetir não muda o resultado.
 */
export function criarQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: UMA_HORA,
        gcTime: UMA_HORA,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        retry: (falhas, erro) => erro instanceof ApiIndisponivelError && falhas < 1,
      },
    },
  });
}

export const saudeQueryOptions = () =>
  queryOptions({
    queryKey: ["api", "saude"] as const,
    queryFn: ({ signal }) => obterSaude({ signal }),
    staleTime: 0,
  });

export const metadadosQueryOptions = () =>
  queryOptions({
    queryKey: ["api", "metadados"] as const,
    queryFn: ({ signal }) => obterMetadados({ signal }),
  });

export const catalogoQueryOptions = () =>
  queryOptions({
    queryKey: ["api", "indicadores"] as const,
    queryFn: ({ signal }) => listarIndicadores({ signal }),
  });

/**
 * Valores de um indicador. A chave usa a query string efetiva, de modo que seleções que resultam
 * na mesma requisição (ex.: dimensão marcada em indicador que não a usa) compartilham o cache.
 * Fica desabilitada quando o indicador exige dimensão e nenhuma das selecionadas é admitida.
 */
export const indicadorQueryOptions = (indicador: IndicadorInfo, consulta: ConsultaIndicador) => {
  const { consultavel } = resolverDimensoes(indicador, consulta.nivel, consulta.dimensoes ?? []);
  return queryOptions({
    queryKey: [
      "api",
      "indicador",
      indicador.slug,
      montarParametrosIndicador(indicador, consulta).toString(),
    ] as const,
    queryFn: ({ signal }) => consultarIndicador(indicador, consulta, { signal }),
    enabled: consultavel,
  });
};
