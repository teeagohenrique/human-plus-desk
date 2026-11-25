"""Tela da Marina (src/ui_marina.py) com AppTest.

As dependencias de arquivo, banco e auditoria entram controladas; a fila vem da
fixture `itens_regras` (pipeline real, offline, sem chamada de API).
"""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.percepcao import LEITURAS
from src.textos import I18N

TXT = I18N["PT"]
SCRIPT = """
from src.ui_marina import tela_marina
from src.textos import I18N
tela_marina('regras', I18N['PT'])
"""


@contextmanager
def _tela(itens):
    with ExitStack() as pilha:
        pilha.enter_context(patch("src.ui_marina.fila_base", return_value=itens))
        pilha.enter_context(patch("src.ui_marina.repositorio.estado", return_value={}))
        pilha.enter_context(patch("src.ui_marina.repositorio.ids_concluidos", return_value=set()))
        pilha.enter_context(patch("src.ui_marina.repositorio.registrar_urgencia"))
        pilha.enter_context(patch("src.ui_marina.auditoria.ler", return_value=[]))
        pilha.enter_context(patch(
            "src.ui_marina.carregar_config",
            return_value={"ativas": list(LEITURAS), "aprovacoes": []},
        ))
        yield AppTest.from_string(SCRIPT)


def test_marina_mostra_fila_e_origem_por_item(itens_regras):
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        # Sem indicador escolhido a tela mostra a welcome (ui_marina.py:471-474).
        at.button(key="btn_kpi_fila").click().run()

        assert not at.exception
        assert TXT["title_marina"] in [titulo.value for titulo in at.title]
        origem = TXT["origens"][itens_regras[0].origem_triagem]
        assert any(origem in legenda.value for legenda in at.caption)
        assert len(at.radio) >= 1


def test_marina_urgencia_sem_preselecao(itens_regras):
    chamado_id = itens_regras[0].id
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()

        assert not at.exception
        assert at.session_state.get(f"urg_ui_{chamado_id}") is None
        assert at.pills(key=f"urg_ui_{chamado_id}").value is None
        assert any(TXT["urg_hint"] in aviso.value for aviso in at.info)


def test_marina_trava_registro_com_placeholder(itens_regras):
    chamado_id = itens_regras[0].id
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()
        at.pills(key=f"urg_ui_{chamado_id}").set_value("media").run()
        at.button(key=f"go3_{chamado_id}").click().run()

        # A caixa de resposta comeca vazia; copiar a sugestao traz os colchetes.
        at.button(key=f"usar_{chamado_id}").click().run()

        assert not at.exception
        assert at.button(key=f"ok_{chamado_id}").disabled is True
        assert any(TXT["need_brack"] in aviso.value for aviso in at.warning)

        at.text_area(key=f"resp_ui_{chamado_id}").set_value("Resposta sem colchetes.").run()

        assert not at.exception
        assert at.button(key=f"ok_{chamado_id}").disabled is False
        assert TXT["ready_banner"] in [aviso.value for aviso in at.success]


def test_marina_prioridade_critica_seleciona_primeiro_chamado_automaticamente(itens_regras):
    # Mesmo quando o chamado ativo anterior era de baixa urgencia (fora da lista critica),
    # abrir Prioridade Critica deve selecionar automaticamente o primeiro chamado critico.
    id_critico = next(i.id for i in itens_regras if i.triagem.urgencia == "alta")
    id_baixo = next(i.id for i in itens_regras if i.triagem.urgencia != "alta")
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.radio(key="chamado_ativo_fila").set_value(id_baixo).run()
        assert at.session_state["chamado_ativo_fila"] == id_baixo

        at.button(key="btn_kpi_critica").click().run()
        assert not at.exception
        assert at.session_state["chamado_ativo_fila"] == id_critico
        assert at.radio(key="chamado_ativo_fila").value == id_critico


def test_marina_fluxo_acervo_substitui_solucao_sinaliza_botao_usar_e_libera_ao_preencher_prazo(itens_regras):
    from src.redator import PEND_PRAZO, PEND_PROVISORIA

    chamado_id = itens_regras[0].id
    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()

        # 1) Clica no botão da Análise Contextual para consultar o Acervo
        at.button(key=f"abrir_acervo_1_{chamado_id}").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"][chamado_id]["aba_acervo_aberta"] is True
        assert len(at.table) == 1

        # 2) Volta para a página onde estava (Análise)
        at.button(key=f"voltar_acervo_{chamado_id}").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"][chamado_id]["aba_acervo_aberta"] is False
        assert at.session_state["estado_chamados"][chamado_id]["camada"] == "chamado"

        # 3) Define urgência na Etapa 2, consulta o Acervo e avança para Resposta
        at.button(key=f"go2_{chamado_id}").click().run()
        at.pills(key=f"urg_ui_{chamado_id}").set_value("alta").run()
        at.button(key=f"go3_{chamado_id}").click().run()
        at.button(key=f"abrir_acervo_3_{chamado_id}").click().run()
        at.button(key=f"ir_resp_acervo_{chamado_id}").click().run()
        assert not at.exception

        # 4) Sugestão OARS já traz o texto estruturado com [@] e a solução do acervo, sem PEND_PROVISORIA
        leitura_reg = at.session_state["estado_chamados"][chamado_id]["leitura"] or "base"
        chave_sug = f"sug_ui_{chamado_id}_{leitura_reg}"
        sugestao_oars = at.text_area(key=chave_sug).value
        assert "Olá, @!" in sugestao_oars
        assert PEND_PROVISORIA not in sugestao_oars
        assert PEND_PRAZO in sugestao_oars

        # 5) Clica em "Usar na minha resposta": o botão acende (✓) e leva o texto para a caixa da Marina
        at.button(key=f"usar_{chamado_id}").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"][chamado_id]["usou_sugestao"] is True
        assert at.button(key=f"usar_{chamado_id}").label.startswith("✓ ")
        assert at.button(key=f"ok_{chamado_id}").disabled is True

        # 6) Marina preenche apenas o [PRAZO DE RETORNO], mantendo os [ ] da solução provisória
        texto_marina = at.text_area(key=f"resp_ui_{chamado_id}").value.replace(PEND_PRAZO, "às 16h30 de hoje")
        at.text_area(key=f"resp_ui_{chamado_id}").set_value(texto_marina).run()
        assert not at.exception
        assert at.button(key=f"ok_{chamado_id}").disabled is False


def test_marina_etapas_4_e_5_simular_passos_e_prazo_clicavel(itens_regras):
    from src.redator import PEND_PRAZO, PEND_PROVISORIA
    from src.ui_comum import topico_do_item

    item = itens_regras[0]
    chamado_id = item.id
    topico, _ = topico_do_item(item)
    assert topico is not None

    esperado_124 = (
        "Identificamos que as quedas também afetam outros usuários. "
        "Como medida alternativa, orientamos o acesso aos sistemas pelo portal web seguro, sem utilização de VPN. "
        "O problema já foi encaminhado à equipe de redes, juntamente com os horários das interrupções, para análise. "
        "No momento, recomendamos aguardar o retorno da equipe técnica."
    )

    with _tela(itens_regras) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        at.button(key=f"go2_{chamado_id}").click().run()
        at.pills(key=f"urg_ui_{chamado_id}").set_value("alta").run()
        at.button(key=f"go3_{chamado_id}").click().run()

        # Analista já escreveu algo antes de abrir o acervo; simular não pode sobrescrever resp_ui.
        at.text_area(key=f"resp_ui_{chamado_id}").set_value("Rascunho manual da analista.").run()
        at.button(key=f"abrir_acervo_3_{chamado_id}").click().run()

        # Marca passos 1, 2 e 4 (deixa passo 3 desmarcado) e simula melhor resposta
        at.checkbox(key=f"passo_{topico.id}_1").set_value(True).run()
        at.checkbox(key=f"passo_{topico.id}_2").set_value(True).run()
        at.checkbox(key=f"passo_{topico.id}_4").set_value(True).run()
        at.button(key=f"simular_melhor_resposta_{chamado_id}").click().run()
        assert not at.exception

        sug_sem_3 = at.session_state["estado_chamados"][chamado_id]["sugestao_acervo"]
        assert f"[{esperado_124}]" in sug_sem_3
        assert "rede alternativa" not in sug_sem_3.lower()
        assert "credenciais" not in sug_sem_3.lower()
        assert PEND_PROVISORIA not in sug_sem_3
        assert PEND_PRAZO in sug_sem_3

        # Marca passo 3 também: pode citar rede alternativa, nunca credenciais
        at.checkbox(key=f"passo_{topico.id}_3").set_value(True).run()
        at.button(key=f"simular_melhor_resposta_{chamado_id}").click().run()
        sug_com_3 = at.session_state["estado_chamados"][chamado_id]["sugestao_acervo"]
        assert "rede alternativa" in sug_com_3.lower()
        assert "credenciais" not in sug_com_3.lower()
        assert PEND_PRAZO in sug_com_3

        # Etapa 5: clica no simulador de prazo para preencher o segundo [ ] na sugestão OARS
        at.button(key=f"prazo_sim_{chamado_id}").click().run()
        assert not at.exception
        janela = at.session_state["estado_chamados"][chamado_id][f"prazo_sim_{chamado_id}"]
        sug_final = at.session_state["estado_chamados"][chamado_id]["sugestao_acervo"]
        assert f"[{janela}]" in sug_final
        assert PEND_PRAZO not in sug_final

        # Volta para Etapa 3: resp_ui não foi sobrescrito antes do clique em "Usar na minha resposta"
        at.button(key=f"ir_resp_acervo_{chamado_id}").click().run()
        assert at.text_area(key=f"resp_ui_{chamado_id}").value == "Rascunho manual da analista."

        # Clica em "Usar na minha resposta": leva tudo para resp_ui e libera o botão de registrar
        at.button(key=f"usar_{chamado_id}").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"][chamado_id]["usou_sugestao"] is True
        assert f"[{janela}]" in at.text_area(key=f"resp_ui_{chamado_id}").value
        assert at.button(key=f"ok_{chamado_id}").disabled is False


def test_marina_botao_unico_dentro_da_supervisao_abre_aba_acervo_inclusive_em_reclamacao():
    import json
    from pathlib import Path

    from src.painel import carregar_historico, montar_fila

    raiz = Path(__file__).resolve().parent.parent
    chamados = [
        c for c in json.loads((raiz / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
        if c["id"] in ("C01", "C09")
    ]
    hist = carregar_historico(raiz / "data" / "historico_simulado.json")
    itens = montar_fila(chamados, hist, provider="regras")

    with _tela(itens) as at:
        at.run(timeout=10)
        at.button(key="btn_kpi_fila").click().run()
        # Testa C09 (reclamação com parecer "Parece que a repetição pode estar pesando...")
        at.radio(key="chamado_ativo_fila").set_value("C09").run()
        at.button(key="go2_C09").click().run()
        at.pills(key="urg_ui_C09").set_value("alta").run()
        at.button(key="go3_C09").click().run()

        # Deve haver apenas UM botão do acervo na Etapa 3 (dentro do Registro de supervisão)
        botoes_acervo = [b for b in at.button if b.key and "acer" in b.key]
        assert [b.key for b in botoes_acervo] == ["abrir_acervo_3_C09"]

        # Ao clicar, abre a aba 📖 Acervo selecionada no segmented_control, com material M05-T04
        at.button(key="abrir_acervo_3_C09").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"]["C09"]["aba_acervo_aberta"] is True
        assert at.segmented_control(key="camada_C09").value == "acervo"
        assert any("M05-T04" in m.value for m in at.markdown)

        # Ao voltar, retorna exatamente para a Etapa 3 ("resposta") e o botão clicado fica aceso (✓)
        at.button(key="voltar_acervo_C09").click().run()
        assert not at.exception
        assert at.session_state["estado_chamados"]["C09"]["aba_acervo_aberta"] is False
        assert at.session_state["estado_chamados"]["C09"]["camada"] == "resposta"
        assert at.segmented_control(key="camada_C09").value == "resposta"
        assert at.button(key="abrir_acervo_3_C09").label.startswith("✓ ")

        # Em C01 (3 pareceres), TODAS as 3 caixinhas de parecer trazem o botão do acervo
        at.radio(key="chamado_ativo_fila").set_value("C01").run()
        botoes_c01_etapa1 = [b.key for b in at.button if b.key and b.key.startswith("abrir_acervo_1_C01")]
        assert botoes_c01_etapa1 == ["abrir_acervo_1_C01", "abrir_acervo_1_C01_1", "abrir_acervo_1_C01_2"]

        # Dentro da Aba do Acervo, os botões de simular passos e preencher prazo acendem (✓) ao clicar
        at.button(key="abrir_acervo_1_C01_2").click().run()
        at.button(key="simular_melhor_resposta_C01").click().run()
        assert at.button(key="simular_melhor_resposta_C01").label.startswith("✓ ")
        at.button(key="prazo_sim_C01").click().run()
        assert at.button(key="prazo_sim_C01").label.startswith("✓ ")
