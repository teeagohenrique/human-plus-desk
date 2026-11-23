"""Protege a paridade PT/EN enquanto as telas ganham novos rotulos.

Se uma chave for adicionada so em um idioma, ou se uma tela usar `txt[...]`
sem traducao, estes testes falham antes de chegar ao painel.
"""
import re
from pathlib import Path

import pytest

from src import textos

RAIZ = Path(__file__).resolve().parent.parent
TELAS = ("app.py", "src/ui_marina.py", "src/ui_rafael.py", "src/ui_comum.py")
PADRAO_CHAVE = re.compile(r"""txt\[\s*["']([^"']+)["']\s*\]""")


def _achatar(dicionario: dict, prefixo: str = "") -> set[str]:
    chaves = set()
    for chave, valor in dicionario.items():
        caminho = f"{prefixo}.{chave}" if prefixo else chave
        if isinstance(valor, dict):
            chaves |= _achatar(valor, caminho)
        else:
            chaves.add(caminho)
    return chaves


@pytest.fixture
def idiomas():
    return textos.I18N["PT"], textos.I18N["EN"]


def test_pt_e_en_tem_as_mesmas_chaves(idiomas):
    pt, en = idiomas
    assert pt.keys() == en.keys()
    assert _achatar(pt) == _achatar(en)


def test_nenhuma_traducao_vazia(idiomas):
    for nome, dicionario in zip(("PT", "EN"), idiomas):
        vazias = [c for c, v in _achatar_com_valores(dicionario).items() if isinstance(v, str) and not v.strip()]
        assert not vazias, f"{nome}: chaves vazias {vazias}"


def _achatar_com_valores(dicionario: dict, prefixo: str = "") -> dict:
    plano = {}
    for chave, valor in dicionario.items():
        caminho = f"{prefixo}.{chave}" if prefixo else chave
        if isinstance(valor, dict):
            plano.update(_achatar_com_valores(valor, caminho))
        else:
            plano[caminho] = valor
    return plano


def test_chaves_usadas_pelas_telas_existem_nos_dois_idiomas(idiomas):
    pt, en = idiomas
    usadas = set()
    for relativo in TELAS:
        fonte = (RAIZ / relativo).read_text(encoding="utf-8")
        usadas.update(PADRAO_CHAVE.findall(fonte))

    assert usadas, "nenhuma chave txt[...] encontrada — verifique o padrao de busca"
    faltando_pt = sorted(usadas - pt.keys())
    faltando_en = sorted(usadas - en.keys())
    assert not faltando_pt, f"ausentes em PT: {faltando_pt}"
    assert not faltando_en, f"ausentes em EN: {faltando_en}"
