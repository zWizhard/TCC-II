/**
 * Contrato da API do Observatório, espelhando `api/schemas.py` e `api/indicadores.py`.
 *
 * Toda resposta é validada aqui antes de chegar a um componente: se o backend mudar o formato,
 * o frontend falha de forma explícita (ApiContratoError) em vez de exibir um número errado.
 */
import { z } from "zod";

export const RECORTES = ["sede", "oferta"] as const;
export const NIVEIS = ["brasil", "regiao", "uf", "municipio"] as const;
export const DIMENSOES = ["presencial", "ead_polo", "ead_nacional", "ead_exterior"] as const;
export const REDES = ["publica", "privada"] as const;

export const recorteSchema = z.enum(RECORTES);
export const nivelSchema = z.enum(NIVEIS);
export const dimensaoSchema = z.enum(DIMENSOES);
export const redeSchema = z.enum(REDES);

export const saudeSchema = z.object({
  status: z.string(),
  base_analitica: z.string(),
});

export const dimensaoOfertaSchema = z.object({
  slug: dimensaoSchema,
  /** Valor literal de `tp_dimensao` no Censo. */
  rotulo: z.string(),
  territorializavel: z.boolean(),
});

export const metadadosSchema = z.object({
  ano_censo: z.string(),
  fonte: z.string(),
  extraido_em: z.string().nullable(),
  recortes: z.array(recorteSchema),
  niveis: z.array(nivelSchema),
  dimensoes_oferta: z.array(dimensaoOfertaSchema),
  aviso: z.string(),
});

export const indicadorInfoSchema = z.object({
  slug: z.string(),
  codigo: z.string(),
  nome: z.string(),
  unidade: z.string(),
  recorte: recorteSchema,
  exige_dimensao: z.boolean(),
  dimensoes_territoriais: z.array(dimensaoSchema),
  limitacoes: z.array(z.string()),
});

export const catalogoSchema = z.array(indicadorInfoSchema);

export const filtrosRespostaSchema = z.object({
  /** Rótulos literais de `tp_dimensao` incluídos. */
  dimensoes: z.array(z.string()),
  rede: z.string().nullable(),
  uf: z.string().nullable(),
});

export const linhaSchema = z.object({
  codigo: z.string(),
  nome: z.string(),
  uf: z.string().nullable().optional(),
  valor: z.number().int(),
  latitude: z.number().nullable().optional(),
  longitude: z.number().nullable().optional(),
});

export const respostaIndicadorSchema = z.object({
  indicador: indicadorInfoSchema,
  ano_censo: z.string(),
  recorte: recorteSchema,
  nivel: nivelSchema,
  filtros: filtrosRespostaSchema,
  /** Soma de todas as unidades do nível, antes do limite. */
  total: z.number().int(),
  /** Número de unidades com registro, antes do limite. */
  unidades: z.number().int(),
  truncado: z.boolean(),
  /** Parcela sem município identificado: incluída no nível brasil, excluída dos demais. */
  valor_sem_territorio: z.number().int().nullable(),
  /** Ressalvas que dependem dos filtros escolhidos. */
  notas: z.array(z.string()),
  linhas: z.array(linhaSchema),
});

/** Envelope único de erro (`api/erros.py`). */
export const envelopeErroSchema = z.object({
  erro: z.object({
    codigo: z.string(),
    mensagem: z.string(),
  }),
});

export type Recorte = z.infer<typeof recorteSchema>;
export type Nivel = z.infer<typeof nivelSchema>;
export type Dimensao = z.infer<typeof dimensaoSchema>;
export type Rede = z.infer<typeof redeSchema>;
export type Saude = z.infer<typeof saudeSchema>;
export type DimensaoOferta = z.infer<typeof dimensaoOfertaSchema>;
export type Metadados = z.infer<typeof metadadosSchema>;
export type IndicadorInfo = z.infer<typeof indicadorInfoSchema>;
export type FiltrosResposta = z.infer<typeof filtrosRespostaSchema>;
export type Linha = z.infer<typeof linhaSchema>;
export type RespostaIndicador = z.infer<typeof respostaIndicadorSchema>;
export type EnvelopeErro = z.infer<typeof envelopeErroSchema>;
