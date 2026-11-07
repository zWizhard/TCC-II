import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState, ErrorState } from "@/components/data/DataState";
import { Notes } from "@/components/data/Notes";
import { SegmentedRadio } from "@/components/filters/SegmentedRadio";
import { Skeleton } from "@/components/ui/skeleton";
import { comparacaoQueryOptions, municipiosQueryOptions } from "@/lib/api/queries";
import type {
  IndicadorComparado,
  Metadados,
  NivelComparacao,
  Rede,
  RespostaComparacao,
  ValorComparado,
} from "@/lib/api/schemas";
import { formatarDecimal, formatarInteiro, formatarPercentual, rotuloRecorte } from "@/lib/format";

import {
  MAX_UNIDADES,
  MIN_UNIDADES,
  NIVEL_PADRAO,
  unidadesDaBusca,
  type CompararSearch,
} from "./search";

const OPCOES_NIVEL: ReadonlyArray<{ valor: NivelComparacao; rotulo: string }> = [
  { valor: "regiao", rotulo: "Regiões" },
  { valor: "uf", rotulo: "UFs" },
  { valor: "municipio", rotulo: "Municípios" },
];

type OpcaoRede = Rede | "todas";
const OPCOES_REDE: ReadonlyArray<{ valor: OpcaoRede; rotulo: string }> = [
  { valor: "todas", rotulo: "Todas" },
  { valor: "publica", rotulo: "Pública" },
  { valor: "privada", rotulo: "Privada" },
];

const SINGULAR: Record<NivelComparacao, string> = {
  regiao: "região",
  uf: "UF",
  municipio: "município",
};
const PLURAL: Record<NivelComparacao, string> = {
  regiao: "regiões",
  uf: "UFs",
  municipio: "municípios",
};

const ROTULO =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground";
const SELECT =
  "h-9 w-full min-w-0 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground disabled:cursor-not-allowed disabled:opacity-60";

type ComparacaoProps = {
  metadados: Metadados;
  search: CompararSearch;
  onChange: (alteracao: Partial<CompararSearch>) => void;
};

/**
 * Seleção das unidades e a tabela que as põe lado a lado. As colunas seguem a ordem escolhida
 * pelo leitor: a tela não ordena nem classifica as unidades por valor.
 */
export function Comparacao({ metadados, search, onChange }: ComparacaoProps) {
  const nivel = search.nivel ?? NIVEL_PADRAO;
  const unidades = unidadesDaBusca(search, metadados.ufs);
  const consulta = useQuery(comparacaoQueryOptions({ nivel, unidades, rede: search.rede }));

  const definir = (proximas: readonly string[]) => onChange({ u: proximas.join(",") });
  // O nome das unidades já escolhidas vem dos metadados; o dos municípios, só da resposta.
  const nomeDe = (codigo: string) =>
    nivel === "regiao"
      ? (metadados.regioes.find((r) => r.slug === codigo)?.nome ?? codigo)
      : nivel === "uf"
        ? (metadados.ufs.find((u) => u.sigla === codigo)?.nome ?? codigo)
        : (consulta.data?.unidades.find((u) => u.codigo === codigo)?.nome ?? `Código ${codigo}`);

  return (
    <ChartCard
      title={`Comparação entre ${PLURAL[nivel]}`}
      description={
        <>
          De {MIN_UNIDADES} a {MAX_UNIDADES} unidades do mesmo nível, com as mesmas definições, o
          mesmo ano e os mesmos filtros. O Brasil entra como coluna de referência.
        </>
      }
      actions={
        <>
          <SegmentedRadio<NivelComparacao>
            legenda="Comparar"
            opcoes={OPCOES_NIVEL}
            valor={nivel}
            // Trocar de nível zera a seleção: unidades de níveis diferentes não se comparam.
            onChange={(valor) =>
              onChange({ nivel: valor === NIVEL_PADRAO ? undefined : valor, u: undefined })
            }
          />
          <SegmentedRadio<OpcaoRede>
            legenda="Rede"
            opcoes={OPCOES_REDE}
            valor={search.rede ?? "todas"}
            onChange={(valor) => onChange({ rede: valor === "todas" ? undefined : valor })}
          />
        </>
      }
    >
      <Selecao
        // Outro nível = outro seletor: a UF escolhida para listar municípios não persiste.
        key={nivel}
        nivel={nivel}
        metadados={metadados}
        unidades={unidades}
        nomeDe={nomeDe}
        onChange={definir}
      />

      <div className="mt-6">
        {unidades.length < MIN_UNIDADES ? (
          <EmptyState>
            Escolha ao menos {MIN_UNIDADES} {PLURAL[nivel]} para comparar.
          </EmptyState>
        ) : (
          <DataState
            query={consulta}
            loadingLabel="Carregando a comparação…"
            loading={<Skeleton className="h-96 w-full" />}
          >
            {(dados) => (
              <>
                <Tabela dados={dados} />
                <Notes notas={dados.notas} className="mt-5" />
              </>
            )}
          </DataState>
        )}
      </div>
    </ChartCard>
  );
}

function Selecao({
  nivel,
  metadados,
  unidades,
  nomeDe,
  onChange,
}: {
  nivel: NivelComparacao;
  metadados: Metadados;
  unidades: readonly string[];
  nomeDe: (codigo: string) => string;
  onChange: (proximas: readonly string[]) => void;
}) {
  const ufId = useId();
  const adicionarId = useId();
  const [uf, setUf] = useState("");
  const municipios = useQuery(municipiosQueryOptions(nivel === "municipio" && uf ? uf : undefined));
  const cheia = unidades.length >= MAX_UNIDADES;
  const ufs = [...metadados.ufs].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));

  const opcoes: ReadonlyArray<{ valor: string; rotulo: string }> =
    nivel === "regiao"
      ? metadados.regioes.map((r) => ({ valor: r.slug, rotulo: r.nome }))
      : nivel === "uf"
        ? ufs.map((u) => ({ valor: u.sigla, rotulo: `${u.nome} (${u.sigla})` }))
        : (municipios.data?.municipios ?? []).map((m) => ({
            valor: m.codigo,
            rotulo: `${m.nome}${m.sede ? "" : " — sem sede de IES"}`,
          }));
  const livres = opcoes.filter((o) => !unidades.includes(o.valor));

  return (
    <fieldset className="min-w-0">
      <legend className={ROTULO}>
        Unidades comparadas ({unidades.length} de {MAX_UNIDADES})
      </legend>
      {unidades.length > 0 && (
        <ul className="mb-3 flex flex-wrap gap-2" aria-label="Unidades selecionadas">
          {unidades.map((codigo) => (
            <li
              key={codigo}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-muted py-1 pl-2.5 pr-1 text-xs font-medium text-foreground"
            >
              {nomeDe(codigo)}
              <button
                type="button"
                onClick={() => onChange(unidades.filter((u) => u !== codigo))}
                className="grid size-5 place-items-center rounded text-muted-foreground hover:bg-background hover:text-foreground"
                aria-label={`Remover ${nomeDe(codigo)}`}
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-x-4 gap-y-3 sm:grid-cols-3">
        {nivel === "municipio" && (
          <div className="min-w-0">
            <label htmlFor={ufId} className={ROTULO}>
              UF do município
            </label>
            <select
              id={ufId}
              className={SELECT}
              value={uf}
              disabled={cheia}
              onChange={(event) => setUf(event.target.value)}
            >
              <option value="">Escolha uma UF</option>
              {ufs.map((u) => (
                <option key={u.sigla} value={u.sigla}>
                  {u.nome} ({u.sigla})
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="min-w-0">
          <label htmlFor={adicionarId} className={ROTULO}>
            Adicionar {SINGULAR[nivel]}
          </label>
          <select
            id={adicionarId}
            className={SELECT}
            // Sempre volta ao rótulo: escolher uma opção é a ação de adicionar.
            value=""
            disabled={cheia || livres.length === 0}
            onChange={(event) => {
              if (event.target.value) onChange([...unidades, event.target.value]);
            }}
          >
            <option value="">
              {cheia
                ? `Limite de ${MAX_UNIDADES} unidades`
                : nivel === "municipio" && !uf
                  ? "Escolha uma UF"
                  : nivel === "municipio" && municipios.isPending
                    ? "Carregando…"
                    : "Selecione…"}
            </option>
            {livres.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </select>
        </div>
      </div>
      {municipios.isError && (
        <ErrorState
          compact
          className="mt-2"
          error={municipios.error}
          onRetry={() => void municipios.refetch()}
        />
      )}
      {nivel === "municipio" && (
        <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
          A lista traz só os municípios que aparecem no Censo, como sede de IES ou como local de
          oferta de curso (incluindo polos de EAD). O nível reúne municípios e equivalentes
          (Brasília e Fernando de Noronha), que podem ser de UFs diferentes.
        </p>
      )}
    </fieldset>
  );
}

const GRUPOS: ReadonlyArray<{ tipo: IndicadorComparado["tipo"]; titulo: string; texto: string }> = [
  {
    tipo: "absoluto",
    titulo: "Valores absolutos",
    texto: "Contagens e somas: medem sobretudo o porte de cada unidade.",
  },
  {
    tipo: "relativo",
    titulo: "Valores relativos",
    texto: "Razões e proporções: comparáveis entre unidades de portes diferentes.",
  },
];

function formatar(indicador: IndicadorComparado, valor: number): string {
  if (indicador.tipo === "absoluto") return formatarInteiro(valor);
  return indicador.unidade === "%" ? formatarPercentual(valor) : formatarDecimal(valor);
}

function Tabela({ dados }: { dados: RespostaComparacao }) {
  const colunas = dados.unidades.length + 2;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] border-collapse text-sm">
        <caption className="mb-3 text-left text-xs leading-5 text-muted-foreground">
          Comparação entre {dados.unidades.map((u) => u.nome).join(", ")}. Censo da Educação
          Superior {dados.ano_censo} e população estimada de {dados.ano_populacao}. Rede:{" "}
          {dados.rede ?? "todas"}. As colunas seguem a ordem em que as unidades foram escolhidas,
          não uma classificação.
        </caption>
        <thead>
          <tr className="border-b border-border align-bottom">
            <th scope="col" className="px-3 py-2 text-left text-xs font-semibold">
              Indicador
            </th>
            {dados.unidades.map((u) => (
              <th key={u.codigo} scope="col" className="px-3 py-2 text-right text-xs font-semibold">
                {u.nome}
                {u.uf && u.uf !== u.codigo && (
                  <span className="font-normal text-muted-foreground"> – {u.uf}</span>
                )}
              </th>
            ))}
            <th
              scope="col"
              className="border-l border-border bg-section/60 px-3 py-2 text-right text-xs font-semibold"
            >
              {dados.referencia.nome}
              <span className="block text-[10px] font-normal text-muted-foreground">
                referência
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-border text-muted-foreground">
            <th scope="row" className="px-3 py-2 text-left text-xs font-medium">
              População estimada
              <span className="block text-[11px] font-normal">
                IBGE, {dados.ano_populacao} · contexto de porte
              </span>
            </th>
            {dados.unidades.map((u) => (
              <td key={u.codigo} className="px-3 py-2 text-right text-xs tabular-nums">
                {formatarInteiro(u.populacao)}
              </td>
            ))}
            <td className="border-l border-border bg-section/60 px-3 py-2 text-right text-xs tabular-nums">
              {formatarInteiro(dados.referencia.populacao)}
            </td>
          </tr>
        </tbody>
        {GRUPOS.map((grupo) => (
          <tbody key={grupo.tipo}>
            <tr className="border-b border-border bg-muted/60">
              <th scope="colgroup" colSpan={colunas} className="px-3 py-2 text-left">
                <span className="text-xs font-semibold text-foreground">{grupo.titulo}</span>
                <span className="ml-2 text-[11px] font-normal text-muted-foreground">
                  {grupo.texto}
                </span>
              </th>
            </tr>
            {dados.indicadores
              .filter((i) => i.tipo === grupo.tipo)
              .map((indicador) => (
                <Linha key={indicador.slug} indicador={indicador} colunas={colunas} />
              ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

function Linha({ indicador, colunas }: { indicador: IndicadorComparado; colunas: number }) {
  // Barra só nos relativos: nos absolutos ela desenharia o porte, que é o que a tela evita
  // classificar. Percentual usa a escala fixa de 0 a 100; as demais razões, o maior valor da linha.
  const escala =
    indicador.tipo === "absoluto"
      ? undefined
      : indicador.unidade === "%"
        ? 100
        : Math.max(0, ...indicador.valores.map((v) => v.valor ?? 0));
  return (
    <tr className="border-b border-border align-top">
      <th scope="row" className="max-w-xs px-3 py-2.5 text-left font-medium text-foreground">
        {indicador.nome}
        <span className="block text-[11px] font-normal leading-4 text-muted-foreground">
          {indicador.codigo} · {indicador.unidade} · Recorte: {rotuloRecorte(indicador.recorte)}
        </span>
        {indicador.dimensoes.length > 0 && (
          <span className="block text-[11px] font-normal leading-4 text-muted-foreground">
            Oferta: {indicador.dimensoes.join("; ")}
          </span>
        )}
        <details className="mt-1 text-[11px] font-normal leading-4 text-muted-foreground">
          <summary className="cursor-pointer text-foreground/80 underline decoration-border underline-offset-2">
            Definição e limitações
          </summary>
          {indicador.numerador_nome && indicador.denominador_nome && (
            <p className="mt-1.5">
              {indicador.numerador_nome} ÷ {indicador.denominador_nome}.
            </p>
          )}
          <ul className="mt-1.5 list-disc space-y-1 pl-4">
            {indicador.limitacoes.map((limitacao) => (
              <li key={limitacao}>{limitacao}</li>
            ))}
          </ul>
        </details>
      </th>
      {indicador.nao_se_aplica ? (
        <td colSpan={colunas - 1} className="px-3 py-2.5 text-xs text-muted-foreground">
          {indicador.nao_se_aplica}
        </td>
      ) : (
        <>
          {indicador.valores.map((valor, indice) => (
            // As colunas são posicionais: a ordem de `valores` é a de `unidades`.
            <Celula key={indice} indicador={indicador} valor={valor} maximo={escala} />
          ))}
          <Celula indicador={indicador} valor={indicador.referencia} referencia />
        </>
      )}
    </tr>
  );
}

function Celula({
  indicador,
  valor,
  maximo,
  referencia = false,
}: {
  indicador: IndicadorComparado;
  valor: ValorComparado;
  /** Escala da barra; ausente = sem barra. */
  maximo?: number | undefined;
  referencia?: boolean;
}) {
  const classe = referencia
    ? "border-l border-border bg-section/60 px-3 py-2.5 text-right tabular-nums"
    : "px-3 py-2.5 text-right tabular-nums";
  if (valor.valor === null) {
    return (
      <td className={classe}>
        <span aria-hidden="true" className="text-muted-foreground">
          —
        </span>
        <span className="sr-only">sem registro (ausência, não zero)</span>
      </td>
    );
  }
  return (
    <td className={classe}>
      <span className="font-semibold text-foreground">{formatar(indicador, valor.valor)}</span>
      {valor.numerador !== null && valor.denominador !== null && (
        <span className="block text-[11px] leading-4 text-muted-foreground">
          {formatarInteiro(valor.numerador)} ÷ {formatarInteiro(valor.denominador)}
        </span>
      )}
      {maximo !== undefined && maximo > 0 && (
        <span aria-hidden="true" className="mt-1.5 block h-1 rounded-full bg-muted">
          <span
            className="block h-1 rounded-full bg-teal"
            style={{ width: `${(valor.valor / maximo) * 100}%` }}
          />
        </span>
      )}
    </td>
  );
}
