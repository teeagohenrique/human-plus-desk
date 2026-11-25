from src.mascara import mascarar
from src.redator import (
    PEND_PRAZO,
    PEND_PROVISORIA,
    formatar_sugestao_acervo,
    gerar_rascunho,
    pendencias_abertas,
    validar_rascunho,
)
from src.triagem import triar

CARLOS = ("Bom dia, aqui é o Carlos. O sistema de faturamento travou pela terceira vez "
          "essa semana e eu preciso fechar o mês até o meio-dia.")


def test_rascunho_carlos_passa_no_guardrail_e_deixa_prazo_em_branco():
    r = gerar_rascunho(CARLOS, triar(CARLOS))
    assert r.passou_guardrail, r.feedback_guardrail
    assert PEND_PRAZO in r.texto
    assert "Parece que isso já aconteceu mais de uma vez" in r.texto  # reflexão
    assert "?" in r.texto                                              # pergunta aberta


def test_guardrail_bloqueia_exemplo_com_prazo_prometido():
    ruim = "Carlos, entendo que isso é desgastante. Já priorizei o seu caso e te retorno até as 10h30 com o status."
    ok, feedback = validar_rascunho(ruim, CARLOS)
    assert not ok
    assert feedback


def test_guardrail_bloqueia_promessa_sem_numero():
    ok, _ = validar_rascunho("Garanto que resolvo isso hoje.", CARLOS)
    assert not ok


def test_guardrail_bloqueia_rotulo_sobre_a_pessoa():
    ok, _ = validar_rascunho("Percebo que você está muito nervoso.", CARLOS)
    assert not ok


def test_guardrail_bloqueia_numero_que_nao_esta_no_chamado():
    ok, _ = validar_rascunho("Seu chamado tem 3 pendências abertas.", CARLOS)
    assert not ok


def test_guardrail_bloqueia_dado_pessoal_sem_mascara():
    ok, _ = validar_rascunho("Confirme o CPF 123.456.789-09 por favor.", CARLOS)
    assert not ok


def test_guardrail_aceita_rascunho_limpo_com_placeholder():
    limpo = f"Olá, parece que isso aconteceu mais de uma vez. Te dou um retorno {PEND_PRAZO}."
    ok, _ = validar_rascunho(limpo, CARLOS)
    assert ok


def test_rascunho_de_todos_os_chamados_simulados_passa_e_nao_vaza_dado():
    import json
    from pathlib import Path
    dados = json.loads((Path(__file__).parent.parent / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))
    for c in dados["chamados"]:
        m = mascarar(c["texto"])
        r = gerar_rascunho(m.texto, triar(m.texto))
        assert r.passou_guardrail, (c["id"], r.feedback_guardrail)
        assert not mascarar(r.texto).tipos_encontrados, c["id"]


def test_rascunho_reage_a_leitura_e_palpites_da_percepcao():
    from src.percepcao import LEITURAS, perceber
    t = triar(CARLOS)
    palpites = perceber(CARLOS, t)
    r_prazo = gerar_rascunho(CARLOS, t, palpites=palpites, leitura="pressa_prazo")
    r_conf = gerar_rascunho(CARLOS, t, palpites=palpites, leitura="perda_de_confianca")
    assert r_prazo.passou_guardrail and r_conf.passou_guardrail
    assert r_prazo.texto != r_conf.texto
    assert "caminho provisório" in r_prazo.texto
    for chave in LEITURAS:
        r = gerar_rascunho(CARLOS, t, palpites=palpites, leitura=chave)
        assert r.passou_guardrail, (chave, r.feedback_guardrail)


def test_formatar_sugestao_acervo_ingles_mantem_pendencia_detectavel():
    texto = formatar_sugestao_acervo(
        triar(CARLOS), "secure browser-based webmail", idioma="EN"
    )

    assert "Hello, @!" in texto
    assert "[secure browser-based webmail]" in texto
    assert "[RETURN TIME: analyst fills]" in texto
    assert pendencias_abertas(texto) == ["[RETURN TIME: analyst fills]"]


def test_formatar_sugestao_acervo_substitui_solucao_provisoria_e_mantem_prazo_e_arroba():
    t = triar(CARLOS)
    solucao = "acesso alternativo ao módulo de faturamento pela versão web de contingência"
    texto = formatar_sugestao_acervo(t, solucao)

    assert "Olá, @!" in texto
    assert "Com base no relato" in texto
    assert "já está trabalhando" not in texto
    assert f"[{solucao}]" in texto
    assert PEND_PROVISORIA not in texto
    assert PEND_PRAZO in texto
    assert "Marina\nAnalista de Suporte ao Cliente | Human+Desk" in texto
    assert pendencias_abertas(texto) == [PEND_PRAZO]

    respondido = texto.replace(PEND_PRAZO, "às 16h30 de hoje")
    assert pendencias_abertas(respondido) == []

