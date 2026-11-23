import pytest

from src import autonomia as a
from src import auditoria

CTX = a.contexto_de("acesso", "baixa")


def ev(ia="baixa", analista="baixa", intencao="acesso", quando="2026-11-22T10:00:00+00:00", auto=False):
    return {"quando": quando, "chamado_id": "X", "agente": "analista",
            "saida": {"urgencia": ia, "urgencia_analista": analista, "intencao": intencao,
                      "urgencia_automatica": auto},
            "decisao_analista": "aprovou", "texto_final": None}


def cfg():
    return {"aprovados": [], "suspensos": []}


def test_numeros_de_corte_batem_com_o_calculo():
    assert a.casos_necessarios(0) == 299
    assert a.casos_necessarios(1) == 473
    assert a.casos_necessarios(2) == 628


def test_limite_superior_basico():
    assert a.limite_superior_erro(0, 0) == 1.0
    assert a.limite_superior_erro(299, 0) <= 0.01 < a.limite_superior_erro(298, 0)


def test_tudo_comeca_desligado():
    assert a.autonomos(cfg()) == set()
    assert a.deve_perguntar(CTX, "C1", cfg()) is True


def test_dez_acertos_nao_bastam():
    s = a.status([ev()] * 10, cfg())
    assert s[0]["estado"] == "bloqueado" and s[0]["faltam"] == 289


def test_299_acertos_sem_erro_ficam_elegiveis():
    assert a.status([ev()] * 299, cfg())[0]["estado"] == "elegivel"


def test_um_erro_exige_473_casos_no_total():
    # 473 = total de casos (acertos + o erro). Com 472 ainda não prova; com 473 prova.
    antes = a.status([ev()] * 471 + [ev(analista="alta")], cfg())[0]
    assert antes["erros"] == 1 and antes["estado"] == "bloqueado" and antes["faltam"] == 1
    depois = a.status([ev()] * 472 + [ev(analista="alta")], cfg())[0]
    assert depois["estado"] == "elegivel" and depois["faltam"] == 0


def test_decisoes_automaticas_nao_contam_como_evidencia():
    assert a.status([ev(auto=True)] * 400, cfg()) == []


def test_envio_ao_cliente_nunca_pode_ser_autonomo(tmp_path):
    for acao in a.ACOES_PROIBIDAS:
        with pytest.raises(ValueError):
            a.aprovar_autonomia(tmp_path / "c.json", f"{acao}:qualquer:coisa", "Rafael", [ev()] * 999)


def test_aprovacao_exige_prova_mesmo_chamando_direto(tmp_path):
    with pytest.raises(ValueError):
        a.aprovar_autonomia(tmp_path / "c.json", CTX, "Rafael", [ev()] * 50)
    assert not (tmp_path / "c.json").exists()


def test_aprovacao_valida_grava_config_e_auditoria(tmp_path):
    conf, log = tmp_path / "c.json", tmp_path / "log.jsonl"
    c = a.aprovar_autonomia(conf, CTX, "Rafael", [ev()] * 299, log)
    assert CTX in a.autonomos(c) and CTX in a.autonomos(a.carregar_config(conf))
    e = auditoria.ler(log)[0]
    assert e["saida"]["acao"] == "aprovar_autonomia" and e["saida"]["gestor"] == "Rafael"


def test_autonomo_so_pergunta_uma_amostra():
    c = {"aprovados": [{"contexto": CTX, "gestor": "R", "quando": "x"}], "suspensos": []}
    perguntou = sum(a.deve_perguntar(CTX, f"C{i}", c) for i in range(1000))
    assert 50 < perguntou < 150  # ~10%
    assert a.deve_perguntar(CTX, "C7", c) == a.deve_perguntar(CTX, "C7", c)  # determinístico
    assert a.deve_perguntar(a.contexto_de("acesso", "alta"), "C7", c) is True  # outro contexto: sempre


def test_um_erro_humano_depois_da_aprovacao_suspende(tmp_path):
    conf, log = tmp_path / "c.json", tmp_path / "log.jsonl"
    a.aprovar_autonomia(conf, CTX, "Rafael", [ev()] * 299)
    novo = [ev(analista="alta", quando="2999-01-01T00:00:00+00:00")]
    assert a.reavaliar(conf, novo, log) == [CTX]
    assert CTX not in a.autonomos(a.carregar_config(conf))
    assert a.deve_perguntar(CTX, "C0", a.carregar_config(conf)) is True
    assert auditoria.ler(log)[0]["saida"]["acao"] == "suspender_autonomia"


def test_erro_antigo_nao_suspende(tmp_path):
    conf = tmp_path / "c.json"
    a.aprovar_autonomia(conf, CTX, "Rafael", [ev()] * 299)
    assert a.reavaliar(conf, [ev(analista="alta", quando="2000-01-01T00:00:00+00:00")]) == []


def test_revogar_desliga(tmp_path):
    conf = tmp_path / "c.json"
    a.aprovar_autonomia(conf, CTX, "Rafael", [ev()] * 299)
    a.revogar_autonomia(conf, CTX, "Rafael")
    assert a.autonomos(a.carregar_config(conf)) == set()
