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
