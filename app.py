"""Human + Desk (Streamlit). Rodar:  streamlit run app.py

Ponto de entrada: configura a página, o ambiente e a navegação. As telas vivem
em `src/ui_marina.py` (Central de Atendimento) e `src/ui_rafael.py`
(Gestão e Qualidade); textos em `src/textos.py`; identidade visual em
`src/tema_dxc.py`.

A IA só sugere; aqui nada é enviado de verdade: toda decisão fica registrada
na auditoria.
"""
import logging
import os

import streamlit as st

from src import auditoria, repositorio
from src.config import (
    carregar_env,
    configurar_log,
    resolver_config,
    validar_ambiente,
)
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

# Infraestrutura: logging + config + validação de segurança (fail-closed).
configurar_log()
carregar_env(RAIZ / ".env")
_config = resolver_config()
validar_ambiente(_config)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Human + Desk",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Cria human_desk.db na raiz do projeto e reconcilia decisões antigas do JSONL.
# Banco ciente: se falhar, a aplicação segue em modo demonstração e avisa a
# analista, em vez de travar a sessão.
try:
    repositorio.init_db(concluidos=ids_decididos(auditoria.ler(LOG)))
    repositorio.exportar_auditoria_pendente(LOG)
except Exception:  # pragma: no cover - IO/DB temporária, não quebra a UI
    logger.exception("app: inicialização do banco/atlas falhou; rodando sem persistência")
    st.warning(
        "Não foi possível inicializar o banco de dados. "
        "Apenas a demonstração local será exibida."
    )


def main() -> None:
    """Painel: sidebar, navegação e render de uma das telas.

    A parte de manipulação de estado de sessão (tema, idioma, provedor) fica
    aqui, e a renderização de cada tela é tratada com uma defesa final, para
    que um vazamento de exceção em uma tela não mate a sessão.
    """
    _, coluna_idioma = st.columns([9.4, 1.6])
    with coluna_idioma:
        # Alternar um slot vazio antes do popover muda seu delta_path no React
        # a cada clique em PT/EN, desmontando o popover aberto e fechando-o.
        if int(st.session_state.get("_lang_seq", 0)) % 2 == 1:
            st.empty()
        idioma = render_language_selector()
    txt = I18N[idioma]

    with st.sidebar:
        # Reatribuir as chaves antes dos widgets força o Streamlit a enviar
        # set_value=True com o raw_value traduzido do idioma atual (evita radio
        # desmarcado e selectbox preso no texto do idioma anterior ao trocar
        # PT <-> EN).
        st.session_state["tema_ui"] = (
            "Claro" if st.session_state.get("tema_ui") == "Claro" else "Escuro"
        )
        tema = st.segmented_control(
            txt["appearance"],
            options=["Escuro", "Claro"],
            format_func=lambda k: txt["dark"] if k == "Escuro" else txt["light"],
            key="tema_ui",
        )
        modo_escuro = tema != "Claro"
        render_dxc_theme(modo_escuro)
        render_dxc_logo(modo_escuro)

        pagina_atual = st.session_state.get("nav_pagina_ui")
        st.session_state["nav_pagina_ui"] = (
            pagina_atual if pagina_atual in ("marina", "rafael") else "marina"
        )
        pagina = st.radio(
            txt["nav_label"],
            ["marina", "rafael"],
            format_func=lambda k: txt["nav_marina"] if k == "marina" else txt["nav_rafael"],
            key="nav_pagina_ui",
        )
        st.divider()
        valor_prov = str(st.session_state.get("provider_ui", "regras")).strip().lower()
        st.session_state["provider_ui"] = "gemini" if "gemini" in valor_prov else "regras"
        provider = st.selectbox(
            txt["adapter"],
            ["regras", "gemini"],
            format_func=lambda k: txt["rules_opt"] if k == "regras" else txt["gemini_opt"],
            help=txt["adapter_help"],
            key="provider_ui",
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
    try:
        with usar_contadores():
            if pagina == "marina":
                tela_marina(provider, txt, agente="Marina")
            else:
                tela_rafael(provider, escuro=modo_escuro, txt=txt)
    except Exception:  # pragma: no cover - defesa contra exceção em uma tela
        logger.exception("app: tela %r lançou exceção", pagina)
        st.error(
            "Ocorreu um erro ao renderizar esta tela. "
            "Confira o log do servidor."
        )


if __name__ == "__main__":
    main()
