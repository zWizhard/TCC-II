import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { useAreaDeDados } from "@/components/analise/useAreaDeDados";
import { DataState, EmptyState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { GlobalFilters } from "@/components/filters/GlobalFilters";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { DistribuicaoNoMapa } from "@/components/map/DistribuicaoNoMapa";
import { validarMapaSearch, type MapaSearch } from "@/components/map/search";
import { Skeleton } from "@/components/ui/skeleton";
import type { IndicadorInfo } from "@/lib/api/schemas";

export const Route = createFileRoute("/mapa")({
  validateSearch: validarMapaSearch,
  head: () => ({
    meta: [
      { title: "Distribuição Territorial — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Mapa da educação superior no Censo 2024: matrículas por 100 mil habitantes por UF e município, municípios de sede das instituições e concentração de matrículas, ingressantes e concluintes.",
      },
    ],
  }),
  component: Mapa,
});

function temIndicadores(
  catalogo: readonly IndicadorInfo[],
): catalogo is readonly [IndicadorInfo, ...IndicadorInfo[]] {
  return catalogo.length > 0;
}

function Mapa() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const { metadados, catalogo, disponiveis, escopo, dimensoes, rotuloDimensao } =
    useAreaDeDados(search);

  // `replace`: nem troca de filtro nem clique no mapa empilham entradas de histórico.
  const atualizar = (alteracao: Partial<MapaSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });

  return (
    <AppShell
      footer={
        metadados.data && (
          <footer className="bg-ai text-primary-foreground">
            <Container className="py-10">
              <SourceNote metadados={metadados.data} />
              <p className="mt-4 text-xs leading-5 text-primary-foreground/70">
                Malha territorial: IBGE, API de malhas v4, qualidade mínima, baixada em 2026-10-07 —
                geometria simplificada, só para visualização. População: estimativa do IBGE para
                2024. O mapa não usa imagens nem serviços de terceiros.
              </p>
            </Container>
          </footer>
        )
      }
    >
      <Container className="py-10 lg:py-14">
        <SectionHeader as="h1" eyebrow="Distribuição Territorial" title="Onde está a oferta">
          A educação superior do Censo 2024 no território, em três leituras: matrículas em relação à
          população (coroplético), municípios que sediam instituições (pontos) e concentração de um
          indicador (mapa de calor). É o retrato de um único ano, e cada modo declara o recorte
          territorial que usa.
        </SectionHeader>

        <div className="mt-8">
          <GlobalFilters filtros={search} onChange={atualizar} disponiveis={disponiveis} />
        </div>

        <div className="mt-10">
          <DataState
            query={metadados}
            loadingLabel="Carregando o mapa…"
            loading={<Skeleton className="h-[60vh] w-full" />}
          >
            {(meta) => (
              <DataState
                query={catalogo}
                loadingLabel="Carregando o catálogo de indicadores…"
                loading={<Skeleton className="h-[60vh] w-full" />}
              >
                {(indicadores) =>
                  temIndicadores(indicadores) ? (
                    <DistribuicaoNoMapa
                      metadados={meta}
                      catalogo={indicadores}
                      search={search}
                      escopo={escopo}
                      dimensoes={dimensoes}
                      rotuloDimensao={rotuloDimensao}
                      onChange={atualizar}
                    />
                  ) : (
                    <EmptyState>O catálogo de indicadores da API está vazio.</EmptyState>
                  )
                }
              </DataState>
            )}
          </DataState>
        </div>

        <section aria-labelledby="titulo-leitura" className="mt-12">
          <SectionHeader
            as="h2"
            eyebrow="Como ler"
            title="O que o mapa mostra e o que não mostra"
            titleId="titulo-leitura"
            titleClassName="text-2xl"
          />
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
            <li>
              <strong className="text-foreground">Unidades territoriais.</strong> A malha tem 5.571
              municípios e equivalentes (inclui Fernando de Noronha) e 27 UFs. O casamento com os
              dados é sempre pelo código IBGE, nunca pelo nome.
            </li>
            <li>
              <strong className="text-foreground">Ausência não é zero.</strong> Unidade sem registro
              de oferta aparece em cinza hachurado; unidade com registro e zero matrículas entra na
              classe mais baixa, com o valor 0 na dica e na tabela.
            </li>
            <li>
              <strong className="text-foreground">Sem coordenada por instituição.</strong> A base só
              tem a coordenada de referência do município. Os pontos são municípios de sede; em 62
              das 5.571 unidades essa coordenada cai fora do polígono simplificado da própria
              unidade, por isso pontos e coroplético municipal ficam em modos separados.
            </li>
            <li>
              <strong className="text-foreground">Um único ano.</strong> Não há comparação entre
              anos: a base tem só 2024.
            </li>
          </ul>
        </section>
      </Container>
    </AppShell>
  );
}
