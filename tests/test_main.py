import json
import os
from pathlib import Path

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


def test_carregar_env_delega_para_config_compartilhado(monkeypatch, tmp_path):
    vistos = []
    monkeypatch.setattr(main, "RAIZ", tmp_path)
    monkeypatch.setattr(main, "carregar_env", lambda caminho: vistos.append(caminho))

    main._carregar_env()

    assert vistos == [tmp_path / ".env"]


def test_demonstrar_imprime_fila_ordenada_e_log(monkeypatch, capsys, tmp_path):
    """Cobre a demonstracao textual: mascara, motivos, palpites, rascunho e guardrail."""
    chamados = [
        {"id": "C1", "texto": "Sistema travou, preciso fechar o mes hoje."},
        {"id": "C2", "texto": "Nao consigo acessar o sistema."},
    ]
    (tmp_path / "entrada.json").write_text(json.dumps({"chamados": chamados}), encoding="utf-8")
    def processador_falso(cid, texto, provider=None):
        return {
            "id": cid,
            "triagem": type("T", (), {
                "urgencia": "alta" if cid == "C1" else "baixa",
                "pontuacao_urgencia": 5 if cid == "C1" else 1,
                "intencao": "falha_sistema", "confianca": 0.9,
                "motivos_urgencia": [type("M", (), {"sinal": "prazo", "trecho": "hoje"})()],
            })(),
            "mascara": type("Masc", (), {"texto": f"mascarado {cid}"})(),
            "palpites": [type("P", (), {"tipo": "necessidade", "confianca": "baixa",
                                        "hipotese": "precisa de contorno"})()],
            "rascunho": type("R", (), {"texto": "Oi, entendi.", "passou_guardrail": True,
                                       "feedback_guardrail": ""})(),
        }
    monkeypatch.setattr(main, "DADOS", tmp_path / "entrada.json")
    monkeypatch.setattr(main, "carregar", lambda: chamados)
    monkeypatch.setattr(main, "processar", processador_falso)

    main.demonstrar()

    saida = capsys.readouterr().out
    assert "=== C1 | urgência ALTA (5 pts)" in saida
    assert saida.index("C1") < saida.index("C2")
    assert 'porquê [prazo]: "hoje"' in saida
    assert "palpite [necessidade | baixa]" in saida
    assert "guardrail: ok" in saida
    assert f"Log gravado em {main.LOG}" in saida


def test_avaliar_mostra_divergencia_e_retorna_motivos(monkeypatch, capsys, tmp_path):
    """Cobre o print de divergencia (linha 86) e o contrato de fallback_motivos."""
    chamados = [{"id": "C1", "texto": "texto", "gabarito": {"intencao": "acesso", "urgencia": "alta"}}]
    caminho = tmp_path / "gabarito.json"
    caminho.write_text(json.dumps({"chamados": chamados}), encoding="utf-8")
    triagem = type("T", (), {"intencao": "duvida", "urgencia": "baixa"})()
    monkeypatch.setattr(main, "triagem_com_llm", lambda *a, **k: triagem)

    resultado = main.avaliar(caminho)

    saida = capsys.readouterr().out
    assert "C1: previsto duvida/baixa | gabarito acesso/alta" in saida
    assert "Fallbacks: nenhum" in saida
    assert resultado["acertos_intencao"] == 0
    assert resultado["acertos_urgencia"] == 0
    assert resultado["fallback_motivos"] == {k: 0 for k in resultado["fallback_motivos"]}


def test_parse_args_avaliar_e_provider():
    """Cobre todas as opcoes da CLI sem depender de sys.argv global."""
    assert main._parse_args([]).avaliar is None
    assert main._parse_args([]).provider is None

    padrao = main._parse_args(["--avaliar"])
    assert padrao.avaliar == str(Path(main.DADOS))

    explicito = main._parse_args(["--avaliar", "outro.json", "--provider", "gemini"])
    assert explicito.avaliar == "outro.json"
    assert explicito.provider == "gemini"
