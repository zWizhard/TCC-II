import { useQuery } from "@tanstack/react-query";

import { ROTULO_AGRUPAMENTO } from "@/components/analise/search";
import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState } from "@/components/data/DataState";
import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { Notes } from "@/components/data/Notes";
import { RankingBarChart } from "@/components/data/RankingBarChart";
import { filtroDoEscopo, type Escopo } from "@/components/filters/search";
import { Skeleton } from "@/components/ui/skeleton";
import { resolverDimensoesRazao } from "@/lib/api/dimensoes";
import { razaoQueryOptions } from "@/lib/api/queries";
import type {
  Agrupamento,
  BaseFluxo,
  Categoria,
  Dimensao,
  LinhaRazao,
  Nivel,
  Organizacao,
  RazaoInfo,
  Rede,
  RespostaRazao,
} from "@/lib/api/schemas";
import { formatarInteiro, formatarPercentual, formatarRazao, rotuloRecorte } from "@/lib/format";

/** Municípios exibidos na comparação municipal; o valor do território considera todos. */
const LIMITE_MUNICIPIOS = 20;
const ROTULO_MAXIMO_NO_GRAFICO = 22;

const TERRITORIAIS: readonly Agrupamento[] = ["regiao", "uf", "municipio"];

/**
 * Por que uma comparação não se aplica a esta razão neste território — ou `undefined` se ela é
 * válida. Espelha as recusas de `api/fluxo.py`, para explicar em vez de receber o 422.
 */
function motivoSemComparacao(
  razao: RazaoInfo,
  por: Agrupamento,
  escopo: Escopo,
  dimensaoFixa: Dimensao | undefined,
): string | undefined {
  const rotulo = ROTULO_AGRUPAMENTO[por].toLowerCase();
  if (
    TERRITORIAIS.includes(por) &&
    dimensaoFixa !== undefined &&
    !razao.dimensoes_territoriais.includes(dimensaoFixa)
  ) {
    return "Esta dimensão de oferta não tem município, UF nem região na base: não há comparação por território.";
  }
  if (por === "regiao" && escopo.nivel !== "brasil") {
    return `A comparação por região só existe com o Brasil inteiro selecionado; o território atual é ${escopo.nome}.`;
  }
  if (por === "uf" && escopo.nivel !== "brasil" && escopo.nivel !== "regiao") {
    return `A comparação por UF só existe para o Brasil ou uma região; o território atual é ${escopo.nome}.`;
  }
  if (por === "municipio" && escopo.nivel !== "uf") {
    return "A comparação por município exige uma UF selecionada no filtro de território.";
  }
  if (por === "municipio" && !razao.municipal) {
    return `${razao.codigo} não é exibido por município: bloqueio provisório, enquanto o piso de supressão para células pequenas não é definido na metodologia.`;
  }
  if (por === "dimensao" && razao.dimensao_unica) {
    return `${razao.codigo} é calculado em uma única dimensão de oferta: não há comparação por ${rotulo}.`;
  }
  if (por === "area" && escopo.nivel === "municipio") {
    return "Recortes pela classificação CINE não são exibidos para um único município (piso de supressão pendente, IND-R-06).";
  }
  return undefined;
}

type RazaoCardProps = {
  titulo: string;
  razao: RazaoInfo;
  /** Só nas razões com `usa_base`. */
  base?: BaseFluxo | undefined;
  por: Agrupamento;
  escopo: Escopo;
  dimensoes: readonly Dimensao[];
  /** Restringe a consulta a esta dimensão (razões que não somam dimensões diferentes). */
  dimensaoFixa?: Dimensao | undefined;
  rede: Rede | undefined;
  categoria: Categoria | undefined;
  organizacao: Organizacao | undefined;
  rotuloDimensao: (slug: Dimensao) => string;
};

/**
 * Uma razão do Bloco B no território selecionado: o valor, o numerador e o denominador que o
 * formam, e a comparação por um agrupamento. A divisão vem feita pela API.
 */
export function RazaoCard({
  titulo,
  razao,
  base,
  por,
  escopo,
  dimensoes,
  dimensaoFixa,
  rede,
  categoria,
  organizacao,
  rotuloDimensao,
}: RazaoCardProps) {
  const semComparacao = motivoSemComparacao(razao, por, escopo, dimensaoFixa);
  const porEfetivo = semComparacao === undefined ? por : undefined;
  const territorio = filtroDoEscopo(escopo);
  const nivel: Nivel =
    porEfetivo && TERRITORIAIS.includes(porEfetivo) ? (porEfetivo as Nivel) : territorio.nivel;
  const resolucao = resolverDimensoesRazao(razao, nivel, dimensoes, dimensaoFixa);
  const bloqueioMunicipal = escopo.nivel === "municipio" && !razao.municipal;

  const query = useQuery({
    ...razaoQueryOptions(razao, {
      regiao: territorio.regiao,
      uf: territorio.uf,
      municipio: territorio.municipio,
      dimensoes: resolucao.efetivas,
      base,
      por: porEfetivo,
      rede,
      categoria,
      organizacao,
      limite: porEfetivo === "municipio" ? LIMITE_MUNICIPIOS : undefined,
    }),
    ...(bloqueioMunicipal ? { enabled: false } : {}),
  });

  return (
    <ChartCard
      title={titulo}
      description={
        <>
          {razao.codigo} · {escopo.nome} · Recorte territorial:{" "}
          <strong>{rotuloRecorte(razao.recorte)}</strong>
        </>
      }
    >
      {bloqueioMunicipal ? (
        <EmptyState>
          {razao.codigo} não é exibido para um único município: é um bloqueio provisório, enquanto o
          piso de supressão para células pequenas não é definido na metodologia.
        </EmptyState>
      ) : !resolucao.consultavel ? (
        <EmptyState>
          {dimensoes.length === 0
            ? "Selecione ao menos uma dimensão de oferta para consultar este indicador."
            : `Este cartão de ${razao.codigo} depende da dimensão de oferta ${(dimensaoFixa
                ? [dimensaoFixa]
                : razao.dimensoes
              )
                .map((slug) => `"${rotuloDimensao(slug)}"`)
                .join(" ou ")}, que não está selecionada${
                nivel === "brasil" ? "" : " ou não existe por território"
              }.`}
        </EmptyState>
      ) : (
        <>
          {resolucao.excluidas.length > 0 && (
            <div
              role="note"
              className="mb-4 rounded-md bg-demo px-3 py-2.5 text-xs leading-5 text-demo-foreground"
            >
              <p className="font-semibold">
                Dimensões selecionadas que não entram neste cálculo — {razao.codigo} não existe
                nelas{nivel === "brasil" ? "" : " por território"}:
              </p>
              <ul className="mt-1 list-disc pl-4">
                {resolucao.excluidas.map((slug) => (
                  <li key={slug}>{rotuloDimensao(slug)}</li>
                ))}
              </ul>
            </div>
          )}
          <DataState
            query={query}
            loadingLabel={`Carregando ${titulo}…`}
            loading={<Skeleton className="h-56 w-full" />}
          >
            {(dados) => (
              <Resultado
                dados={dados}
                titulo={titulo}
                por={por}
                semComparacao={semComparacao}
                escopo={escopo}
              />
            )}
          </DataState>
        </>
      )}

      {razao.limitacoes.length > 0 && (
        <details className="mt-4 text-xs leading-5 text-muted-foreground">
          <summary className="cursor-pointer rounded font-semibold text-foreground">
            Como ler este indicador ({razao.limitacoes.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {razao.limitacoes.map((limitacao) => (
              <li key={limitacao}>{limitacao}</li>
            ))}
          </ul>
        </details>
      )}
    </ChartCard>
  );
}

function abreviar(texto: string): string {
  return texto.length <= ROTULO_MAXIMO_NO_GRAFICO
    ? texto
    : `${texto.slice(0, ROTULO_MAXIMO_NO_GRAFICO - 1).trimEnd()}…`;
}

function Resultado({
  dados,
  titulo,
  por,
  semComparacao,
  escopo,
}: {
  dados: RespostaRazao;
  titulo: string;
  por: Agrupamento;
  semComparacao: string | undefined;
  escopo: Escopo;
}) {
  const { indicador, filtros, geral } = dados;
  const formatar = indicador.percentual ? formatarPercentual : formatarRazao;
  const cabecalhoValor = indicador.percentual ? "Participação" : `Razão (${indicador.unidade})`;
  const comValor = dados.linhas.filter((linha) => linha.valor !== null);

  const colunas: Array<DataTableColumn<LinhaRazao>> = [
    {
      id: "nome",
      header: ROTULO_AGRUPAMENTO[por],
      cell: (linha) => linha.nome,
      sortValue: (linha) => linha.nome,
      rowHeader: true,
    },
    {
      id: "numerador",
      header: dados.numerador_nome,
      cell: (linha) => formatarInteiro(linha.numerador),
      sortValue: (linha) => linha.numerador,
      align: "right",
    },
    {
      id: "denominador",
      header: dados.denominador_nome,
      cell: (linha) => formatarInteiro(linha.denominador),
      sortValue: (linha) => linha.denominador,
      align: "right",
    },
    {
      id: "valor",
      header: cabecalhoValor,
      cell: (linha) => (linha.valor === null ? "não se aplica" : formatar(linha.valor)),
      sortValue: (linha) => linha.valor ?? -1,
      align: "right",
    },
  ];

  const recortes = [
    `Rede: ${filtros.rede ?? "Todas"}`,
    ...(filtros.categoria ? [filtros.categoria] : []),
    ...(filtros.organizacao ? [filtros.organizacao] : []),
  ];

  return (
    <>
      {geral.valor === null ? (
        <EmptyState>
          Sem {dados.denominador_nome.toLowerCase()} em {escopo.nome} para os filtros selecionados:
          a razão não se aplica (não é zero).
        </EmptyState>
      ) : (
        <p className="font-display text-3xl font-semibold leading-none tabular-nums text-foreground">
          {formatar(geral.valor)}
          {!indicador.percentual && (
            <span className="ml-2 font-sans text-xs font-normal text-muted-foreground">
              {indicador.unidade}
            </span>
          )}
        </p>
      )}
      <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs leading-5 text-muted-foreground sm:grid-cols-2">
        <div className="flex flex-wrap gap-x-1">
          <dt className="font-semibold">{dados.numerador_nome}:</dt>
          <dd className="tabular-nums text-foreground">{formatarInteiro(geral.numerador)}</dd>
        </div>
        <div className="flex flex-wrap gap-x-1">
          <dt className="font-semibold">{dados.denominador_nome}:</dt>
          <dd className="tabular-nums text-foreground">{formatarInteiro(geral.denominador)}</dd>
        </div>
      </dl>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">{recortes.join(" · ")}</p>
      <details className="mt-1 text-xs leading-5 text-muted-foreground">
        <summary className="cursor-pointer rounded font-semibold text-foreground">
          Dimensões de oferta incluídas ({filtros.dimensoes.length})
        </summary>
        <ul className="mt-1 list-disc pl-4">
          {filtros.dimensoes.map((rotulo) => (
            <li key={rotulo}>{rotulo}</li>
          ))}
        </ul>
      </details>
      <Notes notas={dados.notas} className="mt-3" />

      {semComparacao !== undefined ? (
        <EmptyState className="mt-5">{semComparacao}</EmptyState>
      ) : dados.linhas.length === 0 ? (
        <EmptyState className="mt-5">
          Nenhum registro em {escopo.nome} para os filtros selecionados.
        </EmptyState>
      ) : (
        <>
          {dados.truncado && (
            <p role="note" className="mt-4 text-xs text-demo-foreground">
              Exibindo os {formatarInteiro(dados.linhas.length)} grupos de maior denominador entre{" "}
              {formatarInteiro(dados.unidades)}; o valor de {escopo.nome} considera todos.
            </p>
          )}
          <div className="mt-5 grid gap-6 xl:grid-cols-2">
            <div className="min-w-0">
              <RankingBarChart
                itens={comValor.map((linha) => ({
                  chave: linha.codigo,
                  rotulo: abreviar(linha.nome),
                  valor: linha.valor ?? 0,
                }))}
                unidade={indicador.percentual ? "" : indicador.unidade}
                formatarValor={formatar}
                descricao={`Gráfico de barras: ${titulo} por ${ROTULO_AGRUPAMENTO[por].toLowerCase()}, em ${indicador.unidade}. Os mesmos valores estão na tabela ao lado.`}
              />
            </div>
            <div className="min-w-0">
              <DataTable
                caption={`${titulo} por ${ROTULO_AGRUPAMENTO[por].toLowerCase()} — Censo da Educação Superior ${dados.ano_censo}. Recorte: ${rotuloRecorte(dados.recorte)}.`}
                columns={colunas}
                rows={dados.linhas}
                rowKey={(linha) => linha.codigo}
              />
            </div>
          </div>
        </>
      )}
    </>
  );
}
