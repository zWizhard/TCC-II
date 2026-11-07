import { useId } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { ChartCard } from "@/components/data/ChartCard";
import { DataState, EmptyState } from "@/components/data/DataState";
import { Notes } from "@/components/data/Notes";
import { filtroDoEscopo, type Escopo } from "@/components/filters/search";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { instituicoesQueryOptions } from "@/lib/api/queries";
import {
  ordemInstituicoesSchema,
  type Categoria,
  type Dimensao,
  type OrdemInstituicoes,
  type Organizacao,
  type Rede,
  type RespostaInstituicoes,
} from "@/lib/api/schemas";
import { formatarInteiro } from "@/lib/format";

import { LIMITE_INSTITUICOES } from "./search";

const ORDEM_PADRAO: OrdemInstituicoes = "matriculas";

const OPCOES_ORDEM: ReadonlyArray<{ valor: OrdemInstituicoes; rotulo: string }> = [
  { valor: "matriculas", rotulo: "Matrículas (maior primeiro)" },
  { valor: "cursos", rotulo: "Cursos (maior primeiro)" },
  { valor: "ingressantes", rotulo: "Ingressantes (maior primeiro)" },
  { valor: "concluintes", rotulo: "Concluintes (maior primeiro)" },
  { valor: "docentes", rotulo: "Docentes (maior primeiro)" },
  { valor: "tecnicos", rotulo: "Técnicos (maior primeiro)" },
  { valor: "nome", rotulo: "Nome (A–Z)" },
];

type TabelaInstituicoesProps = {
  escopo: Escopo;
  /** Dimensões de oferta selecionadas: delimitam só as métricas de curso. */
  dimensoes: readonly Dimensao[];
  rede: Rede | undefined;
  categoria: Categoria | undefined;
  organizacao: Organizacao | undefined;
  ordem: OrdemInstituicoes | undefined;
  pagina: number | undefined;
  onChange: (alteracao: { ordem?: OrdemInstituicoes | undefined; pagina?: number }) => void;
};

/**
 * Tabela detalhada de IES, paginada e ordenada pela API. Pessoal vem da tabela de IES; as
 * métricas de curso, de `cursos` pré-agregada por IES — a API nunca soma uma sobre a outra.
 */
export function TabelaInstituicoes({
  escopo,
  dimensoes,
  rede,
  categoria,
  organizacao,
  ordem,
  pagina,
  onChange,
}: TabelaInstituicoesProps) {
  const seletorId = useId();
  const { regiao, uf, municipio } = filtroDoEscopo(escopo);
  const query = useQuery({
    ...instituicoesQueryOptions({
      regiao,
      uf,
      municipio,
      dimensoes,
      rede,
      categoria,
      organizacao,
      ordem,
      limite: LIMITE_INSTITUICOES,
      pagina,
    }),
    // Ao trocar de página, a anterior continua visível até a nova chegar.
    placeholderData: keepPreviousData,
  });

  return (
    <ChartCard
      title={`Instituições por sede — ${escopo.nome}`}
      description={
        <>
          IND-D-01, IND-D-08 e IND-D-09 por instituição, com a oferta de cada uma · Recorte
          territorial: <strong>Sede da IES</strong>
        </>
      }
      actions={
        <div className="min-w-0">
          <label
            htmlFor={seletorId}
            className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground"
          >
            Ordenar por
          </label>
          <select
            id={seletorId}
            value={ordem ?? ORDEM_PADRAO}
            onChange={(event) => {
              const valor = ordemInstituicoesSchema.parse(event.target.value);
              onChange({ ordem: valor === ORDEM_PADRAO ? undefined : valor });
            }}
            className="h-9 max-w-full rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground"
          >
            {OPCOES_ORDEM.map((opcao) => (
              <option key={opcao.valor} value={opcao.valor}>
                {opcao.rotulo}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {dimensoes.length === 0 ? (
        <EmptyState>
          Selecione ao menos uma dimensão de oferta: cursos e matrículas de cada instituição só
          existem com a dimensão declarada.
        </EmptyState>
      ) : (
        <DataState
          query={query}
          loadingLabel="Carregando as instituições…"
          loading={<Skeleton className="h-96 w-full" />}
          isEmpty={(dados) => dados.totais.ies === 0}
          empty={`Nenhuma instituição com sede no território selecionado (${escopo.nome}) para os filtros selecionados.`}
        >
          {(dados) => <Resultado dados={dados} escopo={escopo} onChange={onChange} />}
        </DataState>
      )}
    </ChartCard>
  );
}

function numero(valor: number | null): string {
  return valor === null ? "—" : formatarInteiro(valor);
}

const COLUNAS_NUMERICAS = [
  ["cursos", "Cursos"],
  ["matriculas", "Matrículas"],
  ["ingressantes", "Ingressantes"],
  ["concluintes", "Concluintes"],
  ["docentes", "Docentes"],
  ["tecnicos", "Técnicos"],
] as const;

function Resultado({
  dados,
  escopo,
  onChange,
}: {
  dados: RespostaInstituicoes;
  escopo: Escopo;
  onChange: TabelaInstituicoesProps["onChange"];
}) {
  const { totais } = dados;
  const primeira = (dados.pagina - 1) * dados.limite + 1;
  const ultima = primeira + dados.linhas.length - 1;
  const semOferta = totais.ies - totais.ies_com_oferta;

  // Página vinda da URL além da última (ex.: endereço compartilhado com outro filtro).
  if (dados.linhas.length === 0) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <EmptyState>
          A página {formatarInteiro(dados.pagina)} não existe: são {formatarInteiro(totais.ies)}{" "}
          instituições em {formatarInteiro(dados.paginas)} páginas.
        </EmptyState>
        <BotaoPagina
          rotulo="Ir para a primeira página"
          desabilitado={false}
          onClick={() => onChange({ pagina: 1 })}
        />
      </div>
    );
  }

  return (
    <>
      <p className="text-xs leading-5 text-muted-foreground">
        <strong className="tabular-nums text-foreground">{formatarInteiro(totais.ies)}</strong>{" "}
        instituições · Rede: {dados.filtros.rede ?? "Todas"}
        {dados.filtros.categoria && <> · {dados.filtros.categoria}</>}
        {dados.filtros.organizacao && <> · {dados.filtros.organizacao}</>}
      </p>
      <details className="mt-1 text-xs leading-5 text-muted-foreground">
        <summary className="cursor-pointer rounded font-semibold text-foreground">
          Dimensões de oferta nas colunas de curso ({dados.filtros.dimensoes.length})
        </summary>
        <ul className="mt-1 list-disc pl-4">
          {dados.filtros.dimensoes.map((rotulo) => (
            <li key={rotulo}>{rotulo}</li>
          ))}
        </ul>
      </details>
      {semOferta > 0 && (
        <p role="note" className="mt-2 text-xs text-demo-foreground">
          {formatarInteiro(semOferta)} destas instituições não têm oferta nas dimensões
          selecionadas: nelas as colunas de curso aparecem como “—” (ausência, não zero).
        </p>
      )}
      <Notes notas={dados.notas} className="mt-3" />

      <Table className="mt-5">
        <TableCaption className="mt-3 text-left text-xs">
          Instituições de ensino superior por sede — {escopo.nome} — Censo da Educação Superior{" "}
          {dados.ano_censo}. Cursos, matrículas, ingressantes e concluintes: total da instituição em
          qualquer local de oferta.
        </TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="h-10 px-3 text-xs font-semibold">
              Instituição
            </TableHead>
            <TableHead scope="col" className="h-10 px-3 text-xs font-semibold">
              Sede
            </TableHead>
            <TableHead scope="col" className="h-10 px-3 text-xs font-semibold">
              Categoria e organização
            </TableHead>
            {COLUNAS_NUMERICAS.map(([chave, rotulo]) => (
              <TableHead
                key={chave}
                scope="col"
                aria-sort={dados.ordem === chave ? "descending" : undefined}
                className="h-10 px-3 text-right text-xs font-semibold"
              >
                {rotulo}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {dados.linhas.map((linha) => (
            <TableRow key={linha.co_ies}>
              <th scope="row" className="px-3 py-2 text-left text-sm font-medium text-foreground">
                {linha.nome}
                <span className="block text-[11px] font-normal text-muted-foreground">
                  {linha.sigla ? `${linha.sigla} · ` : ""}código da IES no Censo: {linha.co_ies}
                </span>
              </th>
              <TableCell className="px-3 py-2 text-sm">
                {linha.municipio} ({linha.uf})
              </TableCell>
              <TableCell className="px-3 py-2 text-sm">
                {linha.categoria}
                <span className="block text-[11px] text-muted-foreground">{linha.organizacao}</span>
              </TableCell>
              {COLUNAS_NUMERICAS.map(([chave]) => (
                <TableCell key={chave} className="px-3 py-2 text-right text-sm tabular-nums">
                  {numero(linha[chave])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <nav
        aria-label="Páginas da tabela de instituições"
        className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground"
      >
        <p role="status">
          Instituições {formatarInteiro(primeira)}–{formatarInteiro(ultima)} de{" "}
          {formatarInteiro(totais.ies)} · página {formatarInteiro(dados.pagina)} de{" "}
          {formatarInteiro(dados.paginas)}
        </p>
        <div className="flex gap-2">
          <BotaoPagina
            rotulo="Anterior"
            desabilitado={dados.pagina <= 1}
            onClick={() => onChange({ pagina: dados.pagina - 1 })}
          />
          <BotaoPagina
            rotulo="Próxima"
            desabilitado={dados.pagina >= dados.paginas}
            onClick={() => onChange({ pagina: dados.pagina + 1 })}
          />
        </div>
      </nav>
    </>
  );
}

function BotaoPagina({
  rotulo,
  desabilitado,
  onClick,
}: {
  rotulo: string;
  desabilitado: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={desabilitado}
      onClick={onClick}
      className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
    >
      {rotulo}
    </button>
  );
}
