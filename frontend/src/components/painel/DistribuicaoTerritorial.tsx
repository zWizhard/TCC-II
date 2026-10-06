import { useId } from "react";
import { useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState } from "@/components/data/DataState";
import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { Notes } from "@/components/data/Notes";
import { RankingBarChart } from "@/components/data/RankingBarChart";
import { SegmentedRadio } from "@/components/filters/SegmentedRadio";
import { Skeleton } from "@/components/ui/skeleton";
import { resolverDimensoes } from "@/lib/api/dimensoes";
import { indicadorQueryOptions } from "@/lib/api/queries";
import type { Dimensao, IndicadorInfo, Linha, Rede, RespostaIndicador } from "@/lib/api/schemas";
import { formatarInteiro, rotuloRecorte } from "@/lib/format";

import { NIVEL_DISTRIBUICAO_PADRAO, type NivelDistribuicao } from "./search";

const OPCOES_NIVEL: ReadonlyArray<{ valor: NivelDistribuicao; rotulo: string }> = [
  { valor: "regiao", rotulo: "Região" },
  { valor: "uf", rotulo: "UF" },
];

const TEXTO_NIVEL: Record<NivelDistribuicao, { por: string; unidades: string }> = {
  regiao: { por: "por região", unidades: "Regiões com registro" },
  uf: { por: "por UF", unidades: "UFs com registro" },
};

type DistribuicaoTerritorialProps = {
  /** Catálogo não vazio de `/api/v1/indicadores`. */
  catalogo: readonly [IndicadorInfo, ...IndicadorInfo[]];
  /** Slug vindo da URL; ausente ou desconhecido cai no primeiro do catálogo. */
  indicadorSlug: string | undefined;
  nivel: NivelDistribuicao | undefined;
  dimensoes: readonly Dimensao[];
  rede: Rede | undefined;
  /** Rótulo literal de cada dimensão (metadados), para nomear o que foi excluído. */
  rotuloDimensao: (slug: Dimensao) => string;
  onChange: (alteracao: { indicador?: string; nivel?: NivelDistribuicao }) => void;
};

/** Um indicador distribuído por Região ou UF: gráfico de barras + tabela com os mesmos dados. */
export function DistribuicaoTerritorial({
  catalogo,
  indicadorSlug,
  nivel: nivelUrl,
  dimensoes,
  rede,
  rotuloDimensao,
  onChange,
}: DistribuicaoTerritorialProps) {
  const seletorId = useId();
  const nivel = nivelUrl ?? NIVEL_DISTRIBUICAO_PADRAO;
  const encontrado = catalogo.find((i) => i.slug === indicadorSlug);
  const indicador = encontrado ?? catalogo[0];
  const slugDesconhecido = indicadorSlug !== undefined && !encontrado;

  const resolucao = resolverDimensoes(indicador, nivel, dimensoes);
  const query = useQuery(indicadorQueryOptions(indicador, { nivel, dimensoes, rede }));

  return (
    <ChartCard
      title={`${indicador.nome} ${TEXTO_NIVEL[nivel].por}`}
      description={
        <>
          {indicador.codigo} · Recorte territorial:{" "}
          <strong>{rotuloRecorte(indicador.recorte)}</strong>
        </>
      }
      actions={
        <>
          <div className="min-w-0">
            <label
              htmlFor={seletorId}
              className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground"
            >
              Indicador
            </label>
            <select
              id={seletorId}
              value={indicador.slug}
              onChange={(event) => onChange({ indicador: event.target.value })}
              className="h-9 max-w-full rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground"
            >
              {catalogo.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.codigo} — {item.nome}
                </option>
              ))}
            </select>
          </div>
          <SegmentedRadio<NivelDistribuicao>
            legenda="Nível territorial"
            opcoes={OPCOES_NIVEL}
            valor={nivel}
            onChange={(valor) => onChange({ nivel: valor })}
          />
        </>
      }
    >
      {slugDesconhecido && (
        <p role="status" className="mb-4 text-xs text-muted-foreground">
          O indicador informado no endereço não existe no catálogo; exibindo {indicador.codigo}.
        </p>
      )}

      {resolucao.excluidas.length > 0 && (
        <div
          role="note"
          className="mb-4 rounded-md bg-demo px-3 py-2.5 text-xs leading-5 text-demo-foreground"
        >
          <p className="font-semibold">
            Dimensões selecionadas que não entram nesta distribuição — {indicador.codigo} não é
            territorializável nelas neste nível:
          </p>
          <ul className="mt-1 list-disc pl-4">
            {resolucao.excluidas.map((slug) => (
              <li key={slug}>{rotuloDimensao(slug)}</li>
            ))}
          </ul>
        </div>
      )}

      {!resolucao.consultavel ? (
        <EmptyState>
          Nenhuma das dimensões de oferta selecionadas pode ser distribuída por território para{" "}
          {indicador.codigo}. Dimensões admitidas neste nível:{" "}
          {indicador.dimensoes_territoriais.map(rotuloDimensao).join("; ")}.
        </EmptyState>
      ) : (
        <DataState
          query={query}
          loadingLabel={`Carregando ${indicador.nome} ${TEXTO_NIVEL[nivel].por}…`}
          loading={
            <div className="grid gap-6 lg:grid-cols-2">
              <Skeleton className="h-64 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          }
          isEmpty={(dados) => dados.linhas.length === 0}
          empty="Nenhuma unidade territorial com registro para os filtros selecionados."
        >
          {(dados) => (
            <Resultado dados={dados} nivel={nivel} aplicaDimensao={resolucao.aplicavel} />
          )}
        </DataState>
      )}
    </ChartCard>
  );
}

function Resultado({
  dados,
  nivel,
  aplicaDimensao,
}: {
  dados: RespostaIndicador;
  nivel: NivelDistribuicao;
  aplicaDimensao: boolean;
}) {
  const { indicador } = dados;
  const texto = TEXTO_NIVEL[nivel];

  const colunas: Array<DataTableColumn<Linha>> = [
    {
      id: "nome",
      header: nivel === "uf" ? "Unidade da Federação" : "Região",
      cell: (linha) => linha.nome,
      sortValue: (linha) => linha.nome,
      rowHeader: true,
    },
    ...(nivel === "uf"
      ? [
          {
            id: "uf",
            header: "Sigla",
            cell: (linha: Linha) => linha.uf ?? "—",
            sortValue: (linha: Linha) => linha.uf ?? "",
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
  ];

  return (
    <>
      <dl className="grid gap-px overflow-hidden rounded-md border border-border bg-border text-xs sm:grid-cols-2 lg:grid-cols-4">
        <Fato rotulo={`Total ${texto.por}`}>
          <span className="font-display text-xl font-semibold tabular-nums text-foreground">
            {formatarInteiro(dados.total)}
          </span>{" "}
          {indicador.unidade}
        </Fato>
        <Fato rotulo={texto.unidades}>
          <span className="font-display text-xl font-semibold tabular-nums text-foreground">
            {formatarInteiro(dados.unidades)}
          </span>
        </Fato>
        <Fato rotulo="Sem município identificado">
          {dados.valor_sem_territorio === null ? (
            "não informado"
          ) : (
            <>
              <span className="font-display text-xl font-semibold tabular-nums text-foreground">
                {formatarInteiro(dados.valor_sem_territorio)}
              </span>{" "}
              {indicador.unidade}, fora desta distribuição
            </>
          )}
        </Fato>
        <Fato rotulo="Rede">{dados.filtros.rede ?? "Todas"}</Fato>
      </dl>

      <div className="mt-3 text-xs leading-5 text-muted-foreground">
        <p className="font-semibold text-foreground">Dimensões de oferta incluídas</p>
        {aplicaDimensao ? (
          <ul className="list-disc pl-4">
            {dados.filtros.dimensoes.map((rotulo) => (
              <li key={rotulo}>{rotulo}</li>
            ))}
          </ul>
        ) : (
          <p>Não se aplica a este indicador.</p>
        )}
      </div>

      {dados.truncado && (
        <p role="note" className="mt-3 text-xs text-demo-foreground">
          A lista foi truncada pelo limite da consulta; o total considera todas as unidades.
        </p>
      )}
      <Notes notas={dados.notas} className="mt-3" />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <RankingBarChart
            itens={dados.linhas.map((linha) => ({
              chave: linha.codigo,
              rotulo: nivel === "uf" ? (linha.uf ?? linha.nome) : linha.nome,
              valor: linha.valor,
            }))}
            unidade={indicador.unidade}
            descricao={`Gráfico de barras: ${indicador.nome} ${texto.por}, em ${indicador.unidade}. Os mesmos valores estão na tabela ao lado.`}
          />
        </div>
        <div className="min-w-0">
          <DataTable
            caption={`${indicador.nome} ${texto.por} — Censo da Educação Superior ${dados.ano_censo}. Recorte: ${rotuloRecorte(dados.recorte)}.`}
            columns={colunas}
            rows={dados.linhas}
            rowKey={(linha) => linha.codigo}
            initialSort={{ columnId: "valor", direction: "desc" }}
          />
        </div>
      </div>
    </>
  );
}

function Fato({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="bg-card p-3">
      <dt className="text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
        {rotulo}
      </dt>
      <dd className="mt-1.5 text-xs leading-5 text-muted-foreground">{children}</dd>
    </div>
  );
}
