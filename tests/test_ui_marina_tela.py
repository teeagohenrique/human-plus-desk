"""Tela da Marina (src/ui_marina.py) com AppTest.

As dependencias de arquivo, banco e auditoria entram controladas; a fila vem da
fixture `itens_regras` (pipeline real, offline, sem chamada de API).
"""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.percepcao import LEITURAS
from src.textos import I18N

TXT = I18N["PT"]
SCRIPT = """
from src.ui_marina import tela_marina
from src.textos import I18N
tela_marina('regras', I18N['PT'])
"""


@contextmanager
def _tela(itens):
    with ExitStack() as pilha:
        pilha.enter_context(patch("src.ui_marina.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_marina.repositorio.estado", return_value={}))
        pilha.enter_context(patch("src.ui_marina.repositorio.ids_concluidos", return_value=set()))
        pilha.enter_context(patch("src.ui_marina.repositorio.registrar_urgencia"))
        pilha.enter_context(patch("src.ui_marina.auditoria.ler", return_value=[]))
        pilha.enter_context(patch(
            "src.ui_marina.carregar_config",
            return_value={"ativas": list(LEITURAS), "aprovacoes": []},
        ))
        yield AppTest.from_string(SCRIPT)


def test_marina_mostra_fila_e_origem_por_item(itens_regras):
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        # Sem indicador escolhido a tela mostra a welcome (ui_marina.py:471-474).
        at.button(key="btn_kpi_fila").click().run()

        assert not at.exception
        assert TXT["title_marina"] in [titulo.value for titulo in at.title]
        origem = TXT["origens"][itens_regras[0].origem_triagem]
        assert any(origem in legenda.value for legenda in at.caption)
        assert len(at.radio) >= 1


def test_marina_urgencia_sem_preselecao(itens_regras):
    chamado_id = itens_regras[0].id
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()

        assert not at.exception
        assert at.session_state.get(f"urg_ui_{chamado_id}") is None
        assert at.pills(key=f"urg_ui_{chamado_id}").value is None
        assert any(TXT["urg_hint"] in aviso.value for aviso in at.info)


def test_marina_trava_registro_com_placeholder(itens_regras):
    chamado_id = itens_regras[0].id
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()
        at.pills(key=f"urg_ui_{chamado_id}").set_value("media").run()
        at.button(key=f"go3_{chamado_id}").click().run()

        # A caixa de resposta comeca vazia; copiar a sugestao traz os colchetes.
        at.button(key=f"usar_{chamado_id}").click().run()

        assert not at.exception
        assert at.button(key=f"ok_{chamado_id}").disabled is True
        assert any(TXT["need_brack"] in aviso.value for aviso in at.warning)

        at.text_area(key=f"resp_ui_{chamado_id}").set_value("Resposta sem colchetes.").run()

        assert not at.exception
        assert at.button(key=f"ok_{chamado_id}").disabled is False
        assert TXT["ready_banner"] in [aviso.value for aviso in at.success]


def test_marina_prioridade_critica_seleciona_primeiro_chamado_automaticamente(itens_regras):
    # Mesmo quando o chamado ativo anterior era de baixa urgencia (fora da lista critica),
    # abrir Prioridade Critica deve selecionar automaticamente o primeiro chamado critico.
    id_critico = next(i.id for i in itens_regras if i.triagem.urgencia == "alta")
    id_baixo = next(i.id for i in itens_regras if i.triagem.urgencia != "alta")
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.radio(key="chamado_ativo_fila").set_value(id_baixo).run()
        assert at.session_state["chamado_ativo_fila"] == id_baixo

        at.button(key="btn_kpi_critica").click().run()
        assert not at.exception
        assert at.session_state["chamado_ativo_fila"] == id_critico
        assert at.radio(key="chamado_ativo_fila").value == id_critico

