"""Gestão e Qualidade (gestor): indicadores, calibração e trilha de auditoria.

Somente leitura sobre as decisões da analista; as únicas ações são aprovar a
redução de interpretações (calibração) e reabrir um chamado, ambas registradas.
"""
import os

import altair as alt
import pandas as pd
import streamlit as st

from src import auditoria, repositorio
from src.calibracao import (
    LIMIAR_LIVRE,
    LIMIAR_RARA,
    MIN_DECISOES,
    aprovar_reducao,
    avaliar,
    carregar_config,
    propor_reducao,
)
from src.painel import calibracao_triagem, gerar_simulado, metricas
from src.percepcao import LEITURAS
from src.ui_comum import (
    CONFIG,
    DESTAQUE_LARANJA,
    DESTAQUE_ROXO,
    LOG,
    LOG_SIM,
    estilizar_grafico,
    fila_base,
)


def _aba_visao_geral(m: dict, txt: dict, escuro: bool) -> None:
    niveis, decisoes = txt["niveis"], txt["decisoes"]
    ordem_decisao = [decisoes["aprovou"], decisoes["editou"], decisoes["rejeitou"]]
    ordem_nivel = [niveis["alta"], niveis["media"], niveis["baixa"]]
    escala = alt.Scale(domain=ordem_decisao, range=["#10B981", "#7C3AED", "#F43F5E"])

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown(f"#### {txt['chart_decisions']}")
        df = pd.DataFrame([{"Decisão": decisoes[k], "Chamados": v} for k, v in m["decisoes"].items()])
        grafico = (
            alt.Chart(df).mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("Chamados:Q", title="Chamados"),
                y=alt.Y("Decisão:N", sort=ordem_decisao, title=None),
                color=alt.Color("Decisão:N", scale=escala, legend=None),
                tooltip=["Decisão", "Chamados"],
            )
            .properties(height=180)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
    with dir_, st.container(border=True):
        st.markdown(f"#### {txt['chart_by_urgency']}")
        linhas = [
            {"Urgência": niveis[u], "Decisão": decisoes[d], "Chamados": qtd}
            for u in ("alta", "media", "baixa")
            for d, qtd in m["por_urgencia"][u].items()
        ]
        grafico = (
            alt.Chart(pd.DataFrame(linhas)).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Urgência:N", sort=ordem_nivel, axis=alt.Axis(labelAngle=0), title=None),
                y=alt.Y("Chamados:Q", title="Chamados"),
                color=alt.Color("Decisão:N", scale=escala),
                tooltip=["Urgência", "Decisão", "Chamados"],
            )
            .properties(height=180)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown(f"#### {txt['chart_per_day']}")
        df = pd.DataFrame([{"Dia": k, "Atendimentos": v} for k, v in m["por_dia"].items()])
        grafico = (
            alt.Chart(df).mark_line(point=True, color=DESTAQUE_LARANJA, strokeWidth=2.5)
            .encode(
                x=alt.X("Dia:N", axis=alt.Axis(labelAngle=-25), title=None),
                y=alt.Y("Atendimentos:Q", title="Atendimentos"),
                tooltip=["Dia", "Atendimentos"],
            )
            .properties(height=210)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
    with dir_, st.container(border=True):
        st.markdown(f"#### {txt['chart_readings']}")
        if m["leituras"]:
            df = pd.DataFrame([{"Interpretação": LEITURAS[k], "Vezes": v} for k, v in m["leituras"].items()])
            grafico = (
                alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
                .encode(
                    x=alt.X("Vezes:Q", title="Vezes"),
                    y=alt.Y("Interpretação:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                    tooltip=["Interpretação", "Vezes"],
                )
                .properties(height=210)
            )
            st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
            st.caption(f"{m['leituras_livres']} vez(es) a analista escreveu a própria interpretação.")
        else:
            st.caption("Nenhuma interpretação registrada ainda.")
    st.caption("Poucas decisões = poucos dados: leia estes gráficos como indícios, não como conclusões.")


def _aba_interpretacoes(eventos: list, usar_sim: bool, escuro: bool) -> None:
    config = carregar_config(CONFIG)
    a = avaliar(eventos, config["ativas"])
    st.progress(
        min(1.0, a["respostas"] / MIN_DECISOES),
        text=f"{a['respostas']} de {MIN_DECISOES} respostas necessárias para propor mudanças na lista",
    )
    if a["respostas"]:
        df = pd.DataFrame([{"Interpretação": LEITURAS[k], "Uso": v} for k, v in a["uso"].items()])
        grafico = (
            alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
            .encode(
                x=alt.X("Uso:Q", axis=alt.Axis(format="%"), title="Participação nas respostas"),
                y=alt.Y("Interpretação:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                tooltip=[alt.Tooltip("Interpretação:N"), alt.Tooltip("Uso:Q", format=".1%")],
            )
            .properties(height=220)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
        st.caption(
            f"Interpretação própria escrita pela analista: {a['share_livre']:.0%} "
            f"(acima de {LIMIAR_LIVRE:.0%} a lista não é reduzida). "
            f"Uma interpretação só é proposta para sair se ficar abaixo de {LIMIAR_RARA:.0%}."
        )
    propostas, explicacao = propor_reducao(eventos, config)
    st.info(explicacao)
    for p in propostas:
        st.markdown(f"**Proposta:** retirar “{LEITURAS[p.leitura]}”. {p.motivo}")
        if usar_sim:
            st.button("Aprovar (indisponível com dados simulados)", disabled=True, key="ap_sim")
        elif st.button("Aprovar a retirada (gestor)", key=f"ap_{p.leitura}", type="primary"):
            aprovar_reducao(CONFIG, p.leitura, "Rafael", LOG)
            st.rerun()
    st.caption("Interpretações ativas hoje: " + ", ".join(LEITURAS[k] for k in config["ativas"]))


def _aba_urgencia(eventos: list, txt: dict, escuro: bool) -> None:
    niveis = txt["niveis"]
    ct = calibracao_triagem(eventos)
    if ct["n"] == 0:
        st.info("Ainda não há urgências confirmadas pela analista.")
        return
    k = st.columns(3)
    k[0].metric("Concordância IA × analista", f"{ct['concordancia']:.0%}")
    k[1].metric("Analista achou MAIS urgente", ct["subiu"], help="Erro mais crítico: a IA subestimou.")
    k[2].metric("Analista achou MENOS urgente", ct["desceu"])
    if ct["n"] < MIN_DECISOES:
        st.info(f"Informação insuficiente para concluir: {ct['n']} de {MIN_DECISOES} respostas.")

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown("#### Concordância por confiança da IA")
        linhas = [
            {"Confiança": niveis[n], "Respostas": ct["por_confianca"][n]["n"],
             "Concordou": ct["por_confianca"][n]["concordou"], "Taxa": ct["por_confianca"][n]["taxa"]}
            for n in ("baixa", "media", "alta") if n in ct["por_confianca"]
        ]
        df = pd.DataFrame(linhas)
        if not df.empty:
            grafico = (
                alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=DESTAQUE_LARANJA)
                .encode(
                    x=alt.X("Confiança:N", sort=[niveis["baixa"], niveis["media"], niveis["alta"]],
                            axis=alt.Axis(labelAngle=0), title=None),
                    y=alt.Y("Taxa:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%"), title="Concordância"),
                    tooltip=["Confiança", "Respostas", "Concordou", alt.Tooltip("Taxa:Q", format=".1%")],
                )
                .properties(height=190)
            )
            st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
            tabela = df.copy()
            tabela["Taxa"] = tabela["Taxa"].map(lambda x: f"{x:.1%}")
            st.dataframe(tabela, hide_index=True, width="stretch")
    with dir_, st.container(border=True):
        st.markdown("#### Matriz (IA sugeriu × Analista decidiu)")
        matriz = pd.DataFrame(ct["matriz"]).T
        matriz.index = [niveis[i] for i in matriz.index]
        matriz.columns = [niveis[c] for c in matriz.columns]
        matriz.index.name = "IA sugeriu"
        st.dataframe(matriz, width="stretch")
        st.caption("A analista escolhe a urgência explicitamente (sem pré-seleção) para evitar concordância automática.")


def _expander_auditoria(txt: dict) -> None:
    with st.expander(txt["db_title"], expanded=False):
        st.caption(txt["db_caption"])
        finalizados = {
            cid: tk for cid, tk in repositorio.estado(repositorio.DATASET_FILA).items()
            if tk["status"] == "concluido"
        }
        if not finalizados:
            st.info(txt["db_empty"])
        else:
            rotulos = {
                cid: f"{cid} · {tk['resolvido_por']} · {(tk['resolvido_em'] or '')[:16]}"
                for cid, tk in finalizados.items()
            }
            alvo = st.selectbox(txt["db_reopen_select"], list(rotulos), format_func=rotulos.get, key="db_reopen_alvo")
            if st.button(txt["db_reopen_btn"], key="db_reopen_confirmar"):
                repositorio.reabrir(alvo, "Rafael")
                st.toast(txt["db_reopen_done"])
                st.rerun()
        eventos_db = repositorio.eventos()
        if eventos_db:
            st.caption(txt["db_events"])
            for ev in eventos_db[-5:]:
                st.markdown(f"`{ev['criado_em'][:19]}` · **{ev['chamado_id']}** · {ev['acao']} · {ev['agente']}")


def tela_rafael(provider: str, escuro: bool, txt: dict) -> None:
    st.markdown(f'<span class="hpd-eyebrow">{txt["eyebrow_rafael"]}</span>', unsafe_allow_html=True)
    st.title(txt["title_rafael"])
    st.caption(txt["sub_rafael"])

    col_toggle, col_botao = st.columns([2, 1])
    with col_toggle:
        usar_sim = st.toggle(txt["sim_toggle"], value=not LOG.exists())
    with col_botao:
        if usar_sim and st.button(txt["sim_btn"], width="stretch"):
            gerar_simulado(LOG_SIM, fila_base(provider, os.getenv("GEMINI_MODEL", "")))

    if usar_sim:
        st.warning(txt["sim_warn"])
    eventos = auditoria.ler(LOG_SIM if usar_sim else LOG)

    m = metricas(eventos)
    if m["total"] == 0:
        st.info(txt["no_decisions"])
    else:
        k = st.columns(4)
        k[0].metric(txt["kpi_total"], m["total"])
        k[1].metric(txt["kpi_adapted"], f"{m['taxa_edicao']:.0%}")
        k[2].metric(txt["kpi_own"], f"{m['taxa_rejeicao']:.0%}")
        k[3].metric(txt["kpi_recurrent"], m["recorrentes"])

        aba_geral, aba_interpretacoes, aba_urgencia = st.tabs(
            [txt["tab_overview"], txt["tab_readings"], txt["tab_urgency"]]
        )
        with aba_geral:
            _aba_visao_geral(m, txt, escuro)
        with aba_interpretacoes:
            _aba_interpretacoes(eventos, usar_sim, escuro)
        with aba_urgencia:
            _aba_urgencia(eventos, txt, escuro)

    st.divider()
    _expander_auditoria(txt)

    st.divider()
    with st.expander("Visão futura (desligado no MVP): Portão de Autonomia"):
        st.info(
            "No MVP (v2), todas as decisões permanecem 100% humanas. O módulo `src/autonomia.py` "
            "(portão estatístico Clopper-Pearson) permanece guardado no repositório para fases futuras, "
            "quando houver volume real de chamados e modelos treinados."
        )
