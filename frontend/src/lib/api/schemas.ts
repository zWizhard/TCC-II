/**
 * Contrato da API do Observatório, espelhando `api/schemas.py` e `api/indicadores.py`.
 *
 * Toda resposta é validada aqui antes de chegar a um componente: se o backend mudar o formato,
 * o frontend falha de forma explícita (ApiContratoError) em vez de exibir um número errado.
 */
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";
import { z } from "zod";

export const RECORTES = ["sede", "oferta"] as const;
export const NIVEIS = ["brasil", "regiao", "uf", "municipio"] as const;
export const DIMENSOES = ["presencial", "ead_polo", "ead_nacional", "ead_exterior"] as const;
export const REDES = ["publica", "privada"] as const;
export const REGIOES = ["norte", "nordeste", "sudeste", "sul", "centro_oeste"] as const;
export const CATEGORIAS = [
  "publica_federal",
  "publica_estadual",
  "publica_municipal",
  "privada_com_fins_lucrativos",
  "privada_sem_fins_lucrativos",
  "especial",
] as const;
export const ORGANIZACOES = [
  "universidade",
  "centro_universitario",
  "faculdade",
  "instituto_federal",
  "cefet",
] as const;

export const AREAS_CINE = [
  "programas_basicos",
  "educacao",
  "artes_humanidades",
  "ciencias_sociais",
  "negocios_direito",
  "ciencias_naturais",
  "computacao_tic",
  "engenharia",
  "agricultura_veterinaria",
  "saude",
  "servicos",
] as const;
export const GRAUS = ["bacharelado", "licenciatura", "tecnologico", "nao_aplicavel"] as const;
/** Eixos de `/api/v1/indicadores/{slug}/composicao` (`api/indicadores.py`, `Eixo`). */
export const EIXOS = [
  "rede",
  "categoria",
  "organizacao",
  "dimensao",
  "grau",
  "area",
  "rotulo_cine",
  "titulacao",
  "sexo",
  "cor_raca",
  "faixa_etaria",
  "nacionalidade",
  "procedencia_escolar",
  "tipo_ingresso",
] as const;
/** Eixos de perfil (IND-R-07): a API não os serve no nível municipal. */
export const EIXOS_PERFIL = [
  "sexo",
  "cor_raca",
  "faixa_etaria",
  "nacionalidade",
  "procedencia_escolar",
] as const;
/** Bases de IND-R-08 e IND-R-09 (`api/indicadores.py`, `BaseFluxo`). */
export const BASES_FLUXO = ["matriculas", "ingressantes", "concluintes"] as const;
/** Comparações de `/api/v1/razoes/{slug}` (`api/indicadores.py`, `Agrupamento`). */
export const AGRUPAMENTOS = [
  "regiao",
  "uf",
  "municipio",
  "rede",
  "categoria",
  "organizacao",
  "dimensao",
  "grau",
  "area",
] as const;
export const ORDENS_INSTITUICOES = [
  "matriculas",
  "cursos",
  "ingressantes",
  "concluintes",
  "docentes",
  "tecnicos",
  "nome",
] as const;

export const recorteSchema = z.enum(RECORTES);
export const areaCineSchema = z.enum(AREAS_CINE);
export const grauSchema = z.enum(GRAUS);
export const eixoSchema = z.enum(EIXOS);
export const baseFluxoSchema = z.enum(BASES_FLUXO);
export const agrupamentoSchema = z.enum(AGRUPAMENTOS);
export const ordemInstituicoesSchema = z.enum(ORDENS_INSTITUICOES);
export const nivelSchema = z.enum(NIVEIS);
export const dimensaoSchema = z.enum(DIMENSOES);
export const redeSchema = z.enum(REDES);
export const regiaoSchema = z.enum(REGIOES);
export const categoriaSchema = z.enum(CATEGORIAS);
export const organizacaoSchema = z.enum(ORGANIZACOES);
/** Sigla de UF; a lista válida é a de `metadados.ufs`. */
export const siglaUfSchema = z.string().regex(/^[A-Z]{2}$/);
/** Código IBGE de 7 dígitos. */
export const codigoMunicipioSchema = z.string().regex(/^[0-9]{7}$/);

export const saudeSchema = z.object({
  status: z.string(),
  base_analitica: z.string(),
});

export const dimensaoOfertaSchema = z.object({
  slug: dimensaoSchema,
  /** Valor literal de `tp_dimensao` no Censo. */
  rotulo: z.string(),
  territorializavel: z.boolean(),
  /** Valor literal de `tp_modalidade_ensino` nessa dimensão. */
  modalidade: z.string(),
});

export const regiaoInfoSchema = z.object({ slug: regiaoSchema, nome: z.string() });

export const ufInfoSchema = z.object({
  sigla: siglaUfSchema,
  nome: z.string(),
  regiao: regiaoSchema,
});

export const categoriaInfoSchema = z.object({
  slug: categoriaSchema,
  /** Valor literal de `tp_categoria_administrativa`. */
  rotulo: z.string(),
  rede: redeSchema,
});

export const organizacaoInfoSchema = z.object({
  slug: organizacaoSchema,
  /** Valor literal de `tp_organizacao_academica`. */
  rotulo: z.string(),
});

export const areaCineInfoSchema = z.object({
  slug: areaCineSchema,
  /** Valor de `co_cine_area_geral`. */
  codigo: z.number().int(),
  /** Valor literal de `no_cine_area_geral`. */
  nome: z.string(),
});

export const grauInfoSchema = z.object({
  slug: grauSchema,
  /** Valor literal de `tp_grau_academico`. */
  rotulo: z.string(),
});

export const metadadosSchema = z.object({
  ano_censo: z.string(),
  fonte: z.string(),
  extraido_em: z.string().nullable(),
  recortes: z.array(recorteSchema),
  niveis: z.array(nivelSchema),
  dimensoes_oferta: z.array(dimensaoOfertaSchema),
  regioes: z.array(regiaoInfoSchema),
  ufs: z.array(ufInfoSchema),
  categorias: z.array(categoriaInfoSchema),
  organizacoes: z.array(organizacaoInfoSchema),
  areas_cine: z.array(areaCineInfoSchema),
  graus: z.array(grauInfoSchema),
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
  categoria: z.string().nullable(),
  organizacao: z.string().nullable(),
  regiao: z.string().nullable(),
  uf: z.string().nullable(),
  municipio: z.string().nullable(),
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

export const filtrosComposicaoSchema = filtrosRespostaSchema.extend({
  /** Rótulo de `no_cine_area_geral` aplicado como filtro. */
  area: z.string().nullable(),
  /** Rótulo de `tp_grau_academico` aplicado como filtro. */
  grau: z.string().nullable(),
});

export const linhaComposicaoSchema = z.object({
  codigo: z.string(),
  nome: z.string(),
  /** Área geral CINE a que o rótulo pertence (eixo `rotulo_cine`). */
  grupo: z.string().nullable().optional(),
  valor: z.number().int(),
  /** `valor / total * 100`, calculado pela API sobre todas as categorias. */
  participacao: z.number().nullable(),
});

export const respostaComposicaoSchema = z.object({
  indicador: indicadorInfoSchema,
  eixo: eixoSchema,
  eixo_nome: z.string(),
  /** Ficha do Bloco B de INDICADORES.md que a composição realiza, se houver. */
  ficha: z.string().nullable(),
  ano_censo: z.string(),
  recorte: recorteSchema,
  /** Nível do território selecionado pelos filtros. */
  nivel: nivelSchema,
  filtros: filtrosComposicaoSchema,
  /** Soma de todas as categorias, antes do limite. */
  total: z.number().int(),
  /** Número de categorias com registro, antes do limite. */
  categorias: z.number().int(),
  truncado: z.boolean(),
  notas: z.array(z.string()),
  linhas: z.array(linhaComposicaoSchema),
});

export const razaoInfoSchema = indicadorInfoSchema.extend({
  /** Exige `base`: matrículas, ingressantes ou concluintes. */
  usa_base: z.boolean(),
  /** `true`: numerador contido no denominador, valor em %. `false`: razão simples. */
  percentual: z.boolean(),
  /** Dimensões de oferta admitidas em qualquer nível. */
  dimensoes: z.array(dimensaoSchema),
  /** Aceita uma única dimensão de oferta por consulta. */
  dimensao_unica: z.boolean(),
  /** Servida no nível municipal. */
  municipal: z.boolean(),
});

export const catalogoRazoesSchema = z.array(razaoInfoSchema);

export const valorRazaoSchema = z.object({
  numerador: z.number().int(),
  denominador: z.number().int(),
  /** Calculado pela API. Nulo quando o denominador é zero: a razão não se aplica. */
  valor: z.number().nullable(),
});

export const linhaRazaoSchema = valorRazaoSchema.extend({
  codigo: z.string(),
  nome: z.string(),
  uf: z.string().nullable().optional(),
});

export const respostaRazaoSchema = z.object({
  indicador: razaoInfoSchema,
  base: baseFluxoSchema.nullable(),
  numerador_nome: z.string(),
  denominador_nome: z.string(),
  ano_censo: z.string(),
  recorte: recorteSchema,
  /** Nível das linhas quando `por` é territorial; senão, o do território dos filtros. */
  nivel: nivelSchema,
  por: agrupamentoSchema.nullable(),
  filtros: filtrosRespostaSchema,
  /** Razão no território selecionado pelos filtros. */
  geral: valorRazaoSchema,
  /** Número de grupos com registro, antes do limite. */
  unidades: z.number().int(),
  truncado: z.boolean(),
  notas: z.array(z.string()),
  linhas: z.array(linhaRazaoSchema),
});

/** Níveis em que há malha territorial e coroplético (`api/indicadores.py`, `NivelMalha`). */
export const NIVEIS_MALHA = ["uf", "municipio"] as const;
export const nivelMalhaSchema = z.enum(NIVEIS_MALHA);

export const linhaCoropleticoSchema = z.object({
  /** Código IBGE: 7 dígitos (município) ou 2 (UF). É o `codarea` da malha. */
  codigo: z.string(),
  nome: z.string(),
  uf: z.string(),
  /** Matrículas. Nulo = unidade sem registro de oferta (ausência, não zero). */
  numerador: z.number().int().nullable(),
  /** População estimada da unidade. */
  denominador: z.number().int(),
  /** `numerador / denominador × 100.000`, calculado pela API. Nulo sem registro. */
  valor: z.number().nullable(),
  /** Índice da classe da legenda. Nulo sem registro. */
  classe: z.number().int().nullable(),
});

export const classeCoropleticoSchema = z.object({
  indice: z.number().int(),
  /** Menor e maior valor observados na classe. */
  minimo: z.number(),
  maximo: z.number(),
  unidades: z.number().int(),
});

export const respostaCoropleticoSchema = z.object({
  indicador: indicadorInfoSchema,
  numerador_nome: z.string(),
  denominador_nome: z.string(),
  ano_censo: z.string(),
  ano_populacao: z.string(),
  recorte: recorteSchema,
  nivel: nivelMalhaSchema,
  filtros: filtrosRespostaSchema,
  /**
   * Razão no território dos filtros; o denominador inclui as unidades sem oferta. Numerador nulo
   * = nenhuma unidade do recorte tem registro: o território é ausência, não zero.
   */
  geral: z.object({
    numerador: z.number().int().nullable(),
    denominador: z.number().int(),
    valor: z.number().nullable(),
  }),
  /** Unidades do território (universo do denominador). */
  unidades: z.number().int(),
  com_registro: z.number().int(),
  /** Unidades sem linha de oferta: ausência, não zero. */
  sem_registro: z.number().int(),
  metodo_classes: z.string(),
  /** Empates podem fundir classes: pode vir menos do que o pedido. */
  classes: z.array(classeCoropleticoSchema),
  notas: z.array(z.string()),
  /** Todas as unidades do território, inclusive as sem registro. */
  linhas: z.array(linhaCoropleticoSchema),
});

/**
 * Malha territorial do IBGE (`/api/v1/mapa/malha/{nivel}`). Só a casca é validada: conferir
 * 5.571 polígonos vértice a vértice custaria mais do que desenhá-los, e a geometria é dado
 * opaco, entregue como veio ao MapLibre. A chave de cada feição é `properties.codarea`.
 */
export const malhaSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(z.unknown()),
});

export const linhaInstituicaoSchema = z.object({
  co_ies: z.number().int(),
  nome: z.string(),
  /** Nula quando `sg_ies` está vazia. */
  sigla: z.string().nullable(),
  uf: siglaUfSchema,
  municipio_codigo: codigoMunicipioSchema,
  municipio: z.string(),
  rede: z.string(),
  categoria: z.string(),
  organizacao: z.string(),
  docentes: z.number().int(),
  tecnicos: z.number().int().nullable(),
  /** Métricas de curso: nulas quando a IES não tem oferta nas dimensões selecionadas. */
  cursos: z.number().int().nullable(),
  matriculas: z.number().int().nullable(),
  ingressantes: z.number().int().nullable(),
  concluintes: z.number().int().nullable(),
});

export const totaisInstituicoesSchema = z.object({
  ies: z.number().int(),
  ies_com_oferta: z.number().int(),
  docentes: z.number().int(),
  tecnicos: z.number().int(),
  /** Nulos com filtro territorial: a oferta das IES não é um número do território da sede. */
  cursos: z.number().int().nullable(),
  matriculas: z.number().int().nullable(),
  ingressantes: z.number().int().nullable(),
  concluintes: z.number().int().nullable(),
});

export const respostaInstituicoesSchema = z.object({
  ano_censo: z.string(),
  /** O filtro territorial vale para a sede da IES. */
  recorte: recorteSchema,
  filtros: filtrosRespostaSchema,
  ordem: ordemInstituicoesSchema,
  pagina: z.number().int(),
  limite: z.number().int(),
  paginas: z.number().int(),
  /** Somas sobre todas as IES que atendem aos filtros, antes da paginação. */
  totais: totaisInstituicoesSchema,
  notas: z.array(z.string()),
  linhas: z.array(linhaInstituicaoSchema),
});

/** Níveis de `/api/v1/comparacoes` (`api/indicadores.py`, `NivelComparacao`). */
export const NIVEIS_COMPARACAO = ["regiao", "uf", "municipio"] as const;
export const nivelComparacaoSchema = z.enum(NIVEIS_COMPARACAO);
export const TIPOS_COMPARACAO = ["absoluto", "relativo"] as const;

export const unidadeComparadaSchema = z.object({
  /** Slug da região, sigla da UF, código IBGE de 7 dígitos ou `BR` (referência). */
  codigo: z.string(),
  nome: z.string(),
  uf: z.string().nullable(),
  /** População estimada (IBGE): contexto de porte da unidade. */
  populacao: z.number().int(),
});

export const valorComparadoSchema = z.object({
  /** Nulo = sem registro na base ou denominador zero: ausência, nunca zero. */
  valor: z.number().nullable(),
  /** Só nos indicadores relativos. */
  numerador: z.number().int().nullable(),
  denominador: z.number().int().nullable(),
});

export const indicadorComparadoSchema = z.object({
  slug: z.string(),
  codigo: z.string(),
  nome: z.string(),
  unidade: z.string(),
  /** Absoluto mede sobretudo o porte; relativo é comparável entre portes diferentes. */
  tipo: z.enum(TIPOS_COMPARACAO),
  recorte: recorteSchema,
  /** Rótulos literais de `tp_dimensao`; vazio nos indicadores da tabela de IES. */
  dimensoes: z.array(z.string()),
  numerador_nome: z.string().nullable(),
  denominador_nome: z.string().nullable(),
  limitacoes: z.array(z.string()),
  /** Motivo pelo qual a linha inteira não se aplica aos filtros escolhidos. */
  nao_se_aplica: z.string().nullable(),
  /** Na mesma ordem de `unidades`. */
  valores: z.array(valorComparadoSchema),
  /** Brasil, pela mesma definição e pelos mesmos filtros. */
  referencia: valorComparadoSchema,
});

export const respostaComparacaoSchema = z.object({
  ano_censo: z.string(),
  ano_populacao: z.string(),
  nivel: nivelSchema,
  /** Rótulo da rede aplicada a todas as unidades. */
  rede: z.string().nullable(),
  dimensoes: z.array(z.string()),
  /** Na ordem pedida: a API não ordena nem classifica. */
  unidades: z.array(unidadeComparadaSchema),
  referencia: unidadeComparadaSchema,
  indicadores: z.array(indicadorComparadoSchema),
  notas: z.array(z.string()),
});

export const municipioInfoSchema = z.object({
  codigo: codigoMunicipioSchema,
  nome: z.string(),
  /** Há IES com sede no município. */
  sede: z.boolean(),
  /** Há curso presencial ou polo EAD no município. */
  oferta: z.boolean(),
});

export const respostaMunicipiosSchema = z.object({
  ano_censo: z.string(),
  uf: siglaUfSchema,
  municipios: z.array(municipioInfoSchema),
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
export type Regiao = z.infer<typeof regiaoSchema>;
export type Categoria = z.infer<typeof categoriaSchema>;
export type Organizacao = z.infer<typeof organizacaoSchema>;
export type RegiaoInfo = z.infer<typeof regiaoInfoSchema>;
export type UFInfo = z.infer<typeof ufInfoSchema>;
export type CategoriaInfo = z.infer<typeof categoriaInfoSchema>;
export type OrganizacaoInfo = z.infer<typeof organizacaoInfoSchema>;
export type MunicipioInfo = z.infer<typeof municipioInfoSchema>;
export type RespostaMunicipios = z.infer<typeof respostaMunicipiosSchema>;
export type Saude = z.infer<typeof saudeSchema>;
export type DimensaoOferta = z.infer<typeof dimensaoOfertaSchema>;
export type Metadados = z.infer<typeof metadadosSchema>;
export type IndicadorInfo = z.infer<typeof indicadorInfoSchema>;
export type FiltrosResposta = z.infer<typeof filtrosRespostaSchema>;
export type Linha = z.infer<typeof linhaSchema>;
export type RespostaIndicador = z.infer<typeof respostaIndicadorSchema>;
export type EnvelopeErro = z.infer<typeof envelopeErroSchema>;
export type AreaCine = z.infer<typeof areaCineSchema>;
export type Grau = z.infer<typeof grauSchema>;
export type Eixo = z.infer<typeof eixoSchema>;
export type OrdemInstituicoes = z.infer<typeof ordemInstituicoesSchema>;
export type LinhaComposicao = z.infer<typeof linhaComposicaoSchema>;
export type RespostaComposicao = z.infer<typeof respostaComposicaoSchema>;
export type LinhaInstituicao = z.infer<typeof linhaInstituicaoSchema>;
export type RespostaInstituicoes = z.infer<typeof respostaInstituicoesSchema>;
export type BaseFluxo = z.infer<typeof baseFluxoSchema>;
export type Agrupamento = z.infer<typeof agrupamentoSchema>;
export type RazaoInfo = z.infer<typeof razaoInfoSchema>;
export type ValorRazao = z.infer<typeof valorRazaoSchema>;
export type LinhaRazao = z.infer<typeof linhaRazaoSchema>;
export type RespostaRazao = z.infer<typeof respostaRazaoSchema>;
export type NivelMalha = z.infer<typeof nivelMalhaSchema>;
export type LinhaCoropletico = z.infer<typeof linhaCoropleticoSchema>;
export type ClasseCoropletico = z.infer<typeof classeCoropleticoSchema>;
export type RespostaCoropletico = z.infer<typeof respostaCoropleticoSchema>;
export type NivelComparacao = z.infer<typeof nivelComparacaoSchema>;
export type UnidadeComparada = z.infer<typeof unidadeComparadaSchema>;
export type ValorComparado = z.infer<typeof valorComparadoSchema>;
export type IndicadorComparado = z.infer<typeof indicadorComparadoSchema>;
export type RespostaComparacao = z.infer<typeof respostaComparacaoSchema>;
/** Feição da malha: polígono com o código IBGE em `codarea` (2 dígitos na UF, 7 no município). */
export type FeicaoMalha = Feature<Polygon | MultiPolygon, { codarea: string }>;
export type Malha = FeatureCollection<Polygon | MultiPolygon, { codarea: string }>;
