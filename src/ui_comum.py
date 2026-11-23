"""Elementos compartilhados pelas telas: caminhos, cache da fila, formatação e gráficos.

Camada de apresentação. Regras de negócio ficam em `src/painel.py`,
persistência em `src/repositorio.py` e textos em `src/textos.py`.
"""
import json
from datetime import datetime
from pathlib import Path

import altair as alt
import streamlit as st

from src.painel import carregar_historico, montar_fila

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "data" / "painel_log.jsonl"
LOG_SIM = RAIZ / "data" / "painel_simulado.jsonl"
CONFIG = RAIZ / "data" / "calibracao_config.json"

COR = {"alta": "🔴", "media": "🟠", "baixa": "🟢"}
DESTAQUE_ROXO = "#7C3AED"
DESTAQUE_LARANJA = "#FF6B00"


@st.cache_data(show_spinner="Montando a fila com o motor de IA escolhido…")
def fila_base(provider: str = "regras", model: str = ""):
    chamados = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
    hist = carregar_historico(RAIZ / "data" / "historico_simulado.json")
    return montar_fila(chamados, hist, provider=provider, model=model or None)


def formatar_data_hora(iso_str: str | None) -> str:
    """Converte timestamp ISO (UTC) para data e hora local: DD/MM/AAAA às HH:MM:SS."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    except ValueError:
        return iso_str[:19].replace("T", " ")


def nome_sinal(sinal: str, txt: dict) -> str:
    """Rótulo legível de um sinal da triagem (ou de uma evidência do histórico)."""
    if sinal.startswith("historico:"):
        return f"Histórico ({sinal.split(':', 1)[1]})"
    return txt["sinais"].get(sinal, sinal.replace("_", " ").capitalize())


def estilizar_grafico(chart: alt.Chart, escuro: bool = True) -> alt.Chart:
    """Ajusta eixos e legendas de um gráfico Altair ao tema Claro/Escuro."""
    lbl = "#CBD5E1" if escuro else "#334155"
    tit = "#94A3B8" if escuro else "#475569"
    grd = "rgba(148, 163, 184, 0.12)" if escuro else "rgba(15, 23, 42, 0.08)"
    dom = "rgba(148, 163, 184, 0.25)" if escuro else "rgba(15, 23, 42, 0.18)"
    return (
        chart.configure_view(strokeWidth=0, fill="transparent")
        .configure(background="transparent")
        .configure_axis(labelColor=lbl, titleColor=tit, gridColor=grd, domainColor=dom)
        .configure_legend(labelColor=lbl, titleColor=tit)
    )
