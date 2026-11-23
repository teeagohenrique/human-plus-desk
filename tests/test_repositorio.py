import pytest

from src import repositorio


@pytest.fixture
def db(tmp_path):
    caminho = tmp_path / "human_desk.db"
    repositorio.init_db(caminho)
    return caminho


def test_init_cria_banco_e_popula_52_chamados(db):
    assert db.exists()
    tickets = repositorio.estado(caminho=db)
    assert len(tickets) == 52
    assert {f"V{i:02d}" for i in range(1, 37)} <= set(tickets)
    assert {f"C{i:02d}" for i in range(1, 17)} <= set(tickets)
    assert {t["dataset"] for t in tickets.values()} == {
        repositorio.DATASET_FILA, repositorio.DATASET_BENCHMARK,
    }


def test_seed_guarda_apenas_texto_mascarado(db):
    for ticket in repositorio.estado(caminho=db).values():
        assert "123.456.789-09" not in ticket["texto_mascarado"]
        assert "98765" not in ticket["texto_mascarado"]


def test_seed_e_idempotente(db):
    repositorio.init_db(db)
    assert len(repositorio.estado(caminho=db)) == 52


def test_seed_reconcilia_decisoes_anteriores(tmp_path):
    caminho = tmp_path / "recon.db"
    repositorio.init_db(caminho, concluidos={"C01"})
    assert repositorio.estado(caminho=caminho)["C01"]["status"] == "concluido"


def test_urgencia_e_gravada_na_hora_com_agente_e_timestamp(db):
    repositorio.registrar_urgencia("C01", "alta", "Marina", caminho=db)
    ticket = repositorio.estado(caminho=db)["C01"]
    assert ticket["urgencia_confirmada"] == "alta"
    assert ticket["pontuacao_analista"] == 8

    ev = repositorio.eventos(db, "C01")[-1]
    assert ev["acao"] == "urgencia_alterada"
    assert ev["agente"] == "Marina"
    assert ev["criado_em"].startswith("20")
    assert ev["detalhes"]["urgencia_nova"] == "alta"


def test_urgencia_invalida_e_rejeitada(db):
    with pytest.raises(ValueError):
        repositorio.registrar_urgencia("C01", "high", "Marina", caminho=db)


def test_decisao_grava_resposta_e_agente(db):
    repositorio.registrar_decisao(
        "C01", "editou", "Resposta final", "Marina",
        detalhes={"origem_triagem": "gemini"}, caminho=db,
    )
    ticket = repositorio.estado(caminho=db)["C01"]
    assert ticket["status"] == "concluido"
    assert ticket["resposta_final"] == "Resposta final"
    assert ticket["resolvido_por"] == "Marina"
    assert ticket["resolvido_em"]

    ev = repositorio.eventos(db, "C01")[-1]
    assert ev["agente"] == "Marina"
    assert ev["detalhes"]["origem_triagem"] == "gemini"
    assert "C01" in repositorio.ids_concluidos(caminho=db)


def test_reabrir_nao_apaga_auditoria(db):
    repositorio.registrar_decisao("C02", "aprovou", "OK", "Marina", caminho=db)
    antes = repositorio.estado(caminho=db)["C02"]

    repositorio.reabrir("C02", "Rafael", caminho=db)
    depois = repositorio.estado(caminho=db)["C02"]

    assert depois["status"] == "pendente"
    assert depois["resolvido_por"] == antes["resolvido_por"]
    assert depois["resolvido_em"] == antes["resolvido_em"]
    assert depois["resposta_final"] == antes["resposta_final"]
    assert "C02" not in repositorio.ids_concluidos(caminho=db)

    acoes = [e["acao"] for e in repositorio.eventos(db, "C02")]
    assert acoes == ["decisao", "reabriu"]
    assert repositorio.eventos(db, "C02")[-1]["agente"] == "Rafael"


def test_nova_decisao_reconquista_chamado_reaberto(db):
    repositorio.registrar_decisao("C03", "aprovou", "OK", "Marina", caminho=db)
    repositorio.reabrir("C03", "Rafael", caminho=db)
    repositorio.registrar_decisao("C03", "aprovou", "OK 2", "Marina", caminho=db)
    assert "C03" in repositorio.ids_concluidos(caminho=db)
    assert [e["acao"] for e in repositorio.eventos(db, "C03")] == [
        "decisao", "reabriu", "decisao",
    ]
