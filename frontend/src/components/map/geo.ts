/**
 * Lógica pura do mapa: tradução das respostas da API para o que o MapLibre desenha, e a pouca
 * geometria necessária para enquadrar e rotular. Nenhum valor de indicador é calculado aqui —
 * classe, razão e totais vêm da API; o que se deriva é só visual (cor, peso relativo, caixa).
 */
import type { FeatureCollection, MultiPolygon, Point, Polygon, Position } from "geojson";

import type { ClasseCoropletico, Linha, Malha, RespostaCoropletico } from "@/lib/api/schemas";

/**
 * Nome das unidades sem numerador. Com filtro de rede, categoria ou organização, a unidade pode
 * ter oferta de outras instituições: o que falta é matrícula das instituições filtradas.
 */
export function rotuloSemRegistro(
  filtros: Pick<RespostaCoropletico["filtros"], "rede" | "categoria" | "organizacao">,
): string {
  return filtros.rede || filtros.categoria || filtros.organizacao
    ? "Sem matrícula registrada nessas instituições"
    : "Sem registro de oferta";
}

/** Caixa envolvente em graus: [oeste, sul, leste, norte]. */
export type Limites = [number, number, number, number];

function aneis(geometria: Polygon | MultiPolygon): Position[][] {
  // Só os anéis externos: buracos não mudam a caixa nem o ponto do rótulo.
  return geometria.type === "Polygon"
    ? geometria.coordinates.slice(0, 1)
    : geometria.coordinates.flatMap((poligono) => poligono.slice(0, 1));
}

export function limitesDaGeometria(geometria: Polygon | MultiPolygon): Limites {
  const limites: Limites = [Infinity, Infinity, -Infinity, -Infinity];
  for (const anel of aneis(geometria)) {
    for (const [x = 0, y = 0] of anel) {
      if (x < limites[0]) limites[0] = x;
      if (y < limites[1]) limites[1] = y;
      if (x > limites[2]) limites[2] = x;
      if (y > limites[3]) limites[3] = y;
    }
  }
  return limites;
}

export function unirLimites(lista: readonly Limites[]): Limites | null {
  if (lista.length === 0) return null;
  return [
    Math.min(...lista.map((l) => l[0])),
    Math.min(...lista.map((l) => l[1])),
    Math.max(...lista.map((l) => l[2])),
    Math.max(...lista.map((l) => l[3])),
  ];
}

/** Caixa das feições cujo `codarea` está em `codigos` (todas, se omitido). Join por código. */
export function limitesDaMalha(malha: Malha, codigos?: ReadonlySet<string>): Limites | null {
  return unirLimites(
    malha.features
      .filter((f) => codigos === undefined || codigos.has(f.properties.codarea))
      .map((f) => limitesDaGeometria(f.geometry)),
  );
}

/** Caixa em torno da coordenada de um município, para enquadrá-lo sem a malha municipal. */
export function limitesDoPonto(longitude: number, latitude: number, margem = 1): Limites {
  return [longitude - margem, latitude - margem, longitude + margem, latitude + margem];
}

/**
 * Caixa ampliada em volta de uma unidade: o município selecionado fica no centro, com os
 * vizinhos à vista — destacar sem contexto impediria a comparação.
 */
export function ampliarLimites([oeste, sul, leste, norte]: Limites, fator = 1): Limites {
  const folga = Math.max(leste - oeste, norte - sul) * fator;
  return [oeste - folga, sul - folga, leste + folga, norte + folga];
}

function areaComSinal(anel: readonly Position[]): number {
  let soma = 0;
  for (let i = 0; i < anel.length - 1; i += 1) {
    const [x1 = 0, y1 = 0] = anel[i] ?? [];
    const [x2 = 0, y2 = 0] = anel[i + 1] ?? [];
    soma += x1 * y2 - x2 * y1;
  }
  return soma / 2;
}

/**
 * Ponto onde escrever o rótulo de uma unidade: o centroide do maior anel externo (ilhas não
 * deslocam o rótulo). É posição de texto, não medida — pode cair fora de um polígono côncavo.
 */
export function pontoDeRotulo(geometria: Polygon | MultiPolygon): [number, number] {
  let maior: Position[] = [];
  let maiorArea = 0;
  for (const anel of aneis(geometria)) {
    const area = Math.abs(areaComSinal(anel));
    if (area > maiorArea) {
      maior = anel;
      maiorArea = area;
    }
  }
  if (maiorArea === 0) {
    const [oeste, sul, leste, norte] = limitesDaGeometria(geometria);
    return [(oeste + leste) / 2, (sul + norte) / 2];
  }
  const area = areaComSinal(maior);
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < maior.length - 1; i += 1) {
    const [x1 = 0, y1 = 0] = maior[i] ?? [];
    const [x2 = 0, y2 = 0] = maior[i + 1] ?? [];
    const cruz = x1 * y2 - x2 * y1;
    cx += (x1 + x2) * cruz;
    cy += (y1 + y2) * cruz;
  }
  return [cx / (6 * area), cy / (6 * area)];
}

export type ColecaoDeRotulos = FeatureCollection<Point, { codigo: string; sigla: string }>;

/** Um rótulo (sigla) por UF da malha. O casamento com a sigla é por código IBGE, nunca por nome. */
export function rotulosDasUfs(
  malha: Malha,
  siglaDoCodigo: ReadonlyMap<string, string>,
): ColecaoDeRotulos {
  return {
    type: "FeatureCollection",
    features: malha.features.flatMap((feicao) => {
      const codigo = feicao.properties.codarea;
      const sigla = siglaDoCodigo.get(codigo);
      if (sigla === undefined) return [];
      return [
        {
          type: "Feature" as const,
          properties: { codigo, sigla },
          geometry: { type: "Point" as const, coordinates: pontoDeRotulo(feicao.geometry) },
        },
      ];
    }),
  };
}

/**
 * Rampa sequencial de um matiz (azul), do claro ao escuro: ordem legível por luminosidade, sem
 * depender de distinguir matizes (segura para daltonismo). Uma lista por número de classes.
 */
const RAMPAS: Record<number, readonly string[]> = {
  1: ["#4292c6"],
  2: ["#bdd7e7", "#2171b5"],
  3: ["#c6dbef", "#6baed6", "#2171b5"],
  4: ["#dbe9f6", "#9ecae1", "#4292c6", "#08519c"],
  5: ["#dbe9f6", "#a6cde4", "#6baed6", "#2f7fbf", "#08488f"],
  6: ["#dbe9f6", "#b5d4e9", "#85bcdb", "#539ecd", "#2676b8", "#08488f"],
  7: ["#dbe9f6", "#bcd7eb", "#94c4df", "#6aaed6", "#4190c6", "#1f6eb3", "#08458a"],
};
const MAXIMO_DE_CLASSES = 7;

/** Cinza neutro, fora da rampa azul: unidade sem registro de oferta (ausência, não zero). */
export const COR_SEM_REGISTRO = "#d9d9d6";
export const COR_HACHURA = "#7a7a76";

/** Cores das classes devolvidas pela API, na ordem em que vieram (da menor para a maior). */
export function coresDasClasses(classes: readonly ClasseCoropletico[]): string[] {
  const quantidade = Math.min(Math.max(classes.length, 1), MAXIMO_DE_CLASSES);
  const rampa = RAMPAS[quantidade] ?? [];
  const ultima = rampa[rampa.length - 1] ?? "#08458a";
  return classes.map((_, posicao) => rampa[posicao] ?? ultima);
}

/** O que o mapa precisa saber de cada unidade para pintá-la. */
export type EstadoUnidade = { cor: string; semRegistro: boolean };

/**
 * Cor de cada unidade do coroplético, por código. A classe é a que a API atribuiu; aqui só se
 * troca o índice pela cor. Unidade sem registro recebe o cinza; unidade fora da resposta (fora
 * do território dos filtros) não entra no mapa e fica sem preenchimento.
 */
export function estadosDoCoropletico(
  dados: Pick<RespostaCoropletico, "classes" | "linhas">,
): Map<string, EstadoUnidade> {
  const cores = coresDasClasses(dados.classes);
  const corDoIndice = new Map(dados.classes.map((classe, i) => [classe.indice, cores[i]]));
  const estados = new Map<string, EstadoUnidade>();
  for (const linha of dados.linhas) {
    const cor = linha.classe === null ? undefined : corDoIndice.get(linha.classe);
    estados.set(
      linha.codigo,
      cor === undefined
        ? { cor: COR_SEM_REGISTRO, semRegistro: true }
        : { cor, semRegistro: false },
    );
  }
  return estados;
}

export type PropriedadesDoPonto = {
  codigo: string;
  nome: string;
  uf: string;
  valor: number;
  /** `valor ÷ maior valor da resposta` (0 a 1): peso linear do mapa de calor. */
  peso: number;
};

export type ColecaoDePontos = FeatureCollection<Point, PropriedadesDoPonto>;

export type PontosDoIndicador = {
  colecao: ColecaoDePontos;
  /** Maior valor entre os pontos: referência das escalas visuais (raio e peso). */
  maximo: number;
  /** Linhas sem coordenada, que não puderam ser desenhadas (continuam na tabela). */
  semCoordenada: number;
};

/**
 * Linhas de um indicador no nível municipal → um ponto por MUNICÍPIO, na coordenada do
 * município. A base não tem coordenada por instituição: nunca se cria um ponto por IES nem se
 * espalham pontos em volta da coordenada.
 */
export function pontosDoIndicador(linhas: readonly Linha[]): PontosDoIndicador {
  const comCoordenada = linhas.filter(
    (l): l is Linha & { latitude: number; longitude: number } =>
      typeof l.latitude === "number" && typeof l.longitude === "number",
  );
  const maximo = comCoordenada.reduce((maior, l) => Math.max(maior, l.valor), 0);
  return {
    colecao: {
      type: "FeatureCollection",
      features: comCoordenada.map((linha) => ({
        type: "Feature",
        properties: {
          codigo: linha.codigo,
          nome: linha.nome,
          uf: linha.uf ?? "",
          valor: linha.valor,
          peso: maximo > 0 ? linha.valor / maximo : 0,
        },
        geometry: { type: "Point", coordinates: [linha.longitude, linha.latitude] },
      })),
    },
    maximo,
    semCoordenada: linhas.length - comCoordenada.length,
  };
}

const MAXIMO_DE_CASAS = 8;

/**
 * Casas decimais das faixas da legenda: o menor número (a partir de 1) com que os limites de
 * classes vizinhas saem diferentes. Com filtros raros os valores chegam a 0,004 por 100 mil, e
 * com uma casa duas classes distintas apareceriam como "0,0 a 0,0".
 */
export function casasDasClasses(
  classes: ReadonlyArray<Pick<ClasseCoropletico, "minimo" | "maximo">>,
): number {
  for (let casas = 1; casas < MAXIMO_DE_CASAS; casas += 1) {
    const distintas = classes.every((classe, i) => {
      const proxima = classes[i + 1];
      return (
        proxima === undefined || classe.maximo.toFixed(casas) !== proxima.minimo.toFixed(casas)
      );
    });
    if (distintas) return casas;
  }
  return MAXIMO_DE_CASAS;
}

/** Faixa de uma classe da legenda, com os valores observados que a API devolveu. */
export function faixaDaClasse(
  classe: Pick<ClasseCoropletico, "minimo" | "maximo">,
  formatar: (valor: number) => string,
): string {
  const minimo = formatar(classe.minimo);
  const maximo = formatar(classe.maximo);
  return minimo === maximo ? minimo : `de ${minimo} a ${maximo}`;
}
