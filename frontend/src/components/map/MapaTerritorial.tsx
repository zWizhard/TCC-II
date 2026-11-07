import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useId, useRef, useState } from "react";
import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as MapaMaplibre, MapLayerMouseEvent } from "maplibre-gl";

import { Skeleton } from "@/components/ui/skeleton";
import type { Malha, NivelMalha } from "@/lib/api/schemas";

import {
  CAMADA,
  CAMADAS_DE_MODO,
  camadasBase,
  camadasMunicipais,
  camadasVisiveis,
  estiloInicial,
  FONTE_CALOR,
  FONTE_IES,
  FONTE_MUNICIPIOS,
  FONTE_ROTULOS,
  FONTE_UFS,
  IMAGEM_HACHURA,
  imagemDaHachura,
  raioDosClusters,
  raioDosPontos,
  ZOOM_MAXIMO,
  ZOOM_MAXIMO_DE_CLUSTER,
} from "./estilo";
import type { ColecaoDePontos, ColecaoDeRotulos, EstadoUnidade, Limites } from "./geo";

/** O que o mapa desenha além da base. Tudo já vem pronto da rota: o mapa não consulta a API. */
export type CamadaDoMapa =
  | { modo: "nenhum" }
  | {
      modo: "coropletico";
      unidade: NivelMalha;
      /** Só é exigida (e baixada) quando a unidade é o município. */
      malhaMunicipios: Malha | undefined;
      /** Cor de cada unidade, por código IBGE (`codarea`). */
      estados: ReadonlyMap<string, EstadoUnidade>;
    }
  | {
      modo: "pontos";
      pontos: ColecaoDePontos;
      /** Maior nº de IES em um município e soma da resposta: referências dos raios. */
      maximo: number;
      total: number;
    }
  | { modo: "calor"; pontos: ColecaoDePontos };

/** Unidade sob o cursor ou clicada. */
export type AlvoDoMapa =
  | { tipo: "uf"; codigo: string }
  | { tipo: "municipio"; codigo: string }
  | { tipo: "cluster"; ies: number; municipios: number };

export type Enquadramento = {
  /** Identidade do território na URL (`chaveDoTerritorio`). */
  chave: string;
  limites: Limites;
  /** Cresce quando a caixa do mesmo território fica mais precisa (UF → município). */
  precisao: number;
};

type MapaTerritorialProps = {
  /** Descrição do que o mapa mostra agora (modo, indicador, território), para `aria-label`. */
  descricao: string;
  malhaUfs: Malha;
  rotulosUf: ColecaoDeRotulos;
  camada: CamadaDoMapa;
  /** Município destacado (contorno), quando há um selecionado nos filtros. */
  municipioSelecionado: string | undefined;
  enquadramento: Enquadramento;
  /** Linhas da dica de uma unidade (a primeira é o título). `null` = unidade fora do recorte. */
  descrever: (alvo: AlvoDoMapa) => string[] | null;
  onSelecionar: (alvo: Exclude<AlvoDoMapa, { tipo: "cluster" }>) => void;
};

const VAZIA: FeatureCollection = { type: "FeatureCollection", features: [] };
const MARGEM = 28;

const TEXTOS = {
  "Map.Title": "Mapa interativo",
  "NavigationControl.ZoomIn": "Aproximar",
  "NavigationControl.ZoomOut": "Afastar",
  "AttributionControl.ToggleAttribution": "Mostrar ou ocultar a fonte da malha",
  "CooperativeGesturesHandler.WindowsHelpText": "Use Ctrl + rolagem para aproximar o mapa",
  "CooperativeGesturesHandler.MacHelpText": "Use ⌘ + rolagem para aproximar o mapa",
  "CooperativeGesturesHandler.MobileHelpText": "Use dois dedos para mover o mapa",
};

/**
 * O MapLibre precisa de `window` e de WebGL: só é importado aqui, dentro de um efeito, e nunca
 * no servidor (a rota é renderizada por SSR). O worker é um arquivo à parte, servido pelo
 * próprio build — nada vem de CDN.
 */
async function carregarMaplibre() {
  const [maplibre, worker] = await Promise.all([
    import("maplibre-gl"),
    import("maplibre-gl/dist/maplibre-gl-worker.mjs?url"),
  ]);
  maplibre.setWorkerUrl(worker.default);
  return maplibre;
}

function semAnimacao(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Mapa MapLibre da Distribuição Territorial. Só desenha e devolve eventos: recebe as camadas
 * prontas e avisa qual unidade foi escolhida. Mover ou aproximar o mapa não altera nada fora dele.
 */
export function MapaTerritorial(props: MapaTerritorialProps) {
  const { descricao, rotulosUf, camada, municipioSelecionado, enquadramento } = props;
  const conteinerRef = useRef<HTMLDivElement>(null);
  const dicaRef = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<MapaMaplibre | null>(null);
  // Os ouvintes do mapa são registrados uma vez; leem as props mais recentes por aqui.
  const propsRef = useRef(props);
  const pintadoRef = useRef<{ fonte: string; estados: unknown } | null>(null);
  const selecionadoRef = useRef<string | undefined>(undefined);
  const enquadradoRef = useRef<{ chave: string; precisao: number } | null>(null);
  const ouvirRef = useRef<((camadaId: string, fonteDoHover?: string) => void) | null>(null);
  const [estado, setEstado] = useState<"carregando" | "pronto" | "erro">("carregando");
  const [dica, setDica] = useState<{ chave: string; linhas: string[] } | null>(null);
  const ajudaId = useId();

  useEffect(() => {
    propsRef.current = props;
  });

  useEffect(() => {
    const conteiner = conteinerRef.current;
    if (!conteiner) return;
    let cancelado = false;
    let mapa: MapaMaplibre | undefined;
    let observador: ResizeObserver | undefined;

    void carregarMaplibre()
      .then((maplibre) => {
        if (cancelado) return;
        const inicial = propsRef.current;
        mapa = new maplibre.Map({
          container: conteiner,
          style: estiloInicial(),
          bounds: inicial.enquadramento.limites,
          fitBoundsOptions: { padding: MARGEM },
          maxZoom: ZOOM_MAXIMO,
          minZoom: 2,
          renderWorldCopies: false,
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
          // Sem isto, rolar a página sobre o mapa (ou arrastar com um dedo no celular) prenderia
          // o usuário dentro dele.
          cooperativeGestures: true,
          locale: TEXTOS,
          attributionControl: { compact: true, customAttribution: "Malha territorial: IBGE" },
        });
        const criado = mapa;
        mapaRef.current = criado;
        enquadradoRef.current = {
          chave: inicial.enquadramento.chave,
          precisao: inicial.enquadramento.precisao,
        };
        criado.touchZoomRotate.disableRotation();
        criado.keyboard.disableRotation();
        criado.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");

        let hover: { fonte: string; codigo: string } | null = null;
        const limparHover = () => {
          if (hover)
            criado.setFeatureState({ source: hover.fonte, id: hover.codigo }, { hover: false });
          hover = null;
          criado.getCanvas().style.cursor = "";
          setDica(null);
        };

        const alvoDe = (camadaId: string, evento: MapLayerMouseEvent): AlvoDoMapa | null => {
          const propriedades = evento.features?.[0]?.properties;
          if (!propriedades) return null;
          if (camadaId === CAMADA.clusters) {
            return {
              tipo: "cluster",
              ies: Number(propriedades["ies"]),
              municipios: Number(propriedades["point_count"]),
            };
          }
          if (camadaId === CAMADA.ufPreenchimento) {
            return { tipo: "uf", codigo: String(propriedades["codarea"]) };
          }
          if (camadaId === CAMADA.municipioPreenchimento) {
            return { tipo: "municipio", codigo: String(propriedades["codarea"]) };
          }
          return { tipo: "municipio", codigo: String(propriedades["codigo"]) };
        };

        const ouvir = (camadaId: string, fonteDoHover?: string) => {
          criado.on("mousemove", camadaId, (evento) => {
            const alvo = alvoDe(camadaId, evento);
            const linhas = alvo && propsRef.current.descrever(alvo);
            if (!alvo || !linhas) {
              limparHover();
              return;
            }
            criado.getCanvas().style.cursor = "pointer";
            if (fonteDoHover && alvo.tipo !== "cluster" && hover?.codigo !== alvo.codigo) {
              if (hover) {
                criado.setFeatureState({ source: hover.fonte, id: hover.codigo }, { hover: false });
              }
              hover = { fonte: fonteDoHover, codigo: alvo.codigo };
              criado.setFeatureState({ source: fonteDoHover, id: alvo.codigo }, { hover: true });
            }
            const caixa = dicaRef.current;
            if (caixa) {
              const { x, y } = evento.point;
              // Abre para o lado em que há espaço, para não sair do mapa.
              const paraEsquerda = x > conteiner.clientWidth / 2;
              const paraCima = y > conteiner.clientHeight / 2;
              caixa.style.left = `${x}px`;
              caixa.style.top = `${y}px`;
              caixa.style.transform = `translate(${paraEsquerda ? "calc(-100% - 12px)" : "12px"}, ${paraCima ? "calc(-100% - 12px)" : "12px"})`;
            }
            const chave = `${camadaId}:${linhas.join("|")}`;
            setDica((atual) => (atual?.chave === chave ? atual : { chave, linhas }));
          });
          criado.on("mouseleave", camadaId, limparHover);
          criado.on("click", camadaId, (evento) => {
            const alvo = alvoDe(camadaId, evento);
            if (!alvo) return;
            if (alvo.tipo === "cluster") {
              // Agrupamento: aproxima até ele se desfazer em municípios.
              const feicao = evento.features?.[0];
              const id = Number(feicao?.properties["cluster_id"]);
              const fonte = criado.getSource<GeoJSONSource>(FONTE_IES);
              if (!fonte || feicao?.geometry.type !== "Point") return;
              const [longitude = 0, latitude = 0] = feicao.geometry.coordinates;
              void fonte.getClusterExpansionZoom(id).then((zoom) => {
                criado.easeTo({
                  center: [longitude, latitude],
                  zoom,
                  duration: semAnimacao() ? 0 : 500,
                });
              });
              return;
            }
            // Unidade fora do recorte dos filtros não tem dado: não é selecionável.
            if (propsRef.current.descrever(alvo) !== null) propsRef.current.onSelecionar(alvo);
          });
        };

        criado.on("load", () => {
          if (cancelado) return;
          criado.addImage(IMAGEM_HACHURA, imagemDaHachura());
          criado.addSource(FONTE_UFS, {
            type: "geojson",
            data: propsRef.current.malhaUfs,
            // O código IBGE vira o id da feição: é por ele que cada unidade recebe a sua cor.
            promoteId: "codarea",
          });
          criado.addSource(FONTE_ROTULOS, { type: "geojson", data: propsRef.current.rotulosUf });
          criado.addSource(FONTE_IES, {
            type: "geojson",
            data: VAZIA,
            cluster: true,
            clusterMaxZoom: ZOOM_MAXIMO_DE_CLUSTER,
            clusterRadius: 48,
            // Cada ponto é um município com N IES: o agrupamento soma as IES.
            clusterProperties: { ies: ["+", ["get", "valor"]] },
          });
          criado.addSource(FONTE_CALOR, { type: "geojson", data: VAZIA });
          for (const base of camadasBase()) criado.addLayer(base);
          ouvir(CAMADA.ufPreenchimento, FONTE_UFS);
          ouvir(CAMADA.clusters);
          ouvir(CAMADA.pontos);
          ouvir(CAMADA.calorCirculos);
          // As camadas municipais entram depois, com a malha; os ouvintes são registrados lá.
          ouvirRef.current = ouvir;
          setEstado("pronto");
        });

        // Mudança de layout (legenda que desce no celular, painel que abre) redimensiona o canvas.
        observador = new ResizeObserver(() => criado.resize());
        observador.observe(conteiner);
      })
      .catch(() => {
        if (!cancelado) setEstado("erro");
      });

    return () => {
      cancelado = true;
      observador?.disconnect();
      mapa?.remove();
      mapaRef.current = null;
      pintadoRef.current = null;
      selecionadoRef.current = undefined;
    };
  }, []);

  // Rótulos das UFs: chegam depois da malha (dependem da tabela código → sigla).
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || estado !== "pronto") return;
    void mapa.getSource<GeoJSONSource>(FONTE_ROTULOS)?.setData(rotulosUf);
  }, [estado, rotulosUf]);

  // Camada ativa: visibilidade, dados dos pontos e cor das unidades.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || estado !== "pronto") return;

    if (
      camada.modo === "coropletico" &&
      camada.malhaMunicipios &&
      !mapa.getSource(FONTE_MUNICIPIOS)
    ) {
      mapa.addSource(FONTE_MUNICIPIOS, {
        type: "geojson",
        data: camada.malhaMunicipios,
        promoteId: "codarea",
      });
      for (const { camada: municipal, antes } of camadasMunicipais()) {
        mapa.addLayer(municipal, antes);
      }
      ouvirRef.current?.(CAMADA.municipioPreenchimento, FONTE_MUNICIPIOS);
    }

    const visiveis = camadasVisiveis(
      camada.modo,
      camada.modo === "coropletico" ? camada.unidade : undefined,
    );
    for (const id of CAMADAS_DE_MODO) {
      if (mapa.getLayer(id)) {
        mapa.setLayoutProperty(id, "visibility", visiveis.has(id) ? "visible" : "none");
      }
    }

    if (camada.modo === "coropletico") {
      const fonte = camada.unidade === "uf" ? FONTE_UFS : FONTE_MUNICIPIOS;
      const pintado = pintadoRef.current;
      const mudou = pintado?.fonte !== fonte || pintado.estados !== camada.estados;
      if (mapa.getSource(fonte) && mudou) {
        // Troca de filtro = troca de estado das feições; a geometria não é reenviada.
        mapa.removeFeatureState({ source: fonte });
        for (const [codigo, unidade] of camada.estados) {
          mapa.setFeatureState({ source: fonte, id: codigo }, unidade);
        }
        pintadoRef.current = { fonte, estados: camada.estados };
        selecionadoRef.current = undefined;
      }
    } else if (camada.modo === "pontos") {
      void mapa.getSource<GeoJSONSource>(FONTE_IES)?.setData(camada.pontos);
      mapa.setPaintProperty(CAMADA.pontos, "circle-radius", raioDosPontos(camada.maximo));
      mapa.setPaintProperty(CAMADA.clusters, "circle-radius", raioDosClusters(camada.total));
    } else if (camada.modo === "calor") {
      void mapa.getSource<GeoJSONSource>(FONTE_CALOR)?.setData(camada.pontos);
    }
  }, [estado, camada]);

  // Município selecionado: contorno no polígono (coroplético) ou anel no ponto.
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || estado !== "pronto") return;
    const filtro = ["==", ["get", "codigo"], municipioSelecionado ?? ""] as [
      "==",
      ["get", string],
      string,
    ];
    mapa.setFilter(CAMADA.pontoSelecionado, filtro);
    mapa.setFilter(CAMADA.calorSelecionado, filtro);
    if (!mapa.getSource(FONTE_MUNICIPIOS)) return;
    const anterior = selecionadoRef.current;
    if (anterior && anterior !== municipioSelecionado) {
      mapa.setFeatureState({ source: FONTE_MUNICIPIOS, id: anterior }, { selecionado: false });
    }
    if (municipioSelecionado) {
      mapa.setFeatureState(
        { source: FONTE_MUNICIPIOS, id: municipioSelecionado },
        { selecionado: true },
      );
    }
    selecionadoRef.current = municipioSelecionado;
  }, [estado, camada, municipioSelecionado]);

  // Enquadramento: reage só ao território da URL (ou à caixa dele ficar mais precisa). O mapa
  // nunca escreve o próprio movimento na URL, então não há laço.
  const { chave, precisao, limites } = enquadramento;
  const limitesRef = useRef(limites);
  useEffect(() => {
    limitesRef.current = limites;
  });
  useEffect(() => {
    const mapa = mapaRef.current;
    if (!mapa || estado !== "pronto") return;
    const anterior = enquadradoRef.current;
    if (anterior && anterior.chave === chave && anterior.precisao >= precisao) return;
    enquadradoRef.current = { chave, precisao };
    mapa.fitBounds(limitesRef.current, {
      padding: MARGEM,
      maxZoom: 9,
      duration: semAnimacao() ? 0 : 600,
    });
  }, [estado, chave, precisao]);

  return (
    <div role="region" aria-label={descricao} aria-describedby={ajudaId} className="relative">
      <div
        ref={conteinerRef}
        data-testid="mapa-conteiner"
        className="h-[60vh] min-h-[320px] max-h-[720px] w-full overflow-hidden rounded-md border border-border bg-map"
      />
      {estado === "carregando" && (
        <div role="status" aria-live="polite" className="absolute inset-0">
          <span className="sr-only">Carregando o mapa…</span>
          <Skeleton className="size-full" />
        </div>
      )}
      {estado === "erro" && (
        <div
          role="alert"
          className="absolute inset-0 flex items-center justify-center rounded-md bg-card p-6 text-center text-sm leading-6 text-muted-foreground"
        >
          Não foi possível iniciar o mapa neste navegador (ele exige WebGL). Os mesmos dados estão
          na legenda e na tabela desta página.
        </div>
      )}
      <div
        ref={dicaRef}
        data-testid="mapa-dica"
        aria-hidden="true"
        className="pointer-events-none absolute left-0 top-0 z-10 max-w-64 rounded-md border border-border bg-card px-3 py-2 text-xs leading-5 text-muted-foreground shadow-soft"
        hidden={dica === null}
      >
        {dica?.linhas.map((linha, i) =>
          i === 0 ? (
            <p key={linha} className="font-semibold text-foreground">
              {linha}
            </p>
          ) : (
            <p key={linha}>{linha}</p>
          ),
        )}
      </div>
      <p id={ajudaId} className="mt-2 text-[11px] leading-4 text-muted-foreground">
        Com o foco no mapa, as setas movem e as teclas + e − aproximam e afastam; com o mouse, use
        Ctrl + rolagem. Passe o cursor para ver os valores e clique para selecionar. Tudo o que o
        mapa mostra está também na tabela abaixo, onde cada unidade pode ser selecionada pelo
        teclado.
      </p>
    </div>
  );
}
