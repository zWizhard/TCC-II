import { useQuery } from "@tanstack/react-query";

import { KpiCard, type KpiEstado } from "@/components/data/KpiCard";
import { filtroDoEscopo, type Escopo } from "@/components/filters/search";
import { resolverDimensoes } from "@/lib/api/dimensoes";
import { indicadorQueryOptions } from "@/lib/api/queries";
import type { Categoria, Dimensao, IndicadorInfo, Organizacao, Rede } from "@/lib/api/schemas";
import { rotuloRede } from "@/lib/format";

/**
 * Indicadores em destaque na Visão Geral, na ordem de exibição: presença institucional, oferta
 * e os três de fluxo estudantil. Os demais do catálogo ficam recolhidos, não escondidos.
 */
const KPIS_PRINCIPAIS = ["ies", "cursos", "matriculas", "ingressantes", "concluintes"];

type KpisTerritorioProps = {
  /** Catálogo de `/api/v1/indicadores`, na ordem devolvida. */
  catalogo: readonly IndicadorInfo[];
  /** Território selecionado nos filtros globais (Brasil quando não há filtro). */
  escopo: Escopo;
  /** Dimensões de oferta selecionadas nos filtros globais. */
  dimensoes: readonly Dimensao[];
  /** Quantas dimensões existem ao todo (para "n de m"). */
  totalDimensoes: number;
  rede: Rede | undefined;
  categoria: Categoria | undefined;
  organizacao: Organizacao | undefined;
  /** Rótulo literal de cada dimensão (metadados), para nomear as que entram no valor. */
  rotuloDimensao: (slug: Dimensao) => string;
};

/** Um cartão por indicador, com o valor agregado no território selecionado. */
export function KpisTerritorio({ catalogo, ...filtros }: KpisTerritorioProps) {
  const destacados = KPIS_PRINCIPAIS.flatMap((slug) => catalogo.filter((i) => i.slug === slug));
  // Catálogo sem nenhum dos indicadores esperados: mostra o que houver em vez de uma tela vazia.
  const principais = destacados.length > 0 ? destacados : catalogo;
  const demais = catalogo.filter((i) => !principais.includes(i));

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {principais.map((indicador) => (
          <IndicadorKpi key={indicador.slug} indicador={indicador} {...filtros} />
        ))}
      </div>
      {demais.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer rounded text-xs font-semibold text-foreground">
            Demais indicadores do catálogo ({demais.length})
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {demais.map((indicador) => (
              <IndicadorKpi key={indicador.slug} indicador={indicador} {...filtros} />
            ))}
          </div>
        </details>
      )}
    </>
  );
}

type IndicadorKpiProps = Omit<KpisTerritorioProps, "catalogo"> & { indicador: IndicadorInfo };

export function IndicadorKpi({
  indicador,
  escopo,
  dimensoes,
  totalDimensoes,
  rede,
  categoria,
  organizacao,
  rotuloDimensao,
}: IndicadorKpiProps) {
  const consulta = { ...filtroDoEscopo(escopo), dimensoes, rede, categoria, organizacao };
  const resolucao = resolverDimensoes(indicador, consulta.nivel, dimensoes);
  const query = useQuery(indicadorQueryOptions(indicador, consulta));

  let estado: KpiEstado;
  if (!resolucao.consultavel) {
    estado = {
      tipo: "vazio",
      mensagem:
        resolucao.excluidas.length > 0
          ? `${indicador.codigo} não existe por território em nenhuma das dimensões de oferta selecionadas; não há valor para ${escopo.nome}.`
          : "Selecione ao menos uma dimensão de oferta para consultar este indicador.",
    };
  } else if (query.isError) {
    estado = { tipo: "erro", erro: query.error, onRetry: () => void query.refetch() };
  } else if (query.isPending) {
    estado = { tipo: "carregando" };
  } else if (query.data.linhas.length === 0) {
    estado = {
      tipo: "vazio",
      mensagem: `Nenhum registro em ${escopo.nome} para os filtros selecionados.`,
    };
  } else {
    estado = {
      tipo: "sucesso",
      valor: query.data.total,
      valorSemTerritorio: query.data.valor_sem_territorio,
      notas: query.data.notas,
    };
  }

  // Depois da resposta, mostra os rótulos que a API de fato aplicou.
  const aplicados = query.data?.filtros;
  let dimensao: string;
  if (!resolucao.aplicavel) dimensao = "não se aplica a este indicador";
  else {
    dimensao = `${resolucao.efetivas.length} de ${totalDimensoes} selecionadas`;
    if (resolucao.excluidas.length > 0) {
      // Nomeia o que entra: cartões vizinhos podem cobrir dimensões diferentes (ex.: cursos só
      // no presencial, matrículas também nos polos) e não são comparáveis entre si.
      dimensao = `só ${resolucao.efetivas.map(rotuloDimensao).join("; ")} — nas outras ${resolucao.excluidas.length} selecionadas este indicador não existe por território`;
    }
  }

  return (
    <KpiCard
      nome={indicador.nome}
      codigo={indicador.codigo}
      unidade={indicador.unidade}
      recorte={indicador.recorte}
      limitacoes={indicador.limitacoes}
      estado={estado}
      contexto={[
        { rotulo: "Território", valor: escopo.nome },
        { rotulo: "Rede", valor: aplicados ? (aplicados.rede ?? "Todas") : rotuloRede(rede) },
        ...(aplicados?.categoria ? [{ rotulo: "Categoria", valor: aplicados.categoria }] : []),
        ...(aplicados?.organizacao
          ? [{ rotulo: "Organização", valor: aplicados.organizacao }]
          : []),
        { rotulo: "Dimensão de oferta", valor: dimensao },
      ]}
    />
  );
}
