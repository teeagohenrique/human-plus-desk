"""Fixtures compartilhadas pelos testes de tela (AppTest)."""
import json
from pathlib import Path

import pytest

from src import auditoria
from src.painel import ItemFila, carregar_historico, montar_fila, registrar_decisao

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def itens_regras() -> list[ItemFila]:
    """Fila real, offline e deterministica: dois chamados do dataset, via regras."""
    chamados = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"][:2]
    historico = carregar_historico(RAIZ / "data" / "historico_simulado.json")
    return montar_fila(chamados, historico, provider="regras")


@pytest.fixture
def eventos_regras(tmp_path: Path, itens_regras: list[ItemFila]) -> list[dict]:
    """Eventos reais gravados por registrar_decisao, para a tela do Rafael."""
    log = tmp_path / "l.jsonl"
    registrar_decisao(log, itens_regras[0], "aprovou", "x", leitura="pressa_prazo")
    registrar_decisao(log, itens_regras[1], "editou", "y", leitura_livre="cansado do processo")
    return auditoria.ler(log)
