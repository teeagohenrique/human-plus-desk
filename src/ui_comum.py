"""Elementos compartilhados pelas telas: caminhos, cache da fila, formatação e gráficos.

Camada de apresentação. Regras de negócio ficam em `src/painel.py`,
persistência em `src/repositorio.py` e textos em `src/textos.py`.
"""
import inspect
import json
import re
from datetime import datetime
from pathlib import Path

import altair as alt
import streamlit as st

from src.painel import carregar_historico, montar_fila
from src.percepcao import JANELA_DIAS, LEITURAS

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "data" / "painel_log.jsonl"
LOG_SIM = RAIZ / "data" / "painel_simulado.jsonl"
CONFIG = RAIZ / "data" / "calibracao_config.json"

COR = {"alta": "🔴", "media": "🟠", "baixa": "🟢"}
DESTAQUE_ROXO = "#7C3AED"
DESTAQUE_LARANJA = "#FF6B00"
_RE_PADRAO = re.compile(r"há (\d+) chamados.*?últimos (\d+) dias")


@st.cache_resource
def _cache_filas() -> dict[tuple[str, str], list]:
    return {}


def _aceita_progresso(fn) -> bool:
    try:
        return "ao_avancar" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _limpar_cache_filas() -> None:
    _cache_filas().clear()


def fila_base(provider: str = "regras", model: str = "", txt: dict | None = None):
    chave = (provider, model or "")
    cache = _cache_filas()
    if chave in cache:
        return list(cache[chave])

    chamados = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
    hist = carregar_historico(RAIZ / "data" / "historico_simulado.json")
    modelo_arg = model or None

    if provider == "gemini" and _aceita_progresso(montar_fila):
        total_etapas = len(chamados) * 2
        t = txt or {}
        tpl_init = t.get("gemini_progress_init", "Montando a fila com Gemini: 0/{total}…")
        tpl_step = t.get("gemini_progress_step", "Montando a fila com Gemini: {passo}/{total} ({etapa})")
        lbl_triagem = t.get("triage", "Triagem")
        lbl_sugestao = t.get("draft", "Sugestão")
        slot = st.empty()
        barra = slot.progress(0.0, text=tpl_init.format(total=total_etapas))

        def _atualizar(passo: int, total: int, etapa: str) -> None:
            cid, fase = etapa.split(":", 1) if ":" in etapa else ("", etapa)
            fase_lbl = lbl_triagem if fase == "triagem" else lbl_sugestao
            desc = f"{cid} · {fase_lbl}" if cid else fase_lbl
            frac = min(1.0, passo / total) if total else 1.0
            barra.progress(frac, text=tpl_step.format(passo=passo, total=total, etapa=desc))

        try:
            itens = montar_fila(chamados, hist, provider=provider, model=modelo_arg, ao_avancar=_atualizar)
        finally:
            slot.empty()
    else:
        itens = montar_fila(chamados, hist, provider=provider, model=modelo_arg)

    cache[chave] = list(itens)
    return itens


fila_base.clear = _limpar_cache_filas


def formatar_data_hora(iso_str: str | None, lang: str = "PT") -> str:
    """Converte timestamp ISO (UTC) para data e hora local (PT ou EN)."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        fmt = "%Y-%m-%d at %H:%M:%S" if lang == "EN" else "%d/%m/%Y às %H:%M:%S"
        return dt.strftime(fmt)
    except ValueError:
        return iso_str[:19].replace("T", " ")


def nome_sinal(sinal: str, txt: dict) -> str:
    """Rótulo legível de um sinal da triagem (ou de uma evidência do histórico)."""
    if sinal.startswith("historico:"):
        prefixo = txt.get("history_prefix", "Histórico")
        return f"{prefixo} ({sinal.split(':', 1)[1]})"
    return txt["sinais"].get(sinal, sinal.replace("_", " ").capitalize())


def traduzir_leitura(chave: str, txt: dict) -> str:
    """Rótulo traduzido de uma interpretação padronizada do caso."""
    return txt.get("leituras", {}).get(chave) or LEITURAS.get(chave, chave)


def traduzir_palpite(palpite, txt: dict) -> tuple[str, str]:
    """Traduz hipótese e pergunta de confirmação a partir de `palpite.tipo`."""
    tipo = getattr(palpite, "tipo", "")
    hip_tpl = txt.get("hipoteses", {}).get(tipo)
    perg = txt.get("perguntas_hipotese", {}).get(tipo) or palpite.pergunta_confirmacao
    if not hip_tpl:
        return palpite.hipotese, perg
    n_ev = len(getattr(palpite, "evidencias", ()) or ())
    return hip_tpl.format(n=n_ev, dias=JANELA_DIAS), perg


def traduzir_hipotese_salva(texto: str, n_evidencias: int, txt: dict) -> str:
    """Traduz hipóteses salvas em registros de supervisão pela estrutura PT."""
    hips = txt.get("hipoteses", {})
    if not hips or txt.get("lang_code") == "PT":
        return texto
    if "solução provisória" in texto or "prazo mencionado" in texto:
        return hips.get("necessidade_nao_dita", texto)
    if "caso isolado" in texto:
        m = _RE_PADRAO.search(texto)
        n = int(m.group(1)) if m else n_evidencias
        dias = int(m.group(2)) if m else JANELA_DIAS
        tpl = hips.get("padrao")
        return tpl.format(n=n, dias=dias) if tpl else texto
    if "repetição pode estar pesando" in texto:
        return hips.get("risco_recorrencia", texto)
    return texto


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
