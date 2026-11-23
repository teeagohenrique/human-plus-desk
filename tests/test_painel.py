import json
from pathlib import Path

from src import auditoria
from src.painel import (carregar_historico, decisao_por_texto, gerar_simulado, ids_decididos,
                        metricas, montar_fila, registrar_decisao)

RAIZ = Path(__file__).parent.parent
CHAMADOS = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
HIST = carregar_historico(RAIZ / "data" / "historico_simulado.json")


def fila():
    return montar_fila(CHAMADOS, HIST)


def test_fila_ordenada_por_urgencia():
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    valores = [ordem[i.triagem.urgencia] for i in fila()]
    assert valores == sorted(valores)
    assert len(valores) == len(CHAMADOS)


def test_fila_nao_expoe_dado_pessoal():
    for i in fila():
        assert "123.456.789-09" not in i.texto_mascarado and "98765" not in i.texto_mascarado


def test_decisao_por_texto():
    assert decisao_por_texto("abc", " abc ") == "aprovou"
    assert decisao_por_texto("abc", "abd") == "editou"


def test_registrar_decisao_e_decididos(tmp_path):
    log = tmp_path / "l.jsonl"
    item = fila()[0]
    registrar_decisao(log, item, "editou", "texto final", leitura="pressa_prazo")
    ev = auditoria.ler(log)
    assert ids_decididos(ev) == {item.id}
    assert ev[0]["decisao_analista"] == "editou"


def test_decisao_invalida_e_recusada(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        registrar_decisao(tmp_path / "l.jsonl", fila()[0], "talvez", None)


def test_metricas_contam_corretamente(tmp_path):
    log = tmp_path / "l.jsonl"
    itens = fila()
    registrar_decisao(log, itens[0], "aprovou", "x", leitura="pressa_prazo")
    registrar_decisao(log, itens[1], "editou", "y", leitura_livre="cansado do processo")
    registrar_decisao(log, itens[2], "rejeitou", None)
    m = metricas(auditoria.ler(log))
    assert m["total"] == 3
    assert m["decisoes"] == {"aprovou": 1, "editou": 1, "rejeitou": 1}
    assert abs(m["taxa_edicao"] - 1 / 3) < 1e-9
    assert m["leituras"] == {"pressa_prazo": 1}
    assert m["leituras_livres"] == 1


def test_metricas_sem_dados():
    m = metricas([])
    assert m["total"] == 0 and m["taxa_edicao"] == 0.0


def test_simulado_e_reprodutivel_e_marcado(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    gerar_simulado(a, fila(), n=30, semente=1)
    gerar_simulado(b, fila(), n=30, semente=1)
    ea, eb = auditoria.ler(a), auditoria.ler(b)
    assert [e["chamado_id"] for e in ea] == [e["chamado_id"] for e in eb]
    assert all(e["simulado"] is True for e in ea)
    assert metricas(ea)["total"] == 30


# --- calibração da urgência (triagem) ---
from src.painel import calibracao_triagem


def _ev(ia, analista, conf="media"):
    return {"quando": "2026-11-22T10:00:00+00:00", "chamado_id": "X", "agente": "analista",
            "saida": {"urgencia": ia, "urgencia_analista": analista, "confianca_triagem": conf,
                      "intencao": "acesso", "recorrente": False, "leitura": None, "leitura_livre": None},
            "decisao_analista": "aprovou", "texto_final": None}


def test_calibracao_triagem_concordancia_e_direcao():
    ev = [_ev("alta", "alta"), _ev("media", "alta"), _ev("alta", "baixa"), _ev("baixa", "baixa")]
    c = calibracao_triagem(ev)
    assert c["n"] == 4 and c["concordancia"] == 0.5
    assert c["subiu"] == 1 and c["desceu"] == 1  # media->alta sobe; alta->baixa desce
    assert c["matriz"]["media"]["alta"] == 1


def test_calibracao_triagem_por_confianca():
    ev = [_ev("alta", "alta", "alta")] * 3 + [_ev("alta", "baixa", "baixa")] * 2
    c = calibracao_triagem(ev)["por_confianca"]
    assert c["alta"]["taxa"] == 1.0 and c["baixa"]["taxa"] == 0.0 and c["baixa"]["n"] == 2


def test_calibracao_triagem_ignora_eventos_sem_urgencia_da_analista():
    assert calibracao_triagem([_ev("alta", None)])["n"] == 0


def test_registrar_urgencia_da_analista(tmp_path):
    log = tmp_path / "l.jsonl"
    item = fila()[0]
    registrar_decisao(log, item, "aprovou", "x", urgencia_analista="baixa")
    e = auditoria.ler(log)[0]["saida"]
    assert e["urgencia_analista"] == "baixa" and e["confianca_triagem"] == item.triagem.confianca


def test_urgencia_invalida_e_recusada(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        registrar_decisao(tmp_path / "l.jsonl", fila()[0], "aprovou", "x", urgencia_analista="critica")
