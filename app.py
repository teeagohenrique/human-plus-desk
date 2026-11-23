"""Human + Desk (Streamlit). Rodar:  streamlit run app.py

Ponto de entrada enxuto: configura a página, o tema e a navegação. As telas vivem em
`src/ui_marina.py` (Central de Atendimento) e `src/ui_rafael.py` (Gestão e Qualidade);
textos em `src/textos.py`; identidade visual em `src/tema_dxc.py`.
A IA só sugere; aqui nada é enviado de verdade: toda decisão fica registrada na auditoria.
"""
import os

import streamlit as st

from src import auditoria, repositorio
from src.config import carregar_env
from src.llm import usar_contadores
from src.painel import ids_decididos
from src.tema_dxc import (
    I18N,
    render_dxc_logo,
    render_dxc_theme,
    render_language_selector,
)
from src.ui_comum import LOG, RAIZ
from src.ui_marina import tela_marina
from src.ui_rafael import tela_rafael

st.set_page_config(page_title="Human + Desk", page_icon="💠", layout="wide", initial_sidebar_state="expanded")
carregar_env(RAIZ / ".env")

# Cria human_desk.db na raiz do projeto e reconcilia decisões antigas do JSONL.
repositorio.init_db(concluidos=ids_decididos(auditoria.ler(LOG)))

_, coluna_idioma = st.columns([9.4, 1.6])
with coluna_idioma:
    idioma = render_language_selector()
txt = I18N[idioma]

with st.sidebar:
    tema = st.segmented_control(
        txt["appearance"],
        options=["Escuro", "Claro"],
        default="Escuro",
        format_func=lambda k: txt["dark"] if k == "Escuro" else txt["light"],
        key="tema_ui",
    )
    modo_escuro = tema != "Claro"
    render_dxc_theme(modo_escuro)
    render_dxc_logo(modo_escuro)

    pagina = st.radio(
        txt["nav_label"],
        ["marina", "rafael"],
        format_func=lambda k: txt["nav_marina"] if k == "marina" else txt["nav_rafael"],
    )
    st.divider()
    provider = st.selectbox(
        txt["adapter"],
        ["regras", "gemini"],
        index=0,
        format_func=lambda k: txt["rules_opt"] if k == "regras" else txt["gemini_opt"],
        help=txt["adapter_help"],
    )
    if provider == "gemini":
        st.info(txt["gemini_first_load_warn"])
        if not os.getenv("GEMINI_API_KEY"):
            st.warning(txt["gemini_missing_key"])
        if not os.getenv("GEMINI_MODEL"):
            st.warning(txt["gemini_missing_model"])
        st.caption(txt["gemini_env_caption"])

    st.divider()
    st.caption(txt["footer"])

# Cada rerun ganha contadores próprios: a tela nunca suja as métricas da CLI.
with usar_contadores():
    if pagina == "marina":
        tela_marina(provider, txt, agente="Marina")
    else:
        tela_rafael(provider, escuro=modo_escuro, txt=txt)
