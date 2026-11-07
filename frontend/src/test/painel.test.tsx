import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { respostaIndicadorSchema } from "@/lib/api/schemas";
import { formatarInteiro } from "@/lib/format";

import respostasFiltradas from "./fixtures/painel-filtrado.json";
import respostasReais from "./fixtures/painel-padrao.json";
import { renderRota } from "./render-rota";

// Respostas reais da API para as consultas padrão de /painel, indexadas por caminho + query.
// URL que não esteja aqui responde 404 sem envelope: se o cliente montar uma URL diferente da
// que a API de fato atendeu, o teste falha em vez de passar com dado inventado.
const respostas: Record<string, unknown> = respostasReais;
// Consultas de /painel com território (DF, Centro-Oeste, Brasília) e com categoria administrativa.
const comFiltros: Record<string, unknown> = { ...respostasReais, ...respostasFiltradas };

function resposta(caminho: string, mapa = respostas) {
  const corpo = mapa[caminho];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaIndicadorSchema.parse(corpo);
}

function fetchDasFixtures(mapa = respostas) {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = mapa[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

const renderPainel = (query = "") => renderRota(`/painel${query}`);

/** Falha se alguma consulta saiu das respostas reais capturadas. */
function esperarSoConsultasReais(
  fetchMock: ReturnType<typeof fetchDasFixtures>,
  mapa = comFiltros,
) {
  const consultadas = fetchMock.mock.calls.map(([entrada]) => {
    const url = new URL(String(entrada));
    return url.pathname + url.search;
  });
  expect(consultadas.filter((c) => !(c in mapa))).toEqual([]);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("rota /painel", () => {
  it("mostra os totais nacionais e a distribuição por região com os valores da API", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel();

    const ies = resposta("/api/v1/indicadores/ies?nivel=brasil&recorte=sede");
    const cartaoIes = await screen.findByRole("article", { name: ies.indicador.nome });
    await within(cartaoIes).findByText(formatarInteiro(ies.total));
    expect(within(cartaoIes).getByText("Sede da IES")).toBeInTheDocument();
    expect(within(cartaoIes).getByText(/não se aplica a este indicador/)).toBeInTheDocument();

    // Um cartão por indicador do catálogo, cada um com o total da sua própria resposta.
    const catalogo = respostas["/api/v1/indicadores"] as Array<{ slug: string; nome: string }>;
    expect(await screen.findAllByRole("article")).toHaveLength(catalogo.length);
    const chavesBrasil = Object.keys(respostas).filter((c) => c.includes("nivel=brasil"));
    expect(chavesBrasil).toHaveLength(catalogo.length);
    for (const chave of chavesBrasil) {
      const dados = resposta(chave);
      const cartao = screen.getByRole("article", { name: dados.indicador.nome });
      await within(cartao).findByText(formatarInteiro(dados.total));
      expect(within(cartao).getByText(dados.indicador.codigo)).toBeInTheDocument();
    }

    // Distribuição: primeiro indicador do catálogo, por região, na tabela.
    const regiao = resposta("/api/v1/indicadores/ies?nivel=regiao&recorte=sede");
    const tabela = await screen.findByRole("table");
    for (const linha of regiao.linhas) {
      const celula = within(tabela).getByRole("rowheader", { name: linha.nome });
      expect(celula.closest("tr")).toHaveTextContent(formatarInteiro(linha.valor));
    }

    // Fonte e aviso de retrato transversal vêm dos metadados.
    const metadados = respostas["/api/v1/metadados"] as { fonte: string; aviso: string };
    expect(screen.getByText(metadados.fonte)).toBeInTheDocument();
    expect(screen.getByText(metadados.aviso)).toBeInTheDocument();

    // Nenhuma consulta caiu fora das respostas reais, e todas foram GET.
    for (const [entrada, opcoes] of fetchMock.mock.calls as unknown as Array<
      [string, RequestInit]
    >) {
      const url = new URL(entrada);
      expect(Object.keys(respostas)).toContain(url.pathname + url.search);
      expect(opcoes.method).toBe("GET");
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("troca o nível para UF pela interface e grava a escolha na URL", async () => {
    vi.stubGlobal("fetch", fetchDasFixtures());
    const router = await renderPainel();

    fireEvent.click(await screen.findByRole("radio", { name: "UF" }));

    const uf = resposta("/api/v1/indicadores/ies?nivel=uf&recorte=sede");
    const primeira = uf.linhas[0];
    if (!primeira) throw new Error("fixture de UF sem linhas");
    const celula = await screen.findByRole("rowheader", { name: primeira.nome });
    expect(celula.closest("tr")).toHaveTextContent(formatarInteiro(primeira.valor));
    expect(within(screen.getByRole("table")).getAllByRole("rowheader")).toHaveLength(
      uf.linhas.length,
    );
    await waitFor(() => expect(router.state.location.search).toMatchObject({ nivel: "uf" }));
  });

  it("destaca cinco indicadores e mantém os demais recolhidos", async () => {
    vi.stubGlobal("fetch", fetchDasFixtures());
    await renderPainel();

    const cartaoIes = await screen.findByRole("article", { name: /Instituições de ensino/ });
    const destaque = cartaoIes.parentElement;
    if (!destaque) throw new Error("cartão sem grade");
    expect(
      within(destaque)
        .getAllByRole("article")
        .map((cartao) => within(cartao).getByText(/^IND-D-/).textContent),
    ).toEqual(["IND-D-01", "IND-D-02", "IND-D-03", "IND-D-04", "IND-D-05"]);
    expect(screen.getByText("Demais indicadores do catálogo (4)")).toBeInTheDocument();
  });

  it("com uma UF na URL, os cartões e a distribuição passam a ser os dela", async () => {
    const fetchMock = fetchDasFixtures(comFiltros);
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel("?uf=DF");

    expect(await screen.findByRole("heading", { name: "Distrito Federal" })).toBeInTheDocument();
    const ies = resposta("/api/v1/indicadores/ies?nivel=uf&recorte=sede&uf=DF", comFiltros);
    const cartaoIes = await screen.findByRole("article", { name: ies.indicador.nome });
    await within(cartaoIes).findByText(formatarInteiro(ies.total));
    expect(within(cartaoIes).getByText("Distrito Federal")).toBeInTheDocument();

    // Cursos só existe territorializado no presencial: o cartão declara o que ficou de fora.
    const cursos = resposta(
      "/api/v1/indicadores/cursos?nivel=uf&recorte=oferta&dimensao=presencial&uf=DF",
      comFiltros,
    );
    const cartaoCursos = screen.getByRole("article", { name: cursos.indicador.nome });
    await within(cartaoCursos).findByText(formatarInteiro(cursos.total));
    expect(
      within(cartaoCursos).getByText(/^só Cursos presenciais ofertados no Brasil — nas outras 3/),
    ).toBeInTheDocument();

    // A distribuição desce um nível: municípios da UF.
    const municipios = resposta(
      "/api/v1/indicadores/ies?nivel=municipio&recorte=sede&uf=DF&limite=20",
      comFiltros,
    );
    const tabela = await screen.findByRole("table");
    for (const linha of municipios.linhas) {
      const celula = within(tabela).getByRole("rowheader", { name: linha.nome });
      expect(celula.closest("tr")).toHaveTextContent(formatarInteiro(linha.valor));
    }
    expect(screen.queryByRole("radio", { name: "Região" })).not.toBeInTheDocument();

    // O seletor de município é preenchido pela rota de territórios e a região segue a UF.
    await screen.findByRole("option", { name: "Brasília" });
    expect(screen.getByRole("combobox", { name: "Região" })).toHaveValue("centro_oeste");
    esperarSoConsultasReais(fetchMock);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("escolher a UF pela interface grava UF e região na URL e refaz as consultas", async () => {
    const fetchMock = fetchDasFixtures(comFiltros);
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderPainel();

    fireEvent.change(await screen.findByRole("combobox", { name: "UF" }), {
      target: { value: "DF" },
    });

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ uf: "DF", regiao: "centro_oeste" }),
    );
    const ies = resposta("/api/v1/indicadores/ies?nivel=uf&recorte=sede&uf=DF", comFiltros);
    const cartaoIes = await screen.findByRole("article", { name: ies.indicador.nome });
    await within(cartaoIes).findByText(formatarInteiro(ies.total));
    esperarSoConsultasReais(fetchMock);

    // Limpar devolve ao Brasil.
    fireEvent.click(screen.getByRole("button", { name: /Limpar filtros/ }));
    await waitFor(() => expect(router.state.location.search).not.toHaveProperty("uf"));
    const brasil = resposta("/api/v1/indicadores/ies?nivel=brasil&recorte=sede");
    await within(cartaoIes).findByText(formatarInteiro(brasil.total));
  });

  it("com uma região, distribui pelas UFs dela", async () => {
    const fetchMock = fetchDasFixtures(comFiltros);
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel("?regiao=centro_oeste");

    expect(await screen.findByRole("heading", { name: "Região Centro-Oeste" })).toBeInTheDocument();
    const ufs = resposta(
      "/api/v1/indicadores/ies?nivel=uf&recorte=sede&regiao=centro_oeste",
      comFiltros,
    );
    const tabela = await screen.findByRole("table");
    expect(within(tabela).getAllByRole("rowheader")).toHaveLength(ufs.linhas.length);
    // A soma das UFs exibidas é o total da região devolvido pela API.
    const regiao = resposta(
      "/api/v1/indicadores/ies?nivel=regiao&recorte=sede&regiao=centro_oeste",
      comFiltros,
    );
    expect(ufs.linhas.reduce((soma, linha) => soma + linha.valor, 0)).toBe(regiao.total);
    esperarSoConsultasReais(fetchMock);
  });

  it("com um município, mostra os valores dele e explica que não há nível abaixo", async () => {
    const fetchMock = fetchDasFixtures(comFiltros);
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel("?uf=DF&municipio=5300108");

    expect(await screen.findByRole("heading", { name: "Brasília (DF)" })).toBeInTheDocument();
    const matriculas = resposta(
      "/api/v1/indicadores/matriculas?nivel=municipio&recorte=oferta&dimensao=presencial&dimensao=ead_polo&uf=DF&municipio=5300108",
      comFiltros,
    );
    const cartao = await screen.findByRole("article", { name: matriculas.indicador.nome });
    await within(cartao).findByText(formatarInteiro(matriculas.total));
    expect(screen.getByText(/menor unidade territorial da base/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });

  it("categoria administrativa na URL filtra os cartões e abre 'Mais filtros'", async () => {
    const fetchMock = fetchDasFixtures(comFiltros);
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel("?categoria=publica_federal");

    const ies = resposta(
      "/api/v1/indicadores/ies?nivel=brasil&recorte=sede&categoria=publica_federal",
      comFiltros,
    );
    const cartao = await screen.findByRole("article", { name: ies.indicador.nome });
    await within(cartao).findByText(formatarInteiro(ies.total));
    // O rótulo exibido é o que a API declarou ter aplicado.
    expect(within(cartao).getByText(ies.filtros.categoria ?? "")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Categoria administrativa" })).toHaveValue(
      "publica_federal",
    );
    expect(screen.getByText("Mais filtros (1 ativo)").closest("details")).toHaveAttribute("open");
    esperarSoConsultasReais(fetchMock);
  });

  it("com a API fora do ar, avisa e não exibe número algum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await renderPainel();

    const alertas = await screen.findAllByRole("alert", {}, { timeout: 5000 });
    expect(alertas[0]).toHaveTextContent("API indisponível");
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
