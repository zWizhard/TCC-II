import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { ComposicaoCard } from "@/components/analise/ComposicaoCard";
import { RazaoCard } from "@/components/analise/RazaoCard";
import {
  BASE_FLUXO_PADRAO,
  COMPARACAO_PADRAO,
  ROTULO_AGRUPAMENTO,
  validarMatriculasSearch,
  type MatriculasSearch,
} from "@/components/analise/search";
import { useAreaDeDados } from "@/components/analise/useAreaDeDados";
import { DataState, EmptyState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { GlobalFilters } from "@/components/filters/GlobalFilters";
import { SegmentedRadio } from "@/components/filters/SegmentedRadio";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { IndicadorKpi } from "@/components/painel/KpisTerritorio";
import { Skeleton } from "@/components/ui/skeleton";
import { razoesQueryOptions } from "@/lib/api/queries";
import {
  AGRUPAMENTOS,
  BASES_FLUXO,
  agrupamentoSchema,
  type BaseFluxo,
  type Eixo,
} from "@/lib/api/schemas";

export const Route = createFileRoute("/matriculas")({
  validateSearch: validarMatriculasSearch,
  head: () => ({
    meta: [
      { title: "Matrículas e Fluxo — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Matrículas, ingressantes, concluintes, vagas e inscrições no Censo 2024: perfil dos estudantes, financiamento, reserva de vagas e razões por vaga ofertada.",
      },
    ],
  }),
  component: Matriculas,
});

const ROTULO =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground";
const SELECT =
  "h-9 w-full min-w-0 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground";

/** Os cinco indicadores diretos de fluxo, na ordem de exibição. */
const KPIS_DE_FLUXO = ["matriculas", "ingressantes", "concluintes", "vagas", "inscricoes"];

const ROTULO_BASE: Record<BaseFluxo, string> = {
  matriculas: "Matrículas",
  ingressantes: "Ingressantes",
  concluintes: "Concluintes",
};

/** Eixos de perfil (IND-R-07), com o cabeçalho da coluna de categorias. */
const PERFIS: ReadonlyArray<{ eixo: Eixo; coluna: string; por: string }> = [
  { eixo: "sexo", coluna: "Sexo", por: "por sexo" },
  { eixo: "faixa_etaria", coluna: "Faixa etária", por: "por faixa etária" },
  { eixo: "cor_raca", coluna: "Cor ou raça", por: "por cor ou raça" },
  { eixo: "procedencia_escolar", coluna: "Procedência escolar", por: "por procedência escolar" },
  { eixo: "nacionalidade", coluna: "Nacionalidade", por: "por nacionalidade" },
];

function Matriculas() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const { metadados, catalogo, disponiveis, escopo, dimensoes, rotuloDimensao } =
    useAreaDeDados(search);
  const razoes = useQuery(razoesQueryOptions());
  const idComparar = useId();

  const atualizar = (alteracao: Partial<MatriculasSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });

  const base = search.base ?? BASE_FLUXO_PADRAO;
  const comparar = search.comparar ?? COMPARACAO_PADRAO;
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
        <SectionHeader as="h1" eyebrow="Matrículas e Fluxo" title="Matrículas, ingressos e vagas">
          Quantos estudantes a educação superior atende no Censo 2024, quem são, e como vagas,
          inscrições e ingressos se relacionam. Tudo aqui é um retrato de um único ano: os números
          contam vínculos, não pessoas, e não acompanham uma turma do ingresso à conclusão.
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
            {(meta) => (
              <DataState
                query={catalogo}
                loadingLabel="Carregando o catálogo de indicadores…"
                loading={<Skeleton className="h-64 w-full" />}
              >
                {(indicadores) => {
                  const kpis = KPIS_DE_FLUXO.flatMap((slug) =>
                    indicadores.filter((i) => i.slug === slug),
                  );
                  const indicadorBase = indicadores.find((i) => i.slug === base);
                  return (
                    <>
                      <section aria-labelledby="titulo-numeros">
                        <SectionHeader
                          as="h2"
                          eyebrow="Números de 2024"
                          title={escopo.nome}
                          titleId="titulo-numeros"
                          titleClassName="text-2xl"
                        />
                        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                          {kpis.map((indicador) => (
                            <IndicadorKpi
                              key={indicador.slug}
                              indicador={indicador}
                              totalDimensoes={meta.dimensoes_oferta.length}
                              {...comuns}
                            />
                          ))}
                        </div>
                        <p
                          role="note"
                          className="mt-4 rounded-md bg-demo px-3 py-2.5 text-xs leading-5 text-demo-foreground"
                        >
                          Estes números aparecem lado a lado apenas como descrição. Concluintes,
                          ingressantes e matrículas de 2024 pertencem a turmas diferentes: dividir
                          um pelo outro não mede conclusão nem abandono, e essa conta não é feita
                          aqui (IND-Q-01).
                        </p>
                      </section>

                      <section aria-labelledby="titulo-perfil" className="mt-12">
                        <div className="flex flex-wrap items-end justify-between gap-4">
                          <SectionHeader
                            as="h2"
                            eyebrow="Perfil dos estudantes"
                            title="Quem são"
                            titleId="titulo-perfil"
                            titleClassName="text-2xl"
                          />
                          <SegmentedRadio<BaseFluxo>
                            legenda="Base"
                            opcoes={BASES_FLUXO.map((valor) => ({
                              valor,
                              rotulo: ROTULO_BASE[valor],
                            }))}
                            valor={base}
                            onChange={(valor) =>
                              atualizar({ base: valor === BASE_FLUXO_PADRAO ? undefined : valor })
                            }
                          />
                        </div>
                        {indicadorBase ? (
                          <div className="mt-6 grid gap-6 lg:grid-cols-2">
                            {PERFIS.map(({ eixo, coluna, por }) => (
                              <ComposicaoCard
                                key={eixo}
                                {...comuns}
                                titulo={`${indicadorBase.nome} ${por}`}
                                indicador={indicadorBase}
                                eixo={eixo}
                                coluna={coluna}
                                ordemDaApi
                              />
                            ))}
                            {base === "ingressantes" && (
                              <ComposicaoCard
                                {...comuns}
                                titulo={`${indicadorBase.nome} por tipo de vaga`}
                                indicador={indicadorBase}
                                eixo="tipo_ingresso"
                                coluna="Tipo de vaga"
                                ordemDaApi
                              />
                            )}
                          </div>
                        ) : (
                          <EmptyState className="mt-6">
                            O indicador desta base não está no catálogo da API.
                          </EmptyState>
                        )}
                      </section>

                      <DataState
                        query={razoes}
                        loadingLabel="Carregando o catálogo de razões…"
                        loading={<Skeleton className="mt-12 h-64 w-full" />}
                      >
                        {(catalogoRazoes) => {
                          const razao = (slug: string) =>
                            catalogoRazoes.find((r) => r.slug === slug);
                          const financiamento = razao("financiamento");
                          const reserva = razao("reserva_vagas");
                          const ingressos = razao("ingressantes_por_vaga");
                          const inscricoes = razao("inscricoes_por_vaga");
                          return (
                            <>
                              <section aria-labelledby="titulo-acesso" className="mt-12">
                                <div className="flex flex-wrap items-end justify-between gap-4">
                                  <SectionHeader
                                    as="h2"
                                    eyebrow={`Base: ${ROTULO_BASE[base].toLowerCase()}`}
                                    title="Financiamento e reserva de vagas"
                                    titleId="titulo-acesso"
                                    titleClassName="text-2xl"
                                  />
                                  <div className="w-full min-w-0 sm:w-64">
                                    <label htmlFor={idComparar} className={ROTULO}>
                                      Comparar por
                                    </label>
                                    <select
                                      id={idComparar}
                                      value={comparar}
                                      onChange={(event) => {
                                        const valor = agrupamentoSchema.parse(event.target.value);
                                        atualizar({
                                          comparar: valor === COMPARACAO_PADRAO ? undefined : valor,
                                        });
                                      }}
                                      className={SELECT}
                                    >
                                      {AGRUPAMENTOS.map((valor) => (
                                        <option key={valor} value={valor}>
                                          {ROTULO_AGRUPAMENTO[valor]}
                                        </option>
                                      ))}
                                    </select>
                                  </div>
                                </div>
                                <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                                  A base e a comparação escolhidas valem para os cartões desta seção
                                  e da seguinte. Cada percentual é a parte do total que tem a marca
                                  indicada; os tipos de financiamento e de reserva não são
                                  detalhados porque se sobrepõem na base.
                                </p>
                                <div className="mt-6 grid gap-6">
                                  {financiamento && (
                                    <RazaoCard
                                      {...comuns}
                                      titulo={`${ROTULO_BASE[base]} com financiamento estudantil`}
                                      razao={financiamento}
                                      base={base}
                                      por={comparar}
                                    />
                                  )}
                                  {reserva && (
                                    <RazaoCard
                                      {...comuns}
                                      titulo={`${ROTULO_BASE[base]} com reserva de vagas`}
                                      razao={reserva}
                                      base={base}
                                      por={comparar}
                                    />
                                  )}
                                </div>
                              </section>

                              <section aria-labelledby="titulo-vagas" className="mt-12">
                                <SectionHeader
                                  as="h2"
                                  eyebrow="Vagas, inscrições e ingressos"
                                  title="Razões por vaga ofertada"
                                  titleId="titulo-vagas"
                                  titleClassName="text-2xl"
                                >
                                  Em cursos a distância, a base registra vagas e ingressos em
                                  dimensões de oferta diferentes; por isso estas razões são
                                  calculadas no presencial, e a dimensão EAD sem território aparece
                                  à parte, nunca somada.
                                </SectionHeader>
                                <div className="mt-6 grid gap-6">
                                  {ingressos && (
                                    <RazaoCard
                                      {...comuns}
                                      titulo="Ingressantes por vaga ofertada (presencial)"
                                      razao={ingressos}
                                      por={comparar}
                                      dimensaoFixa="presencial"
                                    />
                                  )}
                                  {inscricoes && (
                                    <RazaoCard
                                      {...comuns}
                                      titulo="Inscrições por vaga ofertada (presencial)"
                                      razao={inscricoes}
                                      por={comparar}
                                      dimensaoFixa="presencial"
                                    />
                                  )}
                                  {inscricoes && escopo.nivel === "brasil" && (
                                    <RazaoCard
                                      {...comuns}
                                      titulo="Inscrições por vaga ofertada (EAD, só no nível Brasil)"
                                      razao={inscricoes}
                                      por={comparar}
                                      dimensaoFixa="ead_nacional"
                                    />
                                  )}
                                </div>
                              </section>
                            </>
                          );
                        }}
                      </DataState>

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
                            <strong className="text-foreground">
                              Razão entre concluintes, ingressantes e matrículas.
                            </strong>{" "}
                            São turmas diferentes observadas no mesmo ano; nenhuma razão entre elas
                            é calculada (IND-Q-01).
                          </li>
                          <li>
                            <strong className="text-foreground">
                              Trancamentos, desvinculações e transferências.
                            </strong>{" "}
                            As contagens de situação existem na base, mas não são um subconjunto das
                            matrículas e não têm denominador válido; ficam em quarentena
                            metodológica (IND-Q-02).
                          </li>
                          <li>
                            <strong className="text-foreground">
                              Tipo de processo seletivo e tipos de financiamento ou de reserva.
                            </strong>{" "}
                            Essas colunas não fecham com o total ou se sobrepõem; só os agregados
                            são publicados.
                          </li>
                          <li>
                            <strong className="text-foreground">Perfil por município.</strong>{" "}
                            Bloqueio provisório: muitos municípios têm poucas matrículas, e o piso
                            de supressão ainda não foi definido.
                          </li>
                          <li>
                            <strong className="text-foreground">Turno.</strong> Só existe para
                            cursos presenciais e ainda não é um indicador formal da plataforma.
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
