"""Testes da camada de apresentacao compartilhada (src/ui_comum.py).

O modulo depende de Streamlit e Altair. As funcoes puras sao testadas direto;
`fila_base` e testada com monkeypatch nas entradas de arquivo e no montador.
"""
import json
from datetime import datetime

import altair as alt
import pytest

from src import ui_comum


@pytest.mark.parametrize("valor", [None, ""])
def test_formatar_data_hora_vazio_devolve_travessao(valor):
    assert ui_comum.formatar_data_hora(valor) == "—"


def test_formatar_data_hora_sem_fuso_mantem_hora_local():
    """Sem tzinfo nao ha conversao: apenas reformatacao."""
    assert ui_comum.formatar_data_hora("2026-11-23T10:30:45") == "23/11/2026 às 10:30:45"


def test_formatar_data_hora_com_fuso_converte_para_horario_local():
    """O esperado e calculado com a biblioteca padrao para nao fixar o fuso da maquina."""
    iso = "2026-11-23T10:30:45+00:00"
    esperado = datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y às %H:%M:%S")
    assert ui_comum.formatar_data_hora(iso) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("2026-11-23T10:30:45XYZ_INVALIDA", "2026-11-23 10:30:45"),
        ("nao-e-data-boa", "nao-e-data-boa"),
    ],
)
def test_formatar_data_hora_invalido_devolve_prefixo_cortado(entrada, esperado):
    assert ui_comum.formatar_data_hora(entrada) == esperado


def test_nome_sinal_usa_rotulo_do_dicionario_quando_existe():
    txt = {"sinais": {"prazo": "Prazo apertado"}}
    assert ui_comum.nome_sinal("prazo", txt) == "Prazo apertado"


def test_nome_sinal_fallback_humaniza_underscore():
    assert ui_comum.nome_sinal("desconhecido_ai", {"sinais": {}}) == "Desconhecido ai"


def test_nome_sinal_historico_nao_consulta_dicionario():
    """O prefixo 'historico:' tem prioridade sobre o dicionario de sinais."""
    assert ui_comum.nome_sinal("historico:analista_viu_3x", {}) == "Histórico (analista_viu_3x)"


@pytest.mark.parametrize(
    ("escuro", "lbl", "tit", "grd", "dom"),
    [
        (True, "#CBD5E1", "#94A3B8", "rgba(148, 163, 184, 0.12)", "rgba(148, 163, 184, 0.25)"),
        (False, "#334155", "#475569", "rgba(15, 23, 42, 0.08)", "rgba(15, 23, 42, 0.18)"),
    ],
)
def test_estilizar_grafico_aplica_tema(escuro, lbl, tit, grd, dom):
    chart = alt.Chart(alt.Data(values=[{"x": 1}])).mark_point()

    resultado = ui_comum.estilizar_grafico(chart, escuro=escuro)

    cfg = resultado.to_dict()["config"]
    assert isinstance(resultado, alt.Chart)
    assert cfg["background"] == "transparent"
    assert cfg["axis"] == {"labelColor": lbl, "titleColor": tit, "gridColor": grd, "domainColor": dom}
    assert cfg["legend"] == {"labelColor": lbl, "titleColor": tit}


def test_fila_base_le_arquivos_e_repassa_provider_e_modelo(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "chamados_simulados.json").write_text(
        json.dumps({"chamados": [{"id": "C1", "texto": "t"}]}), encoding="utf-8"
    )
    historico = [{"chamado_id": "C1"}]
    caminhos_lidos = []
    visto = {}

    def carregar(caminho):
        caminhos_lidos.append(caminho)
        return historico

    def montar(chamados, hist, provider=None, model=None):
        visto.update(chamados=chamados, hist=hist, provider=provider, model=model)
        return ["fila"]

    monkeypatch.setattr(ui_comum, "RAIZ", tmp_path)
    monkeypatch.setattr(ui_comum, "carregar_historico", carregar)
    monkeypatch.setattr(ui_comum, "montar_fila", montar)

    ui_comum.fila_base.clear()
    try:
        assert ui_comum.fila_base() == ["fila"]
        assert visto == {
            "chamados": [{"id": "C1", "texto": "t"}],
            "hist": historico,
            "provider": "regras",
            "model": None,
        }

        assert ui_comum.fila_base("gemini", "gemini-2.5-flash") == ["fila"]
        assert visto["provider"] == "gemini"
        assert visto["model"] == "gemini-2.5-flash"
        assert caminhos_lidos == [tmp_path / "data" / "historico_simulado.json"] * 2
    finally:
        ui_comum.fila_base.clear()
