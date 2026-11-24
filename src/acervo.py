"""Acervo fictício: materiais de solução de problemas usados como extensão do Registro.

Cada material tem tópicos; cada tópico descreve um problema recorrente, palavras-chave,
uma solução provisória curta (sem prazo) e uma tabela de tempo por cenário.
O prazo enviado ao cliente é sempre escrito pela analista (Marina): as funções de
estimativa daqui são apenas apoio e nunca preenchem o campo sozinhas.
Todo o conteúdo é inventado para a simulação.
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_ACERVO = RAIZ / "data" / "acervo_simulado.json"


class FaixaTempo(BaseModel):
    cenario: str
    min: int  # minutos
    max: int  # minutos


class Topico(BaseModel):
    id: str
    titulo: str
    intencoes: list[str]
    problema: str
    palavras_chave: list[str] = []
    solucao_provisoria: str
    passos: list[str]
    tabela_tempo: list[FaixaTempo]
    material_id: str = ""
    material_titulo: str = ""


class Material(BaseModel):
    id: str
    titulo: str
    resumo: str
    topicos: list[Topico]


class Estimativa(BaseModel):
    cenario: str
    minutos_min: int
    minutos_max: int
    previsto_de: datetime
    previsto_ate: datetime


@lru_cache(maxsize=4)
def carregar(caminho: Path = CAMINHO_ACERVO) -> tuple[Material, ...]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    materiais = []
    for m in dados["materiais"]:
        for t in m["topicos"]:
            t["material_id"] = m["id"]
            t["material_titulo"] = m["titulo"]
        materiais.append(Material(**m))
    return tuple(materiais)


def todos_topicos(caminho: Path = CAMINHO_ACERVO) -> list[Topico]:
    return [t for m in carregar(caminho) for t in m.topicos]


def obter_topico(topico_id: str, caminho: Path = CAMINHO_ACERVO) -> Topico | None:
    return next((t for t in todos_topicos(caminho) if t.id == topico_id), None)


class Correspondencia(BaseModel):
    topico: Topico
    palavras: list[str]  # palavras-chave do tópico encontradas no texto do chamado


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")


def buscar(texto: str, intencao: str | None = None, caminho: Path = CAMINHO_ACERVO) -> Correspondencia | None:
    """Tópico do acervo que melhor descreve o problema do chamado, ou None.

    Sem palavra-chave encontrada no texto não há correspondência (evidência primeiro);
    a intenção só desempata/reforça. Ignora acentos e maiúsculas.
    """
    alvo = _normalizar(texto)
    melhor: tuple[tuple[int, int], Correspondencia] | None = None
    for t in todos_topicos(caminho):
        achadas: list[str] = []
        vistas: set[str] = set()
        primeira = len(alvo)
        for k in t.palavras_chave:
            nk = _normalizar(k)
            if nk in vistas:  # 'relatório' e 'relatorio' contam como uma palavra só
                continue
            m = re.search(rf"(?<!\w){re.escape(nk)}(?!\w)", alvo)
            if m:
                vistas.add(nk)
                achadas.append(k)
                primeira = min(primeira, m.start())
        if not achadas:
            continue
        # Mais palavras e intenção compatível vencem; no empate, a palavra que aparece antes no texto.
        chave = (len(achadas) * 2 + (1 if intencao in t.intencoes else 0), -primeira)
        if melhor is None or chave > melhor[0]:
            melhor = (chave, Correspondencia(topico=t, palavras=achadas))
    return melhor[1] if melhor else None


def estimar(topico: Topico, indice_cenario: int, agora: datetime | None = None) -> Estimativa:
    """Converte a faixa de tempo do cenário em janela de hora e data a partir de `agora`.

    Apoio à Marina: mostra a janela provável, mas quem escreve o prazo é ela.
    """
    agora = agora or datetime.now()
    faixa = topico.tabela_tempo[indice_cenario]
    return Estimativa(
        cenario=faixa.cenario,
        minutos_min=faixa.min,
        minutos_max=faixa.max,
        previsto_de=agora + timedelta(minutes=faixa.min),
        previsto_ate=agora + timedelta(minutes=faixa.max),
    )
