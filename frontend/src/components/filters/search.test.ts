import { describe, expect, it } from "vitest";

import {
  detalheDoEscopo,
  LIMITE_MUNICIPIOS,
  validarPainelSearch,
} from "@/components/painel/search";
import { DIMENSOES, metadadosSchema } from "@/lib/api/schemas";
import metadadosReais from "@/test/fixtures/metadados.json";

import {
  alternarDimensao,
  contarFiltrosAtivos,
  dimensoesDaModalidade,
  dimensoesSelecionadas,
  filtroDoEscopo,
  filtrosGlobaisSchema,
  modalidadeSelecionada,
  modalidadesDisponiveis,
  MODALIDADE_PERSONALIZADA,
  MODALIDADE_TODAS,
  resolverEscopo,
} from "./search";

const metadados = metadadosSchema.parse(metadadosReais);

describe("filtros globais na URL", () => {
  it("sem parâmetros: todas as redes e todas as dimensões", () => {
    const filtros = filtrosGlobaisSchema.parse({});
    expect(filtros.rede).toBeUndefined();
    expect(dimensoesSelecionadas(filtros, DIMENSOES)).toEqual([...DIMENSOES]);
  });

  it("aceita dimensão única como texto e remove repetidas", () => {
    expect(filtrosGlobaisSchema.parse({ dimensao: "presencial" }).dimensao).toEqual(["presencial"]);
    expect(
      filtrosGlobaisSchema.parse({ dimensao: ["ead_polo", "ead_polo", "presencial"] }).dimensao,
    ).toEqual(["ead_polo", "presencial"]);
  });

  it("valor inválido na URL cai no padrão em vez de derrubar a página", () => {
    const filtros = filtrosGlobaisSchema.parse({ rede: "federal", dimensao: ["hibrido"] });
    expect(filtros.rede).toBeUndefined();
    expect(filtros.dimensao).toBeUndefined();
  });

  it("devolve as dimensões na ordem publicada pela API, não na da URL", () => {
    const filtros = filtrosGlobaisSchema.parse({ dimensao: ["ead_polo", "presencial"] });
    expect(dimensoesSelecionadas(filtros, DIMENSOES)).toEqual(["presencial", "ead_polo"]);
  });

  it("alternar: desmarca, permite ficar sem nenhuma e volta ao padrão quando todas voltam", () => {
    const semPresencial = alternarDimensao({}, DIMENSOES, "presencial");
    expect(semPresencial).toEqual(DIMENSOES.filter((d) => d !== "presencial"));

    expect(alternarDimensao({ dimensao: ["presencial"] }, DIMENSOES, "presencial")).toEqual([]);
    expect(alternarDimensao({ dimensao: semPresencial }, DIMENSOES, "presencial")).toBeUndefined();
  });
});

describe("território selecionado", () => {
  it("valida região, UF, município, categoria e organização, descartando o inválido", () => {
    const filtros = filtrosGlobaisSchema.parse({
      regiao: "sul",
      uf: "PR",
      municipio: "4106902",
      categoria: "publica_federal",
      organizacao: "universidade",
    });
    expect(filtros).toMatchObject({
      regiao: "sul",
      uf: "PR",
      municipio: 4106902,
      categoria: "publica_federal",
      organizacao: "universidade",
    });

    const invalidos = filtrosGlobaisSchema.parse({
      regiao: "Sul",
      uf: "pr' OR 1=1",
      municipio: "410690",
      categoria: "federal",
      organizacao: "escola",
    });
    expect(Object.values(invalidos).every((valor) => valor === undefined)).toBe(true);
  });

  it("sem filtro é o Brasil; vale sempre o território mais específico", () => {
    expect(resolverEscopo({}, metadados)).toEqual({ nivel: "brasil", nome: "Brasil" });
    expect(resolverEscopo({ regiao: "sul" }, metadados)).toEqual({
      nivel: "regiao",
      nome: "Região Sul",
      regiao: "sul",
    });
    expect(resolverEscopo({ regiao: "sul", uf: "PR" }, metadados)).toMatchObject({
      nivel: "uf",
      nome: "Paraná",
      uf: "PR",
    });
    expect(resolverEscopo({ uf: "PR", municipio: 4106902 }, metadados, "Curitiba")).toMatchObject({
      nivel: "municipio",
      nome: "Curitiba (PR)",
      municipio: "4106902",
    });
  });

  it("UF e região incoerentes na URL: a região passa a ser a da UF", () => {
    expect(resolverEscopo({ regiao: "sul", uf: "SP" }, metadados)).toMatchObject({
      nivel: "uf",
      uf: "SP",
      regiao: "sudeste",
    });
  });

  it("UF desconhecida e município sem UF não restringem a consulta", () => {
    expect(resolverEscopo({ uf: "XX" }, metadados).nivel).toBe("brasil");
    expect(resolverEscopo({ municipio: 4106902 }, metadados).nivel).toBe("brasil");
    expect(resolverEscopo({ regiao: "sul", municipio: 4106902 }, metadados).nivel).toBe("regiao");
  });

  it("a consulta leva o filtro do próprio nível; no município, também a UF", () => {
    expect(filtroDoEscopo(resolverEscopo({}, metadados))).toEqual({ nivel: "brasil" });
    expect(filtroDoEscopo(resolverEscopo({ regiao: "sul" }, metadados))).toEqual({
      nivel: "regiao",
      regiao: "sul",
    });
    expect(filtroDoEscopo(resolverEscopo({ regiao: "sul", uf: "SP" }, metadados))).toEqual({
      nivel: "uf",
      uf: "SP",
    });
    expect(filtroDoEscopo(resolverEscopo({ uf: "SP", municipio: 3550308 }, metadados))).toEqual({
      nivel: "municipio",
      uf: "SP",
      municipio: "3550308",
    });
  });
});

describe("modalidade como atalho para dimensões de oferta", () => {
  const dimensoes = metadados.dimensoes_oferta;

  it("as modalidades e a sua correspondência vêm dos metadados da API", () => {
    expect(modalidadesDisponiveis(dimensoes)).toEqual(["Presencial", "Curso a distância"]);
    expect(dimensoesDaModalidade("Presencial", dimensoes)).toEqual(["presencial"]);
    expect(dimensoesDaModalidade("Curso a distância", dimensoes)).toEqual([
      "ead_polo",
      "ead_nacional",
      "ead_exterior",
    ]);
    expect(dimensoesDaModalidade(MODALIDADE_TODAS, dimensoes)).toBeUndefined();
  });

  it("reconhece a modalidade a partir das dimensões marcadas", () => {
    expect(modalidadeSelecionada({}, dimensoes)).toBe(MODALIDADE_TODAS);
    expect(modalidadeSelecionada({ dimensao: ["presencial"] }, dimensoes)).toBe("Presencial");
    expect(
      modalidadeSelecionada({ dimensao: ["ead_exterior", "ead_polo", "ead_nacional"] }, dimensoes),
    ).toBe("Curso a distância");
    // Seleção que não coincide com uma modalidade não é apresentada como se fosse uma.
    expect(modalidadeSelecionada({ dimensao: ["presencial", "ead_polo"] }, dimensoes)).toBe(
      MODALIDADE_PERSONALIZADA,
    );
    expect(modalidadeSelecionada({ dimensao: [] }, dimensoes)).toBe(MODALIDADE_PERSONALIZADA);
  });
});

describe("contagem de filtros ativos", () => {
  it("conta o território uma vez e separa os de 'Mais filtros'", () => {
    expect(contarFiltrosAtivos({})).toEqual({ total: 0, avancados: 0 });
    expect(
      contarFiltrosAtivos({
        regiao: "sul",
        uf: "PR",
        municipio: 4106902,
        rede: "publica",
        categoria: "publica_federal",
      }),
    ).toEqual({ total: 3, avancados: 1 });
  });
});

describe("nível da distribuição territorial", () => {
  it("detalha sempre o nível imediatamente abaixo do território selecionado", () => {
    const brasil = resolverEscopo({}, metadados);
    expect(detalheDoEscopo(brasil, undefined)).toEqual({ nivel: "regiao" });
    expect(detalheDoEscopo(brasil, "uf")).toEqual({ nivel: "uf" });
    // Com território, a escolha feita para o Brasil deixa de valer.
    expect(detalheDoEscopo(resolverEscopo({ regiao: "sul" }, metadados), "regiao")).toEqual({
      nivel: "uf",
      regiao: "sul",
    });
    expect(detalheDoEscopo(resolverEscopo({ uf: "PR" }, metadados), "regiao")).toEqual({
      nivel: "municipio",
      uf: "PR",
      limite: LIMITE_MUNICIPIOS,
    });
    expect(
      detalheDoEscopo(resolverEscopo({ uf: "PR", municipio: 4106902 }, metadados), undefined),
    ).toBeNull();
  });
});

describe("search params de /painel", () => {
  it("valida indicador e nível, descartando o que não é admitido", () => {
    expect(validarPainelSearch({ indicador: "matriculas", nivel: "uf", rede: "privada" })).toEqual({
      indicador: "matriculas",
      nivel: "uf",
      rede: "privada",
    });
    // Município fica para a fase do mapa; slug com caracteres estranhos nunca chega à API.
    const invalido = validarPainelSearch({ indicador: "../admin", nivel: "municipio" });
    expect(invalido.indicador).toBeUndefined();
    expect(invalido.nivel).toBeUndefined();
  });
});
