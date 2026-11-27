import pytest

from src import main, painel, pipeline

TEXTO = (
    "Bom dia, aqui é o Carlos, CPF 123.456.789-09. O sistema de faturamento "
    "travou pela terceira vez e preciso fechar o mês até o meio-dia."
)


def test_processar_chamado_devolve_artefatos_e_origens():
    r = pipeline.processar_chamado(TEXTO, provider="regras")

    assert "[NOME]" in r.mascara.texto
    assert r.triagem is not None
    assert r.origem_triagem == "regras"
    assert r.rascunho.texto
    assert r.origem_rascunho == "regras"
    assert r.provider_rascunho == "regras"
    assert r.leitura_inicial is None or isinstance(r.leitura_inicial, str)


def test_pipeline_impede_chamada_externa_se_ner_falhar(monkeypatch):
    from src import llm
    from src.mascara import ResultadoMascara

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "dummy-model")
    monkeypatch.setattr(
        pipeline, "mascarar", lambda texto: ResultadoMascara(
            texto="Nome não mascarado", tipos_encontrados=[], ner_disponivel=False
        ),
    )
    monkeypatch.setattr(
        llm, "_triagem_gemini", lambda *args, **kwargs: pytest.fail("não deve enviar para Gemini")
    )
    monkeypatch.setattr(
        llm, "_rascunho_gemini", lambda *args, **kwargs: pytest.fail("não deve enviar para Gemini")
    )

    resultado = pipeline.processar_chamado("texto original", provider="gemini")

    assert resultado.origem_triagem == "fallback"
    assert resultado.origem_rascunho == "fallback"


def test_pipeline_repassa_sinal_ner_para_triagem(monkeypatch):
    from src import llm
    from src.mascara import ResultadoMascara
    from src.triagem import triar

    vistos = []

    def triagem_falsa(texto, provider=None, model=None, ner_disponivel=False):
        vistos.append(ner_disponivel)
        return triar("sistema travou"), "regras"

    def rascunho_falso(texto, triagem, palpites=None, leitura=None, provider=None, model=None, ner_disponivel=False):
        return llm.gerar_rascunho(texto, triagem, palpites=palpites, leitura=leitura), "regras"

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "dummy-model")
    monkeypatch.setattr(
        pipeline, "mascarar",
        lambda texto: ResultadoMascara(
            texto="sistema travou", tipos_encontrados=[], ner_disponivel=True
        ),
    )
    monkeypatch.setattr(llm, "triagem_com_origem", triagem_falsa)
    monkeypatch.setattr(llm, "rascunho_com_origem", rascunho_falso)

    pipeline.processar_chamado(TEXTO, provider="gemini")

    assert vistos == [True]


def test_processar_chamado_repassa_historico_a_percepcao(monkeypatch):
    vistos = []

    def perceber_falso(texto_mascarado, triagem, historico=None):
        vistos.append(historico)
        return []

    monkeypatch.setattr(pipeline, "perceber", perceber_falso)
    historico = object()

    pipeline.processar_chamado(TEXTO, provider="regras", historico=historico)

    assert vistos == [historico]


def test_processar_chamado_emite_etapas_em_ordem():
    etapas = []

    pipeline.processar_chamado(TEXTO, provider="regras", ao_etapa=etapas.append)

    assert etapas == ["triagem", "rascunho"]


def test_cli_e_painel_compartilham_o_nucleo():
    chamado = {"id": "C01", "texto": TEXTO}
    item = painel.montar_fila([chamado], {}, provider="regras")[0]
    saida = main.processar("C01", TEXTO, log=None, provider="regras")

    assert set(saida) == {"id", "mascara", "triagem", "palpites", "rascunho"}
    assert saida["mascara"].texto == item.texto_mascarado
    assert saida["triagem"].model_dump() == item.triagem.model_dump()
    assert saida["rascunho"].model_dump() == item.rascunho.model_dump()
    assert saida["palpites"] == item.palpites
