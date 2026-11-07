import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState } from "@/components/data/DataState";
import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { Notes } from "@/components/data/Notes";
import { RankingBarChart } from "@/components/data/RankingBarChart";
import { filtroDoEscopo, type Escopo } from "@/components/filters/search";
import { Skeleton } from "@/components/ui/skeleton";
import { resolverDimensoes } from "@/lib/api/dimensoes";
import { composicaoQueryOptions } from "@/lib/api/queries";
import { EIXOS_PERFIL } from "@/lib/api/schemas";
import type {
  AreaCine,
  Categoria,
  Dimensao,
  Eixo,
  Grau,
  IndicadorInfo,
  LinhaComposicao,
  Organizacao,
  Rede,
  RespostaComposicao,
} from "@/lib/api/schemas";
import { formatarInteiro, formatarPercentual, rotuloRecorte } from "@/lib/format";

/** Eixos da classificação CINE: a API não os serve no nível municipal. */
const EIXOS_CINE: readonly Eixo[] = ["area", "rotulo_cine"];
/** Eixos de perfil (IND-R-07): mesmo bloqueio municipal, pela mesma pendência. */
const EIXOS_DE_PERFIL: readonly Eixo[] = EIXOS_PERFIL;
/** O eixo do gráfico reserva até 150 px; o nome completo fica na tabela. */
const ROTULO_MAXIMO_NO_GRAFICO = 22;

type ComposicaoCardProps = {
  titulo: string;
  indicador: IndicadorInfo;
  eixo: Eixo;
  /** Cabeçalho da coluna das categorias (ex.: "Grau acadêmico"). */
  coluna: string;
  escopo: Escopo;
  dimensoes: readonly Dimensao[];
  rede: Rede | undefined;
  categoria: Categoria | undefined;
  organizacao: Organizacao | undefined;
  area?: AreaCine | undefined;
  grau?: Grau | undefined;
  /** Quantas categorias pedir; o total e a participação consideram todas. */
  limite?: number | undefined;
  /** Mantém a ordem devolvida pela API (ex.: titulação, que tem ordem natural). */
  ordemDaApi?: boolean;
  /** Rótulo literal de cada dimensão (metadados), para nomear o que foi excluído. */
  rotuloDimensao: (slug: Dimensao) => string;
  actions?: ReactNode;
  className?: string;
};

/**
 * Um indicador direto decomposto por um eixo categórico, no território selecionado:
 * barras + tabela com valor e participação. A participação vem calculada pela API.
 */
export function ComposicaoCard({
  titulo,
  indicador,
  eixo,
  coluna,
  escopo,
  dimensoes,
  rede,
  categoria,
  organizacao,
  area,
  grau,
  limite,
  ordemDaApi = false,
  rotuloDimensao,
  actions,
  className,
}: ComposicaoCardProps) {
  const territorio = filtroDoEscopo(escopo);
  const resolucao = resolverDimensoes(indicador, territorio.nivel, dimensoes);
  const perfilNoMunicipio = escopo.nivel === "municipio" && EIXOS_DE_PERFIL.includes(eixo);
  const cineNoMunicipio =
    perfilNoMunicipio ||
    (escopo.nivel === "municipio" && (EIXOS_CINE.includes(eixo) || area !== undefined));
  const query = useQuery({
    ...composicaoQueryOptions(indicador, {
      ...territorio,
      eixo,
      dimensoes,
      rede,
      categoria,
      organizacao,
      area,
      grau,
      limite,
    }),
    ...(cineNoMunicipio ? { enabled: false } : {}),
  });

  return (
    <ChartCard
      title={titulo}
      description={
        <>
          {indicador.codigo} · {escopo.nome} · Recorte territorial:{" "}
          <strong>{rotuloRecorte(indicador.recorte)}</strong>
        </>
      }
      actions={actions}
      {...(className ? { className } : {})}
    >
      {!cineNoMunicipio && resolucao.consultavel && resolucao.excluidas.length > 0 && (
        <div
          role="note"
          className="mb-4 rounded-md bg-demo px-3 py-2.5 text-xs leading-5 text-demo-foreground"
        >
          <p className="font-semibold">
            Dimensões selecionadas que não entram aqui — {indicador.codigo} não é territorializável
            nelas:
          </p>
          <ul className="mt-1 list-disc pl-4">
            {resolucao.excluidas.map((slug) => (
              <li key={slug}>{rotuloDimensao(slug)}</li>
            ))}
          </ul>
        </div>
      )}

      {cineNoMunicipio ? (
        <EmptyState>
          {perfilNoMunicipio
            ? "O perfil dos estudantes não é exibido"
            : "Recortes pela classificação CINE não são exibidos"}{" "}
          para um único município: é um bloqueio provisório, enquanto o piso de supressão para
          células pequenas não é definido na metodologia (
          {perfilNoMunicipio ? "IND-R-07" : "IND-R-06"}).
        </EmptyState>
      ) : !resolucao.consultavel ? (
        <EmptyState>
          {resolucao.excluidas.length > 0
            ? `${indicador.codigo} não existe por território em nenhuma das dimensões de oferta selecionadas; não há valor para ${escopo.nome}.`
            : "Selecione ao menos uma dimensão de oferta para consultar este indicador."}
        </EmptyState>
      ) : (
        <DataState
          query={query}
          loadingLabel={`Carregando ${titulo}…`}
          loading={<Skeleton className="h-56 w-full" />}
          isEmpty={(dados) => dados.linhas.length === 0}
          empty={`Nenhum registro em ${escopo.nome} para os filtros selecionados.`}
        >
          {(dados) => (
            <Resultado
              dados={dados}
              titulo={titulo}
              coluna={coluna}
              ordemDaApi={ordemDaApi}
              aplicaDimensao={resolucao.aplicavel}
            />
          )}
        </DataState>
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
  coluna,
  ordemDaApi,
  aplicaDimensao,
}: {
  dados: RespostaComposicao;
  titulo: string;
  coluna: string;
  ordemDaApi: boolean;
  aplicaDimensao: boolean;
}) {
  const { indicador, filtros } = dados;
  const temGrupo = dados.linhas.some((linha) => linha.grupo);

  const colunas: Array<DataTableColumn<LinhaComposicao>> = [
    {
      id: "nome",
      header: coluna,
      cell: (linha) => linha.nome,
      sortValue: (linha) => linha.nome,
      rowHeader: true,
    },
    ...(temGrupo
      ? [
          {
            id: "grupo",
            header: "Área geral",
            cell: (linha: LinhaComposicao) => linha.grupo ?? "—",
            sortValue: (linha: LinhaComposicao) => linha.grupo ?? "",
          },
        ]
      : []),
    {
      id: "valor",
      header: `Valor (${indicador.unidade})`,
      cell: (linha) => formatarInteiro(linha.valor),
      sortValue: (linha) => linha.valor,
      align: "right",
    },
    {
      id: "participacao",
      header: "Participação",
      cell: (linha) => formatarPercentual(linha.participacao),
      sortValue: (linha) => linha.participacao ?? -1,
      align: "right",
    },
  ];

  const recortes = [
    `Rede: ${filtros.rede ?? "Todas"}`,
    ...(filtros.categoria ? [filtros.categoria] : []),
    ...(filtros.organizacao ? [filtros.organizacao] : []),
    ...(filtros.area ? [`Área: ${filtros.area}`] : []),
    ...(filtros.grau ? [`Grau: ${filtros.grau}`] : []),
  ];

  return (
    <>
      <p className="text-xs leading-5 text-muted-foreground">
        Total:{" "}
        <strong className="tabular-nums text-foreground">{formatarInteiro(dados.total)}</strong>{" "}
        {indicador.unidade}
        {dados.ficha && <> · composição conforme {dados.ficha}</>} · {recortes.join(" · ")}
      </p>
      {aplicaDimensao && (
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
      )}
      {dados.truncado && (
        <p role="note" className="mt-2 text-xs text-demo-foreground">
          Exibindo as {formatarInteiro(dados.linhas.length)} categorias de maior valor entre{" "}
          {formatarInteiro(dados.categorias)}; o total e a participação consideram todas.
        </p>
      )}
      <Notes notas={dados.notas} className="mt-3" />

      <div className="mt-5 grid gap-6 xl:grid-cols-2">
        <div className="min-w-0">
          <RankingBarChart
            itens={dados.linhas.map((linha) => ({
              chave: linha.codigo,
              rotulo: abreviar(linha.nome),
              valor: linha.valor,
            }))}
            unidade={indicador.unidade}
            descricao={`Gráfico de barras: ${titulo}, em ${indicador.unidade}. Os mesmos valores estão na tabela ao lado.`}
          />
        </div>
        <div className="min-w-0">
          <DataTable
            caption={`${titulo} — Censo da Educação Superior ${dados.ano_censo}. Recorte: ${rotuloRecorte(dados.recorte)}.`}
            columns={colunas}
            rows={dados.linhas}
            rowKey={(linha) => linha.codigo}
            {...(ordemDaApi ? {} : { initialSort: { columnId: "valor", direction: "desc" } })}
          />
        </div>
      </div>
    </>
  );
}
