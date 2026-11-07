/**
 * Estilo do mapa, montado em código. Não há basemap nem tiles de terceiros: o fundo é a própria
 * malha do IBGE servida pela API (UFs como "terra"), e por isso o mapa funciona sem internet.
 * Também não há servidor de fontes (`glyphs`): sem ele, o MapLibre desenha o texto dos rótulos
 * com a fonte do navegador.
 *
 * Só tipos são importados de `maplibre-gl` aqui — o módulo em si só carrega no navegador.
 */
import type { ExpressionSpecification, LayerSpecification, StyleSpecification } from "maplibre-gl";

import type { NivelMalha } from "@/lib/api/schemas";

import { COR_HACHURA } from "./geo";
import type { ModoMapa } from "./search";

export const FONTE_UFS = "ufs";
export const FONTE_MUNICIPIOS = "municipios";
export const FONTE_ROTULOS = "rotulos-uf";
export const FONTE_IES = "ies";
export const FONTE_CALOR = "calor";
export const IMAGEM_HACHURA = "hachura";

export const CAMADA = {
  terra: "terra",
  ufPreenchimento: "coropletico-uf",
  ufHachura: "coropletico-uf-hachura",
  municipioPreenchimento: "coropletico-municipio",
  municipioHachura: "coropletico-municipio-hachura",
  municipioLinha: "coropletico-municipio-linha",
  ufContorno: "ufs-contorno",
  ufDestaque: "ufs-destaque",
  municipioDestaque: "municipios-destaque",
  calor: "calor",
  calorCirculos: "calor-municipios",
  calorSelecionado: "calor-selecionado",
  clusters: "clusters",
  pontos: "pontos",
  pontoSelecionado: "ponto-selecionado",
  clusterRotulo: "clusters-rotulo",
  ufRotulo: "ufs-rotulo",
} as const;

const COR_FUNDO = "#f2f5f9";
const COR_TERRA = "#e3e9ef";
const COR_CONTORNO = "#5f7286";
const COR_DESTAQUE = "#10243a";
const COR_PONTO = "#0f766e";
const COR_CLUSTER = "#134e4a";
const COR_CALOR_PONTO = "#7f2704";

/** Acima deste zoom todo município é um ponto próprio (as 5.571 coordenadas são distintas). */
export const ZOOM_MAXIMO_DE_CLUSTER = 7;
export const ZOOM_MAXIMO = 11;
/** Zoom a partir do qual o mapa de calor mostra os municípios, para ler o valor exato. */
export const ZOOM_DOS_MUNICIPIOS_NO_CALOR = 6;

/** Rampa do mapa de calor: do transparente ao escuro, um só matiz. Sem números: é relativa. */
export const RAMPA_CALOR = ["#fee6ce", "#fdae6b", "#f16913", "#a63603", "#5a1a02"] as const;

/** Estilo inicial: só o fundo. Fontes e camadas entram depois de o mapa carregar. */
export function estiloInicial(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [{ id: "fundo", type: "background", paint: { "background-color": COR_FUNDO } }],
  };
}

const estado = (chave: string): ExpressionSpecification => [
  "boolean",
  ["feature-state", chave],
  false,
];

/** Preenchimento e hachura de uma malha, pintados pelo `feature-state` de cada unidade. */
function camadasDeUnidades(
  fonte: string,
  preenchimento: string,
  hachura: string,
): LayerSpecification[] {
  return [
    {
      id: preenchimento,
      type: "fill",
      source: fonte,
      layout: { visibility: "none" },
      paint: {
        // A cor de cada unidade chega por `setFeatureState` (classe atribuída pela API): trocar
        // de filtro não recria a fonte nem reenvia a geometria. Sem estado = fora do recorte.
        "fill-color": ["to-color", ["feature-state", "cor"], "rgba(0,0,0,0)"],
        "fill-outline-color": "rgba(0,0,0,0)",
      },
    },
    {
      id: hachura,
      type: "fill",
      source: fonte,
      layout: { visibility: "none" },
      paint: {
        // Sem registro de oferta: cinza + hachura, para não depender só da cor.
        "fill-pattern": IMAGEM_HACHURA,
        "fill-opacity": ["case", estado("semRegistro"), 1, 0],
      },
    },
  ];
}

function camadaDeDestaque(id: string, fonte: string): LayerSpecification {
  return {
    id,
    type: "line",
    source: fonte,
    layout: { visibility: "none", "line-join": "round" },
    paint: {
      "line-color": COR_DESTAQUE,
      "line-width": ["case", estado("selecionado"), 3, estado("hover"), 1.5, 0],
    },
  };
}

function camadaDeSelecao(id: string, fonte: string): LayerSpecification {
  return {
    id,
    type: "circle",
    source: fonte,
    layout: { visibility: "none" },
    // O filtro é trocado pelo código do município selecionado.
    filter: ["==", ["get", "codigo"], ""],
    paint: {
      "circle-radius": 14,
      "circle-color": "rgba(0,0,0,0)",
      "circle-stroke-color": COR_DESTAQUE,
      "circle-stroke-width": 2.5,
    },
  };
}

/** Camadas que existem desde o início, na ordem de desenho (as municipais entram depois). */
export function camadasBase(): LayerSpecification[] {
  return [
    { id: CAMADA.terra, type: "fill", source: FONTE_UFS, paint: { "fill-color": COR_TERRA } },
    ...camadasDeUnidades(FONTE_UFS, CAMADA.ufPreenchimento, CAMADA.ufHachura),
    {
      id: CAMADA.ufContorno,
      type: "line",
      source: FONTE_UFS,
      layout: { "line-join": "round" },
      paint: {
        "line-color": COR_CONTORNO,
        "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 8, 1.6],
      },
    },
    camadaDeDestaque(CAMADA.ufDestaque, FONTE_UFS),
    {
      // Siglas das UFs: abaixo dos pontos e do calor, para os círculos não disputarem com o texto.
      id: CAMADA.ufRotulo,
      type: "symbol",
      source: FONTE_ROTULOS,
      layout: {
        "text-field": ["get", "sigla"],
        "text-font": ["sans-serif"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 3, 10, 7, 14],
      },
      paint: {
        "text-color": COR_DESTAQUE,
        "text-halo-color": "rgba(255,255,255,0.85)",
        "text-halo-width": 1.5,
      },
    },
    {
      id: CAMADA.calor,
      type: "heatmap",
      source: FONTE_CALOR,
      layout: { visibility: "none" },
      paint: {
        // Peso linear (valor ÷ maior valor da resposta), sem log nem raiz, e intensidade fixa:
        // o calor é a soma dos pesos próximos, atenuada pela distância.
        "heatmap-weight": ["get", "peso"],
        "heatmap-intensity": 1,
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 14, 6, 24, 9, 40, 11, 60],
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(254,230,206,0)",
          0.05,
          RAMPA_CALOR[0],
          0.25,
          RAMPA_CALOR[1],
          0.5,
          RAMPA_CALOR[2],
          0.75,
          RAMPA_CALOR[3],
          1,
          RAMPA_CALOR[4],
        ],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.9, 10, 0.45],
      },
    },
    {
      id: CAMADA.calorCirculos,
      type: "circle",
      source: FONTE_CALOR,
      minzoom: ZOOM_DOS_MUNICIPIOS_NO_CALOR,
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 2.5, 10, 5],
        "circle-color": COR_CALOR_PONTO,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1,
        "circle-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 8, 0.9],
        "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 6, 0.35, 8, 0.9],
      },
    },
    camadaDeSelecao(CAMADA.calorSelecionado, FONTE_CALOR),
    {
      id: CAMADA.clusters,
      type: "circle",
      source: FONTE_IES,
      filter: ["has", "point_count"],
      layout: { visibility: "none" },
      paint: {
        "circle-color": COR_CLUSTER,
        "circle-opacity": 0.88,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1.5,
        "circle-radius": raioDosClusters(1),
      },
    },
    {
      id: CAMADA.pontos,
      type: "circle",
      source: FONTE_IES,
      filter: ["!", ["has", "point_count"]],
      layout: { visibility: "none" },
      paint: {
        "circle-color": COR_PONTO,
        "circle-opacity": 0.8,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 1,
        "circle-radius": raioDosPontos(1),
      },
    },
    camadaDeSelecao(CAMADA.pontoSelecionado, FONTE_IES),
    {
      id: CAMADA.clusterRotulo,
      type: "symbol",
      source: FONTE_IES,
      filter: ["has", "point_count"],
      layout: {
        visibility: "none",
        // IES somadas no agrupamento (`clusterProperties`), nunca `point_count` — que contaria
        // municípios.
        "text-field": ["number-format", ["get", "ies"], { locale: "pt-BR" }],
        "text-font": ["sans-serif"],
        "text-size": 12,
        "text-allow-overlap": true,
      },
      paint: { "text-color": "#ffffff" },
    },
  ];
}

/** Camadas da malha municipal, com a camada antes da qual cada uma é inserida. */
export function camadasMunicipais(): Array<{ camada: LayerSpecification; antes: string }> {
  const [preenchimento, hachura] = camadasDeUnidades(
    FONTE_MUNICIPIOS,
    CAMADA.municipioPreenchimento,
    CAMADA.municipioHachura,
  ) as [LayerSpecification, LayerSpecification];
  return [
    { camada: preenchimento, antes: CAMADA.ufContorno },
    { camada: hachura, antes: CAMADA.ufContorno },
    {
      camada: {
        id: CAMADA.municipioLinha,
        type: "line",
        source: FONTE_MUNICIPIOS,
        layout: { visibility: "none" },
        paint: {
          // 5.571 contornos na escala do país viram ruído: só aparecem ao aproximar.
          "line-color": "#ffffff",
          "line-width": 0.5,
          "line-opacity": ["interpolate", ["linear"], ["zoom"], 4.5, 0, 6.5, 0.8],
        },
      },
      antes: CAMADA.ufContorno,
    },
    {
      camada: camadaDeDestaque(CAMADA.municipioDestaque, FONTE_MUNICIPIOS),
      antes: CAMADA.ufRotulo,
    },
  ];
}

/**
 * Raio do ponto de um município: proporcional à RAIZ do nº de IES, para que a área do círculo —
 * e não o raio — acompanhe o valor. `maximo` é o maior município da resposta.
 */
export function raioDosPontos(maximo: number): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["get", "valor"]],
    1,
    4,
    Math.max(Math.sqrt(maximo), 2),
    22,
  ];
}

/** Raio do agrupamento: raiz das IES somadas nele; `total` é a soma de toda a resposta. */
export function raioDosClusters(total: number): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["get", "ies"]],
    1,
    12,
    Math.max(Math.sqrt(total), 2),
    38,
  ];
}

/** O que cada modo mostra. Pontos nunca se sobrepõem ao coroplético (ver README, Fase 10). */
export function camadasVisiveis(
  modo: ModoMapa | "nenhum",
  unidade: NivelMalha | undefined,
): Set<string> {
  switch (modo) {
    case "coropletico":
      return unidade === "municipio"
        ? new Set([
            CAMADA.municipioPreenchimento,
            CAMADA.municipioHachura,
            CAMADA.municipioLinha,
            CAMADA.municipioDestaque,
          ])
        : new Set([CAMADA.ufPreenchimento, CAMADA.ufHachura, CAMADA.ufDestaque]);
    case "pontos":
      return new Set([
        CAMADA.clusters,
        CAMADA.pontos,
        CAMADA.pontoSelecionado,
        CAMADA.clusterRotulo,
      ]);
    case "calor":
      return new Set([CAMADA.calor, CAMADA.calorCirculos, CAMADA.calorSelecionado]);
    case "nenhum":
      return new Set();
  }
}

/** Camadas cuja visibilidade depende do modo (as demais ficam sempre ligadas). */
export const CAMADAS_DE_MODO: readonly string[] = [
  CAMADA.ufPreenchimento,
  CAMADA.ufHachura,
  CAMADA.ufDestaque,
  CAMADA.municipioPreenchimento,
  CAMADA.municipioHachura,
  CAMADA.municipioLinha,
  CAMADA.municipioDestaque,
  CAMADA.calor,
  CAMADA.calorCirculos,
  CAMADA.calorSelecionado,
  CAMADA.clusters,
  CAMADA.pontos,
  CAMADA.pontoSelecionado,
  CAMADA.clusterRotulo,
];

/** Hachura diagonal de 8×8 px, transparente entre os traços, gerada em código (sem arquivo). */
export function imagemDaHachura(): { width: number; height: number; data: Uint8Array } {
  const lado = 8;
  const data = new Uint8Array(lado * lado * 4);
  const r = Number.parseInt(COR_HACHURA.slice(1, 3), 16);
  const g = Number.parseInt(COR_HACHURA.slice(3, 5), 16);
  const b = Number.parseInt(COR_HACHURA.slice(5, 7), 16);
  for (let y = 0; y < lado; y += 1) {
    for (let x = 0; x < lado; x += 1) {
      if ((x + y) % lado !== 0) continue;
      const i = (y * lado + x) * 4;
      data[i] = r;
      data[i + 1] = g;
      data[i + 2] = b;
      data[i + 3] = 255;
    }
  }
  return { width: lado, height: lado, data };
}
