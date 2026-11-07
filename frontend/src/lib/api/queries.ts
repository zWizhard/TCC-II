import { QueryClient, queryOptions } from "@tanstack/react-query";

import {
  ApiIndisponivelError,
  consultarComparacao,
  consultarComposicao,
  consultarCoropletico,
  consultarIndicador,
  consultarRazao,
  listarIndicadores,
  listarInstituicoes,
  listarMunicipios,
  listarRazoes,
  montarParametrosComparacao,
  montarParametrosComposicao,
  montarParametrosCoropletico,
  montarParametrosIndicador,
  montarParametrosInstituicoes,
  montarParametrosRazao,
  obterMalha,
  obterMetadados,
  obterSaude,
  type ConsultaComparacao,
  type ConsultaComposicao,
  type ConsultaCoropletico,
  type ConsultaIndicador,
  type ConsultaInstituicoes,
  type ConsultaRazao,
} from "./client";
import { resolverDimensoes } from "./dimensoes";
import type { IndicadorInfo, NivelMalha, RazaoInfo } from "./schemas";

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

/** Municípios de uma UF para o filtro territorial. Desabilitada enquanto não há UF escolhida. */
export const municipiosQueryOptions = (uf: string | undefined) =>
  queryOptions({
    queryKey: ["api", "municipios", uf ?? ""] as const,
    queryFn: ({ signal }) => listarMunicipios(uf ?? "", { signal }),
    enabled: uf !== undefined,
  });

/**
 * Composição de um indicador por um eixo. Mesma regra de `indicadorQueryOptions`: chave pela
 * query string efetiva, desabilitada quando nenhuma dimensão selecionada é admitida.
 */
export const composicaoQueryOptions = (indicador: IndicadorInfo, consulta: ConsultaComposicao) => {
  const { consultavel } = resolverDimensoes(indicador, consulta.nivel, consulta.dimensoes ?? []);
  return queryOptions({
    queryKey: [
      "api",
      "composicao",
      indicador.slug,
      montarParametrosComposicao(indicador, consulta).toString(),
    ] as const,
    queryFn: ({ signal }) => consultarComposicao(indicador, consulta, { signal }),
    enabled: consultavel,
  });
};

export const razoesQueryOptions = () =>
  queryOptions({
    queryKey: ["api", "razoes"] as const,
    queryFn: ({ signal }) => listarRazoes({ signal }),
  });

/** Uma razão. Desabilitada sem dimensão admitida ou, nas que usam base, sem base. */
export const razaoQueryOptions = (razao: RazaoInfo, consulta: ConsultaRazao) =>
  queryOptions({
    queryKey: [
      "api",
      "razao",
      razao.slug,
      montarParametrosRazao(razao, consulta).toString(),
    ] as const,
    queryFn: ({ signal }) => consultarRazao(razao, consulta, { signal }),
    enabled: consulta.dimensoes.length > 0 && (!razao.usa_base || consulta.base !== undefined),
  });

/** Página da tabela de IES. Desabilitada sem dimensão de oferta: a API a exige declarada. */
export const instituicoesQueryOptions = (consulta: ConsultaInstituicoes) =>
  queryOptions({
    queryKey: ["api", "instituicoes", montarParametrosInstituicoes(consulta).toString()] as const,
    queryFn: ({ signal }) => listarInstituicoes(consulta, { signal }),
    enabled: consulta.dimensoes.length > 0,
  });

/**
 * Malha territorial. É estática e grande (municípios: 3,9 MB, 1,1 MB comprimida): nunca fica
 * velha nem sai do cache nesta sessão, e quem chama só a habilita quando vai desenhá-la.
 */
export const malhaQueryOptions = (nivel: NivelMalha, habilitada = true) =>
  queryOptions({
    queryKey: ["api", "malha", nivel] as const,
    queryFn: ({ signal }) => obterMalha(nivel, { signal }),
    staleTime: Infinity,
    gcTime: Infinity,
    enabled: habilitada,
  });

/** Coroplético de IND-R-01. Desabilitada sem dimensão de oferta com território. */
export const coropleticoQueryOptions = (consulta: ConsultaCoropletico) =>
  queryOptions({
    queryKey: ["api", "coropletico", montarParametrosCoropletico(consulta).toString()] as const,
    queryFn: ({ signal }) => consultarCoropletico(consulta, { signal }),
    enabled: consulta.dimensoes.length > 0,
  });

/** Comparação entre unidades. Desabilitada com menos de duas: a API recusa. */
export const comparacaoQueryOptions = (consulta: ConsultaComparacao) =>
  queryOptions({
    queryKey: ["api", "comparacao", montarParametrosComparacao(consulta).toString()] as const,
    queryFn: ({ signal }) => consultarComparacao(consulta, { signal }),
    enabled: consulta.unidades.length >= 2,
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
