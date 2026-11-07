import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { DataState } from "@/components/data/DataState";
import { Skeleton } from "@/components/ui/skeleton";
import { instituicoesQueryOptions } from "@/lib/api/queries";
import type { Categoria, Dimensao, Organizacao, Rede } from "@/lib/api/schemas";
import { formatarInteiro } from "@/lib/format";

import { LIMITE_IES_DO_MUNICIPIO } from "./search";

/** Painel com os números do município selecionado — a linha dele na resposta do modo ativo. */
export function MunicipioSelecionado({ nome, children }: { nome: string; children: ReactNode }) {
  return (
    <section
      aria-label={`Município selecionado: ${nome}`}
      className="rounded-md border border-border bg-section/60 p-4"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
        Município selecionado
      </p>
      <p className="mt-1 font-display text-lg font-semibold text-foreground">{nome}</p>
      <div className="mt-2 text-xs leading-5 text-muted-foreground">{children}</div>
    </section>
  );
}

export function Numero({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
        {rotulo}
      </dt>
      <dd className="mt-0.5 text-sm font-semibold tabular-nums text-foreground">{children}</dd>
    </div>
  );
}

type IesDoMunicipioProps = {
  uf: string;
  /** Código IBGE de 7 dígitos. */
  municipio: string;
  dimensoes: readonly Dimensao[];
  /** Filtro de dimensão como está na URL (ausente = todas), para o link levar o mesmo filtro. */
  dimensaoNaUrl: Dimensao[] | undefined;
  rede: Rede | undefined;
  categoria: Categoria | undefined;
  organizacao: Organizacao | undefined;
};

/**
 * As IES com sede no município (`/api/v1/instituicoes`), as de mais matrículas primeiro. É aqui
 * que as instituições de um ponto aparecem uma a uma: no mapa elas dividem a mesma coordenada.
 */
export function IesDoMunicipio({
  uf,
  municipio,
  dimensoes,
  dimensaoNaUrl,
  rede,
  categoria,
  organizacao,
}: IesDoMunicipioProps) {
  const query = useQuery(
    instituicoesQueryOptions({
      uf,
      municipio,
      dimensoes,
      rede,
      categoria,
      organizacao,
      limite: LIMITE_IES_DO_MUNICIPIO,
    }),
  );
  const link = (
    <Link
      to="/instituicoes"
      search={{
        uf,
        municipio: Number(municipio),
        rede,
        categoria,
        organizacao,
        dimensao: dimensaoNaUrl,
      }}
      className="font-semibold text-teal-dark underline underline-offset-2"
    >
      Ver a tabela completa em Instituições
    </Link>
  );
  // Sem dimensão de oferta a API não lista as IES; o link continua valendo.
  if (dimensoes.length === 0) return <p className="mt-3">{link}</p>;

  return (
    <div className="mt-3">
      <DataState
        query={query}
        loadingLabel="Carregando as instituições do município…"
        loading={<Skeleton className="h-24 w-full" />}
        isEmpty={(dados) => dados.linhas.length === 0}
        empty="Nenhuma instituição com sede neste município para os filtros selecionados."
      >
        {(dados) => (
          <>
            <ul aria-label="Instituições com sede no município" className="space-y-1">
              {dados.linhas.map((ies) => (
                <li key={ies.co_ies} className="text-foreground">
                  {ies.nome}
                  {ies.sigla ? ` (${ies.sigla})` : ""}
                  <span className="text-muted-foreground"> · {ies.categoria}</span>
                </li>
              ))}
            </ul>
            {dados.totais.ies > dados.linhas.length && (
              <p className="mt-2">
                Exibindo {formatarInteiro(dados.linhas.length)} de{" "}
                {formatarInteiro(dados.totais.ies)} instituições, as de mais matrículas primeiro.
              </p>
            )}
          </>
        )}
      </DataState>
      <p className="mt-3">{link}</p>
    </div>
  );
}
