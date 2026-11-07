import { afterEach, describe, expect, it, vi } from "vitest";

import { resolverEscopo } from "@/components/filters/search";
import {
  consultarCoropletico,
  montarParametrosCoropletico,
  obterMalha,
  RECORTE_COROPLETICO,
} from "@/lib/api/client";
import {
  malhaSchema,
  metadadosSchema,
  respostaCoropleticoSchema,
  respostaIndicadorSchema,
  type Malha,
} from "@/lib/api/schemas";
import { formatarDecimal } from "@/lib/format";
import malhaDfJson from "@/test/fixtures/malha-df.json";
import malhaUfsJson from "@/test/fixtures/malha-ufs.json";
import respostas from "@/test/fixtures/mapa.json";

import {
  CAMADA,
  camadasBase,
  camadasMunicipais,
  camadasVisiveis,
  FONTE_IES,
  FONTE_MUNICIPIOS,
  imagemDaHachura,
  raioDosClusters,
  raioDosPontos,
} from "./estilo";
import {
  casasDasClasses,
  COR_SEM_REGISTRO,
  coresDasClasses,
  estadosDoCoropletico,
  faixaDaClasse,
  limitesDaGeometria,
  limitesDaMalha,
  limitesDoPonto,
  pontoDeRotulo,
  pontosDoIndicador,
  rotulosDasUfs,
  rotuloSemRegistro,
} from "./geo";
import {
  chaveDoTerritorio,
  mapaSearchSchema,
  territorioDoMapa,
  unidadePadrao,
  validarMapaSearch,
} from "./search";

// Respostas e geometrias reais (scripts/dev/capturar_fixtures_frontend.py), nunca escritas à mão.
const fixtures: Record<string, unknown> = respostas;
const COM_TERRITORIO = "dimensao=presencial&dimensao=ead_polo";
const malhaUfs = malhaSchema.parse(malhaUfsJson) as Malha;
const malhaDf = malhaSchema.parse(malhaDfJson) as Malha;
const metadados = metadadosSchema.parse(fixtures["/api/v1/metadados"]);

function coropletico(query: string) {
  const corpo = fixtures[`/api/v1/mapa/coropletico?${query}`];
  if (corpo === undefined) throw new Error(`fixture sem ${query}`);
  return respostaCoropleticoSchema.parse(corpo);
}

function indicador(caminho: string) {
  const corpo = fixtures[`/api/v1/indicadores/${caminho}`];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaIndicadorSchema.parse(corpo);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("contrato do mapa contra as respostas reais", () => {
  it("valida o coroplético e casa cada linha com a malha pelo código", () => {
    const porUf = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`);
    expect(porUf.indicador.codigo).toBe("IND-R-01");
    expect(porUf.recorte).toBe(RECORTE_COROPLETICO);
    expect(porUf.linhas).toHaveLength(27);
    const codigos = new Set(malhaUfs.features.map((f) => f.properties.codarea));
    expect(porUf.linhas.every((l) => codigos.has(l.codigo))).toBe(true);
    expect(porUf.com_registro + porUf.sem_registro).toBe(porUf.unidades);

    const df = coropletico(`nivel=municipio&recorte=oferta&${COM_TERRITORIO}&uf=DF`);
    expect(df.linhas.map((l) => l.codigo)).toEqual(
      malhaDf.features.map((f) => f.properties.codarea),
    );
  });

  it("as dimensões com território de /metadados são as que IND-R-01 admite", () => {
    const comTerritorio = metadados.dimensoes_oferta
      .filter((d) => d.territorializavel)
      .map((d) => d.slug);
    const porUf = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`);
    expect([...porUf.indicador.dimensoes_territoriais].sort()).toEqual([...comTerritorio].sort());
  });

  it("monta a consulta com o recorte de oferta, sem município", () => {
    expect(
      montarParametrosCoropletico({
        nivel: "municipio",
        dimensoes: ["presencial", "ead_polo"],
        rede: "publica",
        uf: "DF",
      }).toString(),
    ).toBe(`nivel=municipio&recorte=oferta&${COM_TERRITORIO}&rede=publica&uf=DF`);
    expect(montarParametrosCoropletico({ nivel: "uf", dimensoes: ["presencial"] }).toString()).toBe(
      "nivel=uf&recorte=oferta&dimensao=presencial",
    );
  });

  it("consulta o coroplético e a malha nas rotas da API", async () => {
    const fetchMock = vi.fn(async (entrada: RequestInfo | URL) => {
      const url = new URL(String(entrada));
      const corpo = url.pathname.endsWith("/malha/uf")
        ? malhaUfsJson
        : fixtures[url.pathname + url.search];
      return new Response(JSON.stringify(corpo), { status: 200 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const dados = await consultarCoropletico({
      nivel: "uf",
      dimensoes: ["presencial", "ead_polo"],
    });
    expect(dados.linhas).toHaveLength(27);
    const malha = await obterMalha("uf");
    expect(malha.features).toHaveLength(27);
    expect(fetchMock.mock.calls.map(([e]) => new URL(String(e)).pathname)).toEqual([
      "/api/v1/mapa/coropletico",
      "/api/v1/mapa/malha/uf",
    ]);
  });

  it("recusa malha que não é uma FeatureCollection", () => {
    expect(malhaSchema.safeParse({ type: "Feature", features: [] }).success).toBe(false);
    expect(malhaSchema.safeParse({ type: "FeatureCollection" }).success).toBe(false);
  });
});

describe("estado do mapa na URL", () => {
  it("valor inválido cai no padrão sem derrubar a página", () => {
    expect(
      validarMapaSearch({ modo: "satelite", unidade: "bairro", metrica: "DROP TABLE" }),
    ).toEqual({});
    expect(mapaSearchSchema.parse({ modo: "calor", unidade: "uf", metrica: "docentes" })).toEqual({
      modo: "calor",
      unidade: "uf",
      metrica: "docentes",
    });
  });

  it("unidade padrão: UF no Brasil, município dentro de um território", () => {
    const territorios = { regioes: metadados.regioes, ufs: metadados.ufs };
    const brasil = resolverEscopo({}, territorios);
    const regiao = resolverEscopo({ regiao: "centro_oeste" }, territorios);
    const uf = resolverEscopo({ uf: "DF" }, territorios);
    const municipio = resolverEscopo({ uf: "DF", municipio: 5300108 }, territorios, "Brasília");

    expect([brasil, regiao, uf, municipio].map(unidadePadrao)).toEqual([
      "uf",
      "municipio",
      "municipio",
      "municipio",
    ]);
    // Com município selecionado o mapa consulta a UF dele, nunca o município.
    expect(territorioDoMapa(brasil)).toEqual({});
    expect(territorioDoMapa(regiao)).toEqual({ regiao: "centro_oeste" });
    expect(territorioDoMapa(uf)).toEqual({ uf: "DF" });
    expect(territorioDoMapa(municipio)).toEqual({ uf: "DF" });
    expect([brasil, regiao, uf, municipio].map(chaveDoTerritorio)).toEqual([
      "brasil",
      "regiao:centro_oeste",
      "uf:DF",
      "municipio:5300108",
    ]);
  });
});

describe("resposta → o que o mapa desenha", () => {
  it("a cor de cada unidade segue a classe atribuída pela API", () => {
    const dados = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`);
    const cores = coresDasClasses(dados.classes);
    expect(new Set(cores).size).toBe(dados.classes.length);
    const estados = estadosDoCoropletico(dados);
    expect(estados.size).toBe(27);
    for (const linha of dados.linhas) {
      const posicao = dados.classes.findIndex((c) => c.indice === linha.classe);
      expect(estados.get(linha.codigo)).toEqual({ cor: cores[posicao], semRegistro: false });
    }
  });

  it("unidade sem registro recebe o cinza fora da rampa, não a classe mais baixa", () => {
    const dados = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}&categoria=especial`);
    const semRegistro = dados.linhas.filter((l) => l.numerador === null);
    expect(semRegistro).toHaveLength(dados.sem_registro);
    expect(semRegistro.length).toBeGreaterThan(0);
    const estados = estadosDoCoropletico(dados);
    for (const linha of semRegistro) {
      expect(estados.get(linha.codigo)).toEqual({ cor: COR_SEM_REGISTRO, semRegistro: true });
    }
    expect(coresDasClasses(dados.classes)).not.toContain(COR_SEM_REGISTRO);
    // Zero registrado é valor: tem classe e cor da rampa.
    const zero = dados.linhas.find((l) => l.numerador === 0);
    if (zero) expect(estados.get(zero.codigo)?.semRegistro).toBe(false);
  });

  it("aumenta as casas decimais até classes vizinhas ficarem distintas", () => {
    const comum = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`);
    expect(casasDasClasses(comum.classes)).toBe(1);

    const raro = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}&categoria=especial`);
    const casas = casasDasClasses(raro.classes);
    expect(casas).toBeGreaterThan(1);
    const faixas = raro.classes.map((c) => faixaDaClasse(c, (v) => formatarDecimal(v, casas)));
    expect(new Set(faixas).size).toBe(raro.classes.length);
    raro.classes.slice(0, -1).forEach((classe, i) => {
      const proxima = raro.classes[i + 1];
      expect(formatarDecimal(classe.maximo, casas)).not.toBe(
        formatarDecimal(proxima?.minimo, casas),
      );
    });
    expect(faixaDaClasse({ minimo: 2, maximo: 2 }, (v) => formatarDecimal(v))).toBe("2,0");
  });

  it("nomeia a ausência conforme o filtro institucional", () => {
    expect(rotuloSemRegistro({ rede: null, categoria: null, organizacao: null })).toBe(
      "Sem registro de oferta",
    );
    expect(rotuloSemRegistro({ rede: null, categoria: "Especial", organizacao: null })).toBe(
      "Sem matrícula registrada nessas instituições",
    );
  });

  it("um ponto por município de sede, com o nº de IES como atributo", () => {
    const dados = indicador("ies?nivel=municipio&recorte=sede");
    const { colecao, maximo, semCoordenada } = pontosDoIndicador(dados.linhas);
    // 698 municípios de sede para 2.561 IES: nunca um ponto por instituição.
    expect(colecao.features).toHaveLength(dados.linhas.length);
    expect(colecao.features.length).toBe(dados.unidades);
    expect(colecao.features.reduce((soma, f) => soma + f.properties.valor, 0)).toBe(dados.total);
    expect(semCoordenada).toBe(0);
    expect(maximo).toBe(Math.max(...dados.linhas.map((l) => l.valor)));
    // Coordenadas distintas: nenhum ponto foi "espalhado" nem empilhado.
    const coordenadas = new Set(colecao.features.map((f) => f.geometry.coordinates.join(",")));
    expect(coordenadas.size).toBe(colecao.features.length);
    // Peso linear: 1 no maior município, proporcional nos demais.
    for (const { properties } of colecao.features) {
      expect(properties.peso).toBeCloseTo(properties.valor / maximo, 10);
    }
  });

  it("linha sem coordenada não vira ponto e é contada", () => {
    const porUf = indicador("ies?nivel=uf&recorte=sede");
    const { colecao, semCoordenada } = pontosDoIndicador(porUf.linhas);
    expect(colecao.features).toHaveLength(0);
    expect(semCoordenada).toBe(27);
  });

  it("enquadra pelo código da feição e rotula dentro da caixa da UF", () => {
    const brasil = limitesDaMalha(malhaUfs);
    const df = limitesDaMalha(malhaUfs, new Set(["53"]));
    if (!brasil || !df) throw new Error("malha sem limites");
    expect(df[0]).toBeGreaterThan(brasil[0]);
    expect(df[2]).toBeLessThan(brasil[2]);
    expect(limitesDaMalha(malhaUfs, new Set(["00"]))).toBeNull();
    expect(limitesDoPonto(-47.9, -15.8, 0.5)).toEqual([-48.4, -16.3, -47.4, -15.3]);

    const tabela = indicador("ies?nivel=uf&recorte=sede");
    const siglas = new Map(tabela.linhas.map((l) => [l.codigo, l.uf ?? ""]));
    const rotulos = rotulosDasUfs(malhaUfs, siglas);
    expect(rotulos.features).toHaveLength(27);
    for (const feicao of malhaUfs.features) {
      const [oeste, sul, leste, norte] = limitesDaGeometria(feicao.geometry);
      const [x, y] = pontoDeRotulo(feicao.geometry);
      expect(x).toBeGreaterThanOrEqual(oeste);
      expect(x).toBeLessThanOrEqual(leste);
      expect(y).toBeGreaterThanOrEqual(sul);
      expect(y).toBeLessThanOrEqual(norte);
    }
    expect(rotulos.features.find((f) => f.properties.codigo === "53")?.properties.sigla).toBe("DF");
  });
});

describe("estilo do mapa", () => {
  it("não depende de tiles, fontes ou imagens de terceiros", () => {
    const camadas = [...camadasBase(), ...camadasMunicipais().map((c) => c.camada)];
    expect(JSON.stringify(camadas)).not.toMatch(/https?:/);
    const hachura = imagemDaHachura();
    expect(hachura.data).toHaveLength(hachura.width * hachura.height * 4);
    expect(hachura.data.some((v) => v > 0)).toBe(true);
  });

  it("o agrupamento mostra IES somadas, nunca a contagem de municípios", () => {
    const rotulo = camadasBase().find((c) => c.id === CAMADA.clusterRotulo);
    const texto = JSON.stringify(rotulo);
    expect(texto).toContain('["get","ies"]');
    expect(texto).not.toContain("point_count_abbreviated");
    expect(rotulo && "source" in rotulo ? rotulo.source : undefined).toBe(FONTE_IES);
    // Raio pela raiz do valor: é a área, não o raio, que acompanha o número.
    expect(JSON.stringify(raioDosPontos(172))).toContain('["sqrt",["get","valor"]]');
    expect(JSON.stringify(raioDosClusters(2561))).toContain('["sqrt",["get","ies"]]');
  });

  it("cada modo liga só as suas camadas; pontos nunca sobre o coroplético", () => {
    const porUf = camadasVisiveis("coropletico", "uf");
    const porMunicipio = camadasVisiveis("coropletico", "municipio");
    const pontos = camadasVisiveis("pontos", undefined);
    const calor = camadasVisiveis("calor", undefined);
    expect(porUf.has(CAMADA.ufPreenchimento)).toBe(true);
    expect(porUf.has(CAMADA.municipioPreenchimento)).toBe(false);
    expect(porMunicipio.has(CAMADA.municipioPreenchimento)).toBe(true);
    for (const id of [...pontos, ...calor]) {
      expect(porUf.has(id)).toBe(false);
      expect(porMunicipio.has(id)).toBe(false);
    }
    expect([...pontos].some((id) => calor.has(id))).toBe(false);
    expect(camadasVisiveis("nenhum", undefined).size).toBe(0);
    expect(
      camadasMunicipais().every(
        (c) => "source" in c.camada && c.camada.source === FONTE_MUNICIPIOS,
      ),
    ).toBe(true);
  });

  it("o calor usa peso linear e intensidade fixa", () => {
    const calor = camadasBase().find((c) => c.id === CAMADA.calor);
    const pintura = calor && "paint" in calor ? (calor.paint as Record<string, unknown>) : {};
    expect(pintura["heatmap-weight"]).toEqual(["get", "peso"]);
    expect(pintura["heatmap-intensity"]).toBe(1);
    // O raio cresce com o zoom.
    expect(JSON.stringify(pintura["heatmap-radius"])).toContain('["zoom"]');
  });
});
