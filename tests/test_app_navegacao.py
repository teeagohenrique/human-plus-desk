"""Navegacao do entrypoint Streamlit (app.py) com AppTest.

O arquivo de entrada executa `init_db` e carrega o .env no topo (app.py:26-30):
os dois sao patchados para o teste nao gravar no SQLite nem ler segredos reais.
A fila tambem entra controlada, para nao chamar LLM.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.textos import I18N

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TXT = I18N["PT"]


@contextmanager
def _app(itens):
    """AppTest do entrypoint com as entradas externas isoladas."""
    with ExitStack() as pilha:
        mocks = {
            "init_db": pilha.enter_context(patch("src.repositorio.init_db")),
            "carregar_env": pilha.enter_context(patch("src.config.carregar_env")),
        }
        pilha.enter_context(patch("src.ui_marina.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_rafael.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_marina.repositorio.estado", return_value={}))
        pilha.enter_context(patch("src.ui_marina.repositorio.ids_concluidos", return_value=set()))
        pilha.enter_context(patch("src.ui_marina.repositorio.registrar_urgencia"))
        pilha.enter_context(patch("src.ui_marina.auditoria.ler", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.auditoria.ler", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.repositorio.eventos", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.repositorio.estado", return_value={}))
        yield AppTest.from_file(APP), mocks


def test_app_abre_sem_excecao_e_sem_gravar_db(itens_regras):
    with _app(itens_regras) as (at, mocks):
        at.run(timeout=10)

        assert not at.exception
        # A linha do app.py rodou, mas contra o mock: nada foi escrito no SQLite.
        mocks["init_db"].assert_called_once()
        mocks["carregar_env"].assert_called_once()


def test_app_alterna_entre_marina_e_rafael(itens_regras):
    with _app(itens_regras) as (at, _):
        at.run(timeout=10)
        assert not at.exception
        assert TXT["title_marina"] in [titulo.value for titulo in at.title]

        # O radio usa `format_func`: AppTest espera o valor cru, nao o rotulo.
        at.radio[0].set_value("rafael").run()
        assert not at.exception
        assert TXT["title_rafael"] in [titulo.value for titulo in at.title]

        at.radio[0].set_value("marina").run()
        assert not at.exception
        assert TXT["title_marina"] in [titulo.value for titulo in at.title]


def test_app_mantem_etapa_ativa_ao_sair_e_voltar_do_rafael(itens_regras):
    chamado_id = itens_regras[0].id
    chave = f"camada_{chamado_id}"
    with _app(itens_regras) as (at, _):
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()
        assert at.session_state[chave] == "decisao"

        # Com a fila aberta, o primeiro radio é o seletor de chamados; o de
        # navegação vem por último na árvore do AppTest.
        at.radio[-1].set_value("rafael").run()
        at.radio[-1].set_value("marina").run()

        assert not at.exception
        assert at.session_state["estado_chamados"][chamado_id]["camada"] == "decisao"
        assert at.session_state[chave] == "decisao"
        assert at.segmented_control(key=chave).value == "decisao"


def test_app_preserva_pagina_e_controles_ao_trocar_idioma(itens_regras):
    with _app(itens_regras) as (at, _):
        at.run(timeout=10)
        assert not at.exception

        at.radio(key="nav_pagina_ui").set_value("rafael").run()
        at.toggle(key="sim_toggle_ui").set_value(True).run()
        at.selectbox(key="provider_ui").set_value("gemini").run()
        at.segmented_control(key="tema_ui").set_value("Claro").run()

        at.button(key="set_lang_en").click().run()
        assert not at.exception
        assert at.session_state["lang"] == "EN"
        assert at.session_state["nav_pagina_ui"] == "rafael"
        assert at.session_state["provider_ui"] == "gemini"
        assert at.session_state["tema_ui"] == "Claro"
        assert at.session_state["sim_toggle_ui"] is True
        assert I18N["EN"]["title_rafael"] in [titulo.value for titulo in at.title]

        at.button(key="set_lang_pt").click().run()
        assert not at.exception
        assert at.session_state["lang"] == "PT"
        assert at.session_state["nav_pagina_ui"] == "rafael"
        assert at.session_state["provider_ui"] == "gemini"
        assert at.session_state["tema_ui"] == "Claro"
        assert at.session_state["sim_toggle_ui"] is True
        assert TXT["title_rafael"] in [titulo.value for titulo in at.title]
