import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { respostaComposicaoSchema, respostaInstituicoesSchema } from "@/lib/api/schemas";
import { formatarInteiro, formatarPercentual } from "@/lib/format";

import respostasCursos from "./fixtures/cursos.json";
import respostasInstituicoes from "./fixtures/instituicoes.json";
import { renderRota } from "./render-rota";

// Respostas reais da API (scripts/dev/capturar_fixtures_frontend.py), por caminho + query.
// URL fora da fixture responde 404 sem envelope: o teste falha em vez de passar com dado inventado.
type Mapa = Record<string, unknown>;
const instituicoes: Mapa = respostasInstituicoes;
const cursos: Mapa = respostasCursos;

const TODAS = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_nacional&dimensao=ead_exterior";

function composicao(mapa: Mapa, caminho: string) {
  const corpo = mapa[`/api/v1/indicadores/${caminho}`];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaComposicaoSchema.parse(corpo);
}

function tabelaDeIes(query: string) {
  const corpo = instituicoes[`/api/v1/instituicoes?${TODAS}${query}`];
  if (corpo === undefined) throw new Error(`fixture sem instituicoes ${query}`);
  return respostaInstituicoesSchema.parse(corpo);
}

function fetchDasFixtures(mapa: Mapa) {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = mapa[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

/** Falha se alguma consulta saiu das respostas reais capturadas. */
function esperarSoConsultasReais(fetchMock: ReturnType<typeof fetchDasFixtures>, mapa: Mapa) {
  const consultadas = fetchMock.mock.calls.map(([entrada]) => {
    const url = new URL(String(entrada));
    return url.pathname + url.search;
  });
  expect(consultadas.filter((c) => !(c in mapa))).toEqual([]);
}

/** Cada linha da composição aparece na tabela com o valor e a participação da API. */
async function esperarComposicao(nomeDaTabela: RegExp, dados: ReturnType<typeof composicao>) {
  const tabela = await screen.findByRole("table", { name: nomeDaTabela });
  expect(within(tabela).getAllByRole("rowheader")).toHaveLength(dados.linhas.length);
  for (const linha of dados.linhas) {
    const tr = within(tabela).getByRole("rowheader", { name: linha.nome }).closest("tr");
    expect(tr).toHaveTextContent(formatarInteiro(linha.valor));
    expect(tr).toHaveTextContent(formatarPercentual(linha.participacao));
  }
  return tabela;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("rota /instituicoes", () => {
  it("mostra as composições, a titulação docente e a tabela de IES com os valores da API", async () => {
    const fetchMock = fetchDasFixtures(instituicoes);
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/instituicoes");

    await esperarComposicao(
      /por categoria administrativa/,
      composicao(instituicoes, "ies/composicao?por=categoria&recorte=sede"),
    );
    await esperarComposicao(
      /por organização acadêmica/,
      composicao(instituicoes, "ies/composicao?por=organizacao&recorte=sede"),
    );

    // Titulação: ordem natural devolvida pela API, não por valor.
    const titulacao = composicao(instituicoes, "docentes/composicao?por=titulacao&recorte=sede");
    const tabelaTitulacao = await esperarComposicao(/por maior titulação/, titulacao);
    expect(
      within(tabelaTitulacao)
        .getAllByRole("rowheader")
        .map((th) => th.textContent),
    ).toEqual(titulacao.linhas.map((linha) => linha.nome));
    expect(screen.getByText(/composição conforme IND-R-12/)).toBeInTheDocument();

    // Tabela detalhada: primeira página, ordenada por matrículas.
    const ies = tabelaDeIes("&limite=25");
    const tabela = await screen.findByRole("table", { name: /por sede — Brasil/ });
    expect(within(tabela).getAllByRole("rowheader")).toHaveLength(ies.linhas.length);
    const primeira = ies.linhas[0];
    if (!primeira || primeira.matriculas === null) throw new Error("fixture sem a primeira IES");
    const tr = within(tabela).getByRole("rowheader", { name: new RegExp(primeira.nome) });
    expect(tr.closest("tr")).toHaveTextContent(formatarInteiro(primeira.matriculas));
    expect(tr.closest("tr")).toHaveTextContent(formatarInteiro(primeira.docentes));
    expect(
      screen.getByText(new RegExp(`de ${formatarInteiro(ies.totais.ies)} · página 1 de`)),
    ).toBeInTheDocument();
    // A ressalva de recorte e a recusa da razão aluno/docente vêm da API e são exibidas.
    for (const nota of ies.notas) expect(screen.getByText(nota)).toBeInTheDocument();

    esperarSoConsultasReais(fetchMock, instituicoes);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("pagina e reordena pela API, gravando o estado na URL", async () => {
    const fetchMock = fetchDasFixtures(instituicoes);
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/instituicoes");

    fireEvent.click(await screen.findByRole("button", { name: "Próxima" }));
    await waitFor(() => expect(router.state.location.search).toMatchObject({ pagina: 2 }));
    const segunda = tabelaDeIes("&limite=25&pagina=2");
    const nomeSegunda = segunda.linhas[0]?.nome;
    if (!nomeSegunda) throw new Error("fixture sem a página 2");
    await screen.findByRole("rowheader", { name: new RegExp(nomeSegunda) });
    expect(screen.getByText(/página 2 de/)).toBeInTheDocument();

    // Trocar a ordem volta à primeira página.
    fireEvent.change(screen.getByRole("combobox", { name: "Ordenar por" }), {
      target: { value: "docentes" },
    });
    await waitFor(() => expect(router.state.location.search).toMatchObject({ ordem: "docentes" }));
    expect(router.state.location.search).not.toHaveProperty("pagina");
    const porDocentes = tabelaDeIes("&ordem=docentes&limite=25");
    const nomeDocentes = porDocentes.linhas[0]?.nome;
    if (!nomeDocentes) throw new Error("fixture sem a ordem por docentes");
    await screen.findByRole("rowheader", { name: new RegExp(nomeDocentes) });
    expect(screen.getByRole("columnheader", { name: "Docentes" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    esperarSoConsultasReais(fetchMock, instituicoes);
  });

  it("troca a medida das composições para docentes", async () => {
    const fetchMock = fetchDasFixtures(instituicoes);
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/instituicoes");

    fireEvent.click(await screen.findByRole("radio", { name: "Docentes" }));
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ metrica: "docentes" }),
    );
    await esperarComposicao(
      /Docentes em exercício por categoria administrativa/,
      composicao(instituicoes, "docentes/composicao?por=categoria&recorte=sede"),
    );
    esperarSoConsultasReais(fetchMock, instituicoes);
  });

  it("com uma UF na URL, tudo passa a ser das IES com sede nela", async () => {
    const fetchMock = fetchDasFixtures(instituicoes);
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/instituicoes?uf=DF");

    expect(await screen.findByRole("heading", { name: "Distrito Federal" })).toBeInTheDocument();
    const categoria = composicao(instituicoes, "ies/composicao?por=categoria&recorte=sede&uf=DF");
    await esperarComposicao(/por categoria administrativa/, categoria);
    const ies = tabelaDeIes("&uf=DF&limite=25");
    // A composição e a tabela descrevem o mesmo conjunto de IES.
    expect(ies.totais.ies).toBe(categoria.total);
    const tabela = await screen.findByRole("table", { name: /por sede — Distrito Federal/ });
    expect(within(tabela).getAllByRole("rowheader")).toHaveLength(ies.linhas.length);
    esperarSoConsultasReais(fetchMock, instituicoes);
  });
});

describe("rota /cursos", () => {
  const base = `recorte=oferta&${TODAS}`;

  it("decompõe matrículas por grau, dimensão, área e rótulo CINE com os valores da API", async () => {
    const fetchMock = fetchDasFixtures(cursos);
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/cursos");

    const grau = composicao(cursos, `matriculas/composicao?por=grau&${base}`);
    await esperarComposicao(/Matrículas por grau acadêmico/, grau);
    await esperarComposicao(
      /Matrículas por dimensão de oferta/,
      composicao(cursos, `matriculas/composicao?por=dimensao&${base}`),
    );
    const area = composicao(cursos, `matriculas/composicao?por=area&${base}`);
    await esperarComposicao(/Matrículas por área geral/, area);
    // Todas as composições repartem o mesmo total.
    expect(area.total).toBe(grau.total);

    // Ranking truncado: a API declara quantos rótulos existem, e a tela repete.
    const rotulos = composicao(cursos, `matriculas/composicao?por=rotulo_cine&${base}&limite=20`);
    expect(rotulos.truncado).toBe(true);
    await esperarComposicao(/rótulos CINE de maior valor/, rotulos);
    expect(
      screen.getByText(new RegExp(`entre\\s+${formatarInteiro(rotulos.categorias)}`)),
    ).toBeInTheDocument();

    esperarSoConsultasReais(fetchMock, cursos);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("troca o indicador e filtra por área pela interface, gravando na URL", async () => {
    const fetchMock = fetchDasFixtures(cursos);
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/cursos");

    fireEvent.change(await screen.findByRole("combobox", { name: "Indicador" }), {
      target: { value: "cursos" },
    });
    await waitFor(() => expect(router.state.location.search).toMatchObject({ metrica: "cursos" }));
    const cursosPorArea = composicao(cursos, `cursos/composicao?por=area&${base}`);
    await esperarComposicao(/Cursos contabilizados na oferta por área geral/, cursosPorArea);
    // A ressalva dos Programas básicos (ABI) vem da API junto com a composição.
    for (const nota of cursosPorArea.notas) expect(screen.getByText(nota)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Indicador" }), {
      target: { value: "matriculas" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Área geral (CINE)" }), {
      target: { value: "saude" },
    });
    await waitFor(() => expect(router.state.location.search).toMatchObject({ area: "saude" }));
    expect(router.state.location.search).not.toHaveProperty("metrica");
    const saude = composicao(cursos, `matriculas/composicao?por=grau&${base}&area=saude`);
    await esperarComposicao(/Matrículas por grau acadêmico/, saude);
    expect(screen.getAllByText(new RegExp(`Área: ${saude.filtros.area}`)).length).toBeGreaterThan(
      0,
    );
    esperarSoConsultasReais(fetchMock, cursos);
  });

  it("em um município, não consulta os recortes CINE e explica o motivo", async () => {
    const fetchMock = fetchDasFixtures(cursos);
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/cursos?uf=DF&municipio=5300108");

    expect(await screen.findByRole("heading", { name: "Brasília (DF)" })).toBeInTheDocument();
    await esperarComposicao(
      /Matrículas por grau acadêmico/,
      composicao(
        cursos,
        "matriculas/composicao?por=grau&recorte=oferta&dimensao=presencial&dimensao=ead_polo&uf=DF&municipio=5300108",
      ),
    );
    expect(screen.getAllByText(/piso de\s+supressão/)).toHaveLength(2);
    expect(screen.queryByRole("table", { name: /área geral/ })).not.toBeInTheDocument();
    esperarSoConsultasReais(fetchMock, cursos);
  });

  it("com a API fora do ar, avisa e não exibe número algum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await renderRota("/cursos");

    const alertas = await screen.findAllByRole("alert", {}, { timeout: 5000 });
    expect(alertas[0]).toHaveTextContent("API indisponível");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
