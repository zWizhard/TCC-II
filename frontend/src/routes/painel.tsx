import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { DataState, EmptyState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { GlobalFilters, type FiltrosDisponiveis } from "@/components/filters/GlobalFilters";
import { dimensoesSelecionadas, resolverEscopo } from "@/components/filters/search";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { DistribuicaoTerritorial } from "@/components/painel/DistribuicaoTerritorial";
import { KpisTerritorio } from "@/components/painel/KpisTerritorio";
import { validarPainelSearch, type PainelSearch } from "@/components/painel/search";
import { Skeleton } from "@/components/ui/skeleton";
import {
  catalogoQueryOptions,
  metadadosQueryOptions,
  municipiosQueryOptions,
} from "@/lib/api/queries";
import type { Dimensao, IndicadorInfo } from "@/lib/api/schemas";

export const Route = createFileRoute("/painel")({
  validateSearch: validarPainelSearch,
  head: () => ({
    meta: [
      { title: "Visão Geral — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Indicadores diretos do Censo da Educação Superior 2024: totais do Brasil, de uma região, UF ou município, e distribuição territorial.",
      },
    ],
  }),
  component: Painel,
});

function Painel() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const metadados = useQuery(metadadosQueryOptions());
  const catalogo = useQuery(catalogoQueryOptions());

  // `replace` para a troca de filtro não empilhar uma entrada de histórico por clique.
  const atualizar = (alteracao: Partial<PainelSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });

  let disponiveis: FiltrosDisponiveis;
  if (metadados.isError) {
    disponiveis = { tipo: "erro", erro: metadados.error, onRetry: () => void metadados.refetch() };
  } else if (metadados.isPending) {
    disponiveis = { tipo: "carregando" };
  } else {
    disponiveis = { tipo: "sucesso", metadados: metadados.data };
  }

  // Mesma consulta do seletor de município (cache compartilhado): só para nomear o território.
  const ufValida = metadados.data?.ufs.find((u) => u.sigla === search.uf)?.sigla;
  const municipios = useQuery(municipiosQueryOptions(search.municipio ? ufValida : undefined));
  const escopo = resolverEscopo(
    search,
    { regioes: metadados.data?.regioes ?? [], ufs: metadados.data?.ufs ?? [] },
    municipios.data?.municipios.find((m) => m.codigo === String(search.municipio))?.nome,
  );

  const dimensoesOferta = metadados.data?.dimensoes_oferta ?? [];
  const dimensoes = dimensoesSelecionadas(
    search,
    dimensoesOferta.map((d) => d.slug),
  );
  const rotuloDimensao = (slug: Dimensao) =>
    dimensoesOferta.find((d) => d.slug === slug)?.rotulo ?? slug;

  return (
    <AppShell
      footer={
        // Só com a fonte em mãos: carregamento e erro dos metadados já aparecem no conteúdo,
        // e repeti-los aqui faria o leitor de tela anunciar a mesma falha de novo.
        metadados.data && (
          <footer className="bg-ai text-primary-foreground">
            <Container className="py-10">
              <SourceNote metadados={metadados.data} />
            </Container>
          </footer>
        )
      }
    >
      <Container className="py-10 lg:py-14">
        <SectionHeader as="h1" eyebrow="Visão Geral" title="Educação Superior no Censo 2024">
          Indicadores diretos do Censo da Educação Superior, agregados a partir da cópia local dos
          dados. É o retrato de um único ano de referência — a base não permite comparar anos — e
          cada número declara o recorte territorial e as ressalvas da sua ficha metodológica.
        </SectionHeader>

        <div className="mt-8">
          <GlobalFilters filtros={search} onChange={atualizar} disponiveis={disponiveis} />
        </div>

        {/* Os valores dependem das dimensões de oferta: sem os metadados não há o que consultar. */}
        <div className="mt-12">
          <DataState
            query={metadados}
            loadingLabel="Carregando os indicadores…"
            loading={<EsqueletoDoPainel />}
          >
            {() => (
              <DataState
                query={catalogo}
                loadingLabel="Carregando o catálogo de indicadores…"
                loading={<EsqueletoDoPainel />}
              >
                {(indicadores) =>
                  temIndicadores(indicadores) ? (
                    <>
                      <section aria-labelledby="titulo-kpis">
                        <SectionHeader
                          as="h2"
                          eyebrow={
                            escopo.nivel === "brasil" ? "Totais nacionais" : "Totais do território"
                          }
                          title={escopo.nome}
                          titleId="titulo-kpis"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6">
                          <KpisTerritorio
                            catalogo={indicadores}
                            escopo={escopo}
                            dimensoes={dimensoes}
                            totalDimensoes={dimensoesOferta.length}
                            rede={search.rede}
                            categoria={search.categoria}
                            organizacao={search.organizacao}
                            rotuloDimensao={rotuloDimensao}
                          />
                        </div>
                      </section>

                      <section aria-labelledby="titulo-distribuicao" className="mt-12">
                        <SectionHeader
                          as="h2"
                          eyebrow="Distribuição territorial"
                          title={
                            {
                              brasil: "Por região e por UF",
                              regiao: "UFs da região",
                              uf: "Municípios da UF",
                              municipio: "Município selecionado",
                            }[escopo.nivel]
                          }
                          titleId="titulo-distribuicao"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6">
                          <DistribuicaoTerritorial
                            catalogo={indicadores}
                            indicadorSlug={search.indicador}
                            nivel={search.nivel}
                            escopo={escopo}
                            dimensoes={dimensoes}
                            rede={search.rede}
                            categoria={search.categoria}
                            organizacao={search.organizacao}
                            rotuloDimensao={rotuloDimensao}
                            onChange={atualizar}
                          />
                        </div>
                      </section>
                    </>
                  ) : (
                    <EmptyState>O catálogo de indicadores da API está vazio.</EmptyState>
                  )
                }
              </DataState>
            )}
          </DataState>
        </div>
      </Container>
    </AppShell>
  );
}

function temIndicadores(
  catalogo: readonly IndicadorInfo[],
): catalogo is readonly [IndicadorInfo, ...IndicadorInfo[]] {
  return catalogo.length > 0;
}

function EsqueletoDoPainel() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-40 w-full" />
      ))}
    </div>
  );
}
