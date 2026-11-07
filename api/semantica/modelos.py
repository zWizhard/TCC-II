"""Modelos da camada semantica do Analista IA (Fase 12).

A camada e a ponte entre a linguagem do usuario e a base: diz o que existe, em que grain, o que
pode ser agregado, o que e proibido e o que e ambiguo. Tudo aqui e Pydantic congelado e sem campo
extra, exportavel como JSON (`model_dump_json`) e com JSON Schema (`model_json_schema`).

A integridade e conferida na construcao: `CamadaSemantica` recusa referencia pendente, coluna
proibida em uso, metrica fora do grain e termo que aponte para dois alvos sem ambiguidade
declarada. Uma camada inconsistente nao chega a existir.
"""

from collections import defaultdict
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from api.indicadores import Dimensao, Nivel, Recorte
from api.semantica.texto import FRASES_IGNORADAS, NEGACOES, OPERADORES, STOPWORDS, chave


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StatusSinonimo(StrEnum):
    VERIFICADO = "verificado"  # rotulo literal do dado, nome de ficha ou termo da documentacao/UI
    # Termo coloquial que DIRECIONA para um conceito canonico sem mudar a terminologia da
    # resposta ('alunos' -> matriculas; a resposta fala em matriculas). Decisao do autor.
    ALIAS = "alias_de_intencao"
    PROPOSTO = "proposto"  # coloquial, escolhido por nos: o autor ainda confirma


class Sinonimo(_Modelo):
    termo: str
    status: StatusSinonimo
    terminologia: str = ""  # instrucao obrigatoria do alias: como a resposta deve falar

    @model_validator(mode="after")
    def _alias_declara_a_terminologia(self) -> Self:
        if (self.status == StatusSinonimo.ALIAS) != bool(self.terminologia):
            raise ValueError(f"'{self.termo}': terminologia e exigida no alias, e so nele")
        return self


class Papel(StrEnum):
    """Estado de cada coluna do inventario: exatamente um por coluna."""

    CHAVE = "chave"
    DIMENSAO = "dimensao"
    METRICA = "metrica"
    COMPONENTE = "componente_decomposicao"
    ESTRUTURAL = "estrutural"
    SEM_INDICADOR = "nao_exposta_sem_indicador"
    QUARENTENA = "proibida_quarentena"
    NAO_AUDITADA = "proibida_nao_auditada"
    IRRELEVANTE = "irrelevante_redundante"


# So estes papeis podem ser citados por entidade, dimensao, metrica ou relacionamento.
PAPEIS_EXPOSTOS = frozenset(
    {Papel.CHAVE, Papel.DIMENSAO, Papel.METRICA, Papel.COMPONENTE, Papel.ESTRUTURAL}
)


class Coluna(_Modelo):
    """Uma coluna fisica do DuckDB local, com o tipo real e o papel na camada."""

    entidade: str
    nome: str
    datatype: str
    papel: Papel
    familia: str  # familia do inventario (auditar_schema_semantico.py)
    motivo: str = ""  # obrigatorio quando a coluna nao e exposta
    ficha: str | None = None
    proveniencia: str

    @model_validator(mode="after")
    def _motivo_de_quem_fica_fora(self) -> Self:
        if self.papel not in PAPEIS_EXPOSTOS and not self.motivo:
            raise ValueError(f"{self.entidade}.{self.nome}: coluna nao exposta exige motivo")
        return self


class RefColuna(_Modelo):
    entidade: str
    coluna: str


class Entidade(_Modelo):
    id: str
    nome: str
    descricao: str
    tabela: str  # nome fisico no DuckDB
    linhas: int
    grain: str
    chave: tuple[str, ...]
    sinonimos: tuple[Sinonimo, ...] = ()
    # Metrica que conta esta entidade: entra no contexto quando a pergunta cita a entidade e
    # nenhuma metrica ('quantos cursos').
    metrica_de_contagem: str | None = None
    limitacoes: tuple[str, ...] = ()
    proveniencia: str


class Alvo(_Modelo):
    """Referencia a um item da camada; `valor` so quando o tipo e 'valor' (de uma dimensao)."""

    tipo: Literal["entidade", "dimensao", "valor", "metrica", "ambiguidade", "recusa"]
    id: str
    valor: str | None = None

    def __str__(self) -> str:
        return f"{self.tipo}:{self.id}" + (f"={self.valor}" if self.valor else "")


class LiteralColuna(_Modelo):
    """Como um valor de dimensao aparece numa coluna (o tipo do literal e o da coluna)."""

    entidade: str
    coluna: str
    valor: str | int


class Componente(RefColuna):
    """Coluna que carrega um valor de dimensao decomposta (ex.: qt_mat_fem) e a metrica-base."""

    metrica: str


class ValorDimensao(_Modelo):
    id: str
    rotulo: str
    rotulo_no_lexico: bool = True
    sinonimos: tuple[Sinonimo, ...] = ()
    literais: tuple[LiteralColuna, ...] = ()
    componentes: tuple[Componente, ...] = ()
    limitacoes: tuple[str, ...] = ()


class ColunaDimensao(RefColuna):
    coluna_rotulo: str | None = None


class DimensaoSemantica(_Modelo):
    id: str
    nome: str
    nome_no_lexico: bool = True
    descricao: str
    # categorica: GROUP BY/WHERE numa coluna; decomposicao: uma coluna por valor;
    # virtual: nao e coluna (nivel territorial, recorte) e vale para toda metrica.
    tipo: Literal["categorica", "decomposicao", "virtual"]
    territorial: bool = False
    colunas: tuple[ColunaDimensao, ...] = ()
    valores: tuple[ValorDimensao, ...] = ()
    valores_enumerados: bool = True  # False: dominio grande, resolvido fora da camada
    n_valores: int | None = None
    sinonimos: tuple[Sinonimo, ...] = ()
    filtravel: bool = True
    agrupavel: bool = True
    so_metricas: tuple[str, ...] = ()  # vazio = qualquer metrica das entidades da dimensao
    niveis_bloqueados: tuple[Nivel, ...] = ()
    ficha: str | None = None
    limitacoes: tuple[str, ...] = ()
    proveniencia: str

    @property
    def entidades(self) -> frozenset[str]:
        """Entidades em que a dimensao existe (vazio para as virtuais)."""
        return frozenset(c.entidade for c in self.colunas) | frozenset(
            c.entidade for v in self.valores for c in v.componentes
        )


class AgregacaoProibida(_Modelo):
    expressao: str
    motivo: str


class Razao(_Modelo):
    """Razao de somas: SUM(numerador) / NULLIF(SUM(denominador), 0) * fator."""

    base: str | None = None  # metrica-base quando a razao existe em mais de uma (IND-R-08/09)
    numerador: RefColuna
    denominador: RefColuna
    nome_numerador: str
    nome_denominador: str
    fator: int = 1

    @property
    def expressao(self) -> str:
        texto = f"SUM({self.numerador.coluna}) / NULLIF(SUM({self.denominador.coluna}), 0)"
        return texto if self.fator == 1 else f"{texto} * {self.fator}"


class Metrica(_Modelo):
    id: str
    ficha: str  # IND-... em docs/tcc/methodology/INDICADORES.md
    nome: str
    nome_no_lexico: bool = True
    descricao: str
    tipo: Literal["direta", "razao", "composicao"]
    entidade: str  # onde a metrica e agregada
    grain: str
    expressao: str  # fragmento SQL fixo (direta/razao) ou formula da ficha (composicao)
    filtro_obrigatorio: str | None = None
    colunas: tuple[RefColuna, ...] = ()
    unidade: str
    recortes: tuple[Recorte, ...]
    exige_dimensao_oferta: bool
    dimensoes_oferta: tuple[Dimensao, ...] = ()  # admitidas em algum nivel
    dimensoes_oferta_territoriais: tuple[Dimensao, ...] = ()  # admitidas com territorio
    dimensoes_oferta_com_registro: tuple[Dimensao, ...] = ()  # onde a soma nao e zero estrutural
    dimensao_oferta_unica: bool = False  # as admitidas nao se somam numa unica consulta
    dimensoes_obrigatorias: tuple[str, ...]
    dimensoes_permitidas: tuple[str, ...]
    niveis: tuple[Nivel, ...]
    niveis_bloqueados: tuple[Nivel, ...] = ()
    agregacoes_permitidas: tuple[str, ...]
    agregacoes_proibidas: tuple[AgregacaoProibida, ...] = ()
    razoes: tuple[Razao, ...] = ()
    bases: tuple[str, ...] = ()  # metricas diretas sobre as quais a razao/composicao e medida
    eixos: tuple[str, ...] = ()  # dimensoes que a composicao reparte
    relacionamentos: tuple[str, ...] = ()
    limitacoes: tuple[str, ...] = ()
    sinonimos: tuple[Sinonimo, ...] = ()
    controle_nacional: int | None = None  # soma de controle de INDICADORES.md (so diretas)
    origem_definicao: str
    proveniencia: str


class Relacionamento(_Modelo):
    id: str
    de: str
    para: str
    cardinalidade: Literal["N:1", "1:1"]
    alias_de: str
    alias_para: str
    predicado: str  # condicao do ON, escrita com os dois alias
    filtro: str | None = None  # WHERE obrigatorio, escrito com os alias
    colunas: tuple[RefColuna, ...]
    pre_condicoes: tuple[str, ...] = ()
    limitacoes: tuple[str, ...] = ()
    proveniencia: str


class RegraDominio(_Modelo):
    """Regra que um QueryPlan nao pode violar, mesmo que o SQL resultante execute."""

    id: str
    nome: str
    enunciado: str
    predicado: str | None = None  # fragmento SQL que a regra impoe, quando ha
    # Aplicabilidade: `sempre`, ou quando o contexto toca alguma destas referencias.
    sempre: bool = False
    entidades: tuple[str, ...] = ()
    metricas: tuple[str, ...] = ()
    dimensoes: tuple[str, ...] = ()
    so_territorial: bool = False  # so quando a pergunta tem nivel/filtro territorial
    proveniencia: str


class TermoVedado(_Modelo):
    """Termo cujo efeito e uma RECUSA explicada — nunca um mapeamento."""

    id: str
    nome: str
    # quarentena: ficha IND-Q; denominacao_vedada: nome recusado numa ficha servida;
    # nao_servido: conceito que a base ou a plataforma nao entrega.
    categoria: Literal["quarentena", "denominacao_vedada", "nao_servido"]
    termos: tuple[Sinonimo, ...] = ()
    # True: a recusa e disparada pela estrutura da pergunta (razao entre duas medidas), sem termo.
    estrutural: bool = False
    motivo: str
    ficha: str | None = None
    alternativas: tuple[Alvo, ...] = ()  # o que pode ser oferecido no lugar, se houver
    regras: tuple[str, ...] = ()  # regras de dominio que explicam a recusa
    proveniencia: str


class Leitura(_Modelo):
    id: str
    descricao: str
    servida: bool = True  # False: leitura que a base nao permite responder
    alvos: tuple[Alvo, ...] = ()
    # A leitura e dada como escolhida pela pergunta se algum destes alvos foi casado nela.
    resolve_se: tuple[Alvo, ...] = ()


class ValorMedido(_Modelo):
    rotulo: str
    valor: int
    leitura: str | None = None


class Medida(_Modelo):
    id: str
    descricao: str
    valores: tuple[ValorMedido, ...]


class Ambiguidade(_Modelo):
    id: str
    nome: str
    descricao: str
    gatilhos: tuple[Sinonimo, ...] = ()  # termos que disparam
    gatilhos_itens: tuple[Alvo, ...] = ()  # itens cuja presenca no contexto dispara
    leituras: tuple[Leitura, ...]
    medidas: tuple[Medida, ...] = ()  # magnitude medida da diferenca entre as leituras
    nota_magnitude: str = ""
    pergunta: str  # o que perguntar ao usuario
    padrao: str | None = None  # None: nao pode ser resolvida em silencio
    justificativa_padrao: str = ""
    regra_resolucao: str
    proveniencia: str


class EntradaLexico(_Modelo):
    chave: str
    termo: str
    alvo: Alvo
    status: StatusSinonimo
    terminologia: str = ""


class CamadaSemantica(_Modelo):
    versao: str
    ano_censo: str
    fontes: tuple[str, ...]
    entidades: tuple[Entidade, ...]
    colunas: tuple[Coluna, ...]
    dimensoes: tuple[DimensaoSemantica, ...]
    metricas: tuple[Metrica, ...]
    relacionamentos: tuple[Relacionamento, ...]
    regras: tuple[RegraDominio, ...]
    termos_vedados: tuple[TermoVedado, ...]
    ambiguidades: tuple[Ambiguidade, ...]

    # --- acesso por id ----------------------------------------------------------------------------

    def entidade(self, id_: str) -> Entidade:
        return next(e for e in self.entidades if e.id == id_)

    def dimensao(self, id_: str) -> DimensaoSemantica:
        return next(d for d in self.dimensoes if d.id == id_)

    def metrica(self, id_: str) -> Metrica:
        return next(m for m in self.metricas if m.id == id_)

    def relacionamento(self, id_: str) -> Relacionamento:
        return next(r for r in self.relacionamentos if r.id == id_)

    def regra(self, id_: str) -> RegraDominio:
        return next(r for r in self.regras if r.id == id_)

    def termo_vedado(self, id_: str) -> TermoVedado:
        return next(t for t in self.termos_vedados if t.id == id_)

    def ambiguidade(self, id_: str) -> Ambiguidade:
        return next(a for a in self.ambiguidades if a.id == id_)

    def coluna(self, entidade: str, nome: str) -> Coluna:
        return next(c for c in self.colunas if c.entidade == entidade and c.nome == nome)

    def nome_tecnico(self, ref: RefColuna) -> str:
        """`tabela.coluna` fisico de uma referencia."""
        return f"{self.entidade(ref.entidade).tabela}.{ref.coluna}"

    # --- lexico -----------------------------------------------------------------------------------

    def entradas_lexico(self) -> tuple[EntradaLexico, ...]:
        """Todo termo que a camada conhece, com o alvo e o status; sem resolver colisoes."""
        entradas: list[EntradaLexico] = []

        def junta(alvo: Alvo, termo: str, status: StatusSinonimo, fala: str = "") -> None:
            entradas.append(
                EntradaLexico(
                    chave=chave(termo), termo=termo, alvo=alvo, status=status, terminologia=fala
                )
            )

        def sinonimos(alvo: Alvo, lista: tuple[Sinonimo, ...]) -> None:
            for s in lista:
                junta(alvo, s.termo, s.status, s.terminologia)

        ver = StatusSinonimo.VERIFICADO
        for e in self.entidades:
            sinonimos(Alvo(tipo="entidade", id=e.id), e.sinonimos)
        for d in self.dimensoes:
            alvo = Alvo(tipo="dimensao", id=str(d.id))
            if d.nome_no_lexico:
                junta(alvo, d.nome, ver)
            sinonimos(alvo, d.sinonimos)
            for v in d.valores:
                alvo_valor = Alvo(tipo="valor", id=str(d.id), valor=str(v.id))
                if v.rotulo_no_lexico:
                    junta(alvo_valor, v.rotulo, ver)
                sinonimos(alvo_valor, v.sinonimos)
        for m in self.metricas:
            alvo = Alvo(tipo="metrica", id=m.id)
            if m.nome_no_lexico:
                junta(alvo, m.nome, ver)
            sinonimos(alvo, m.sinonimos)
        for t in self.termos_vedados:
            sinonimos(Alvo(tipo="recusa", id=t.id), t.termos)
        for a in self.ambiguidades:
            sinonimos(Alvo(tipo="ambiguidade", id=a.id), a.gatilhos)
        return tuple(entradas)

    def lexico(self) -> dict[str, tuple[EntradaLexico, ...]]:
        """Chave normalizada -> entradas. Termo que e gatilho de ambiguidade aponta so para ela."""
        por_chave: dict[str, list[EntradaLexico]] = defaultdict(list)
        for e in self.entradas_lexico():
            por_chave[e.chave].append(e)
        resultado: dict[str, tuple[EntradaLexico, ...]] = {}
        for k, lista in por_chave.items():
            ambiguas = [e for e in lista if e.alvo.tipo == "ambiguidade"]
            resultado[k] = tuple(ambiguas or lista)
        return resultado

    def aliases_de_intencao(self) -> tuple[EntradaLexico, ...]:
        """Todo alias de intencao, com o alvo canonico e a instrucao de terminologia."""
        return tuple(e for e in self.entradas_lexico() if e.status == StatusSinonimo.ALIAS)

    def sinonimos_propostos(self) -> tuple[EntradaLexico, ...]:
        """Todo termo `proposto`, para revisao do autor."""
        vistos: set[tuple[str, str]] = set()
        saida: list[EntradaLexico] = []
        for e in self.entradas_lexico():
            marca = (e.chave, str(e.alvo))
            if e.status == StatusSinonimo.PROPOSTO and marca not in vistos:
                vistos.add(marca)
                saida.append(e)
        return tuple(sorted(saida, key=lambda e: (str(e.alvo), e.chave)))

    # --- integridade ------------------------------------------------------------------------------

    @model_validator(mode="after")
    def _integridade(self) -> Self:
        erros = [
            *self._erros_de_ids(),
            *self._erros_referenciais(),
            *self._erros_de_grain(),
            *self._erros_do_lexico(),
        ]
        if erros:
            raise ValueError("camada semantica inconsistente:\n- " + "\n- ".join(erros))
        return self

    def _erros_de_ids(self) -> list[str]:
        erros: list[str] = []
        grupos: dict[str, list[str]] = {
            "entidade": [e.id for e in self.entidades],
            "dimensao": [d.id for d in self.dimensoes],
            "metrica": [m.id for m in self.metricas],
            "relacionamento": [r.id for r in self.relacionamentos],
            "regra": [r.id for r in self.regras],
            "termo vedado": [t.id for t in self.termos_vedados],
            "ambiguidade": [a.id for a in self.ambiguidades],
            "coluna": [f"{c.entidade}.{c.nome}" for c in self.colunas],
        }
        for tipo, ids in grupos.items():
            repetidos = sorted({i for i in ids if ids.count(i) > 1})
            erros += [f"{tipo} com id repetido: {i}" for i in repetidos]
        for d in self.dimensoes:
            ids = [v.id for v in d.valores]
            erros += [
                f"dimensao {d.id}: valor repetido {i}" for i in sorted(set(ids)) if ids.count(i) > 1
            ]
        for a in self.ambiguidades:
            ids = [x.id for x in a.leituras]
            erros += [
                f"ambiguidade {a.id}: leitura repetida {i}"
                for i in sorted(set(ids))
                if ids.count(i) > 1
            ]
        return erros

    def _alvo_existe(self, alvo: Alvo) -> bool:
        if alvo.tipo == "entidade":
            return any(e.id == alvo.id for e in self.entidades)
        if alvo.tipo == "metrica":
            return any(m.id == alvo.id for m in self.metricas)
        if alvo.tipo == "recusa":
            return any(t.id == alvo.id for t in self.termos_vedados)
        if alvo.tipo == "ambiguidade":
            return any(a.id == alvo.id for a in self.ambiguidades)
        dim = next((d for d in self.dimensoes if d.id == alvo.id), None)
        if dim is None:
            return False
        if alvo.tipo == "dimensao":
            return alvo.valor is None
        return any(v.id == alvo.valor for v in dim.valores)

    def _erros_referenciais(self) -> list[str]:
        erros: list[str] = []
        entidades = {e.id for e in self.entidades}
        dimensoes = {d.id for d in self.dimensoes}
        metricas = {m.id for m in self.metricas}
        relacoes = {r.id for r in self.relacionamentos}
        colunas = {(c.entidade, c.nome): c for c in self.colunas}

        def confere(onde: str, entidade: str, coluna: str, papeis: frozenset[Papel]) -> None:
            col = colunas.get((entidade, coluna))
            if col is None:
                erros.append(f"{onde}: coluna inexistente {entidade}.{coluna}")
            elif col.papel not in papeis:
                erros.append(
                    f"{onde}: {entidade}.{coluna} tem papel '{col.papel}', nao pode ser usada"
                )

        for c in self.colunas:
            if c.entidade not in entidades:
                erros.append(f"coluna {c.entidade}.{c.nome}: entidade inexistente")
        for e in self.entidades:
            for nome in e.chave:
                confere(f"entidade {e.id}", e.id, nome, PAPEIS_EXPOSTOS - {Papel.METRICA})
            if e.metrica_de_contagem is not None and e.metrica_de_contagem not in metricas:
                erros.append(f"entidade {e.id}: metrica de contagem inexistente")
        for d in self.dimensoes:
            onde = f"dimensao {d.id}"
            papeis_dim = frozenset({Papel.DIMENSAO, Papel.CHAVE})
            for cd in d.colunas:
                confere(onde, cd.entidade, cd.coluna, papeis_dim)
                if cd.coluna_rotulo is not None:
                    confere(onde, cd.entidade, cd.coluna_rotulo, papeis_dim)
            pares = {(cd.entidade, cd.coluna) for cd in d.colunas} | {
                (cd.entidade, cd.coluna_rotulo) for cd in d.colunas if cd.coluna_rotulo
            }
            for v in d.valores:
                for lit in v.literais:
                    if (lit.entidade, lit.coluna) not in pares:
                        erros.append(f"{onde}={v.id}: literal em coluna que nao e da dimensao")
                for comp in v.componentes:
                    confere(
                        f"{onde}={v.id}", comp.entidade, comp.coluna, frozenset({Papel.COMPONENTE})
                    )
                    if comp.metrica not in metricas:
                        erros.append(f"{onde}={v.id}: metrica-base inexistente {comp.metrica}")
            if d.tipo == "virtual" and (d.colunas or d.entidades):
                erros.append(f"{onde}: dimensao virtual nao tem coluna")
            if d.tipo == "decomposicao" and (d.colunas or not d.valores):
                erros.append(f"{onde}: decomposicao se define pelos componentes dos valores")
            if d.tipo == "categorica" and not d.colunas:
                erros.append(f"{onde}: dimensao categorica sem coluna")
            erros += [
                f"{onde}: metrica inexistente {m}" for m in d.so_metricas if m not in metricas
            ]
        for m in self.metricas:
            onde = f"metrica {m.id}"
            if m.entidade not in entidades:
                erros.append(f"{onde}: entidade inexistente {m.entidade}")
            papeis_met = frozenset({Papel.METRICA, Papel.COMPONENTE, Papel.CHAVE})
            for ref in m.colunas:
                confere(onde, ref.entidade, ref.coluna, papeis_met)
            for r in m.razoes:
                confere(onde, r.numerador.entidade, r.numerador.coluna, papeis_met)
                confere(onde, r.denominador.entidade, r.denominador.coluna, papeis_met)
                if r.base is not None and r.base not in m.bases:
                    erros.append(f"{onde}: razao sobre base nao declarada {r.base}")
            for campo, ids, universo in (
                ("dimensao obrigatoria", m.dimensoes_obrigatorias, dimensoes),
                ("dimensao permitida", m.dimensoes_permitidas, dimensoes),
                ("eixo", m.eixos, dimensoes),
                ("base", m.bases, metricas),
                ("relacionamento", m.relacionamentos, relacoes),
            ):
                erros += [f"{onde}: {campo} inexistente {i}" for i in ids if i not in universo]
            erros += [
                f"{onde}: dimensao obrigatoria fora das permitidas: {i}"
                for i in m.dimensoes_obrigatorias
                if i not in m.dimensoes_permitidas
            ]
            erros += [
                f"{onde}: eixo fora das permitidas: {i}"
                for i in m.eixos
                if i not in m.dimensoes_permitidas
            ]
            if not set(m.niveis_bloqueados) <= set(m.niveis):
                erros.append(f"{onde}: nivel bloqueado que nao e nivel da metrica")
        for rel in self.relacionamentos:
            onde = f"relacionamento {rel.id}"
            erros += [
                f"{onde}: entidade inexistente {x}"
                for x in (rel.de, rel.para)
                if x not in entidades
            ]
            for ref in rel.colunas:
                confere(onde, ref.entidade, ref.coluna, frozenset({Papel.CHAVE, Papel.ESTRUTURAL}))
        for g in self.regras:
            onde = f"regra {g.id}"
            erros += [
                f"{onde}: entidade inexistente {x}" for x in g.entidades if x not in entidades
            ]
            erros += [f"{onde}: metrica inexistente {x}" for x in g.metricas if x not in metricas]
            erros += [
                f"{onde}: dimensao inexistente {x}" for x in g.dimensoes if x not in dimensoes
            ]
            citada = any(g.id in t.regras for t in self.termos_vedados)
            if not (g.sempre or g.entidades or g.metricas or g.dimensoes or citada):
                erros.append(f"{onde}: regra sem aplicabilidade declarada")
        regras = {g.id for g in self.regras}
        for t in self.termos_vedados:
            erros += [
                f"termo vedado {t.id}: regra inexistente {r}" for r in t.regras if r not in regras
            ]
            erros += [
                f"termo vedado {t.id}: alternativa inexistente {a}"
                for a in t.alternativas
                if not self._alvo_existe(a)
            ]
            if t.categoria == "quarentena" and not (t.ficha or "").startswith("IND-Q-"):
                erros.append(f"termo vedado {t.id}: quarentena exige ficha IND-Q")
            if not t.termos and not t.estrutural:
                erros.append(f"termo vedado {t.id}: sem termo")
        for a in self.ambiguidades:
            onde = f"ambiguidade {a.id}"
            leituras = {x.id: x for x in a.leituras}
            if len(leituras) < 2:
                erros.append(f"{onde}: precisa de ao menos duas leituras")
            if not (a.gatilhos or a.gatilhos_itens):
                erros.append(f"{onde}: sem gatilho")
            if a.padrao is not None:
                if a.padrao not in leituras:
                    erros.append(f"{onde}: padrao nao e uma leitura")
                elif not leituras[a.padrao].servida:
                    erros.append(f"{onde}: padrao aponta para leitura nao servida")
                if not a.justificativa_padrao:
                    erros.append(f"{onde}: padrao exige decisao registrada")
            for alvo in (
                *a.gatilhos_itens,
                *(x for lt in a.leituras for x in (*lt.alvos, *lt.resolve_se)),
            ):
                if not self._alvo_existe(alvo) or alvo.tipo in ("recusa", "ambiguidade"):
                    erros.append(f"{onde}: alvo invalido {alvo}")
            for med in a.medidas:
                erros += [
                    f"{onde}: medida {med.id} cita leitura inexistente {v.leitura}"
                    for v in med.valores
                    if v.leitura is not None and v.leitura not in leituras
                ]
        return erros

    def _erros_de_grain(self) -> list[str]:
        """As cinco regras de dominio de AI_ANALYST.md que cabem na estrutura da metrica."""
        erros: list[str] = []
        dims = {d.id: d for d in self.dimensoes}
        oferta = next((d for d in self.dimensoes if d.id == "dimensao"), None)
        for m in self.metricas:
            onde = f"metrica {m.id}"
            if "recorte" not in m.dimensoes_obrigatorias:
                erros.append(f"{onde}: toda metrica declara o recorte territorial (ADR-0004)")
            if not m.recortes:
                erros.append(f"{onde}: sem recorte admitido")
            if m.entidade == "cursos":
                if not m.exige_dimensao_oferta or "dimensao" not in m.dimensoes_obrigatorias:
                    erros.append(f"{onde}: metrica de cursos exige a dimensao de oferta")
                if not m.dimensoes_oferta:
                    erros.append(f"{onde}: sem dimensao de oferta admitida")
            else:
                if (
                    m.exige_dimensao_oferta
                    or m.dimensoes_oferta
                    or "dimensao" in m.dimensoes_permitidas
                ):
                    erros.append(f"{onde}: so a tabela de cursos tem dimensao de oferta")
            if not set(m.dimensoes_oferta_territoriais) <= set(m.dimensoes_oferta):
                erros.append(f"{onde}: dimensao territorial fora das admitidas")
            if not set(m.dimensoes_oferta_com_registro) <= set(m.dimensoes_oferta):
                erros.append(f"{onde}: dimensao com registro fora das admitidas")
            if m.entidade == "ies":
                if m.recortes != (Recorte.SEDE,):
                    erros.append(f"{onde}: metrica de IES so existe no recorte sede")
                fora = [
                    r
                    for r in (
                        *m.colunas,
                        *(x for z in m.razoes for x in (z.numerador, z.denominador)),
                    )
                    if r.entidade != "ies"
                ]
                if fora:
                    erros.append(f"{onde}: metrica de IES so agrega no grain de IES")
            for id_dim in m.dimensoes_permitidas:
                d = dims.get(id_dim)
                if d is None or d.tipo == "virtual":
                    continue
                if m.entidade not in d.entidades and not (set(m.bases) & set(d.so_metricas)):
                    erros.append(f"{onde}: dimensao {id_dim} nao existe em '{m.entidade}'")
                if (
                    d.so_metricas
                    and m.id not in d.so_metricas
                    and not (set(m.bases) & set(d.so_metricas))
                ):
                    erros.append(f"{onde}: dimensao {id_dim} e restrita a {d.so_metricas}")
            if m.tipo == "composicao" and not m.eixos:
                erros.append(f"{onde}: composicao sem eixo")
            if m.tipo == "razao" and not m.razoes:
                erros.append(f"{onde}: razao sem numerador/denominador")
            if m.tipo == "direta" and m.controle_nacional is None:
                erros.append(f"{onde}: metrica direta sem soma de controle")
        if oferta is not None and {v.id for v in oferta.valores} != {str(x) for x in Dimensao}:
            erros.append("dimensao de oferta: valores diferem do enum Dimensao")
        return erros

    def _erros_do_lexico(self) -> list[str]:
        """Um termo so pode ter dois alvos se uma ambiguidade declarada o tiver como gatilho."""
        erros: list[str] = []
        por_chave: dict[str, set[Alvo]] = defaultdict(set)
        for e in self.entradas_lexico():
            if e.status == StatusSinonimo.ALIAS and e.alvo.tipo not in ("metrica", "valor"):
                erros.append(f"alias de intencao '{e.termo}' tem de apontar para metrica ou valor")
            if not e.chave:
                erros.append(f"termo vazio apos normalizacao: '{e.termo}' ({e.alvo})")
            por_chave[e.chave].add(e.alvo)
        leituras = {a.id: {x for lt in a.leituras for x in lt.alvos} for a in self.ambiguidades}
        for k, alvos in sorted(por_chave.items()):
            if k in STOPWORDS or k in OPERADORES or k in NEGACOES or k in FRASES_IGNORADAS:
                erros.append(f"termo '{k}' e stopword/operador/frase ignorada: nunca seria casado")
            if len(alvos) == 1:
                continue
            nomes = ", ".join(sorted(str(a) for a in alvos))
            if any(a.tipo == "recusa" for a in alvos):
                erros.append(f"termo vedado '{k}' tambem resolve para outro alvo: {nomes}")
                continue
            ambiguas = [a for a in alvos if a.tipo == "ambiguidade"]
            if len(ambiguas) != 1:
                erros.append(f"termo '{k}' aponta para alvos diferentes sem ambiguidade: {nomes}")
                continue
            fora = [
                a for a in alvos if a.tipo != "ambiguidade" and a not in leituras[ambiguas[0].id]
            ]
            if fora:
                erros.append(
                    f"termo '{k}': alvo fora das leituras de {ambiguas[0].id}: "
                    + ", ".join(sorted(str(a) for a in fora))
                )
        return erros
