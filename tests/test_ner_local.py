"""Camada NER local: nomes fora dos prefixos, sem falsos positivos conhecidos."""
from unittest.mock import patch

from src.ner_local import nomes_encontrados


def test_encontra_nome_fora_dos_prefixos_da_heuristica():
    texto = "O relatório foi revisado por Beatriz Lima antes do envio."
    inicio = texto.index("Beatriz Lima")
    assert nomes_encontrados(texto) == [(inicio, inicio + len("Beatriz Lima"))]


def test_nao_marca_termos_de_servicedesk_como_pessoa():
    for texto in [
        "Procurei no menu e não achei.",
        "Abri dois chamados semana passada.",
        "CNPJ 12.345.678/0001-95",
        "Olá, tudo bem?",
        "Favor verificar o chamado.",
    ]:
        assert nomes_encontrados(texto) == [], texto


def test_modelo_indisponivel_devolve_lista_vazia():
    with patch("src.ner_local._analisador", side_effect=RuntimeError("modelo ausente")):
        assert nomes_encontrados("Beatriz Lima") == []
