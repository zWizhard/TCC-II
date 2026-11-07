"""A camada semantica montada: fonte unica da verdade para o Analista IA.

`CAMADA` e construida na importacao; se alguma referencia estiver pendente, a importacao falha
(ver `CamadaSemantica._integridade`). Exportacao: `CAMADA.model_dump_json()`; schema:
`CamadaSemantica.model_json_schema()`.
"""

from api.semantica.colunas import COLUNAS
from api.semantica.dimensoes import DIMENSOES
from api.semantica.dominio import ENTIDADES, REGRAS, RELACIONAMENTOS
from api.semantica.fontes import DIRETORIO_DIAGNOSTICOS, INVENTARIO_CSV, VERIFICACOES_CSV
from api.semantica.metricas import METRICAS
from api.semantica.modelos import CamadaSemantica, EntradaLexico
from api.semantica.restricoes import AMBIGUIDADES, TERMOS_VEDADOS

CAMADA = CamadaSemantica(
    versao="2026-10-07.2",
    ano_censo="2024",
    fontes=(
        f"{DIRETORIO_DIAGNOSTICOS}/{INVENTARIO_CSV}",
        f"{DIRETORIO_DIAGNOSTICOS}/{VERIFICACOES_CSV}",
        "docs/tcc/methodology/INDICADORES.md",
        "docs/tcc/architecture/AI_ANALYST.md",
        "api/indicadores.py",
    ),
    entidades=ENTIDADES,
    colunas=COLUNAS,
    dimensoes=DIMENSOES,
    metricas=METRICAS,
    relacionamentos=RELACIONAMENTOS,
    regras=REGRAS,
    termos_vedados=TERMOS_VEDADOS,
    ambiguidades=AMBIGUIDADES,
)


def listar_sinonimos_propostos() -> tuple[EntradaLexico, ...]:
    """Sinonimos `proposto` (coloquiais, escolhidos por nos), para o autor confirmar."""
    return CAMADA.sinonimos_propostos()
