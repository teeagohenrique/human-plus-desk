import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from src import repositorio


@pytest.fixture
def db(tmp_path):
    caminho = tmp_path / "human_desk.db"
    repositorio.init_db(caminho)
    return caminho


def test_init_cria_banco_e_popula_66_chamados(db):
    assert db.exists()
    tickets = repositorio.estado(caminho=db)
    assert len(tickets) == 66
    assert {f"V{i:02d}" for i in range(1, 51)} <= set(tickets)
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
    assert len(repositorio.estado(caminho=db)) == 66


def test_seed_reconcilia_decisoes_anteriores(tmp_path):
    caminho = tmp_path / "recon.db"
    repositorio.init_db(caminho, concluidos={"C01"})
    assert repositorio.estado(caminho=caminho)["C01"]["status"] == "concluido"


def test_reconciliacao_ignora_linha_jsonl_corrompida(tmp_path, monkeypatch):
    caminho = tmp_path / "recon.db"
    repositorio.init_db(caminho)
    with repositorio.conectar(caminho) as conn:
        conn.execute("UPDATE tickets SET status = 'concluido', resposta_final = NULL WHERE id = 'C01'")

    monkeypatch.setattr(repositorio, "RAIZ", tmp_path)
    log = tmp_path / "data" / "painel_log.jsonl"
    log.parent.mkdir()
    log.write_text("{linha incompleta\n", encoding="utf-8")
    with repositorio.conectar(caminho) as conn:
        repositorio._reconciliar_respostas(conn, {"C01"})

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


def test_decisao_outbox_exporta_jsonl_idempotente(tmp_path):
    caminho_db = tmp_path / "outbox.db"
    caminho_log = tmp_path / "audit.jsonl"
    repositorio.init_db(caminho_db)
    payload = {
        "agente": "analista",
        "saida": {"urgencia": "media", "intencao": "acesso"},
        "decisao_analista": "editou",
        "texto_final": "Resposta simulada",
    }

    repositorio.registrar_decisao(
        "C01", "editou", "Resposta simulada", "Marina",
        payload_auditoria=payload, caminho=caminho_db,
    )
    repositorio.exportar_auditoria_pendente(caminho_log, caminho_db)
    with repositorio.conectar(caminho_db) as conn:
        conn.execute("UPDATE eventos SET jsonl_exportado = 0 WHERE id = 1")
    repositorio.exportar_auditoria_pendente(caminho_log, caminho_db)

    registros = [json.loads(linha) for linha in caminho_log.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1
    assert registros[0]["evento_db_id"] == 1
    assert registros[0]["decisao_analista"] == "editou"
    assert repositorio.eventos(caminho_db, "C01")[-1]["jsonl_exportado"] == 1


@pytest.mark.parametrize("payload", [
    {},
    {"agente": "analista"},
    {"agente": "analista", "saida": {}},
])
def test_payload_incompleto_nao_fica_pendente(db, payload):
    with pytest.raises(ValueError, match="payload_auditoria incompleto"):
        repositorio.registrar_decisao(
            "C01", "aprovou", "OK", "Marina", payload_auditoria=payload, caminho=db
        )
    assert repositorio.eventos(db, "C01") == []


def test_exportacao_recupera_de_falha_entre_jsonl_e_flag(tmp_path, monkeypatch):
    from src import auditoria

    caminho_db = tmp_path / "outbox.db"
    caminho_log = tmp_path / "audit.jsonl"
    repositorio.init_db(caminho_db)
    repositorio.registrar_decisao(
        "C01", "editou", "Resposta", "Marina",
        payload_auditoria={
            "agente": "analista",
            "saida": {"urgencia": "media", "intencao": "acesso"},
            "decisao_analista": "editou",
            "texto_final": "Resposta",
        },
        caminho=caminho_db,
    )
    original = auditoria.registrar_payload

    def falha_depois_de_escrever(caminho, evento):
        original(caminho, evento)
        raise OSError("falha simulada antes do UPDATE")

    monkeypatch.setattr(auditoria, "registrar_payload", falha_depois_de_escrever)
    assert repositorio.exportar_auditoria_pendente(caminho_log, caminho_db) == 0
    assert repositorio.eventos(caminho_db, "C01")[-1]["jsonl_exportado"] == 0

    monkeypatch.setattr(auditoria, "registrar_payload", original)
    assert repositorio.exportar_auditoria_pendente(caminho_log, caminho_db) == 0
    assert repositorio.eventos(caminho_db, "C01")[-1]["jsonl_exportado"] == 1
    registros = [json.loads(linha) for linha in caminho_log.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1


def test_exportacao_concorrente_nao_duplica(tmp_path):
    caminho_db = tmp_path / "outbox.db"
    caminho_log = tmp_path / "audit.jsonl"
    repositorio.init_db(caminho_db)
    repositorio.registrar_decisao(
        "C01", "aprovou", "OK", "Marina",
        payload_auditoria={
            "agente": "analista",
            "saida": {"urgencia": "baixa", "intencao": "acesso"},
            "decisao_analista": "aprovou",
            "texto_final": "OK",
        },
        caminho=caminho_db,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(
            lambda _: repositorio.exportar_auditoria_pendente(caminho_log, caminho_db),
            range(2),
        ))

    assert sum(resultados) == 1
    registros = [json.loads(linha) for linha in caminho_log.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1
    assert repositorio.eventos(caminho_db, "C01")[-1]["jsonl_exportado"] == 1


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


def test_nova_decisao_guarda_resposta_e_resolvedor_anteriores_no_evento(db):
    repositorio.registrar_decisao("C04", "editou", "Resposta original", "Marina", caminho=db)
    repositorio.reabrir("C04", "Rafael", caminho=db)
    repositorio.registrar_decisao(
        "C04", "aprovou", "Resposta revisada", "Rafael",
        detalhes={"origem_triagem": "gemini", "resposta_anterior": "forjada"}, caminho=db,
    )

    ev = repositorio.eventos(db, "C04")[-1]
    det = ev["detalhes"]
    assert ev["acao"] == "decisao"
    assert det["decisao"] == "aprovou"
    assert det["origem_triagem"] == "gemini"
    # Os campos de rastreabilidade são autorais: detalhes do chamador não os sobrescrevem.
    assert det["resposta_anterior"] == "Resposta original"
    assert det["resolvido_por_anterior"] == "Marina"
    assert det["resolvido_em_anterior"]
    assert det["status_anterior"] == "pendente"
    assert det["tem_resposta_anterior"] is True

    atual = repositorio.estado(caminho=db)["C04"]
    assert atual["resposta_final"] == "Resposta revisada"
    assert atual["resolvido_por"] == "Rafael"


def test_primeira_decisao_registra_ausencia_de_resposta_anterior(db):
    repositorio.registrar_decisao("C05", "rejeitou", None, "Marina", caminho=db)

    det = repositorio.eventos(db, "C05")[-1]["detalhes"]
    assert det["resposta_anterior"] is None
    assert det["resolvido_por_anterior"] is None
    assert det["resolvido_em_anterior"] is None
    assert det["status_anterior"] == "pendente"
    assert det["tem_resposta_anterior"] is False


def test_decisao_sem_texto_preserva_resposta_ja_gravada(db):
    repositorio.registrar_decisao("C06", "editou", "Texto enviado ao cliente.", "Marina", caminho=db)
    repositorio.reabrir("C06", "Rafael", caminho=db)
    repositorio.registrar_decisao("C06", "rejeitou", None, "Marina", caminho=db)

    atual = repositorio.estado(caminho=db)["C06"]
    assert atual["status"] == "concluido"
    assert atual["resposta_final"] == "Texto enviado ao cliente."

