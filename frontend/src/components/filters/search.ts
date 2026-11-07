/**
 * Filtros globais da área de dados, guardados na URL (search params) para serem
 * compartilháveis e reaproveitados por qualquer tela. Cada rota valida com `validateSearch`.
 *
 * Valor inválido na URL nunca derruba a página: cai no padrão (`catch`).
 */
import { z } from "zod";

import {
  categoriaSchema,
  dimensaoSchema,
  organizacaoSchema,
  redeSchema,
  regiaoSchema,
  siglaUfSchema,
  type Dimensao,
  type DimensaoOferta,
  type Nivel,
  type Regiao,
  type UFInfo,
} from "@/lib/api/schemas";

const listaDeDimensoes = z.preprocess(
  // Aceita `?dimensao=presencial` (texto único) além da lista.
  (valor) => (typeof valor === "string" ? [valor] : valor),
  z.array(dimensaoSchema).transform((lista) => [...new Set(lista)]),
);

export const filtrosGlobaisSchema = z.object({
  /** Ausente = todas as redes. */
  rede: redeSchema.optional().catch(undefined),
  /** Ausente = todas as dimensões de oferta. Lista vazia = nenhuma selecionada. */
  dimensao: listaDeDimensoes.optional().catch(undefined),
  /** Território: ausentes = Brasil. Vale o mais específico (município > UF > região). */
  regiao: regiaoSchema.optional().catch(undefined),
  uf: siglaUfSchema.optional().catch(undefined),
  /**
   * Código IBGE de 7 dígitos; só é considerado junto com `uf`. É número porque o roteador lê
   * `?municipio=5300108` como número — como texto, o endereço sairia com aspas codificadas.
   */
  municipio: z
    .preprocess(
      (valor) => (typeof valor === "string" && /^[0-9]{7}$/.test(valor) ? Number(valor) : valor),
      z.number().int().min(1_000_000).max(9_999_999),
    )
    .optional()
    .catch(undefined),
  /** Ausente = todas as categorias administrativas. */
  categoria: categoriaSchema.optional().catch(undefined),
  /** Ausente = todas as organizações acadêmicas. */
  organizacao: organizacaoSchema.optional().catch(undefined),
});

export type FiltrosGlobais = z.infer<typeof filtrosGlobaisSchema>;

/** Dimensões selecionadas, na ordem de `disponiveis`. Sem filtro na URL = todas. */
export function dimensoesSelecionadas(
  filtros: Pick<FiltrosGlobais, "dimensao">,
  disponiveis: readonly Dimensao[],
): Dimensao[] {
  if (filtros.dimensao === undefined) return [...disponiveis];
  const marcadas = new Set(filtros.dimensao);
  return disponiveis.filter((slug) => marcadas.has(slug));
}

/** Alterna uma dimensão. Quando todas ficam marcadas, volta ao padrão (parâmetro ausente). */
export function alternarDimensao(
  filtros: Pick<FiltrosGlobais, "dimensao">,
  disponiveis: readonly Dimensao[],
  slug: Dimensao,
): Dimensao[] | undefined {
  const atuais = new Set(dimensoesSelecionadas(filtros, disponiveis));
  if (atuais.has(slug)) atuais.delete(slug);
  else atuais.add(slug);
  const proximas = disponiveis.filter((d) => atuais.has(d));
  return proximas.length === disponiveis.length ? undefined : proximas;
}

/**
 * Modalidade (`tp_modalidade_ensino`) é função da dimensão de oferta, e a correspondência vem
 * de `/api/v1/metadados`. O filtro principal de modalidade é, portanto, um atalho para um
 * conjunto de dimensões — o estado na URL continua sendo `dimensao`.
 */
export const MODALIDADE_TODAS = "todas";
export const MODALIDADE_PERSONALIZADA = "personalizada";

/** Modalidades distintas, na ordem em que aparecem nas dimensões publicadas pela API. */
export function modalidadesDisponiveis(dimensoes: readonly DimensaoOferta[]): string[] {
  return [...new Set(dimensoes.map((d) => d.modalidade))];
}

/**
 * Modalidade correspondente à seleção atual de dimensões: `todas`, o rótulo literal de uma
 * modalidade, ou `personalizada` quando a seleção não coincide com nenhuma delas.
 */
export function modalidadeSelecionada(
  filtros: Pick<FiltrosGlobais, "dimensao">,
  dimensoes: readonly DimensaoOferta[],
): string {
  const slugs = dimensoes.map((d) => d.slug);
  const selecionadas = dimensoesSelecionadas(filtros, slugs);
  if (selecionadas.length === slugs.length) return MODALIDADE_TODAS;
  const marcadas = new Set(selecionadas);
  for (const modalidade of modalidadesDisponiveis(dimensoes)) {
    const grupo = dimensoes.filter((d) => d.modalidade === modalidade).map((d) => d.slug);
    if (grupo.length === marcadas.size && grupo.every((slug) => marcadas.has(slug))) {
      return modalidade;
    }
  }
  return MODALIDADE_PERSONALIZADA;
}

/** Dimensões a gravar na URL ao escolher uma modalidade (`undefined` = todas). */
export function dimensoesDaModalidade(
  modalidade: string,
  dimensoes: readonly DimensaoOferta[],
): Dimensao[] | undefined {
  if (modalidade === MODALIDADE_TODAS) return undefined;
  return dimensoes.filter((d) => d.modalidade === modalidade).map((d) => d.slug);
}

/**
 * Território selecionado, já reduzido ao nível mais específico. É o que as consultas usam:
 * a região nunca é enviada junto com a UF, o que impede a combinação incoerente vinda da URL
 * (ex.: `uf=SP&regiao=sul`), que a API recusaria.
 */
export type Escopo =
  | { nivel: "brasil"; nome: string }
  | { nivel: "regiao"; nome: string; regiao: Regiao }
  | { nivel: "uf"; nome: string; regiao: Regiao; uf: string }
  | { nivel: "municipio"; nome: string; regiao: Regiao; uf: string; municipio: string };

export type Territorios = {
  regioes: ReadonlyArray<{ slug: Regiao; nome: string }>;
  ufs: readonly UFInfo[];
};

export function resolverEscopo(
  filtros: Pick<FiltrosGlobais, "regiao" | "uf" | "municipio">,
  territorios: Territorios,
  /** Nome do município, quando a lista da UF já foi carregada. */
  nomeMunicipio?: string | undefined,
): Escopo {
  const uf = territorios.ufs.find((u) => u.sigla === filtros.uf);
  if (uf) {
    if (filtros.municipio) {
      return {
        nivel: "municipio",
        nome: `${nomeMunicipio ?? `Município ${filtros.municipio}`} (${uf.sigla})`,
        regiao: uf.regiao,
        uf: uf.sigla,
        municipio: String(filtros.municipio),
      };
    }
    return { nivel: "uf", nome: uf.nome, regiao: uf.regiao, uf: uf.sigla };
  }
  const regiao = territorios.regioes.find((r) => r.slug === filtros.regiao);
  if (regiao) return { nivel: "regiao", nome: `Região ${regiao.nome}`, regiao: regiao.slug };
  return { nivel: "brasil", nome: "Brasil" };
}

/** Parâmetros de consulta que restringem um indicador ao território do escopo. */
export function filtroDoEscopo(escopo: Escopo): {
  nivel: Nivel;
  regiao?: Regiao;
  uf?: string;
  municipio?: string;
} {
  switch (escopo.nivel) {
    case "brasil":
      return { nivel: "brasil" };
    case "regiao":
      return { nivel: "regiao", regiao: escopo.regiao };
    case "uf":
      return { nivel: "uf", uf: escopo.uf };
    case "municipio":
      // A UF vai junto: código de município de outra UF devolve vazio, em vez de os números
      // de um município aparecerem sob o nome de outra UF.
      return { nivel: "municipio", uf: escopo.uf, municipio: escopo.municipio };
  }
}

/** Quantos filtros estão ativos entre os de "Mais filtros" e no total. */
export function contarFiltrosAtivos(filtros: FiltrosGlobais): { total: number; avancados: number } {
  const avancados = [filtros.categoria, filtros.organizacao].filter((v) => v !== undefined).length;
  const principais = [filtros.regiao ?? filtros.uf, filtros.rede, filtros.dimensao].filter(
    (v) => v !== undefined,
  ).length;
  return { total: principais + avancados, avancados };
}

/** Alteração que devolve todos os filtros globais ao padrão. */
export const FILTROS_LIMPOS = {
  rede: undefined,
  dimensao: undefined,
  regiao: undefined,
  uf: undefined,
  municipio: undefined,
  categoria: undefined,
  organizacao: undefined,
} satisfies Record<keyof FiltrosGlobais, undefined>;
