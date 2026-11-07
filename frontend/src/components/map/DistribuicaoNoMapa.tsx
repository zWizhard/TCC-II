import { useId, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState, ErrorState } from "@/components/data/DataState";
import type { DataTableColumn } from "@/components/data/DataTable";
import { SegmentedRadio } from "@/components/filters/SegmentedRadio";
import type { Escopo, FiltrosGlobais } from "@/components/filters/search";
import { Skeleton } from "@/components/ui/skeleton";
import { resolverDimensoes } from "@/lib/api/dimensoes";
import {
  coropleticoQueryOptions,
  indicadorQueryOptions,
  malhaQueryOptions,
} from "@/lib/api/queries";
import type {
  Dimensao,
  IndicadorInfo,
  Linha,
  LinhaCoropletico,
  Metadados,
  NivelMalha,
  RespostaCoropletico,
  RespostaIndicador,
} from "@/lib/api/schemas";
import { formatarDecimal, formatarInteiro, rotuloRecorte } from "@/lib/format";

import {
  ampliarLimites,
  casasDasClasses,
  estadosDoCoropletico,
  faixaDaClasse,
  limitesDaGeometria,
  limitesDaMalha,
  limitesDoPonto,
  pontosDoIndicador,
  rotulosDasUfs,
  rotuloSemRegistro,
  type ColecaoDeRotulos,
} from "./geo";
import { LegendaCalor, LegendaCoropletico, LegendaPontos } from "./Legendas";
import {
  MapaTerritorial,
  type AlvoDoMapa,
  type CamadaDoMapa,
  type Enquadramento,
} from "./MapaTerritorial";
import { IesDoMunicipio, MunicipioSelecionado, Numero } from "./MunicipioSelecionado";
import {
  chaveDoTerritorio,
  INDICADOR_PONTOS,
  METRICA_CALOR_PADRAO,
  METRICAS_CALOR,
  MODO_PADRAO,
  MODOS_MAPA,
  nomeDoTerritorioDoMapa,
  ROTULO_MODO,
  territorioDoMapa,
  unidadePadrao,
  type MapaSearch,
  type ModoMapa,
} from "./search";
import { TabelaPaginada, type Ordenacao } from "./TabelaPaginada";

const OPCOES_UNIDADE: ReadonlyArray<{ valor: NivelMalha; rotulo: string }> = [
  { valor: "uf", rotulo: "UF" },
  { valor: "municipio", rotulo: "Município" },
];

const SEM_CAMADA: CamadaDoMapa = { modo: "nenhum" };
const SEM_ROTULOS: ColecaoDeRotulos = { type: "FeatureCollection", features: [] };
const BOTAO =
  "h-9 rounded-md border border-border bg-background px-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted";

const colador = new Intl.Collator("pt-BR", { sensitivity: "base" });

type DistribuicaoNoMapaProps = {
  metadados: Metadados;
  /** Catálogo não vazio de `/api/v1/indicadores`. */
  catalogo: readonly [IndicadorInfo, ...IndicadorInfo[]];
  search: MapaSearch;
  escopo: Escopo;
  /** Dimensões de oferta selecionadas nos filtros globais. */
  dimensoes: readonly Dimensao[];
  rotuloDimensao: (slug: Dimensao) => string;
  onChange: (alteracao: Partial<MapaSearch>) => void;
};

/**
 * O mapa e tudo o que o explica: controles de modo, legenda, painel do município selecionado e
 * a tabela com as mesmas unidades. As três consultas ficam aqui para o mapa permanecer montado
 * ao trocar de modo ou de filtro — só os dados mudam.
 */
export function DistribuicaoNoMapa({
  metadados,
  catalogo,
  search,
  escopo,
  dimensoes,
  rotuloDimensao,
  onChange,
}: DistribuicaoNoMapaProps) {
  const seletorId = useId();
  const modo = search.modo ?? MODO_PADRAO;
  const unidade = search.unidade ?? unidadePadrao(escopo);
  const territorio = territorioDoMapa(escopo);
  const nomeTerritorio = nomeDoTerritorioDoMapa(escopo, metadados.ufs);
  const institucionais = {
    rede: search.rede,
    categoria: search.categoria,
    organizacao: search.organizacao,
  };

  // Base do mapa: a malha das UFs (sempre) e a tabela código IBGE ↔ sigla. A tabela é a resposta
  // de IES por UF sem filtros — o `codigo` das linhas de nível UF é o `codarea` da malha.
  const malhaUfs = useQuery(malhaQueryOptions("uf"));
  const indicadorIes = catalogo.find((i) => i.slug === INDICADOR_PONTOS);
  const tabelaUfs = useQuery({
    ...indicadorQueryOptions(indicadorIes ?? catalogo[0], { nivel: "uf" }),
    enabled: indicadorIes !== undefined,
  });

  // Coroplético (IND-R-01): só existe nas dimensões com território, as que `/metadados` marca
  // como territorializáveis; a resposta devolve as mesmas em `indicador.dimensoes_territoriais`.
  const comTerritorio = metadados.dimensoes_oferta
    .filter((d) => d.territorializavel)
    .map((d) => d.slug);
  const dimensoesCoropletico = resolverDimensoes(
    { exige_dimensao: true, dimensoes_territoriais: comTerritorio },
    unidade,
    dimensoes,
  );
  const coropletico = useQuery({
    ...coropleticoQueryOptions({
      nivel: unidade,
      dimensoes: dimensoesCoropletico.efetivas,
      ...institucionais,
      ...territorio,
    }),
    enabled: modo === "coropletico" && dimensoesCoropletico.consultavel,
  });
  // 3,9 MB: só é pedida quando o coroplético municipal está na tela.
  const malhaMunicipios = useQuery(
    malhaQueryOptions("municipio", modo === "coropletico" && unidade === "municipio"),
  );

  // Pontos e calor: um indicador direto por município, na coordenada do município.
  const metricas = METRICAS_CALOR.flatMap((slug) => catalogo.filter((i) => i.slug === slug));
  const indicadorCalor =
    metricas.find((i) => i.slug === search.metrica) ??
    metricas.find((i) => i.slug === METRICA_CALOR_PADRAO) ??
    metricas[0];
  const indicadorPontos = modo === "pontos" ? indicadorIes : indicadorCalor;
  const dimensoesPontos = resolverDimensoes(indicadorPontos ?? catalogo[0], "municipio", dimensoes);
  const pontosAtivos =
    modo !== "coropletico" && indicadorPontos !== undefined && dimensoesPontos.consultavel;
  const porMunicipio = useQuery({
    ...indicadorQueryOptions(indicadorPontos ?? catalogo[0], {
      nivel: "municipio",
      dimensoes,
      ...institucionais,
      ...territorio,
    }),
    enabled: pontosAtivos,
  });

  const dadosCoropletico = modo === "coropletico" ? coropletico.data : undefined;
  const dadosPontos = pontosAtivos ? porMunicipio.data : undefined;

  const estados = useMemo(
    () => (dadosCoropletico ? estadosDoCoropletico(dadosCoropletico) : undefined),
    [dadosCoropletico],
  );
  const linhasCoropletico = useMemo(
    () => new Map((dadosCoropletico?.linhas ?? []).map((l) => [l.codigo, l])),
    [dadosCoropletico],
  );
  const pontos = useMemo(
    () => (dadosPontos ? pontosDoIndicador(dadosPontos.linhas) : undefined),
    [dadosPontos],
  );
  const linhasPontos = useMemo(
    () => new Map((dadosPontos?.linhas ?? []).map((l) => [l.codigo, l])),
    [dadosPontos],
  );

  const siglaDoCodigo = useMemo(
    () =>
      new Map(
        (tabelaUfs.data?.linhas ?? []).flatMap((l) => (l.uf ? [[l.codigo, l.uf] as const] : [])),
      ),
    [tabelaUfs.data],
  );
  const rotulos = useMemo(
    () => (malhaUfs.data ? rotulosDasUfs(malhaUfs.data, siglaDoCodigo) : SEM_ROTULOS),
    [malhaUfs.data, siglaDoCodigo],
  );

  const malhaMunicipal = malhaMunicipios.data;
  const camada = useMemo<CamadaDoMapa>(() => {
    if (modo === "coropletico") {
      if (!dadosCoropletico || !estados) return SEM_CAMADA;
      // A unidade pintada é a da RESPOSTA, não a da URL: nunca se pinta um nível com dado de outro.
      if (dadosCoropletico.nivel === "municipio" && !malhaMunicipal) return SEM_CAMADA;
      return {
        modo: "coropletico",
        unidade: dadosCoropletico.nivel,
        malhaMunicipios: malhaMunicipal,
        estados,
      };
    }
    if (!dadosPontos || !pontos) return SEM_CAMADA;
    return modo === "pontos"
      ? { modo: "pontos", pontos: pontos.colecao, maximo: pontos.maximo, total: dadosPontos.total }
      : { modo: "calor", pontos: pontos.colecao };
  }, [modo, dadosCoropletico, estados, malhaMunicipal, dadosPontos, pontos]);

  // Enquadramento do território da URL. `precisao` só cresce quando a caixa do MESMO território
  // melhora (tabela de UFs chegou; coordenada ou polígono do município chegou).
  const municipioSelecionado = escopo.nivel === "municipio" ? escopo.municipio : undefined;
  const pontoDoMunicipio = municipioSelecionado
    ? linhasPontos.get(municipioSelecionado)
    : undefined;
  const enquadramento = useMemo<Enquadramento | null>(() => {
    if (!malhaUfs.data) return null;
    const chave = chaveDoTerritorio(escopo);
    const brasil = limitesDaMalha(malhaUfs.data);
    if (!brasil) return null;
    if (escopo.nivel === "brasil") return { chave, limites: brasil, precisao: 1 };

    if (escopo.nivel === "municipio") {
      const feicao = malhaMunicipal?.features.find(
        (f) => f.properties.codarea === escopo.municipio,
      );
      if (feicao)
        return { chave, limites: ampliarLimites(limitesDaGeometria(feicao.geometry)), precisao: 3 };
      if (
        typeof pontoDoMunicipio?.longitude === "number" &&
        typeof pontoDoMunicipio.latitude === "number"
      ) {
        return {
          chave,
          limites: limitesDoPonto(pontoDoMunicipio.longitude, pontoDoMunicipio.latitude),
          precisao: 2,
        };
      }
    }
    const siglas = new Set(
      escopo.nivel === "regiao"
        ? metadados.ufs.filter((u) => u.regiao === escopo.regiao).map((u) => u.sigla)
        : [escopo.uf],
    );
    const codigos = new Set(
      [...siglaDoCodigo].filter(([, sigla]) => siglas.has(sigla)).map(([codigo]) => codigo),
    );
    const limites = codigos.size > 0 ? limitesDaMalha(malhaUfs.data, codigos) : null;
    return limites ? { chave, limites, precisao: 1 } : { chave, limites: brasil, precisao: 0 };
  }, [malhaUfs.data, malhaMunicipal, escopo, metadados.ufs, siglaDoCodigo, pontoDoMunicipio]);

  const semRegistro = dadosCoropletico
    ? rotuloSemRegistro(dadosCoropletico.filtros)
    : "Sem registro de oferta";

  // Mesmas casas decimais da legenda, para a dica e o painel não arredondarem classes distintas
  // para o mesmo número.
  const casas = dadosCoropletico ? casasDasClasses(dadosCoropletico.classes) : 1;

  /** Texto da dica de uma unidade; `null` quando ela está fora do recorte dos filtros. */
  const descrever = (alvo: AlvoDoMapa): string[] | null => {
    if (alvo.tipo === "cluster") {
      return [
        `${formatarInteiro(alvo.municipios)} municípios de sede agrupados`,
        `${formatarInteiro(alvo.ies)} instituições com sede neles, somadas`,
        "Clique para aproximar",
      ];
    }
    if (modo === "coropletico") {
      const linha = linhasCoropletico.get(alvo.codigo);
      if (!linha || !dadosCoropletico) return null;
      return [
        alvo.tipo === "uf" ? `${linha.nome} (${linha.uf})` : `${linha.nome} – ${linha.uf}`,
        linha.valor === null
          ? semRegistro
          : `${formatarDecimal(linha.valor, casas)} ${dadosCoropletico.indicador.unidade}`,
        `${dadosCoropletico.numerador_nome}: ${linha.numerador === null ? "sem registro" : formatarInteiro(linha.numerador)}`,
        `${dadosCoropletico.denominador_nome}: ${formatarInteiro(linha.denominador)}`,
      ];
    }
    const linha = linhasPontos.get(alvo.codigo);
    if (!linha || !dadosPontos) return null;
    return [
      `${linha.nome}${linha.uf ? ` – ${linha.uf}` : ""}`,
      modo === "pontos"
        ? `${formatarInteiro(linha.valor)} ${dadosPontos.indicador.unidade} com sede no município`
        : `${formatarInteiro(linha.valor)} ${dadosPontos.indicador.unidade}`,
    ];
  };

  /** Mapa → filtros: a unidade escolhida vira o território dos filtros globais (URL). */
  const selecionar = (alvo: Exclude<AlvoDoMapa, { tipo: "cluster" }>) => {
    const linha =
      modo === "coropletico" ? linhasCoropletico.get(alvo.codigo) : linhasPontos.get(alvo.codigo);
    const uf = metadados.ufs.find((u) => u.sigla === linha?.uf);
    if (!uf) return;
    onChange({
      regiao: uf.regiao,
      uf: uf.sigla,
      municipio: alvo.tipo === "municipio" ? Number(alvo.codigo) : undefined,
    });
  };

  const botaoDeSelecao = (alvo: Exclude<AlvoDoMapa, { tipo: "cluster" }>, nome: string) => (
    <button
      type="button"
      onClick={() => selecionar(alvo)}
      title="Selecionar nos filtros"
      className="rounded text-left font-medium text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
    >
      {nome}
    </button>
  );

  const titulo =
    modo === "coropletico"
      ? `Coroplético por ${unidade === "uf" ? "UF" : "município"} — ${nomeTerritorio}`
      : modo === "pontos"
        ? `Municípios de sede de IES — ${nomeTerritorio}`
        : `Mapa de calor${indicadorCalor ? `: ${indicadorCalor.nome}` : ""} — ${nomeTerritorio}`;
  const descricaoDoMapa =
    modo === "coropletico"
      ? `Mapa coroplético de ${dadosCoropletico?.indicador.nome ?? "matrículas por habitante"} por ${unidade === "uf" ? "UF" : "município"}, em ${nomeTerritorio}. As faixas estão na legenda e os valores, na tabela.`
      : modo === "pontos"
        ? `Mapa de pontos: municípios de sede de instituições de ensino superior em ${nomeTerritorio}, com o número de IES de cada um. Os valores estão na tabela.`
        : `Mapa de calor de ${indicadorCalor?.nome ?? "indicador"} por município em ${nomeTerritorio}. Mostra concentração relativa; os valores exatos estão na tabela.`;

  const excluidas = modo === "coropletico" ? dimensoesCoropletico.excluidas : [];
  const excluidasPontos =
    modo !== "coropletico" && dimensoesPontos.aplicavel ? dimensoesPontos.excluidas : [];

  let legenda: ReactNode;
  let abaixo: ReactNode = null;

  if (modo === "coropletico") {
    if (!dimensoesCoropletico.consultavel) {
      legenda = (
        <EmptyState>
          Nenhuma das dimensões de oferta selecionadas tem território: o indicador por habitante só
          existe em {comTerritorio.map(rotuloDimensao).join("; ")}.
        </EmptyState>
      );
    } else {
      legenda = (
        <DataState
          query={coropletico}
          loadingLabel="Carregando o coroplético…"
          loading={<Skeleton className="h-80 w-full" />}
          isEmpty={(dados) => dados.linhas.length === 0}
          empty={`Nenhuma unidade territorial em ${nomeTerritorio}.`}
        >
          {(dados) => <LegendaCoropletico dados={dados} territorio={nomeTerritorio} />}
        </DataState>
      );
      if (dadosCoropletico && dadosCoropletico.linhas.length > 0) {
        const linha = municipioSelecionado
          ? linhasCoropletico.get(municipioSelecionado)
          : undefined;
        abaixo = (
          <>
            {escopo.nivel === "municipio" && (
              <MunicipioSelecionado nome={escopo.nome}>
                {dadosCoropletico.nivel !== "municipio" ? (
                  <p>
                    O mapa está pintado por UF. Escolha a unidade “Município” para ver o valor deste
                    município.
                  </p>
                ) : !linha ? (
                  <p>Este município não está entre as unidades territoriais da resposta.</p>
                ) : (
                  <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
                    <Numero rotulo={dadosCoropletico.indicador.nome}>
                      {linha.valor === null
                        ? semRegistro
                        : `${formatarDecimal(linha.valor, casas)} ${dadosCoropletico.indicador.unidade}`}
                    </Numero>
                    <Numero rotulo={dadosCoropletico.numerador_nome}>
                      {linha.numerador === null
                        ? "sem registro (ausência, não zero)"
                        : formatarInteiro(linha.numerador)}
                    </Numero>
                    <Numero rotulo={dadosCoropletico.denominador_nome}>
                      {formatarInteiro(linha.denominador)}
                    </Numero>
                  </dl>
                )}
              </MunicipioSelecionado>
            )}
            <TabelaDoCoropletico
              // Outra resposta = outra tabela: volta à primeira página e à ordem inicial.
              key={coropletico.dataUpdatedAt}
              dados={dadosCoropletico}
              territorio={nomeTerritorio}
              semRegistro={semRegistro}
              botao={botaoDeSelecao}
            />
          </>
        );
      }
    }
  } else if (!indicadorPontos) {
    legenda = <EmptyState>O indicador deste modo não está no catálogo da API.</EmptyState>;
  } else if (!dimensoesPontos.consultavel) {
    legenda = (
      <EmptyState>
        Nenhuma das dimensões de oferta selecionadas pode ser distribuída por município para{" "}
        {indicadorPontos.codigo}. Dimensões admitidas:{" "}
        {indicadorPontos.dimensoes_territoriais.map(rotuloDimensao).join("; ")}.
      </EmptyState>
    );
  } else {
    legenda = (
      <DataState
        query={porMunicipio}
        loadingLabel={`Carregando ${indicadorPontos.nome} por município…`}
        loading={<Skeleton className="h-80 w-full" />}
        isEmpty={(dados) => dados.linhas.length === 0}
        empty={`Nenhum município com registro em ${nomeTerritorio} para os filtros selecionados.`}
      >
        {(dados) =>
          modo === "pontos" ? (
            <LegendaPontos dados={dados} maximo={pontos?.maximo ?? 0} />
          ) : (
            <LegendaCalor
              dados={dados}
              maior={dados.linhas.find((l) => l.valor === pontos?.maximo && pontos.maximo > 0)}
            />
          )
        }
      </DataState>
    );
    if (dadosPontos && dadosPontos.linhas.length > 0) {
      abaixo = (
        <>
          {escopo.nivel === "municipio" && (
            <MunicipioSelecionado nome={escopo.nome}>
              {pontoDoMunicipio ? (
                <p>
                  <span className="text-sm font-semibold tabular-nums text-foreground">
                    {formatarInteiro(pontoDoMunicipio.valor)}
                  </span>{" "}
                  {dadosPontos.indicador.unidade}
                  {modo === "pontos" ? " com sede neste município" : ""} ·{" "}
                  {dadosPontos.indicador.codigo} · Recorte: {rotuloRecorte(dadosPontos.recorte)}
                </p>
              ) : (
                <p>
                  {modo === "pontos"
                    ? "Nenhuma instituição tem sede neste município para os filtros selecionados; por isso ele não aparece como ponto. Pode haver oferta de cursos de instituições sediadas em outro lugar."
                    : "Sem registro deste indicador neste município para os filtros selecionados (ausência de registro, não zero)."}
                </p>
              )}
              {modo === "pontos" && (
                <IesDoMunicipio
                  uf={escopo.uf}
                  municipio={escopo.municipio}
                  dimensoes={dimensoes}
                  dimensaoNaUrl={search.dimensao}
                  {...institucionais}
                />
              )}
            </MunicipioSelecionado>
          )}
          {dadosPontos.truncado && (
            <p role="note" className="text-xs text-demo-foreground">
              A API devolveu só os {formatarInteiro(dadosPontos.linhas.length)} municípios de maior
              valor entre {formatarInteiro(dadosPontos.unidades)}; o mapa e a tabela estão
              incompletos.
            </p>
          )}
          {pontos && pontos.semCoordenada > 0 && (
            <p role="note" className="text-xs text-demo-foreground">
              {formatarInteiro(pontos.semCoordenada)} municípios vieram sem coordenada e não foram
              desenhados; continuam na tabela.
            </p>
          )}
          <TabelaDePontos
            key={porMunicipio.dataUpdatedAt}
            dados={dadosPontos}
            territorio={nomeTerritorio}
            deSede={modo === "pontos"}
            botao={botaoDeSelecao}
          />
        </>
      );
    }
  }

  return (
    <ChartCard
      title={titulo}
      description={
        modo === "coropletico" ? (
          dadosCoropletico ? (
            <>
              {dadosCoropletico.indicador.codigo} · {dadosCoropletico.indicador.nome} · Recorte
              territorial: <strong>{rotuloRecorte(dadosCoropletico.recorte)}</strong> · Censo{" "}
              {dadosCoropletico.ano_censo}
            </>
          ) : undefined
        ) : indicadorPontos ? (
          <>
            {indicadorPontos.codigo} · Recorte territorial:{" "}
            <strong>{rotuloRecorte(indicadorPontos.recorte)}</strong> · Censo {metadados.ano_censo}
          </>
        ) : undefined
      }
      actions={
        <>
          <SegmentedRadio<ModoMapa>
            legenda="Modo do mapa"
            opcoes={MODOS_MAPA.map((valor) => ({ valor, rotulo: ROTULO_MODO[valor] }))}
            valor={modo}
            onChange={(valor) => onChange({ modo: valor === MODO_PADRAO ? undefined : valor })}
          />
          {modo === "coropletico" && (
            <SegmentedRadio<NivelMalha>
              legenda="Unidade"
              opcoes={OPCOES_UNIDADE}
              valor={unidade}
              // Fica sempre explícita na URL: a unidade muda a escala de cores.
              onChange={(valor) => onChange({ unidade: valor })}
            />
          )}
          {modo === "calor" && indicadorCalor && (
            <div className="min-w-0">
              <label
                htmlFor={seletorId}
                className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground"
              >
                Métrica
              </label>
              <select
                id={seletorId}
                value={indicadorCalor.slug}
                onChange={(event) =>
                  onChange({
                    metrica:
                      event.target.value === METRICA_CALOR_PADRAO ? undefined : event.target.value,
                  })
                }
                className="h-9 max-w-full rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground"
              >
                {metricas.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.nome} ({rotuloRecorte(item.recorte).toLowerCase()})
                  </option>
                ))}
              </select>
            </div>
          )}
          {escopo.nivel === "municipio" && (
            <button
              type="button"
              className={BOTAO}
              onClick={() => onChange({ municipio: undefined })}
            >
              Limpar seleção do município
            </button>
          )}
          {escopo.nivel !== "brasil" && (
            <button
              type="button"
              className={BOTAO}
              onClick={() => onChange({ regiao: undefined, uf: undefined, municipio: undefined })}
            >
              Ver Brasil
            </button>
          )}
        </>
      }
    >
      {escopo.nivel === "municipio" && (
        <p role="note" className="mb-4 text-xs leading-5 text-muted-foreground">
          Com um município selecionado, o mapa continua mostrando {nomeTerritorio} inteiro, para
          haver com o que comparar; {escopo.nome} aparece destacado e enquadrado.
        </p>
      )}
      {[...excluidas, ...excluidasPontos].length > 0 && (
        <div
          role="note"
          className="mb-4 rounded-md bg-demo px-3 py-2.5 text-xs leading-5 text-demo-foreground"
        >
          <p className="font-semibold">
            Dimensões selecionadas que não entram neste mapa — não têm município identificado:
          </p>
          <ul className="mt-1 list-disc pl-4">
            {[...excluidas, ...excluidasPontos].map((slug) => (
              <li key={slug}>{rotuloDimensao(slug)}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0">
          <DataState
            query={malhaUfs}
            loadingLabel="Carregando a malha territorial…"
            loading={<Skeleton className="h-[60vh] min-h-[320px] w-full" />}
            isEmpty={(malha) => malha.features.length === 0}
            empty="A malha territorial veio vazia da API."
          >
            {(malha) =>
              enquadramento && (
                <MapaTerritorial
                  descricao={descricaoDoMapa}
                  malhaUfs={malha}
                  rotulosUf={rotulos}
                  camada={camada}
                  municipioSelecionado={municipioSelecionado}
                  enquadramento={enquadramento}
                  descrever={descrever}
                  onSelecionar={selecionar}
                />
              )
            }
          </DataState>
          {modo === "coropletico" && unidade === "municipio" && malhaMunicipios.isError && (
            <ErrorState
              compact
              className="mt-3"
              error={malhaMunicipios.error}
              onRetry={() => void malhaMunicipios.refetch()}
            />
          )}
          {modo === "coropletico" &&
            unidade === "municipio" &&
            malhaMunicipios.isPending &&
            dimensoesCoropletico.consultavel && (
              <p role="status" className="mt-3 text-xs text-muted-foreground">
                Carregando a malha dos municípios (cerca de 1 MB, uma única vez)…
              </p>
            )}
        </div>
        <aside aria-label="Legenda do mapa" className="min-w-0">
          {legenda}
        </aside>
      </div>

      {abaixo && <div className="mt-6 space-y-6">{abaixo}</div>}
    </ChartCard>
  );
}

type Botao = (alvo: Exclude<AlvoDoMapa, { tipo: "cluster" }>, nome: string) => ReactNode;

/** As unidades do coroplético em texto: valor, numerador, denominador e a faixa da legenda. */
function TabelaDoCoropletico({
  dados,
  territorio,
  semRegistro,
  botao,
}: {
  dados: RespostaCoropletico;
  territorio: string;
  semRegistro: string;
  botao: Botao;
}) {
  const porUf = dados.nivel === "uf";
  const casas = casasDasClasses(dados.classes);
  const classeDoIndice = new Map(dados.classes.map((c) => [c.indice, c]));
  const faixa = (linha: LinhaCoropletico) => {
    const classe = linha.classe === null ? undefined : classeDoIndice.get(linha.classe);
    return classe ? faixaDaClasse(classe, (v) => formatarDecimal(v, casas)) : "fora das classes";
  };

  const colunas: Array<DataTableColumn<LinhaCoropletico>> = [
    {
      id: "nome",
      header: porUf ? "Unidade da Federação" : "Município",
      cell: (l) => botao({ tipo: dados.nivel, codigo: l.codigo }, l.nome),
      rowHeader: true,
    },
    { id: "uf", header: "UF", cell: (l) => l.uf },
    {
      id: "valor",
      header: `Valor (${dados.indicador.unidade})`,
      cell: (l) => (l.valor === null ? semRegistro.toLowerCase() : formatarDecimal(l.valor, casas)),
      align: "right",
    },
    {
      id: "numerador",
      header: dados.numerador_nome,
      cell: (l) => (l.numerador === null ? "—" : formatarInteiro(l.numerador)),
      align: "right",
    },
    {
      id: "denominador",
      header: dados.denominador_nome,
      cell: (l) => formatarInteiro(l.denominador),
      align: "right",
    },
    { id: "faixa", header: "Faixa na legenda", cell: faixa, align: "right" },
  ];

  // Sem registro vai sempre para o fim: não é o menor valor, é ausência de valor.
  const porValor = (sentido: 1 | -1) => (a: LinhaCoropletico, b: LinhaCoropletico) => {
    if (a.valor === null || b.valor === null) {
      return a.valor === b.valor ? colador.compare(a.nome, b.nome) : a.valor === null ? 1 : -1;
    }
    return sentido * (a.valor - b.valor);
  };
  const ordenacoes: readonly [Ordenacao<LinhaCoropletico>, ...Array<Ordenacao<LinhaCoropletico>>] =
    [
      { id: "maior", rotulo: "Valor (maior primeiro)", comparar: porValor(-1) },
      { id: "menor", rotulo: "Valor (menor primeiro)", comparar: porValor(1) },
      { id: "nome", rotulo: "Nome (A–Z)", comparar: (a, b) => colador.compare(a.nome, b.nome) },
      {
        id: "populacao",
        rotulo: "População (maior primeiro)",
        comparar: (a, b) => b.denominador - a.denominador,
      },
    ];

  return (
    <TabelaPaginada
      caption={`${dados.indicador.nome} por ${porUf ? "UF" : "município"} — ${territorio}. Censo da Educação Superior ${dados.ano_censo} e população estimada de ${dados.ano_populacao}. Recorte: ${rotuloRecorte(dados.recorte)}.`}
      columns={colunas}
      rows={dados.linhas}
      rowKey={(l) => l.codigo}
      ordenacoes={ordenacoes}
      unidades={porUf ? "UFs" : "Unidades"}
    />
  );
}

/** Os municípios do modo de pontos ou de calor, com o valor de cada um. */
function TabelaDePontos({
  dados,
  territorio,
  deSede,
  botao,
}: {
  dados: RespostaIndicador;
  territorio: string;
  deSede: boolean;
  botao: Botao;
}) {
  const colunas: Array<DataTableColumn<Linha>> = [
    {
      id: "nome",
      header: deSede ? "Município de sede" : "Município",
      cell: (l) => botao({ tipo: "municipio", codigo: l.codigo }, l.nome),
      rowHeader: true,
    },
    { id: "uf", header: "UF", cell: (l) => l.uf ?? "—" },
    {
      id: "valor",
      header: `Valor (${dados.indicador.unidade})`,
      cell: (l) => formatarInteiro(l.valor),
      align: "right",
    },
  ];
  const ordenacoes: readonly [Ordenacao<Linha>, ...Array<Ordenacao<Linha>>] = [
    { id: "maior", rotulo: "Valor (maior primeiro)", comparar: (a, b) => b.valor - a.valor },
    { id: "nome", rotulo: "Nome (A–Z)", comparar: (a, b) => colador.compare(a.nome, b.nome) },
  ];
  return (
    <TabelaPaginada
      caption={`${dados.indicador.nome} por município${deSede ? " de sede" : ""} — ${territorio}. Censo da Educação Superior ${dados.ano_censo}. Recorte: ${rotuloRecorte(dados.recorte)}.`}
      columns={colunas}
      rows={dados.linhas}
      rowKey={(l) => l.codigo}
      ordenacoes={ordenacoes}
      unidades={deSede ? "Municípios de sede" : "Municípios"}
    />
  );
}
