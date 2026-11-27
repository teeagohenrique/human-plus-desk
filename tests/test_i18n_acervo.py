"""Item 6: o idioma da sugestão do Acervo acompanha PT/EN sem apagar edição humana."""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.textos import I18N

APP = str(Path(__file__).resolve().parent.parent / "app.py")
IDIOMA_EN = I18N["EN"]


@contextmanager
def _app(itens):
    """Entrypoint com banco, .env e fila isolados; sem chamada externa."""
    with ExitStack() as pilha:
        pilha.enter_context(patch("src.repositorio.init_db"))
        pilha.enter_context(patch("src.repositorio.exportar_auditoria_pendente"))
        pilha.enter_context(patch("src.config.carregar_env"))
        pilha.enter_context(patch("src.ui_marina.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_rafael.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_marina.repositorio.estado", return_value={}))
        pilha.enter_context(patch("src.ui_marina.repositorio.ids_concluidos", return_value=set()))
        pilha.enter_context(patch("src.ui_marina.repositorio.registrar_urgencia"))
        pilha.enter_context(patch("src.ui_marina.auditoria.ler", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.auditoria.ler", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.repositorio.eventos", return_value=[]))
        pilha.enter_context(patch("src.ui_rafael.repositorio.estado", return_value={}))
        yield AppTest.from_file(APP)


def _abrir_acervo_na_resposta(at, chamado_id):
    at.run(timeout=10)
    at.button(key="btn_kpi_fila").click().run()
    at.button(key=f"go2_{chamado_id}").click().run()
    at.pills(key=f"urg_ui_{chamado_id}").set_value("alta").run()
    at.button(key=f"go3_{chamado_id}").click().run()
    at.button(key=f"abrir_acervo_3_{chamado_id}").click().run()
    at.button(key=f"ir_resp_acervo_{chamado_id}").click().run()
    assert not at.exception


def _chave_sugestao(at, chamado_id):
    estado = at.session_state["estado_chamados"][chamado_id]
    return f"sug_ui_{chamado_id}_{estado.get('leitura') or 'base'}"


def test_sugestao_do_acervo_segue_a_troca_de_idioma(itens_regras):
    chamado_id = itens_regras[0].id
    with _app(itens_regras) as at:
        _abrir_acervo_na_resposta(at, chamado_id)
        chave = _chave_sugestao(at, chamado_id)
        assert "Olá, @" in at.text_area(key=chave).value

        at.button(key="set_lang_en").click().run()
        assert not at.exception
        assert at.session_state["lang"] == "EN"
        assert IDIOMA_EN["title_marina"] in [titulo.value for titulo in at.title]
        sugestao_en = at.text_area(key=chave).value
        assert "Hello, @" in sugestao_en
        assert "Olá, @" not in sugestao_en
        estado = at.session_state["estado_chamados"][chamado_id]
        assert estado["sugestao_acervo_lang"] == "EN"

        at.button(key="set_lang_pt").click().run()
        assert not at.exception
        assert "Olá, @" in at.text_area(key=chave).value


def test_troca_de_idioma_preserva_edicao_da_analista(itens_regras):
    chamado_id = itens_regras[0].id
    with _app(itens_regras) as at:
        _abrir_acervo_na_resposta(at, chamado_id)
        chave = _chave_sugestao(at, chamado_id)
        editado = "Sugestão revisada manualmente pela analista."
        at.text_area(key=chave).set_value(editado).run()

        at.button(key="set_lang_en").click().run()
        assert not at.exception
        assert at.text_area(key=chave).value == editado
        estado = at.session_state["estado_chamados"][chamado_id]
        assert estado["sugestao_acervo"] != editado
