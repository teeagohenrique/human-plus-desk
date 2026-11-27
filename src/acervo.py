"""Acervo fictício: materiais de solução de problemas usados como extensão do Registro.

Cada material tem tópicos; cada tópico descreve um problema recorrente, palavras-chave,
uma solução provisória curta (sem prazo) e uma tabela de tempo por cenário.
O prazo enviado ao cliente é sempre escrito pela analista (Marina): as funções de
estimativa daqui são apenas apoio e nunca preenchem o campo sozinhas.
Todo o conteúdo é inventado para a simulação.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_ACERVO = RAIZ / "data" / "acervo_simulado.json"
CAMINHO_ACERVO_EN = RAIZ / "data" / "acervo_simulado_en.json"


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


@lru_cache(maxsize=8)
def _carregar_por_mtime(caminho_resolvido: Path, mtime_ns: int) -> tuple[Material, ...]:
    _ = mtime_ns
    dados = json.loads(caminho_resolvido.read_text(encoding="utf-8"))
    materiais = []
    for m in dados["materiais"]:
        for t in m["topicos"]:
            t["material_id"] = m["id"]
            t["material_titulo"] = m["titulo"]
        materiais.append(Material(**m))
    return tuple(materiais)


def carregar(caminho: Path = CAMINHO_ACERVO) -> tuple[Material, ...]:
    alvo = Path(caminho)
    return _carregar_por_mtime(alvo, alvo.stat().st_mtime_ns)


setattr(carregar, "cache_clear", _carregar_por_mtime.cache_clear)


def todos_topicos(caminho: Path = CAMINHO_ACERVO) -> list[Topico]:
    return [t for m in carregar(caminho) for t in m.topicos]


@lru_cache(maxsize=4)
def _traducoes_en_por_mtime(caminho_resolvido: Path, mtime_ns: int) -> dict:
    _ = mtime_ns
    dados: dict = json.loads(caminho_resolvido.read_text(encoding="utf-8"))
    return dados


def _carregar_traducoes_en(caminho: Path = CAMINHO_ACERVO_EN) -> dict:
    alvo = Path(caminho)
    return _traducoes_en_por_mtime(alvo, alvo.stat().st_mtime_ns)


def texto_material(material_id: str, campo: str, idioma: str = "PT") -> str:
    """Texto localizado de um material; ausências caem de forma explícita para PT."""
    material = next((m for m in carregar() if m.id == material_id), None)
    if material is None:
        return ""
    base: str = getattr(material, campo)
    if idioma.upper() != "EN":
        return base
    chave = {"titulo": "title", "resumo": "summary"}.get(campo)
    traduzido: str | None = _carregar_traducoes_en().get("materials", {}).get(material_id, {}).get(chave)
    return traduzido or base


def texto_topico(topico: Topico, campo: str, idioma: str = "PT") -> Any:
    """Texto localizado do tópico, preservando o conteúdo original como fallback."""
    base = getattr(topico, campo)
    if idioma.upper() != "EN":
        return base
    chave = {
        "titulo": "title",
        "problema": "problem",
        "solucao_provisoria": "solution",
        "passos": "steps",
    }.get(campo)
    traduzido = _carregar_traducoes_en().get("topics", {}).get(topico.id, {}).get(chave)
    return traduzido or base


def cenarios_topico(topico: Topico, idioma: str = "PT") -> list[str]:
    """Rótulos localizados dos cenários, mantendo o alinhamento das faixas de tempo."""
    base = [faixa.cenario for faixa in topico.tabela_tempo]
    if idioma.upper() != "EN":
        return base
    traduzidos = _carregar_traducoes_en().get("topics", {}).get(topico.id, {}).get("scenarios")
    return traduzidos if isinstance(traduzidos, list) and len(traduzidos) == len(base) else base


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


FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")
INICIO_EXPEDIENTE = time(9, 0)
FIM_EXPEDIENTE = time(18, 0)


def _proximo_dia_util(data: date) -> date:
    proxima = data + timedelta(days=1)
    while proxima.weekday() >= 5:
        proxima += timedelta(days=1)
    return proxima


def _ajustar_para_expediente(instante: datetime) -> datetime:
    """Move para o próximo minuto dentro do expediente de segunda a sexta."""
    local = instante.replace(tzinfo=FUSO_HORARIO) if instante.tzinfo is None else instante.astimezone(FUSO_HORARIO)
    while True:
        if local.weekday() >= 5:
            local = datetime.combine(_proximo_dia_util(local.date()), INICIO_EXPEDIENTE, FUSO_HORARIO)
        elif local.time() < INICIO_EXPEDIENTE:
            local = datetime.combine(local.date(), INICIO_EXPEDIENTE, FUSO_HORARIO)
        elif local.time() >= FIM_EXPEDIENTE:
            local = datetime.combine(_proximo_dia_util(local.date()), INICIO_EXPEDIENTE, FUSO_HORARIO)
        else:
            return local


def _somar_minutos_uteis(instante: datetime, minutos: int) -> datetime:
    """Soma minutos de expediente (09h–18h, dias úteis, sem calendário de feriados)."""
    local = _ajustar_para_expediente(instante)
    restantes = minutos
    while restantes > 0:
        fechamento = datetime.combine(local.date(), FIM_EXPEDIENTE, FUSO_HORARIO)
        disponiveis = int((fechamento - local).total_seconds() // 60)
        if restantes <= disponiveis:
            return local + timedelta(minutes=restantes)
        restantes -= disponiveis
        local = datetime.combine(_proximo_dia_util(local.date()), INICIO_EXPEDIENTE, FUSO_HORARIO)
    return local


def estimar(topico: Topico, indice_cenario: int, agora: datetime | None = None) -> Estimativa:
    """Estima a janela em minutos úteis, de segunda a sexta, 09h–18h em São Paulo.

    As faixas são fictícias, não constituem SLA e não incluem feriados. Horários
    ingênuos são interpretados como horário local de São Paulo.
    """
    agora = agora or datetime.now(FUSO_HORARIO)
    if indice_cenario < 0 or indice_cenario >= len(topico.tabela_tempo):
        raise ValueError(f"índice_cenario {indice_cenario} fora da faixa [0, {len(topico.tabela_tempo) - 1}]")
    faixa = topico.tabela_tempo[indice_cenario]
    inicio = _ajustar_para_expediente(agora)
    return Estimativa(
        cenario=faixa.cenario,
        minutos_min=faixa.min,
        minutos_max=faixa.max,
        previsto_de=_somar_minutos_uteis(inicio, faixa.min),
        previsto_ate=_somar_minutos_uteis(inicio, faixa.max),
    )
