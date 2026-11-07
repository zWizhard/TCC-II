"""Cobertura da camada semantica sobre o inventario de colunas.

Cruza o catalogo de colunas da camada com o inventario (`fontes.INVENTARIO_CSV`: uma linha por coluna
das quatro tabelas, medido no DuckDB local). Cada coluna do inventario tem de aparecer na camada
exatamente uma vez, com o mesmo tipo e a mesma familia; nada na camada pode faltar no inventario.
"""

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from api.config import RAIZ
from api.semantica.camada import CAMADA
from api.semantica.fontes import DIRETORIO_DIAGNOSTICOS, INVENTARIO_CSV
from api.semantica.modelos import PAPEIS_EXPOSTOS, CamadaSemantica, Papel

CAMINHO_INVENTARIO = RAIZ / DIRETORIO_DIAGNOSTICOS / INVENTARIO_CSV


@dataclass(frozen=True)
class RelatorioCobertura:
    total_inventario: int
    estado: dict[str, Papel]  # 'tabela.coluna' -> estado, so das classificadas uma unica vez
    sem_classificacao: tuple[str, ...]  # no inventario, fora da camada
    em_duas: tuple[str, ...]  # declaradas mais de uma vez na camada
    fora_do_inventario: tuple[str, ...]  # na camada, mas nao no inventario
    tipos_divergentes: tuple[str, ...]
    familias_divergentes: tuple[str, ...]

    @property
    def completa(self) -> bool:
        return (
            not (
                self.sem_classificacao
                or self.em_duas
                or self.fora_do_inventario
                or self.tipos_divergentes
                or self.familias_divergentes
            )
            and len(self.estado) == self.total_inventario
        )

    @property
    def totais(self) -> dict[Papel, int]:
        contagem = Counter(self.estado.values())
        return {p: contagem.get(p, 0) for p in Papel}

    @property
    def expostas(self) -> int:
        return sum(n for p, n in self.totais.items() if p in PAPEIS_EXPOSTOS)

    def totais_por_tabela(self) -> dict[str, dict[Papel, int]]:
        saida: dict[str, dict[Papel, int]] = {}
        for nome, papel in self.estado.items():
            tabela = nome.split(".", 1)[0]
            saida.setdefault(tabela, dict.fromkeys(Papel, 0))[papel] += 1
        return saida


def ler_inventario(caminho: Path = CAMINHO_INVENTARIO) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cruzar_com_inventario(
    camada: CamadaSemantica | None = None, caminho: Path = CAMINHO_INVENTARIO
) -> RelatorioCobertura:
    """Classifica cada coluna do inventario em exatamente um estado e aponta toda divergencia."""
    camada = camada or CAMADA
    tabela_de = {e.id: e.tabela for e in camada.entidades}
    declaradas = [(f"{tabela_de[c.entidade]}.{c.nome}", c) for c in camada.colunas]
    vezes = Counter(nome for nome, _ in declaradas)
    por_nome = dict(declaradas)

    inventario = {
        f"{linha['tabela']}.{linha['coluna']}": linha for linha in ler_inventario(caminho)
    }
    estado: dict[str, Papel] = {}
    sem: list[str] = []
    tipos: list[str] = []
    familias: list[str] = []
    for nome, linha in inventario.items():
        if nome not in por_nome:
            sem.append(nome)
            continue
        if vezes[nome] > 1:
            continue
        coluna = por_nome[nome]
        estado[nome] = coluna.papel
        if coluna.datatype != linha["tipo"]:
            tipos.append(f"{nome}: camada {coluna.datatype} x inventario {linha['tipo']}")
        if coluna.familia != linha["familia"]:
            familias.append(f"{nome}: camada {coluna.familia} x inventario {linha['familia']}")
    return RelatorioCobertura(
        total_inventario=len(inventario),
        estado=estado,
        sem_classificacao=tuple(sem),
        em_duas=tuple(sorted(n for n, v in vezes.items() if v > 1)),
        fora_do_inventario=tuple(sorted(n for n in por_nome if n not in inventario)),
        tipos_divergentes=tuple(tipos),
        familias_divergentes=tuple(familias),
    )
