"""Permissões mínimas e retenção de logs: fail-closed em produção."""
from datetime import UTC, datetime, timedelta

import pytest

from src import seguranca


def test_externo_e_negado(monkeypatch):
    monkeypatch.delenv("SUPPORT_ALLOW_ALL", raising=False)
    with pytest.raises(PermissionError):
        seguranca.verificar_permissao("externo", "admin", {"leitura"})


def test_allow_all_e_recusado_em_producao(monkeypatch):
    monkeypatch.setenv("SUPPORT_ALLOW_ALL", "true")
    monkeypatch.setenv("APP_ENV", "producao")
    with pytest.raises(RuntimeError, match="SUPPORT_ALLOW_ALL"):
        seguranca.verificar_permissao("analista", "analista", {"leitura"})


def test_allow_all_funciona_fora_de_producao(monkeypatch):
    monkeypatch.setenv("SUPPORT_ALLOW_ALL", "true")
    monkeypatch.setenv("APP_ENV", "homologacao")
    seguranca.verificar_permissao("analista", "analista", {"leitura"})


def test_reter_logs_remove_antigas_e_preserva_recentes(tmp_path):
    log = tmp_path / "auditoria.jsonl"
    agora = datetime.now(UTC)
    antiga = (agora - timedelta(hours=48)).isoformat()
    recente = agora.isoformat()
    log.write_text(
        '{"quando": "' + antiga + '", "chamado_id": "antigo"}\n'
        + '{"quando": "' + recente + '", "chamado_id": "recente"}\n',
        encoding="utf-8",
    )

    removidas = seguranca.reter_logs(log, horas=24)

    assert removidas == 1
    linhas = [linha for linha in log.read_text(encoding="utf-8").splitlines() if linha]
    assert len(linhas) == 1
    assert "recente" in linhas[0]
