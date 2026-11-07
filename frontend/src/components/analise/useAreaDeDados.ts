import { useQuery } from "@tanstack/react-query";

import type { FiltrosDisponiveis } from "@/components/filters/GlobalFilters";
import {
  dimensoesSelecionadas,
  resolverEscopo,
  type FiltrosGlobais,
} from "@/components/filters/search";
import {
  catalogoQueryOptions,
  metadadosQueryOptions,
  municipiosQueryOptions,
} from "@/lib/api/queries";
import type { Dimensao } from "@/lib/api/schemas";

/**
 * O que toda tela de análise deriva dos filtros globais: opções de filtro, território
 * selecionado e dimensões de oferta. As consultas são as mesmas de `/painel` (cache compartilhado).
 */
export function useAreaDeDados(filtros: FiltrosGlobais) {
  const metadados = useQuery(metadadosQueryOptions());
  const catalogo = useQuery(catalogoQueryOptions());

  let disponiveis: FiltrosDisponiveis;
  if (metadados.isError) {
    disponiveis = { tipo: "erro", erro: metadados.error, onRetry: () => void metadados.refetch() };
  } else if (metadados.isPending) {
    disponiveis = { tipo: "carregando" };
  } else {
    disponiveis = { tipo: "sucesso", metadados: metadados.data };
  }

  // Mesma consulta do seletor de município: só para nomear o território.
  const ufValida = metadados.data?.ufs.find((u) => u.sigla === filtros.uf)?.sigla;
  const municipios = useQuery(municipiosQueryOptions(filtros.municipio ? ufValida : undefined));
  const escopo = resolverEscopo(
    filtros,
    { regioes: metadados.data?.regioes ?? [], ufs: metadados.data?.ufs ?? [] },
    municipios.data?.municipios.find((m) => m.codigo === String(filtros.municipio))?.nome,
  );

  const dimensoesOferta = metadados.data?.dimensoes_oferta ?? [];
  const dimensoes = dimensoesSelecionadas(
    filtros,
    dimensoesOferta.map((d) => d.slug),
  );
  const rotuloDimensao = (slug: Dimensao) =>
    dimensoesOferta.find((d) => d.slug === slug)?.rotulo ?? slug;

  return { metadados, catalogo, disponiveis, escopo, dimensoes, rotuloDimensao };
}
