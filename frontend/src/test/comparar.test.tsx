import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { unidadesDaBusca } from "@/components/comparar/search";
import { respostaComparacaoSchema, REGIOES } from "@/lib/api/schemas";
import { formatarDecimal, formatarInteiro, formatarPercentual } from "@/lib/format";

import respostas from "./fixtures/comparar.json";
import { renderRota } from "./render-rota";

// Respostas reais da API (scripts/dev/capturar_fixtures_frontend.py), por caminho + query.
// URL fora da fixture responde 404 sem envelope: o teste falha em vez de passar com dado inventado.
const fixtures: Record<string, unknown> = respostas;

function comparacao(query: string) {
  const corpo = fixtures[`/api/v1/comparacoes?${query}`];
  if (corpo === undefined) throw new Error(`fixture sem comparacoes ${query}`);
  return respostaComparacaoSchema.parse(corpo);
}

function fetchDasFixtures() {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = fixtures[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

/** Falha se alguma consulta saiu das respostas reais capturadas. */
function esperarSoConsultasReais(fetchMock: ReturnType<typeof fetchDasFixtures>) {
  const consultadas = fetchMock.mock.calls.map(([entrada]) => {
    const url = new URL(String(entrada));
    return url.pathname + url.search;
  });
  expect(consultadas.filter((c) => !(c in fixtures))).toEqual([]);
}

const REGIOES_QUERY = REGIOES.map((r) => `unidade=${r}`).join("&");

function cabecalhos(tabela: HTMLElement): string[] {
  return within(tabela)
    .getAllByRole("columnheader")
    .map((th) => th.textContent ?? "");
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("unidadesDaBusca", () => {
  const ufs = [{ sigla: "SP" }, { sigla: "DF" }, { sigla: "RR" }];

  it("usa as cinco regiões como padrão e nada nos outros níveis", () => {
    expect(unidadesDaBusca({}, ufs)).toEqual([...REGIOES]);
    expect(unidadesDaBusca({ nivel: "uf" }, ufs)).toEqual([]);
    expect(unidadesDaBusca({ nivel: "municipio" }, ufs)).toEqual([]);
    // Lista vazia explícita não volta ao padrão.
    expect(unidadesDaBusca({ nivel: "regiao", u: "" }, ufs)).toEqual([]);
  });

  it("preserva a ordem da URL e descarta repetição, excesso e unidade de outro nível", () => {
    expect(unidadesDaBusca({ nivel: "uf", u: "RR,SP,RR,norte,3550308,XX,DF" }, ufs)).toEqual([
      "RR",
      "SP",
      "DF",
    ]);
    expect(unidadesDaBusca({ nivel: "regiao", u: "sul,SP,norte" }, ufs)).toEqual(["sul", "norte"]);
    expect(
      unidadesDaBusca(
        { nivel: "municipio", u: "1,2,3,4,5,6".replace(/\d/g, (d) => `350000${d}`) },
        ufs,
      ),
    ).toHaveLength(5);
  });
});

describe("rota /comparar", () => {
  it("compara as cinco regiões por padrão, com absolutos e relativos separados e o Brasil de referência", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/comparar");

    const dados = comparacao(`nivel=regiao&${REGIOES_QUERY}`);
    const tabela = await screen.findByRole("table", { name: /Comparação entre Norte/ });
    expect(cabecalhos(tabela)).toEqual([
      "Indicador",
      ...dados.unidades.map((u) => u.nome),
      "Brasilreferência",
      expect.stringContaining("Valores absolutos"),
      expect.stringContaining("Valores relativos"),
    ]);

    // Cada indicador da API vira uma linha, com o valor de cada unidade e o da referência.
    for (const indicador of dados.indicadores) {
      // "Matrículas" também é o começo de "Matrículas por 100 mil habitantes": o código desempata.
      const tr = within(tabela).getByRole("rowheader", {
        name: new RegExp(`^${indicador.nome}\\s*${indicador.codigo}\\b`),
      });
      const linha = tr.closest("tr");
      expect(linha).toHaveTextContent(indicador.codigo);
      for (const valor of [...indicador.valores, indicador.referencia]) {
        if (valor.valor === null) continue;
        expect(linha).toHaveTextContent(
          indicador.tipo === "absoluto"
            ? formatarInteiro(valor.valor)
            : indicador.unidade === "%"
              ? formatarPercentual(valor.valor)
              : formatarDecimal(valor.valor),
        );
      }
    }
    // Recorte declarado em cada linha: sede e oferta convivem na tabela, nunca na mesma linha.
    expect(within(tabela).getAllByText(/Recorte: Sede da IES/)).toHaveLength(3);
    expect(within(tabela).getAllByText(/Recorte: Local de oferta/)).toHaveLength(7);
    // Dimensões de oferta visíveis na linha: cursos só no presencial, matrículas em duas.
    const cursos = within(tabela).getByRole("rowheader", { name: /^Cursos contabilizados/ });
    expect(cursos).toHaveTextContent("Oferta: Cursos presenciais ofertados no Brasil");
    expect(cursos).not.toHaveTextContent("Cursos a distância ofertados no Brasil");
    // Barra só nos valores relativos: nos absolutos ela desenharia o porte.
    const barras = (nome: RegExp) =>
      within(tabela)
        .getByRole("rowheader", { name: nome })
        .closest("tr")!
        .querySelectorAll("td span[style]").length;
    expect(barras(/^Matrículas\s*IND-D-03/)).toBe(0);
    expect(barras(/^Matrículas por 100 mil habitantes/)).toBe(dados.unidades.length);
    // População como contexto de porte.
    const populacao = within(tabela).getByRole("rowheader", { name: /^População estimada/ });
    expect(populacao.closest("tr")).toHaveTextContent(formatarInteiro(dados.referencia.populacao));

    for (const nota of dados.notas) expect(screen.getByText(nota)).toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });

  it("mantém as colunas na ordem da URL, sem classificar por valor", async () => {
    vi.stubGlobal("fetch", fetchDasFixtures());
    await renderRota("/comparar?nivel=uf&u=RR,SP,DF");

    const dados = comparacao("nivel=uf&unidade=RR&unidade=SP&unidade=DF");
    const tabela = await screen.findByRole("table", { name: /Comparação entre Roraima/ });
    expect(cabecalhos(tabela).slice(1, 4)).toEqual(["Roraima", "São Paulo", "Distrito Federal"]);
    // Roraima vem primeiro mesmo com o menor número de matrículas.
    const matriculas = dados.indicadores.find((i) => i.slug === "matriculas");
    expect(matriculas?.valores.map((v) => v.valor)).toEqual([34171, 2441033, 248333]);
    expect(screen.getByText(/64 vezes a população da menor/)).toBeInTheDocument();
  });

  it("com a rede fixada, a participação da privada não se aplica em vez de virar 0%", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/comparar?rede=publica");

    const tabela = await screen.findByRole("table", { name: /Rede: Pública/ });
    const linha = within(tabela)
      .getByRole("rowheader", { name: /^Participação da rede privada/ })
      .closest("tr");
    expect(linha).toHaveTextContent("Não se aplica com a rede fixada");
    expect(linha).not.toHaveTextContent("0,0%");
    esperarSoConsultasReais(fetchMock);
  });

  it("pede ao menos duas unidades e consulta quando a segunda é adicionada", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/comparar?nivel=uf&u=SP");

    expect(await screen.findByText(/Escolha ao menos 2 UFs para comparar/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Adicionar UF"), { target: { value: "DF" } });
    const tabela = await screen.findByRole("table", { name: /Comparação entre São Paulo/ });
    expect(cabecalhos(tabela).slice(1, 3)).toEqual(["São Paulo", "Distrito Federal"]);

    // Remover volta ao estado vazio; trocar de nível zera a seleção.
    fireEvent.click(screen.getByRole("button", { name: "Remover Distrito Federal" }));
    await waitFor(() => expect(screen.queryByRole("table")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("radio", { name: "Municípios" }));
    expect(
      await screen.findByText(/Escolha ao menos 2 municípios para comparar/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Unidades selecionadas" })).not.toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });

  it("no município, ausência aparece como traço e zero de IES como zero", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/comparar?nivel=municipio&u=1100015");

    // O segundo município é escolhido pela tela: UF, depois município.
    fireEvent.change(await screen.findByLabelText("UF do município"), { target: { value: "DF" } });
    await screen.findByRole("option", { name: /Brasília/ });
    fireEvent.change(screen.getByLabelText("Adicionar município"), {
      target: { value: "5300108" },
    });

    const tabela = await screen.findByRole("table", { name: /Comparação entre Alta Floresta/ });
    expect(cabecalhos(tabela).slice(1, 3)).toEqual(["Alta Floresta D'Oeste – RO", "Brasília – DF"]);
    const celulas = (nome: RegExp) =>
      within(within(tabela).getByRole("rowheader", { name: nome }).closest("tr")!).getAllByRole(
        "cell",
      );
    expect(celulas(/^Instituições de ensino superior/)[0]).toHaveTextContent(/^0$/);
    expect(celulas(/^Docentes em exercício/)[0]).toHaveTextContent("sem registro");
    expect(celulas(/^Cursos contabilizados/)[0]).toHaveTextContent("sem registro");
    expect(screen.getByText(/Célula vazia não é zero/)).toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });
});
