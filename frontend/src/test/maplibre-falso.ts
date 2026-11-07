/**
 * Substituto do `maplibre-gl` nos testes: o jsdom não tem WebGL. Não desenha nada — registra o
 * que a aplicação pediu ao mapa (fontes, camadas, estado das feições, enquadramentos) e permite
 * disparar os eventos que o usuário provocaria (`disparar("click", camada, evento)`).
 */
type Ouvinte = (evento: unknown) => void;
type Estado = Record<string, unknown>;

export class MapaFalso {
  static instancias: MapaFalso[] = [];

  readonly opcoes: Record<string, unknown>;
  readonly fontes = new Map<string, { spec: Record<string, unknown>; dados: unknown }>();
  readonly camadas: Array<{
    id: string;
    antes: string | undefined;
    spec: Record<string, unknown>;
  }> = [];
  readonly estados = new Map<string, Map<string, Estado>>();
  readonly visibilidade = new Map<string, unknown>();
  readonly pintura = new Map<string, unknown>();
  readonly filtros = new Map<string, unknown>();
  readonly imagens: string[] = [];
  readonly enquadramentos: unknown[] = [];
  readonly aproximacoes: unknown[] = [];
  removido = false;
  private readonly ouvintes: Array<{ tipo: string; camada: string | undefined; fn: Ouvinte }> = [];
  private readonly canvas = { style: { cursor: "" } };

  readonly touchZoomRotate = { disableRotation: () => {} };
  readonly keyboard = { disableRotation: () => {} };

  constructor(opcoes: Record<string, unknown>) {
    this.opcoes = opcoes;
    MapaFalso.instancias.push(this);
    setTimeout(() => this.disparar("load"), 0);
  }

  on(tipo: string, camadaOuFn: string | Ouvinte, fn?: Ouvinte) {
    if (typeof camadaOuFn === "string") {
      if (fn) this.ouvintes.push({ tipo, camada: camadaOuFn, fn });
    } else {
      this.ouvintes.push({ tipo, camada: undefined, fn: camadaOuFn });
    }
    return this;
  }

  /** Dispara um evento como o MapLibre faria, para os ouvintes daquela camada. */
  disparar(tipo: string, camada?: string, evento: unknown = {}) {
    for (const ouvinte of [...this.ouvintes]) {
      if (ouvinte.tipo === tipo && ouvinte.camada === camada) ouvinte.fn(evento);
    }
  }

  addControl() {
    return this;
  }

  addImage(id: string) {
    this.imagens.push(id);
    return this;
  }

  addSource(id: string, spec: Record<string, unknown>) {
    this.fontes.set(id, { spec, dados: spec["data"] });
    return this;
  }

  getSource(id: string) {
    const fonte = this.fontes.get(id);
    if (!fonte) return undefined;
    return {
      setData: async (dados: unknown) => {
        fonte.dados = dados;
      },
      getClusterExpansionZoom: async () => 6,
    };
  }

  addLayer(spec: Record<string, unknown>, antes?: string) {
    const id = String(spec["id"]);
    this.camadas.push({ id, antes, spec });
    const layout = spec["layout"] as Record<string, unknown> | undefined;
    this.visibilidade.set(id, layout?.["visibility"] ?? "visible");
    return this;
  }

  getLayer(id: string) {
    return this.camadas.find((c) => c.id === id);
  }

  setLayoutProperty(id: string, nome: string, valor: unknown) {
    if (nome === "visibility") this.visibilidade.set(id, valor);
    return this;
  }

  setPaintProperty(id: string, nome: string, valor: unknown) {
    this.pintura.set(`${id}.${nome}`, valor);
    return this;
  }

  setFilter(id: string, filtro: unknown) {
    this.filtros.set(id, filtro);
    return this;
  }

  setFeatureState(alvo: { source: string; id: string }, estado: Estado) {
    const daFonte = this.estados.get(alvo.source) ?? new Map<string, Estado>();
    this.estados.set(alvo.source, daFonte);
    daFonte.set(alvo.id, { ...daFonte.get(alvo.id), ...estado });
    return this;
  }

  removeFeatureState(alvo: { source: string }) {
    this.estados.delete(alvo.source);
    return this;
  }

  fitBounds(limites: unknown, opcoes?: unknown) {
    this.enquadramentos.push({ limites, opcoes });
    return this;
  }

  easeTo(opcoes: unknown) {
    this.aproximacoes.push(opcoes);
    return this;
  }

  getCanvas() {
    return this.canvas;
  }

  resize() {
    return this;
  }

  remove() {
    this.removido = true;
  }

  /** Camadas visíveis agora, na ordem em que foram adicionadas. */
  visiveis(): string[] {
    return this.camadas.map((c) => c.id).filter((id) => this.visibilidade.get(id) === "visible");
  }
}

// Exportado como `Map` sem criar um nome local que esconderia o `Map` nativo usado acima.
export { MapaFalso as Map };

export class NavigationControl {}

export function setWorkerUrl() {}
