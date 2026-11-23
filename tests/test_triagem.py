import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.triagem import Motivo, Triagem, triar

CARLOS = ("Bom dia, aqui é o Carlos. O sistema de faturamento travou pela terceira vez "
          "essa semana e eu preciso fechar o mês até o meio-dia.")


def test_caso_carlos():
    t = triar(CARLOS)
    assert t.intencao == "falha_sistema"
    assert t.urgencia == "alta"
    assert t.recorrente is True
    sinais = {m.sinal for m in t.motivos_urgencia}
    assert {"prazo", "recorrencia", "processo_critico"} <= sinais


def test_motivos_sao_trechos_literais_do_chamado():
    t = triar(CARLOS)
    for m in t.motivos_urgencia + t.motivos_intencao:
        assert m.trecho in CARLOS


def test_hoje_sozinho_nao_e_prazo():
    t = triar("O sistema está muito lento hoje, mas consigo trabalhar.")
    assert t.urgencia == "baixa"


def test_texto_sem_sinais_fica_indefinido_com_confianca_baixa():
    t = triar("Obrigado pelo atendimento de ontem, deu tudo certo!")
    assert t.intencao == "indefinida"
    assert t.confianca == "baixa"
    assert t.urgencia == "baixa"


def test_regra_sem_trecho_sem_campo_urgencia():
    with pytest.raises(ValidationError):
        Triagem(intencao="duvida", urgencia="alta", recorrente=False,
                motivos_intencao=[Motivo(sinal="palavra_chave", trecho="dúvida")],
                motivos_urgencia=[], pontuacao_urgencia=0, confianca="media")


def test_regra_sem_trecho_sem_campo_intencao():
    with pytest.raises(ValidationError):
        Triagem(intencao="acesso", urgencia="baixa", recorrente=False,
                motivos_intencao=[], motivos_urgencia=[], pontuacao_urgencia=0, confianca="media")


def test_recorrencia_aumenta_pontuacao():
    base = triar("O VPN caiu.")
    rec = triar("O VPN caiu de novo.")
    assert rec.pontuacao_urgencia > base.pontuacao_urgencia
    assert rec.recorrente and not base.recorrente


def test_todos_chamados_simulados_geram_triagem_valida():
    dados = json.loads((Path(__file__).parent.parent / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))
    for c in dados["chamados"]:
        t = triar(c["texto"])
        for m in t.motivos_urgencia + t.motivos_intencao:
            assert m.trecho in c["texto"], c["id"]
