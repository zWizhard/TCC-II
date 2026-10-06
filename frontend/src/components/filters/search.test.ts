import { describe, expect, it } from "vitest";

import { validarPainelSearch } from "@/components/painel/search";
import { DIMENSOES } from "@/lib/api/schemas";

import { alternarDimensao, dimensoesSelecionadas, filtrosGlobaisSchema } from "./search";

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
