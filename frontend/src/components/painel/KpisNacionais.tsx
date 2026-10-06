import { useQuery } from "@tanstack/react-query";

import { KpiCard, type KpiEstado } from "@/components/data/KpiCard";
import { resolverDimensoes } from "@/lib/api/dimensoes";
import { indicadorQueryOptions } from "@/lib/api/queries";
import type { Dimensao, IndicadorInfo, Rede } from "@/lib/api/schemas";
import { rotuloRede } from "@/lib/format";

type KpisNacionaisProps = {
  /** Catálogo de `/api/v1/indicadores`, na ordem devolvida. */
  catalogo: readonly IndicadorInfo[];
  /** Dimensões de oferta selecionadas nos filtros globais. */
  dimensoes: readonly Dimensao[];
  /** Quantas dimensões existem ao todo (para "n de m"). */
  totalDimensoes: number;
  rede: Rede | undefined;
};

/** Um cartão por indicador do catálogo, com o valor agregado no nível Brasil. */
export function KpisNacionais({ catalogo, dimensoes, totalDimensoes, rede }: KpisNacionaisProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {catalogo.map((indicador) => (
        <IndicadorKpi
          key={indicador.slug}
          indicador={indicador}
          dimensoes={dimensoes}
          totalDimensoes={totalDimensoes}
          rede={rede}
        />
      ))}
    </div>
  );
}

type IndicadorKpiProps = Omit<KpisNacionaisProps, "catalogo"> & { indicador: IndicadorInfo };

function IndicadorKpi({ indicador, dimensoes, totalDimensoes, rede }: IndicadorKpiProps) {
  const resolucao = resolverDimensoes(indicador, "brasil", dimensoes);
  const query = useQuery(indicadorQueryOptions(indicador, { nivel: "brasil", dimensoes, rede }));

  let estado: KpiEstado;
  if (!resolucao.consultavel) {
    estado = {
      tipo: "vazio",
      mensagem: "Selecione ao menos uma dimensão de oferta para consultar este indicador.",
    };
  } else if (query.isError) {
    estado = { tipo: "erro", erro: query.error, onRetry: () => void query.refetch() };
  } else if (query.isPending) {
    estado = { tipo: "carregando" };
  } else if (query.data.linhas.length === 0) {
    estado = { tipo: "vazio", mensagem: "Nenhum registro para os filtros selecionados." };
  } else {
    estado = {
      tipo: "sucesso",
      valor: query.data.total,
      valorSemTerritorio: query.data.valor_sem_territorio,
      notas: query.data.notas,
    };
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
        { rotulo: "Nível", valor: "Brasil" },
        // Depois da resposta, mostra o rótulo que a API de fato aplicou.
        {
          rotulo: "Rede",
          valor: query.data ? (query.data.filtros.rede ?? "Todas") : rotuloRede(rede),
        },
        {
          rotulo: "Dimensão de oferta",
          valor: resolucao.aplicavel
            ? `${resolucao.efetivas.length} de ${totalDimensoes} selecionadas`
            : "não se aplica a este indicador",
        },
      ]}
    />
  );
}
