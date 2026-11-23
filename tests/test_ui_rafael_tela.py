"""Tela do Rafael (src/ui_rafael.py) com AppTest.

Cobre os dois estados da tela (sem decisoes e com decisoes) e a regressao do
commit 8b04f59: campos extras em `detalhes` nao podem quebrar a auditoria.
"""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.percepcao import LEITURAS
from src.textos import I18N

TXT = I18N["PT"]
SCRIPT = """
from src.ui_rafael import tela_rafael
from src.textos import I18N
tela_rafael('regras', False, I18N['PT'])
"""


@contextmanager
def _tela(eventos, itens, eventos_db=None, estado_db=None):
    with ExitStack() as pilha:
        pilha.enter_context(patch("src.ui_rafael.auditoria.ler", return_value=eventos))
        pilha.enter_context(patch("src.ui_rafael.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_rafael.repositorio.estado", return_value=estado_db or {}))
        pilha.enter_context(patch("src.ui_rafael.repositorio.eventos", return_value=eventos_db or []))
        pilha.enter_context(patch(
            "src.ui_rafael.carregar_config",
            return_value={"ativas": list(LEITURAS), "aprovacoes": []},
        ))
        yield AppTest.from_string(SCRIPT)


def test_rafael_sem_decisoes_mostra_info_e_nao_quebra(itens_regras):
    with _tela([], itens_regras) as at:
        at.run(timeout=10)

        assert not at.exception
        assert TXT["title_rafael"] in [titulo.value for titulo in at.title]
        assert TXT["no_decisions"] in [aviso.value for aviso in at.info]
        assert not at.metric


def test_rafael_com_decisoes_mostra_kpis_e_abas(eventos_regras, itens_regras):
    with _tela(eventos_regras, itens_regras) as at:
        at.run(timeout=10)

        assert not at.exception
        assert [metrica.label for metrica in at.metric[:4]] == [
            TXT["kpi_total"], TXT["kpi_adapted"], TXT["kpi_own"], TXT["kpi_recurrent"],
        ]
        assert [aba.label for aba in at.tabs] == [
            TXT["tab_overview"], TXT["tab_readings"], TXT["tab_urgency"],
        ]


def test_rafael_auditoria_exibe_evento_com_agente_e_data(eventos_regras, itens_regras):
    chamado_id = itens_regras[0].id
    evento_db = {
        "chamado_id": chamado_id,
        "acao": "decisao",
        "agente": "Marina",
        "criado_em": "2026-11-23T10:00:00+00:00",
        "detalhes": {"resposta_anterior": "x", "origem_triagem": "regras"},
    }
    estado_db = {
        chamado_id: {
            "status": "concluido",
            "resolvido_por": "Marina",
            "resolvido_em": "2026-11-23T10:05:00+00:00",
        }
    }
    with _tela(eventos_regras, itens_regras, eventos_db=[evento_db], estado_db=estado_db) as at:
        at.run(timeout=10)

        assert not at.exception
        textos = [bloco.value for bloco in at.markdown]
        assert any(chamado_id in texto for texto in textos)
        assert any("Marina" in texto for texto in textos)
