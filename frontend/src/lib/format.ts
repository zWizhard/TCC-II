import type { Nivel, Recorte, Rede } from "@/lib/api/schemas";

const inteiro = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const compacto = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** 10227266 → "10.227.266". */
export function formatarInteiro(valor: number): string {
  return inteiro.format(valor);
}

/** Rótulo curto para eixos de gráfico: 4518942 → "4,5 mi". Nunca usar como valor principal. */
export function formatarCompacto(valor: number): string {
  return compacto.format(valor);
}

const ISO_LOCAL = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/;

/**
 * Data de extração da cópia local (`extraido_em`, ISO sem fuso) → "19/09/2026 às 02:25".
 * Lida como texto, sem `Date`, para o fuso do navegador não deslocar o dia.
 */
export function formatarDataExtracao(iso: string | null | undefined): string {
  if (!iso) return "não informada";
  const partes = ISO_LOCAL.exec(iso);
  if (!partes) return iso;
  const [, ano, mes, dia, hora, minuto] = partes;
  const data = `${dia}/${mes}/${ano}`;
  return hora && minuto ? `${data} às ${hora}:${minuto}` : data;
}

const ROTULO_RECORTE: Record<Recorte, string> = {
  sede: "Sede da IES",
  oferta: "Local de oferta",
};

/** Recorte territorial (ADR-0004), sempre declarado ao lado do número. */
export function rotuloRecorte(recorte: Recorte): string {
  return ROTULO_RECORTE[recorte];
}

const ROTULO_NIVEL: Record<Nivel, string> = {
  brasil: "Brasil",
  regiao: "Região",
  uf: "UF",
  municipio: "Município",
};

export function rotuloNivel(nivel: Nivel): string {
  return ROTULO_NIVEL[nivel];
}

const ROTULO_REDE: Record<Rede, string> = {
  publica: "Pública",
  privada: "Privada",
};

export function rotuloRede(rede: Rede | undefined): string {
  return rede ? ROTULO_REDE[rede] : "Todas";
}
