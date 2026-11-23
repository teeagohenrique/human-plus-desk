import json

from src import auditoria
from src.main import processar


def test_registrar_e_ler(tmp_path):
    log = tmp_path / "log.jsonl"
    auditoria.registrar(log, "C1", "triagem", {"urgencia": "alta"})
    auditoria.registrar(log, "C1", "analista", {}, decisao="editou", texto_final="oi")
    eventos = auditoria.ler(log)
    assert len(eventos) == 2
    assert eventos[0]["decisao_analista"] == "pendente"
    assert eventos[1]["decisao_analista"] == "editou"


def test_log_so_acrescenta(tmp_path):
    log = tmp_path / "log.jsonl"
    auditoria.registrar(log, "C1", "a", {})
    primeira = log.read_text(encoding="utf-8")
    auditoria.registrar(log, "C2", "a", {})
    assert log.read_text(encoding="utf-8").startswith(primeira)


def test_ler_arquivo_inexistente(tmp_path):
    assert auditoria.ler(tmp_path / "nao_existe.jsonl") == []


def test_pipeline_nao_grava_dado_pessoal_no_log(tmp_path):
    log = tmp_path / "log.jsonl"
    processar("C1", "CPF 123.456.789-09, tel (11) 98765-4321, ana@x.com. O sistema travou.", log=log)
    conteudo = log.read_text(encoding="utf-8")
    for dado in ["123.456.789-09", "98765-4321", "ana@x.com"]:
        assert dado not in conteudo
    assert all(e["decisao_analista"] == "pendente" for e in auditoria.ler(log))


def test_ler_ignora_json_quebrado_e_mantem_validos(tmp_path, caplog):
    log = tmp_path / "log.jsonl"
    auditoria.registrar(log, "C1", "triagem", {"urgencia": "alta"})
    with log.open("a", encoding="utf-8") as f:
        f.write("{linha quebrada\n")
    auditoria.registrar(log, "C2", "triagem", {"urgencia": "baixa"})

    eventos = auditoria.ler(log)

    assert [e["chamado_id"] for e in eventos] == ["C1", "C2"]
    assert "linha 2" in caplog.text


def test_ler_ignora_eventos_com_campos_obrigatorios_invalidos(tmp_path, caplog):
    log = tmp_path / "log.jsonl"
    base = {"quando": "2026-11-23T12:00:00+00:00", "agente": "analista",
            "decisao_analista": "aprovou"}
    with log.open("w", encoding="utf-8") as f:
        f.write(json.dumps({**base, "chamado_id": "C1"}) + "\n")  # sem "saida"
        f.write(json.dumps({**base, "chamado_id": "C2", "saida": ["errado"]}) + "\n")
        f.write(json.dumps({**base, "chamado_id": "C3", "saida": {"urgencia": "alta"}}) + "\n")

    eventos = auditoria.ler(log)

    assert [e["chamado_id"] for e in eventos] == ["C3"]
    assert "linha 1" in caplog.text and "linha 2" in caplog.text


def test_ler_preserva_campos_extras_e_preenche_defaults(tmp_path):
    log = tmp_path / "log.jsonl"
    original = {
        "quando": "2026-11-23T12:00:00+00:00",
        "chamado_id": "C1",
        "agente": "analista",
        "saida": {"urgencia": "alta"},
        "decisao_analista": "aprovou",
        "simulado": True,
        "campo_futuro": "preservado",
    }
    log.write_text(json.dumps(original) + "\n", encoding="utf-8")

    lido = auditoria.ler(log)[0]

    assert lido["simulado"] is True
    assert lido["texto_final"] is None
    assert lido["saida"] == {"urgencia": "alta"}
    assert lido["campo_futuro"] == "preservado"
