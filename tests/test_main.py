import os

from src import main


def _preparar(monkeypatch, tmp_path, conteudo=None):
    """Isola os testes de qualquer GEMINI_* exportado no shell que rodou o pytest."""
    ambiente = dict(os.environ)
    ambiente.pop("GEMINI_API_KEY", None)
    ambiente.pop("GEMINI_MODEL", None)
    monkeypatch.setattr(main, "RAIZ", tmp_path)
    monkeypatch.setattr(os, "environ", ambiente)
    if conteudo is not None:
        (tmp_path / ".env").write_text(conteudo, encoding="utf-8")


def test_carregar_env_le_chave_e_modelo(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, "GEMINI_MODEL=gemini-3.5-flash-lite\nGEMINI_API_KEY=chave_teste\n")

    main._carregar_env()

    assert os.environ["GEMINI_MODEL"] == "gemini-3.5-flash-lite"
    assert os.environ["GEMINI_API_KEY"] == "chave_teste"


def test_carregar_env_ignora_comentarios_linhas_vazias_e_aspas(monkeypatch, tmp_path):
    _preparar(
        monkeypatch,
        tmp_path,
        '# comentario\n\nGEMINI_MODEL = "gemini-3.5-flash-lite"\nGEMINI_API_KEY=\'chave_teste\'\n',
    )

    main._carregar_env()

    assert os.environ["GEMINI_MODEL"] == "gemini-3.5-flash-lite"
    assert os.environ["GEMINI_API_KEY"] == "chave_teste"
    assert "# comentario" not in os.environ


def test_carregar_env_nao_sobrescreve_variavel_do_terminal(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, "GEMINI_MODEL=gemini-3.5-flash-lite\n")
    os.environ["GEMINI_MODEL"] = "modelo_do_terminal"

    main._carregar_env()

    assert os.environ["GEMINI_MODEL"] == "modelo_do_terminal"


def test_carregar_env_ignora_placeholder_e_valor_vazio(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, "GEMINI_API_KEY=sua_chave_aqui\nGEMINI_MODEL=\n")

    main._carregar_env()

    assert "GEMINI_API_KEY" not in os.environ
    assert "GEMINI_MODEL" not in os.environ


def test_carregar_env_sem_arquivo_nao_falha(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path)

    main._carregar_env()

    assert "GEMINI_API_KEY" not in os.environ
