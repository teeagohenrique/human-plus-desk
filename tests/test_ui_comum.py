"""Testes da camada de apresentacao compartilhada (src/ui_comum.py).

O modulo depende de Streamlit e Altair. As funcoes puras sao testadas direto;
`fila_base` e testada com monkeypatch nas entradas de arquivo e no montador.
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import altair as alt
import pytest

from src import ui_comum
from src.percepcao import JANELA_DIAS, Palpite
from src.textos import I18N
from src.triagem import Motivo


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


def test_formatar_data_hora_passa_fuso_sao_paulo_explicitamente(monkeypatch):
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    class InstanteFalso:
        tzinfo = object()

        def astimezone(self, zona):
            assert zona == ZoneInfo("America/Sao_Paulo")
            return SimpleNamespace(strftime=lambda formato: "24/11/2026 às 12:00:00")

    class DataHoraFalsa:
        @staticmethod
        def fromisoformat(_texto):
            return InstanteFalso()

    monkeypatch.setattr(ui_comum, "datetime", DataHoraFalsa)
    assert ui_comum.formatar_data_hora("timestamp", lang="PT") == "24/11/2026 às 12:00:00"


def test_formatar_data_hora_en_e_nome_sinal_en():
    assert ui_comum.formatar_data_hora("2026-11-23T10:30:45", lang="EN") == "2026-11-23 at 10:30:45"
    assert ui_comum.nome_sinal("historico:C01", I18N["EN"]) == "History (C01)"


def test_traduzir_leitura_palpite_e_hipotese_salva():
    assert ui_comum.traduzir_leitura("pressa_prazo", I18N["PT"]) == "Pressão de prazo"
    assert ui_comum.traduzir_leitura("pressa_prazo", I18N["EN"]) == "Deadline pressure"
    assert ui_comum.traduzir_leitura("desconhecida", I18N["EN"]) == "desconhecida"

    ev = [Motivo(sinal="historico:C01", trecho="erro"), Motivo(sinal="historico:C02", trecho="erro")]
    p = Palpite(
        tipo="padrao",
        hipotese=f"Pode não ser um caso isolado: há 2 chamados parecidos nos últimos {JANELA_DIAS} dias.",
        evidencias=ev,
        confianca="media",
        pergunta_confirmacao="Pergunta PT?",
        leituras=["cansaco_repeticao"],
    )
    hip_en, perg_en = ui_comum.traduzir_palpite(p, I18N["EN"])
    assert f"2 similar tickets in the last {JANELA_DIAS} days" in hip_en
    assert "root cause" in perg_en

    assert ui_comum.traduzir_hipotese_salva(p.hipotese, 2, I18N["PT"]) == p.hipotese
    assert ui_comum.traduzir_hipotese_salva(p.hipotese, 2, I18N["EN"]) == hip_en
    assert "temporary workaround" in ui_comum.traduzir_hipotese_salva(
        "Pode ser que, além da correção, ajude uma solução provisória para cumprir o prazo mencionado.",
        1,
        I18N["EN"],
    )
    assert "Repeated issues" in ui_comum.traduzir_hipotese_salva(
        "Parece que a repetição pode estar pesando na relação com o serviço; uma resposta padrão talvez não baste.",
        1,
        I18N["EN"],
    )


def test_fila_base_gemini_exibe_progresso_e_reaproveita_cache_entre_idiomas(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "chamados_simulados.json").write_text(
        json.dumps({"chamados": [{"id": "C1", "texto": "t1"}, {"id": "C2", "texto": "t2"}]}),
        encoding="utf-8",
    )
    chamadas = 0

    def montar(chamados, hist, provider=None, model=None, ao_avancar=None):
        nonlocal chamadas
        chamadas += 1
        assert ao_avancar is not None
        ao_avancar(1, 4, "C1:triagem")
        ao_avancar(2, 4, "C1:rascunho")
        ao_avancar(3, 4, "C2:triagem")
        ao_avancar(4, 4, "C2:rascunho")
        return ["ok"]

    barra = MagicMock()
    slot = MagicMock()
    slot.progress.return_value = barra

    monkeypatch.setattr(ui_comum, "RAIZ", tmp_path)
    monkeypatch.setattr(ui_comum, "carregar_historico", lambda _: {})
    monkeypatch.setattr(ui_comum, "montar_fila", montar)

    ui_comum.fila_base.clear()
    try:
        with patch.object(ui_comum.st, "empty", return_value=slot):
            assert ui_comum.fila_base("gemini", "m", txt=I18N["EN"]) == ["ok"]
            assert ui_comum.fila_base("gemini", "m", txt=I18N["PT"]) == ["ok"]

        assert chamadas == 1
        assert slot.progress.call_args[1]["text"] == I18N["EN"]["gemini_progress_init"].format(total=4)
        textos_passos = [c[1]["text"] for c in barra.progress.call_args_list]
        assert len(textos_passos) == 4
        assert "1/4 (C1 · Triage)" in textos_passos[0]
        assert "4/4 (C2 · Suggestion)" in textos_passos[3]
        slot.empty.assert_called_once()
    finally:
        ui_comum.fila_base.clear()


def test_resolver_arroba_rafael_substitui_nome_do_paciente():
    msg = "Olá, Sr. @ !\nAtenciosamente,\nMarina"
    assert ui_comum.resolver_arroba_rafael("C01", msg) == "Olá, Sr. Carlos !\nAtenciosamente,\nMarina"
    assert ui_comum.resolver_arroba_rafael("C02", msg) == "Olá, Sr. Ana Souza !\nAtenciosamente,\nMarina"
    assert ui_comum.resolver_arroba_rafael("C01", None) == ""

