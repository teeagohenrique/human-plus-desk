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
