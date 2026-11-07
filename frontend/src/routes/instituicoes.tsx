import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { ComposicaoCard } from "@/components/analise/ComposicaoCard";
import {
  METRICA_INSTITUICOES_PADRAO,
  METRICAS_INSTITUICOES,
  validarInstituicoesSearch,
  type InstituicoesSearch,
  type MetricaInstituicoes,
} from "@/components/analise/search";
import { TabelaInstituicoes } from "@/components/analise/TabelaInstituicoes";
import { useAreaDeDados } from "@/components/analise/useAreaDeDados";
import { DataState, EmptyState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { GlobalFilters } from "@/components/filters/GlobalFilters";
import { SegmentedRadio } from "@/components/filters/SegmentedRadio";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { Skeleton } from "@/components/ui/skeleton";
import type { FiltrosGlobais } from "@/components/filters/search";

export const Route = createFileRoute("/instituicoes")({
  validateSearch: validarInstituicoesSearch,
  head: () => ({
    meta: [
      { title: "Instituições — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Instituições de ensino superior no Censo 2024: composição por categoria administrativa e organização acadêmica, titulação do corpo docente e tabela detalhada por instituição.",
      },
    ],
  }),
  component: Instituicoes,
});

const ROTULO_METRICA: Record<MetricaInstituicoes, string> = {
  ies: "Instituições",
  docentes: "Docentes",
  tecnicos: "Técnicos",
};

function Instituicoes() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const { metadados, catalogo, disponiveis, escopo, dimensoes, rotuloDimensao } =
    useAreaDeDados(search);

  const atualizar = (alteracao: Partial<InstituicoesSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });
  // Qualquer mudança de filtro muda o conjunto de IES: a tabela volta à primeira página.
  const filtrar = (alteracao: Partial<FiltrosGlobais>) =>
    atualizar({ ...alteracao, pagina: undefined });

  const metrica = search.metrica ?? METRICA_INSTITUICOES_PADRAO;
  const comuns = {
    escopo,
    dimensoes,
    rede: search.rede,
    categoria: search.categoria,
    organizacao: search.organizacao,
    rotuloDimensao,
  };

  return (
    <AppShell
      footer={
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
        <SectionHeader as="h1" eyebrow="Instituições" title="Instituições de ensino superior">
          Quem oferta a educação superior no Censo 2024: o perfil das instituições por categoria
          administrativa e organização acadêmica, a titulação do corpo docente e cada instituição em
          detalhe. Uma instituição é contada uma única vez, no município da sua sede — não é
          contagem de campi nem de polos.
        </SectionHeader>

        <div className="mt-8">
          <GlobalFilters filtros={search} onChange={filtrar} disponiveis={disponiveis} />
        </div>

        <div className="mt-12">
          <DataState
            query={metadados}
            loadingLabel="Carregando as análises…"
            loading={<Skeleton className="h-64 w-full" />}
          >
            {() => (
              <DataState
                query={catalogo}
                loadingLabel="Carregando o catálogo de indicadores…"
                loading={<Skeleton className="h-64 w-full" />}
              >
                {(indicadores) => {
                  const indicador = indicadores.find((i) => i.slug === metrica);
                  const docentes = indicadores.find((i) => i.slug === "docentes");
                  return (
                    <>
                      <section aria-labelledby="titulo-perfil">
                        <div className="flex flex-wrap items-end justify-between gap-4">
                          <SectionHeader
                            as="h2"
                            eyebrow="Perfil institucional"
                            title={escopo.nome}
                            titleId="titulo-perfil"
                            titleClassName="text-2xl"
                          />
                          <SegmentedRadio<MetricaInstituicoes>
                            legenda="Medida"
                            opcoes={METRICAS_INSTITUICOES.map((valor) => ({
                              valor,
                              rotulo: ROTULO_METRICA[valor],
                            }))}
                            valor={metrica}
                            onChange={(valor) =>
                              atualizar({
                                metrica: valor === METRICA_INSTITUICOES_PADRAO ? undefined : valor,
                              })
                            }
                          />
                        </div>
                        {indicador ? (
                          <div className="mt-6 grid gap-6 lg:grid-cols-2">
                            <ComposicaoCard
                              {...comuns}
                              titulo={`${indicador.nome} por categoria administrativa`}
                              indicador={indicador}
                              eixo="categoria"
                              coluna="Categoria administrativa"
                            />
                            <ComposicaoCard
                              {...comuns}
                              titulo={`${indicador.nome} por organização acadêmica`}
                              indicador={indicador}
                              eixo="organizacao"
                              coluna="Organização acadêmica"
                            />
                          </div>
                        ) : (
                          <EmptyState className="mt-6">
                            O indicador desta composição não está no catálogo da API.
                          </EmptyState>
                        )}
                      </section>

                      {docentes && (
                        <section aria-labelledby="titulo-docentes" className="mt-12">
                          <SectionHeader
                            as="h2"
                            eyebrow="Corpo docente"
                            title="Titulação dos docentes em exercício"
                            titleId="titulo-docentes"
                            titleClassName="text-2xl"
                          />
                          <div className="mt-6">
                            <ComposicaoCard
                              {...comuns}
                              titulo="Docentes em exercício por maior titulação"
                              indicador={docentes}
                              eixo="titulacao"
                              coluna="Maior titulação"
                              ordemDaApi
                            />
                          </div>
                        </section>
                      )}

                      <section aria-labelledby="titulo-tabela" className="mt-12">
                        <SectionHeader
                          as="h2"
                          eyebrow="Tabela detalhada"
                          title="Instituição por instituição"
                          titleId="titulo-tabela"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6">
                          <TabelaInstituicoes
                            escopo={escopo}
                            dimensoes={dimensoes}
                            rede={search.rede}
                            categoria={search.categoria}
                            organizacao={search.organizacao}
                            ordem={search.ordem}
                            pagina={search.pagina}
                            onChange={({ ordem, pagina }) =>
                              // Trocar a ordem volta à primeira página.
                              atualizar(
                                pagina === undefined
                                  ? { ordem, pagina: undefined }
                                  : { pagina: pagina > 1 ? pagina : undefined },
                              )
                            }
                          />
                        </div>
                      </section>
                    </>
                  );
                }}
              </DataState>
            )}
          </DataState>
        </div>
      </Container>
    </AppShell>
  );
}
