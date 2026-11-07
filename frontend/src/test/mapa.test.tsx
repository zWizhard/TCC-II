import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CAMADA,
  FONTE_CALOR,
  FONTE_IES,
  FONTE_MUNICIPIOS,
  FONTE_UFS,
} from "@/components/map/estilo";
import {
  casasDasClasses,
  estadosDoCoropletico,
  faixaDaClasse,
  limitesDaMalha,
} from "@/components/map/geo";
import {
  malhaSchema,
  respostaCoropleticoSchema,
  respostaIndicadorSchema,
  type Malha,
} from "@/lib/api/schemas";
import { formatarDecimal, formatarInteiro } from "@/lib/format";

import malhaDf from "./fixtures/malha-df.json";
import malhaUfs from "./fixtures/malha-ufs.json";
import respostas from "./fixtures/mapa.json";
import { MapaFalso } from "./maplibre-falso";
import { renderRota } from "./render-rota";

// O jsdom não tem WebGL: o MapLibre é trocado por um registrador (ver maplibre-falso.ts).
vi.mock("maplibre-gl", () => import("./maplibre-falso"));

// Respostas reais da API (scripts/dev/capturar_fixtures_frontend.py), por caminho + query.
// A malha municipal da fixture é o recorte real do DF (a inteira tem 3,9 MB).
const mapa: Record<string, unknown> = {
  ...respostas,
  "/api/v1/mapa/malha/uf": malhaUfs,
  "/api/v1/mapa/malha/municipio": malhaDf,
};

const COM_TERRITORIO = "dimensao=presencial&dimensao=ead_polo";
const MALHA_MUNICIPAL = "/api/v1/mapa/malha/municipio";

function coropletico(query: string) {
  const corpo = mapa[`/api/v1/mapa/coropletico?${query}`];
  if (corpo === undefined) throw new Error(`fixture sem ${query}`);
  return respostaCoropleticoSchema.parse(corpo);
}

function indicador(caminho: string) {
  const corpo = mapa[`/api/v1/indicadores/${caminho}`];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaIndicadorSchema.parse(corpo);
}

function fetchDasFixtures() {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = mapa[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

function consultadas(fetchMock: ReturnType<typeof fetchDasFixtures>): string[] {
  return fetchMock.mock.calls.map(([entrada]) => {
    const url = new URL(String(entrada));
    return url.pathname + url.search;
  });
}

/** Falha se alguma consulta saiu das respostas reais capturadas. */
function esperarSoConsultasReais(fetchMock: ReturnType<typeof fetchDasFixtures>) {
  expect(consultadas(fetchMock).filter((c) => !(c in mapa))).toEqual([]);
}

/** O mapa (falso) depois de carregado e com a camada do modo já ligada. */
async function mapaCom(camada: string): Promise<MapaFalso> {
  await waitFor(() => {
    expect(MapaFalso.instancias).toHaveLength(1);
    expect(MapaFalso.instancias[0]?.visiveis()).toContain(camada);
  });
  const instancia = MapaFalso.instancias[0];
  if (!instancia) throw new Error("mapa não criado");
  return instancia;
}

function clicar(instancia: MapaFalso, camada: string, propriedades: Record<string, unknown>) {
  act(() => {
    instancia.disparar("click", camada, {
      features: [
        { properties: propriedades, geometry: { type: "Point", coordinates: [-47, -15] } },
      ],
      point: { x: 10, y: 10 },
    });
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  MapaFalso.instancias = [];
});

describe("rota /mapa", () => {
  it("abre no coroplético por UF, com legenda, tabela e cores vindas da API", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/mapa");

    const dados = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`);
    const instancia = await mapaCom(CAMADA.ufPreenchimento);

    // Sem basemap: o estilo inicial não tem fonte alguma, e nada aponta para fora.
    expect(JSON.stringify(instancia.opcoes["style"])).not.toMatch(/https?:/);
    expect(instancia.opcoes["cooperativeGestures"]).toBe(true);
    expect(instancia.fontes.get(FONTE_UFS)?.spec["promoteId"]).toBe("codarea");
    // Cada UF recebe, pelo código, a cor da classe que a API atribuiu.
    const estados = estadosDoCoropletico(dados);
    for (const [codigo, estado] of estados) {
      expect(instancia.estados.get(FONTE_UFS)?.get(codigo)).toMatchObject(estado);
    }
    expect(instancia.visiveis()).not.toContain(CAMADA.pontos);
    expect(instancia.visiveis()).not.toContain(CAMADA.calor);

    // Legenda: faixas e contagens da resposta, ausência com item próprio, valor do território.
    const legenda = screen.getByRole("complementary", { name: "Legenda do mapa" });
    const casas = casasDasClasses(dados.classes);
    for (const classe of dados.classes) {
      const faixa = faixaDaClasse(classe, (v) => formatarDecimal(v, casas));
      expect(within(legenda).getByText(faixa)).toBeInTheDocument();
    }
    expect(within(legenda).getByText(/Sem registro de oferta \(cinza hachurado\)/)).toBeVisible();
    expect(within(legenda).getByText(/Quantis: cada cor reúne número parecido/)).toBeVisible();
    expect(within(legenda).getByText(formatarDecimal(dados.geral.valor, casas))).toBeVisible();
    expect(within(legenda).getByText(formatarInteiro(dados.geral.numerador ?? -1))).toBeVisible();
    expect(within(legenda).getByText(formatarInteiro(dados.geral.denominador))).toBeVisible();
    expect(within(legenda).getByText("Local de oferta")).toBeVisible();
    for (const nota of [...dados.notas, ...dados.indicador.limitacoes]) {
      expect(within(legenda).getByText(nota)).toBeInTheDocument();
    }

    // Alternativa em texto: as mesmas unidades, com numerador e denominador.
    const tabela = screen.getByRole("table", { name: /Matrículas por 100 mil habitantes por UF/ });
    expect(within(tabela).getAllByRole("rowheader")).toHaveLength(25);
    expect(screen.getByText(/UFs 1–25 de 27/)).toBeInTheDocument();
    const maior = [...dados.linhas].sort((a, b) => (b.valor ?? 0) - (a.valor ?? 0))[0];
    if (!maior) throw new Error("fixture sem linhas");
    const primeira = within(tabela).getAllByRole("rowheader")[0]?.closest("tr");
    expect(primeira).toHaveTextContent(maior.nome);
    expect(primeira).toHaveTextContent(formatarInteiro(maior.numerador ?? -1));
    expect(primeira).toHaveTextContent(formatarInteiro(maior.denominador));

    // O mapa tem nome acessível que descreve o modo.
    expect(screen.getByRole("region", { name: /Mapa coroplético de Matrículas por 100 mil/ }));
    // A malha municipal (3,9 MB) não é pedida enquanto o mapa está por UF.
    expect(consultadas(fetchMock)).not.toContain(MALHA_MUNICIPAL);
    esperarSoConsultasReais(fetchMock);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("mostra na dica o valor, o numerador e o denominador da unidade", async () => {
    vi.stubGlobal("fetch", fetchDasFixtures());
    await renderRota("/mapa");
    const instancia = await mapaCom(CAMADA.ufPreenchimento);
    const df = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}`).linhas.find(
      (l) => l.codigo === "53",
    );
    if (!df) throw new Error("fixture sem o DF");

    act(() => {
      instancia.disparar("mousemove", CAMADA.ufPreenchimento, {
        features: [{ properties: { codarea: "53" } }],
        point: { x: 40, y: 40 },
      });
    });
    const dica = screen.getByTestId("mapa-dica");
    expect(await within(dica).findByText(`${df.nome} (DF)`)).toBeInTheDocument();
    expect(screen.getByText(`Matrículas: ${formatarInteiro(df.numerador ?? -1)}`)).toBeVisible();
    expect(
      screen.getByText(`População estimada (IBGE, 2024): ${formatarInteiro(df.denominador)}`),
    ).toBeVisible();
    expect(instancia.estados.get(FONTE_UFS)?.get("53")).toMatchObject({ hover: true });
  });

  it("clicar numa UF e depois num município grava o território na URL", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/mapa");
    const instancia = await mapaCom(CAMADA.ufPreenchimento);

    clicar(instancia, CAMADA.ufPreenchimento, { codarea: "53" });
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ uf: "DF", regiao: "centro_oeste" }),
    );
    // Território novo: a unidade passa a município, a malha municipal é pedida e o mapa enquadra.
    await mapaCom(CAMADA.municipioPreenchimento);
    expect(consultadas(fetchMock)).toContain(MALHA_MUNICIPAL);
    expect(instancia.fontes.get(FONTE_MUNICIPIOS)?.spec["promoteId"]).toBe("codarea");
    expect(instancia.estados.get(FONTE_MUNICIPIOS)?.get("5300108")).toMatchObject({
      semRegistro: false,
    });
    expect(instancia.visiveis()).not.toContain(CAMADA.ufPreenchimento);
    await waitFor(() => expect(instancia.enquadramentos.length).toBeGreaterThanOrEqual(1));
    const antes = instancia.enquadramentos.length;

    clicar(instancia, CAMADA.municipioPreenchimento, { codarea: "5300108" });
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ uf: "DF", municipio: 5300108 }),
    );
    // O município é destacado e enquadrado; os dados continuam sendo os da UF.
    await waitFor(() =>
      expect(instancia.estados.get(FONTE_MUNICIPIOS)?.get("5300108")).toMatchObject({
        selecionado: true,
      }),
    );
    await waitFor(() => expect(instancia.enquadramentos.length).toBeGreaterThan(antes));
    const painel = await screen.findByRole("region", { name: /Município selecionado: Brasília/ });
    const linha = coropletico(`nivel=municipio&recorte=oferta&${COM_TERRITORIO}&uf=DF`).linhas[0];
    if (!linha) throw new Error("fixture sem Brasília");
    expect(painel).toHaveTextContent(formatarInteiro(linha.numerador ?? -1));
    expect(painel).toHaveTextContent(formatarInteiro(linha.denominador));
    expect(consultadas(fetchMock).filter((c) => c.includes("/mapa/coropletico"))).toEqual([
      `/api/v1/mapa/coropletico?nivel=uf&recorte=oferta&${COM_TERRITORIO}`,
      `/api/v1/mapa/coropletico?nivel=municipio&recorte=oferta&${COM_TERRITORIO}&uf=DF`,
    ]);
    // O mapa não foi recriado em nenhuma das trocas.
    expect(MapaFalso.instancias).toHaveLength(1);
    expect(instancia.removido).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Ver Brasil" }));
    await waitFor(() => expect(router.state.location.search).not.toHaveProperty("uf"));
    expect(router.state.location.search).not.toHaveProperty("municipio");
    esperarSoConsultasReais(fetchMock);
  });

  it("no modo de pontos, um ponto é um município de sede e o agrupamento soma IES", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/mapa?modo=pontos");
    const instancia = await mapaCom(CAMADA.pontos);
    const dados = indicador("ies?nivel=municipio&recorte=sede");

    const fonte = instancia.fontes.get(FONTE_IES);
    expect(fonte?.spec["cluster"]).toBe(true);
    expect(fonte?.spec["clusterProperties"]).toEqual({ ies: ["+", ["get", "valor"]] });
    await waitFor(() =>
      expect((fonte?.dados as { features: unknown[] }).features).toHaveLength(dados.unidades),
    );
    expect(instancia.visiveis()).not.toContain(CAMADA.ufPreenchimento);
    expect(instancia.visiveis()).not.toContain(CAMADA.municipioPreenchimento);

    const legenda = screen.getByRole("complementary", { name: "Legenda do mapa" });
    expect(legenda).toHaveTextContent(/Cada ponto é um município de sede, não uma instituição/);
    expect(legenda).toHaveTextContent(/não o endereço da instituição/);
    expect(legenda).toHaveTextContent(/soma das IES/);
    expect(within(legenda).getByText(formatarInteiro(dados.total))).toBeVisible();
    expect(within(legenda).getByText("Sede da IES")).toBeVisible();
    expect(screen.getByText(/Municípios de sede 1–25 de 698/)).toBeInTheDocument();

    // Agrupamento: a dica soma IES e o clique só aproxima, sem mexer nos filtros.
    act(() => {
      instancia.disparar("mousemove", CAMADA.clusters, {
        features: [{ properties: { ies: 412, point_count: 37, cluster_id: 9 } }],
        point: { x: 5, y: 5 },
      });
    });
    expect(await screen.findByText("412 instituições com sede neles, somadas")).toBeVisible();
    expect(screen.getByText("37 municípios de sede agrupados")).toBeVisible();
    clicar(instancia, CAMADA.clusters, { ies: 412, point_count: 37, cluster_id: 9 });
    await waitFor(() => expect(instancia.aproximacoes).toHaveLength(1));
    expect(router.state.location.search).toEqual({ modo: "pontos" });

    // Ponto: seleciona o município nos filtros globais.
    clicar(instancia, CAMADA.pontos, { codigo: "5300108" });
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({
        modo: "pontos",
        uf: "DF",
        municipio: 5300108,
      }),
    );
    const painel = await screen.findByRole("region", { name: /Município selecionado: Brasília/ });
    const brasilia = indicador("ies?nivel=municipio&recorte=sede&uf=DF").linhas[0];
    if (!brasilia) throw new Error("fixture sem Brasília");
    expect(painel).toHaveTextContent(`${formatarInteiro(brasilia.valor)} instituições com sede`);
    const lista = await within(painel).findByRole("list", { name: /Instituições com sede/ });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(10);
    expect(within(painel).getByRole("link", { name: /tabela completa/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/instituicoes?uf=DF&municipio=5300108"),
    );
    await waitFor(() =>
      expect(instancia.filtros.get(CAMADA.pontoSelecionado)).toEqual([
        "==",
        ["get", "codigo"],
        "5300108",
      ]),
    );
    esperarSoConsultasReais(fetchMock);
  });

  it("no mapa de calor, a legenda define a intensidade e nomeia o maior município", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/mapa?modo=calor&uf=DF");
    const instancia = await mapaCom(CAMADA.calor);
    const dados = indicador(`matriculas?nivel=municipio&recorte=oferta&${COM_TERRITORIO}&uf=DF`);
    const maior = [...dados.linhas].sort((a, b) => b.valor - a.valor)[0];
    if (!maior) throw new Error("fixture sem linhas");

    await waitFor(() => {
      const colecao = instancia.fontes.get(FONTE_CALOR)?.dados as {
        features: Array<{ properties: { codigo: string; peso: number } }>;
      };
      expect(colecao.features).toHaveLength(dados.linhas.length);
      expect(
        colecao.features.find((f) => f.properties.codigo === maior.codigo)?.properties.peso,
      ).toBe(1);
    });

    const legenda = screen.getByRole("complementary", { name: "Legenda do mapa" });
    expect(legenda).toHaveTextContent(/não normalizado por população/);
    expect(legenda).toHaveTextContent(/Não é valor por habitante nem valor por área/);
    expect(legenda).toHaveTextContent(/muda com o zoom, por isso não tem unidade/);
    expect(legenda).toHaveTextContent(/não são comparáveis/);
    expect(legenda).toHaveTextContent(/coordenada de referência/);
    expect(legenda).toHaveTextContent(maior.nome);
    expect(within(legenda).getByText(formatarInteiro(maior.valor))).toBeVisible();
    expect(within(legenda).getByText("menor intensidade")).toBeVisible();

    // A métrica vem do catálogo, com o recorte de cada indicador.
    fireEvent.change(screen.getByRole("combobox", { name: "Métrica" }), {
      target: { value: "docentes" },
    });
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ metrica: "docentes" }),
    );
    await waitFor(() =>
      expect(consultadas(fetchMock)).toContain(
        "/api/v1/indicadores/docentes?nivel=municipio&recorte=sede&uf=DF",
      ),
    );
    expect(await within(legenda).findByText("Sede da IES")).toBeVisible();
    esperarSoConsultasReais(fetchMock);
  });

  it("deixa de fora as dimensões sem território e diz quais", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/mapa?dimensao=presencial&dimensao=ead_nacional");
    await mapaCom(CAMADA.ufPreenchimento);

    expect(consultadas(fetchMock)).toContain(
      "/api/v1/mapa/coropletico?nivel=uf&recorte=oferta&dimensao=presencial",
    );
    const aviso = screen.getByText(
      /Dimensões selecionadas que não entram neste mapa/,
    ).parentElement;
    expect(aviso).toHaveTextContent(
      "Cursos a distância com dimensão de dados somente a nível Brasil",
    );
    esperarSoConsultasReais(fetchMock);
  });

  it("com filtro institucional, a ausência muda de nome e as faixas ganham casas", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/mapa?categoria=especial");
    const instancia = await mapaCom(CAMADA.ufPreenchimento);
    const dados = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}&categoria=especial`);

    const legenda = screen.getByRole("complementary", { name: "Legenda do mapa" });
    expect(
      within(legenda).getByText(/Sem matrícula registrada nessas instituições \(cinza hachurado\)/),
    ).toBeVisible();
    expect(within(legenda).queryByText(/Sem registro de oferta \(/)).not.toBeInTheDocument();
    expect(legenda).toHaveTextContent(`${dados.sem_registro} UFs — ausência de registro, não zero`);
    const classes = within(legenda).getByRole("list", { name: "Classes do mapa" });
    const faixas = within(classes)
      .getAllByRole("listitem")
      .slice(0, dados.classes.length)
      .map((li) => li.textContent?.split(" · ")[0]);
    expect(new Set(faixas).size).toBe(dados.classes.length);

    const semRegistro = dados.linhas.filter((l) => l.numerador === null);
    for (const linha of semRegistro) {
      expect(instancia.estados.get(FONTE_UFS)?.get(linha.codigo)).toMatchObject({
        semRegistro: true,
      });
    }
    esperarSoConsultasReais(fetchMock);
  });

  it("numa região, pinta só as UFs dela e enquadra o território", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/mapa?regiao=centro_oeste&unidade=uf");
    const instancia = await mapaCom(CAMADA.ufPreenchimento);
    const dados = coropletico(`nivel=uf&recorte=oferta&${COM_TERRITORIO}&regiao=centro_oeste`);

    await waitFor(() =>
      expect([...(instancia.estados.get(FONTE_UFS)?.keys() ?? [])].sort()).toEqual(
        dados.linhas.map((l) => l.codigo).sort(),
      ),
    );
    // A caixa é a das UFs da região (pelo código): vem já na criação do mapa ou, se a tabela de
    // UFs chegar depois, num novo enquadramento.
    const esperada = limitesDaMalha(
      malhaSchema.parse(malhaUfs) as Malha,
      new Set(dados.linhas.map((l) => l.codigo)),
    );
    await waitFor(() => {
      const ultimo = instancia.enquadramentos.at(-1) as { limites: unknown } | undefined;
      expect(ultimo?.limites ?? instancia.opcoes["bounds"]).toEqual(esperada);
    });
    expect(screen.getByRole("heading", { name: /Coroplético por UF — Região Centro-Oeste/ }));
    esperarSoConsultasReais(fetchMock);
  });

  it("com a API fora do ar, avisa e não cria mapa nem tabela", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await renderRota("/mapa");

    const alertas = await screen.findAllByRole("alert", {}, { timeout: 5000 });
    expect(alertas[0]).toHaveTextContent("API indisponível");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(MapaFalso.instancias).toHaveLength(0);
  });
});
