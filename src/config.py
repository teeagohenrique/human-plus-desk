"""Configuração compartilhada pelos pontos de entrada (CLI e painel).

Este módulo apenas define a função; quem decide chamá-la é o entry point.
Assim a suíte de testes, que importa os módulos de domínio, não carrega
variáveis de um .env real e continua determinística e offline.
"""
import os
from pathlib import Path

PLACEHOLDER_CHAVE = "sua_chave_aqui"


def carregar_env(caminho: Path) -> None:
    """Carrega GEMINI_* de um .env sem sobrescrever variáveis já definidas no shell."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = (parte.strip() for parte in linha.split("=", 1))
        valor = valor.strip("\"'")
        if not valor or valor == PLACEHOLDER_CHAVE:
            continue
        os.environ.setdefault(chave, valor)
