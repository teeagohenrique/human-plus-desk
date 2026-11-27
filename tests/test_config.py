"""Configuração: fail-closed em produção, sem depender de .env real."""
import pytest

from src.config import PLACEHOLDER_CHAVE, Config


def _config(chave: str, ambiente: str = "producao") -> Config:
    return Config(
        gemini_api_key=chave,
        gemini_model="gemini-2.5-flash",
        llm_provider="gemini",
        ambiente=ambiente,
    )


def test_validar_producao_rejeita_chave_de_exemplo():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _config(PLACEHOLDER_CHAVE).validar_producao()


def test_validar_producao_rejeita_chave_vazia():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _config("").validar_producao()


def test_validar_producao_aceita_chave_presente():
    _config("chave-de-teste").validar_producao()
