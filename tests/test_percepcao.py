import pytest
from pydantic import ValidationError

from src.percepcao import LEITURAS, Historico, Palpite, perceber
from src.triagem import Motivo, triar

CARLOS = ("Bom dia, aqui é o Carlos. O sistema de faturamento travou pela terceira vez "
          "essa semana e eu preciso fechar o mês até o meio-dia.")
HIST = [
    Historico(chamado_id="H1", texto_mascarado="O faturamento travou.", dias_atras=2),
    Historico(chamado_id="H2", texto_mascarado="O sistema travou de novo.", dias_atras=5),
    Historico(chamado_id="H3", texto_mascarado="Erro ao abrir o sistema.", dias_atras=40),  # fora da janela
]


def test_sem_sinais_sem_palpites():
    texto = "Obrigado pelo atendimento de ontem!"
    assert perceber(texto, triar(texto)) == []


def test_palpite_exige_evidencia():
    with pytest.raises(ValidationError):
        Palpite(tipo="padrao", hipotese="x", evidencias=[], confianca="baixa",
                pergunta_confirmacao="?", leituras=[])


def test_no_maximo_3_palpites_e_evidencias_do_proprio_texto():
    t = triar(CARLOS)
    ps = perceber(CARLOS, t, HIST)
    assert 1 <= len(ps) <= 3
    for p in ps:
        for e in p.evidencias:
            if not e.sinal.startswith("historico:"):
                assert e.trecho in CARLOS


def test_padrao_usa_so_historico_dentro_da_janela():
    ps = perceber(CARLOS, triar(CARLOS), HIST)
    padrao = next(p for p in ps if p.tipo == "padrao")
    ids = {e.sinal for e in padrao.evidencias}
    assert ids == {"historico:H1", "historico:H2"}  # H3 (40 dias) fica de fora


def test_sem_historico_nao_ha_palpite_de_padrao():
    ps = perceber(CARLOS, triar(CARLOS))
    assert all(p.tipo != "padrao" for p in ps)


def test_risco_recorrencia_so_sugere_nao_altera_urgencia():
    t = triar(CARLOS)
    antes = t.model_copy()
    ps = perceber(CARLOS, t, HIST)
    risco = next(p for p in ps if p.tipo == "risco_recorrencia")
    assert risco.sugere_subir_urgencia is True
    assert t == antes  # triagem intacta


def test_leituras_sao_5_ids_validos_com_prazo_em_primeiro_para_carlos():
    ps = perceber(CARLOS, triar(CARLOS), HIST)
    for p in ps:
        assert len(p.leituras) == 5 and set(p.leituras) <= set(LEITURAS)
    assert ps[0].leituras[0] in {"pressa_prazo", "cansaco_repeticao"}


def test_hipoteses_em_tom_de_duvida_e_sem_rotulo():
    for p in perceber(CARLOS, triar(CARLOS), HIST):
        assert any(w in p.hipotese.lower() for w in ("pode", "parece", "talvez"))
        assert p.pergunta_confirmacao.endswith("?")
