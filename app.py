"""Painel Human + Desk (Streamlit). Rodar:  streamlit run app.py

Duas telas: Painel da Marina (decide) e Painel do Rafael (gráficos).
A IA só sugere; aqui nada é enviado de verdade: a decisão é registrada na auditoria.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src import auditoria
from src.calibracao import (LIMIAR_LIVRE, LIMIAR_RARA, MIN_DECISOES, aprovar_reducao, avaliar,
                            carregar_config, propor_reducao)
from src.painel import (carregar_historico, decisao_por_texto, gerar_simulado, ids_decididos, leituras_do_item,
                        metricas, montar_fila, registrar_decisao, calibracao_triagem)
from src.percepcao import LEITURAS
from src.redator import _PLACEHOLDER, gerar_rascunho

RAIZ = Path(__file__).resolve().parent
LOG = RAIZ / "data" / "painel_log.jsonl"
LOG_SIM = RAIZ / "data" / "painel_simulado.jsonl"
CONFIG = RAIZ / "data" / "calibracao_config.json"
COR = {"alta": "🔴", "media": "🟠", "baixa": "🟢"}
NOMES_DECISAO = {"aprovou": "Aprovou", "editou": "Editou", "rejeitou": "Rejeitou"}

st.set_page_config(page_title="Human + Desk", page_icon="🤝", layout="wide")


@st.cache_data
def fila_base():
    chamados = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
    hist = carregar_historico(RAIZ / "data" / "historico_simulado.json")
    return montar_fila(chamados, hist)


def tela_marina():
    st.title("Painel da Marina")
    st.caption("A IA só sugere. Quem decide é você. Nada é enviado: a decisão fica registrada na auditoria.")
    itens = fila_base()
    feitos = ids_decididos(auditoria.ler(LOG))
    fila = [i for i in itens if i.id not in feitos]
    st.metric("Chamados na fila", len(fila), help=f"{len(feitos)} já decididos")
    if not fila:
        st.success("Fila zerada! Bom trabalho 🎉")
        return

    esq, dir_ = st.columns([1, 2])
    with esq:
        rotulos = {i.id: f"{COR[i.triagem.urgencia]} {i.id} · {i.triagem.intencao}" for i in fila}
        escolhido = st.radio("Fila (mais urgentes primeiro)", list(rotulos), format_func=rotulos.get)
    item = next(i for i in fila if i.id == escolhido)
    t = item.triagem

    with dir_:
        st.subheader(f"{COR[t.urgencia]} {item.id}: urgência {t.urgencia} ({t.pontuacao_urgencia} pts)")
        st.markdown(f"> {item.texto_mascarado}")
        st.caption("Texto já com dados pessoais mascarados.")

        st.markdown(f"**Triagem:** {t.intencao} (confiança {t.confianca})")
        with st.expander("Por quê? (trechos do chamado)", expanded=True):
            for m in t.motivos_urgencia + t.motivos_intencao:
                st.markdown(f"- `{m.sinal}`: “{m.trecho}”")
            if not (t.motivos_urgencia or t.motivos_intencao):
                st.write("Sem sinais encontrados no texto.")

        st.markdown("**Palpites da Percepção** (hipóteses, não diagnósticos)")
        if not item.palpites:
            st.info("Nenhum palpite: sem evidência, sem palpite.")
        for p in item.palpites:
            with st.expander(f"{p.hipotese}  ·  confiança {p.confianca}"):
                for e in p.evidencias:
                    st.markdown(f"- evidência `{e.sinal}`: “{e.trecho}”")
                st.markdown(f"**Pergunta para confirmar:** {p.pergunta_confirmacao}")
                if p.sugere_subir_urgencia:
                    st.warning("Sugestão: considerar subir a prioridade. A decisão é sua.")

        leitura = leitura_livre = None
        if item.palpites:
            st.markdown("**Qual leitura combina mais com este chamado?**")
            opcoes = leituras_do_item(item, auditoria.ler(LOG), carregar_config(CONFIG)) + ["nenhuma"]
            leitura = st.radio("Leitura", opcoes, key=f"leit_{item.id}", horizontal=True,
                               format_func=lambda k: LEITURAS.get(k, "Nenhuma delas"))
            if leitura == "nenhuma":
                leitura = None
                leitura_livre = st.text_input("Escreva a sua leitura (opcional)", key=f"livre_{item.id}")

        niveis = ["alta", "media", "baixa"]
        urgencia_analista = st.radio(
            f"Urgência — a IA sugeriu **{t.urgencia}** (escolha conscientemente a urgência correta):",
            niveis,
            index=None,
            horizontal=True,
            key=f"urg_{item.id}",
        )
        if urgencia_analista is None:
            st.info("Selecione a urgência acima para liberar a decisão (evita concordância automática).")

        rascunho_atual = gerar_rascunho(item.texto_mascarado, t, palpites=item.palpites, leitura=leitura)
        st.markdown("**Rascunho da resposta** (adaptado à leitura escolhida; edite à vontade)")
        texto = st.text_area(
            "Resposta",
            rascunho_atual.texto,
            height=200,
            key=f"txt_{item.id}_{leitura or 'nenhuma'}",
            label_visibility="collapsed",
        )
        pend = _PLACEHOLDER.findall(texto)
        if pend:
            st.warning("Preencha ou remova os campos entre [colchetes] antes de aprovar: " + "; ".join(pend))

        c1, c2 = st.columns(2)
        if c1.button(
            "✅ Aprovar / salvar edição",
            disabled=bool(pend) or urgencia_analista is None,
            type="primary",
            key=f"ok_{item.id}",
        ):
            registrar_decisao(LOG, item, decisao_por_texto(rascunho_atual.texto, texto), texto, leitura, leitura_livre, urgencia_analista, False)
            st.rerun()
        if c2.button(
            "✖ Rejeitar (escrevo a minha)",
            disabled=urgencia_analista is None,
            key=f"rej_{item.id}",
        ):
            registrar_decisao(LOG, item, "rejeitou", None, leitura, leitura_livre, urgencia_analista, False)
            st.rerun()


def tela_rafael():
    st.title("Painel do Rafael (gestor)")
    usar_sim = st.toggle("Usar dados SIMULADOS (demonstração)", value=not LOG.exists())
    if usar_sim:
        if st.button("Gerar/atualizar dados simulados"):
            gerar_simulado(LOG_SIM, fila_base())
        st.warning("⚠️ Dados INVENTADOS, só para ver os gráficos. Não representam resultados reais.")
        eventos = auditoria.ler(LOG_SIM)
    else:
        eventos = auditoria.ler(LOG)
    m = metricas(eventos)
    if m["total"] == 0:
        st.info("Ainda não há decisões. Peça à Marina para decidir alguns chamados, ou gere dados simulados.")
        return

    c = st.columns(4)
    c[0].metric("Decisões", m["total"])
    c[1].metric("Editadas pela analista", f"{m['taxa_edicao']:.0%}")
    c[2].metric("Rejeitadas", f"{m['taxa_rejeicao']:.0%}")
    c[3].metric("Casos recorrentes", m["recorrentes"])

    st.subheader("Decisões da analista")
    st.bar_chart(pd.Series({NOMES_DECISAO[k]: v for k, v in m["decisoes"].items()}, name="chamados"))

    st.subheader("Decisão por urgência")
    df = pd.DataFrame(m["por_urgencia"]).T.rename(columns=NOMES_DECISAO)
    st.bar_chart(df)

    st.subheader("Decisões por dia")
    st.line_chart(pd.Series(m["por_dia"], name="decisões"))

    st.subheader("Leituras escolhidas pela analista")
    if m["leituras"]:
        st.bar_chart(pd.Series({LEITURAS[k]: v for k, v in m["leituras"].items()}, name="vezes"))
        st.caption(f"{m['leituras_livres']} vez(es) a analista escreveu a própria leitura. "
                   "Reduzir a lista de leituras só com regra e aprovação do gestor.")
    else:
        st.write("Nenhuma leitura registrada ainda.")
    st.caption("Poucas decisões = poucos dados: leia estes gráficos como indícios, não como conclusões.")

    st.divider()
    st.subheader("Calibração das leituras")
    config = carregar_config(CONFIG)
    a = avaliar(eventos, config["ativas"])
    st.progress(min(1.0, a["respostas"] / MIN_DECISOES),
                text=f"{a['respostas']} de {MIN_DECISOES} respostas necessárias para propor mudanças")
    if a["respostas"]:
        st.bar_chart(pd.Series({LEITURAS[k]: v for k, v in a["uso"].items()}, name="uso (fração das respostas)"))
        st.caption(f"Leitura própria escrita pela analista: {a['share_livre']:.0%} "
                   f"(acima de {LIMIAR_LIVRE:.0%} a lista não é reduzida). "
                   f"Uma leitura só é proposta para sair se for usada em menos de {LIMIAR_RARA:.0%}.")
    props, explicacao = propor_reducao(eventos, config)
    st.info(explicacao)
    for pr in props:
        st.markdown(f"**Proposta:** retirar “{LEITURAS[pr.leitura]}”. {pr.motivo}")
        if usar_sim:
            st.button("Aprovar (indisponível com dados simulados)", disabled=True, key="ap_sim")
        elif st.button(f"Aprovar a retirada (gestor)", key=f"ap_{pr.leitura}", type="primary"):
            aprovar_reducao(CONFIG, pr.leitura, "Rafael", LOG)
            st.rerun()
    st.caption("Leituras ativas hoje: " + ", ".join(LEITURAS[k] for k in config["ativas"]))

    st.divider()
    st.subheader("Calibração da urgência (triagem)")
    ct = calibracao_triagem(eventos)
    if ct["n"] == 0:
        st.info("Ainda não há urgências confirmadas pela analista.")
    else:
        k = st.columns(3)
        k[0].metric("Concordância IA × analista", f"{ct['concordancia']:.0%}")
        k[1].metric("Analista achou MAIS urgente", ct["subiu"], help="O erro mais perigoso: a IA subestimou.")
        k[2].metric("Analista achou MENOS urgente", ct["desceu"])
        if ct["n"] < MIN_DECISOES:
            st.info(f"Informação insuficiente para concluir: {ct['n']} de {MIN_DECISOES} respostas.")
        st.markdown("**Concordância por nível de confiança** (confiança calibrada = quanto mais alta, mais concordância)")
        df_c = pd.DataFrame(ct["por_confianca"]).T.reindex(["baixa", "media", "alta"]).dropna()
        if not df_c.empty:
            st.bar_chart(df_c["taxa"])
            st.dataframe(df_c.rename(columns={"n": "respostas", "concordou": "concordou", "taxa": "taxa"}))
        st.markdown("**Matriz** (linha = IA sugeriu, coluna = analista decidiu)")
        st.dataframe(pd.DataFrame(ct["matriz"]).T)
        st.caption("A analista escolhe a urgência explicitamente (sem pré-seleção) para evitar concordância automática.")

    st.divider()
    with st.expander("Visão futura (desligado no MVP): Portão de Autonomia"):
        st.info(
            "No MVP (v2), todas as decisões permanecem 100% humanas. O módulo `src/autonomia.py` "
            "(portão estatístico Clopper-Pearson) permanece guardado no repositório para fases futuras, "
            "quando houver volume real de chamados e modelos treinados."
        )


pagina = st.sidebar.radio("Tela", ["Painel da Marina", "Painel do Rafael"])
st.sidebar.caption("Human + Desk v2 · MVP enxuto · humano no controle")
(tela_marina if pagina == "Painel da Marina" else tela_rafael)()
