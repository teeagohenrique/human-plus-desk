"""Caminhos defensivos da camada compartilhada (src/ui_comum.py).

Sao fallbacks que impedem a tela de quebrar: assinatura indisponivel ou
rotulo ausente no dicionario nao podem interromper o painel.
"""
import pytest

from src import ui_comum
from src.percepcao import Palpite
from src.triagem import Motivo


@pytest.mark.parametrize("erro", [TypeError, ValueError])
def test_aceita_progresso_com_assinatura_indisponivel_devolve_falso(monkeypatch, erro):
    def _sem_assinatura(_fn):
        raise erro("assinatura indisponivel")

    monkeypatch.setattr(ui_comum.inspect, "signature", _sem_assinatura)
    assert ui_comum._aceita_progresso(lambda: None) is False


def _palpite_sem_traducao() -> Palpite:
    return Palpite(
        tipo="necessidade_nao_dita",
        hipotese="Hipotese em PT sem traducao.",
        evidencias=[Motivo(sinal="prazo", trecho="ate o meio-dia")],
        confianca="media",
        pergunta_confirmacao="Pergunta em PT sem traducao?",
        leituras=[],
    )


def test_traduzir_palpite_sem_modelo_preserva_hipotese_e_pergunta():
    palpite = _palpite_sem_traducao()
    txt = {"hipoteses": {}, "perguntas_hipotese": {}}

    assert ui_comum.traduzir_palpite(palpite, txt) == (
        "Hipotese em PT sem traducao.",
        "Pergunta em PT sem traducao?",
    )


def test_traduzir_hipotese_salva_sem_marcador_conhecido_devolve_texto():
    txt = {"hipoteses": {"necessidade_nao_dita": " workaround "}, "lang_code": "EN"}
    original = "Texto salvo sem marcador conhecido."

    assert ui_comum.traduzir_hipotese_salva(original, 2, txt) == original


def test_traduzir_hipotese_salva_sem_modelo_padrao_devolve_texto():
    txt = {"hipoteses": {"necessidade_nao_dita": " workaround "}, "lang_code": "EN"}
    original = "Pode nao ser um caso isolado: ha 3 chamados parecidos nos ultimos 7 dias."

    assert ui_comum.traduzir_hipotese_salva(original, 3, txt) == original
