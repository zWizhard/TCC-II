import { useId } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { ComposicaoCard } from "@/components/analise/ComposicaoCard";
import {
  LIMITE_ROTULOS,
  METRICA_CURSOS_PADRAO,
  validarCursosSearch,
  type CursosSearch,
} from "@/components/analise/search";
import { useAreaDeDados } from "@/components/analise/useAreaDeDados";
import { DataState, EmptyState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { GlobalFilters } from "@/components/filters/GlobalFilters";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { Skeleton } from "@/components/ui/skeleton";
import { areaCineSchema, grauSchema, type Metadados } from "@/lib/api/schemas";

export const Route = createFileRoute("/cursos")({
  validateSearch: validarCursosSearch,
  head: () => ({
    meta: [
      { title: "Cursos — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Cursos de graduação no Censo 2024: composição por grau acadêmico, dimensão de oferta e área do conhecimento (CINE), e os rótulos CINE de maior valor.",
      },
    ],
  }),
  component: Cursos,
});

const ROTULO =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground";
const SELECT =
  "h-9 w-full min-w-0 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground";

function Cursos() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const { metadados, catalogo, disponiveis, escopo, dimensoes, rotuloDimensao } =
    useAreaDeDados(search);
  const idIndicador = useId();
  const idArea = useId();
  const idGrau = useId();

  const atualizar = (alteracao: Partial<CursosSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });

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
        <SectionHeader as="h1" eyebrow="Cursos" title="Cursos e oferta">
          O que é ofertado na educação superior no Censo 2024: como cada indicador se reparte por
          grau acadêmico, dimensão de oferta e área do conhecimento. Um curso a distância aparece na
          base uma vez por polo; por isso cursos são contados pelo marcador da própria base, e não
          pelo número de registros.
        </SectionHeader>

        <div className="mt-8">
          <GlobalFilters filtros={search} onChange={atualizar} disponiveis={disponiveis} />
        </div>

        <div className="mt-12">
          <DataState
            query={metadados}
            loadingLabel="Carregando as análises…"
            loading={<Skeleton className="h-64 w-full" />}
          >
            {(meta: Metadados) => (
              <DataState
                query={catalogo}
                loadingLabel="Carregando o catálogo de indicadores…"
                loading={<Skeleton className="h-64 w-full" />}
              >
                {(indicadores) => {
                  // Só indicadores da tabela de cursos: são os que têm grau, área e dimensão.
                  const deCursos = indicadores.filter((i) => i.exige_dimensao);
                  const indicador =
                    deCursos.find((i) => i.slug === search.metrica) ??
                    deCursos.find((i) => i.slug === METRICA_CURSOS_PADRAO) ??
                    deCursos[0];
                  if (!indicador) {
                    return (
                      <EmptyState>O catálogo da API não tem indicadores de cursos.</EmptyState>
                    );
                  }
                  const comuns = {
                    indicador,
                    escopo,
                    dimensoes,
                    rede: search.rede,
                    categoria: search.categoria,
                    organizacao: search.organizacao,
                    area: search.area,
                    grau: search.grau,
                    rotuloDimensao,
                  };
                  return (
                    <>
                      <section aria-labelledby="titulo-composicao">
                        <SectionHeader
                          as="h2"
                          eyebrow="Composição da oferta"
                          title={escopo.nome}
                          titleId="titulo-composicao"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6 grid gap-4 rounded-md border border-border bg-card p-4 sm:grid-cols-3">
                          <div className="min-w-0">
                            <label htmlFor={idIndicador} className={ROTULO}>
                              Indicador
                            </label>
                            <select
                              id={idIndicador}
                              value={indicador.slug}
                              onChange={(event) =>
                                atualizar({
                                  metrica:
                                    event.target.value === METRICA_CURSOS_PADRAO
                                      ? undefined
                                      : event.target.value,
                                })
                              }
                              className={SELECT}
                            >
                              {deCursos.map((item) => (
                                <option key={item.slug} value={item.slug}>
                                  {item.codigo} — {item.nome}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="min-w-0">
                            <label htmlFor={idArea} className={ROTULO}>
                              Área geral (CINE)
                            </label>
                            <select
                              id={idArea}
                              value={search.area ?? ""}
                              onChange={(event) =>
                                atualizar({
                                  area: areaCineSchema
                                    .optional()
                                    .parse(event.target.value || undefined),
                                })
                              }
                              className={SELECT}
                            >
                              <option value="">Todas as áreas</option>
                              {meta.areas_cine.map((area) => (
                                <option key={area.slug} value={area.slug}>
                                  {area.nome}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="min-w-0">
                            <label htmlFor={idGrau} className={ROTULO}>
                              Grau acadêmico
                            </label>
                            <select
                              id={idGrau}
                              value={search.grau ?? ""}
                              onChange={(event) =>
                                atualizar({
                                  grau: grauSchema
                                    .optional()
                                    .parse(event.target.value || undefined),
                                })
                              }
                              className={SELECT}
                            >
                              <option value="">Todos os graus</option>
                              {meta.graus.map((grau) => (
                                <option key={grau.slug} value={grau.slug}>
                                  {grau.rotulo}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>

                        <div className="mt-6 grid gap-6 lg:grid-cols-2">
                          <ComposicaoCard
                            {...comuns}
                            titulo={`${indicador.nome} por grau acadêmico`}
                            eixo="grau"
                            coluna="Grau acadêmico"
                          />
                          <ComposicaoCard
                            {...comuns}
                            titulo={`${indicador.nome} por dimensão de oferta`}
                            eixo="dimensao"
                            coluna="Dimensão de oferta"
                          />
                        </div>
                      </section>

                      <section aria-labelledby="titulo-areas" className="mt-12">
                        <SectionHeader
                          as="h2"
                          eyebrow="Área do conhecimento"
                          title="Classificação CINE"
                          titleId="titulo-areas"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6 grid gap-6">
                          <ComposicaoCard
                            {...comuns}
                            titulo={`${indicador.nome} por área geral`}
                            eixo="area"
                            coluna="Área geral (CINE)"
                          />
                          <ComposicaoCard
                            {...comuns}
                            titulo={`${indicador.nome}: os ${LIMITE_ROTULOS} rótulos CINE de maior valor`}
                            eixo="rotulo_cine"
                            coluna="Rótulo CINE"
                            limite={LIMITE_ROTULOS}
                          />
                        </div>
                      </section>

                      <section aria-labelledby="titulo-ausentes" className="mt-12">
                        <SectionHeader
                          as="h2"
                          eyebrow="Limites da base"
                          title="O que esta página não mostra"
                          titleId="titulo-ausentes"
                          titleClassName="text-2xl"
                        />
                        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                          <li>
                            <strong className="text-foreground">Comparação entre anos.</strong> A
                            base tem um único ano de referência (2024): é um retrato, sem série
                            temporal.
                          </li>
                          <li>
                            <strong className="text-foreground">Situação do curso.</strong> Não
                            existe coluna de situação na base; as contagens de situação de matrícula
                            não têm denominador válido e estão em quarentena metodológica
                            (IND-Q-02).
                          </li>
                          <li>
                            <strong className="text-foreground">Turno.</strong> Só existe para
                            cursos presenciais e ainda não é um indicador formal da plataforma.
                          </li>
                          <li>
                            <strong className="text-foreground">
                              Razão entre concluintes e ingressantes.
                            </strong>{" "}
                            Concluintes e ingressantes de 2024 são de turmas diferentes; a razão
                            entre eles não é calculada (IND-Q-01).
                          </li>
                        </ul>
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
