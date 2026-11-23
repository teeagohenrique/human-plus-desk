import pytest

from src import auditoria
from src.calibracao import (LIMIAR_LIVRE, MIN_ATIVAS, MIN_DECISOES, aprovar_reducao, avaliar,
                            carregar_config, propor_reducao, reordenar)
from src.percepcao import LEITURAS

TODAS = list(LEITURAS)


def ev(leitura=None, livre=None, intencao="falha_sistema", decisao="aprovou", sem_palpites=False, agente="analista"):
    return {"quando": "2026-11-22T10:00:00+00:00", "chamado_id": "X", "agente": agente,
            "saida": {"urgencia": "alta", "intencao": intencao, "recorrente": False, "leitura": leitura,
                      "leitura_livre": livre, "sem_palpites": sem_palpites},
            "decisao_analista": decisao, "texto_final": None}


def lote(n, distribuicao):
    """distribuicao: dict leitura -> quantidade; o resto de n vira 'pressa_prazo'."""
    out = []
    for k, q in distribuicao.items():
        out += [ev(k)] * q
    return out + [ev("pressa_prazo")] * (n - len(out))


def cfg():
    return {"ativas": list(TODAS), "aprovacoes": []}


def test_poucos_dados_nao_propoe_nada():
    props, msg = propor_reducao(lote(MIN_DECISOES - 1, {}), cfg())
    assert props == [] and "insuficiente" in msg.lower()


def test_propoe_no_maximo_uma_leitura_rara():
    # 40 respostas; 'duvida_de_uso' e 'inseguranca_solucao' nunca escolhidas
    props, _ = propor_reducao(lote(40, {"cansaco_repeticao": 10, "perda_de_confianca": 10}), cfg())
    assert len(props) == 1
    assert props[0].leitura in {"duvida_de_uso", "inseguranca_solucao"}


def test_nao_propoe_se_analista_escreve_a_propria_leitura_com_frequencia():
    base = lote(30, {"cansaco_repeticao": 10, "perda_de_confianca": 10})
    muitos_livres = [ev(None, livre="outra coisa") for _ in range(int(40 * LIMIAR_LIVRE) + 2)]
    props, msg = propor_reducao(base + muitos_livres, cfg())
    assert props == [] and "não reduzir" in msg


def test_nunca_reduz_abaixo_do_minimo():
    c = {"ativas": TODAS[:MIN_ATIVAS], "aprovacoes": []}
    props, _ = propor_reducao(lote(60, {}), c)
    assert props == []
    with pytest.raises(ValueError):
        import tempfile, pathlib, json
        d = pathlib.Path(tempfile.mkdtemp()) / "c.json"
        d.write_text(json.dumps(c), encoding="utf-8")
        aprovar_reducao(d, TODAS[0], "Rafael")


def test_chamados_sem_palpites_nao_entram_na_conta():
    eventos = [ev(sem_palpites=True)] * 50
    a = avaliar(eventos, TODAS)
    assert a["respostas"] == 0 and not a["suficiente"]


def test_edicao_e_rejeicao_nao_sao_tratadas_como_erro_de_classificacao():
    a1 = avaliar([ev("pressa_prazo", decisao="aprovou")] * 5, TODAS)
    a2 = avaliar([ev("pressa_prazo", decisao="editou")] * 5, TODAS)
    assert a1["uso"] == a2["uso"]


def test_aprovacao_do_gestor_grava_config_e_auditoria(tmp_path):
    conf, log = tmp_path / "c.json", tmp_path / "log.jsonl"
    novo = aprovar_reducao(conf, "duvida_de_uso", "Rafael", log)
    assert "duvida_de_uso" not in novo["ativas"]
    assert "duvida_de_uso" not in carregar_config(conf)["ativas"]
    e = auditoria.ler(log)
    assert e[0]["agente"] == "gestor" and e[0]["saida"]["gestor"] == "Rafael"


def test_aprovar_leitura_inexistente_falha(tmp_path):
    with pytest.raises(ValueError):
        aprovar_reducao(tmp_path / "c.json", "nao_existe", "Rafael")


def test_config_padrao_tem_as_5_leituras(tmp_path):
    assert carregar_config(tmp_path / "nao_existe.json")["ativas"] == TODAS


def test_reordenar_mantem_ordem_com_poucos_dados():
    assert reordenar(TODAS, "falha_sistema", [ev("duvida_de_uso")] * 3, TODAS) == TODAS


def test_reordenar_com_dados_suficientes_sobe_a_mais_escolhida():
    eventos = [ev("duvida_de_uso")] * 8 + [ev("pressa_prazo")] * 4
    r = reordenar(TODAS, "falha_sistema", eventos, TODAS)
    assert r[0] == "duvida_de_uso" and r[1] == "pressa_prazo"


def test_reordenar_so_olha_a_propria_intencao():
    eventos = [ev("duvida_de_uso", intencao="acesso")] * 20
    assert reordenar(TODAS, "falha_sistema", eventos, TODAS) == TODAS


def test_reordenar_respeita_leituras_ativas():
    ativas = [k for k in TODAS if k != "duvida_de_uso"]
    assert "duvida_de_uso" not in reordenar(TODAS, "falha_sistema", [], ativas)
