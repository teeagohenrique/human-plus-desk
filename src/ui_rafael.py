"""Gestão e Qualidade (gestor): indicadores, calibração e trilha de auditoria.

Somente leitura sobre as decisões da analista; as únicas ações são aprovar a
redução de interpretações (calibração) e reabrir um chamado, ambas registradas.
"""
import os
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from src import auditoria, repositorio
from src.calibracao import (
    LIMIAR_LIVRE,
    LIMIAR_RARA,
    MIN_ATIVAS,
    MIN_DECISOES,
    aprovar_reducao,
    avaliar,
    carregar_config,
    propor_reducao,
)
from src.painel import calibracao_triagem, gerar_simulado, marcador_reabertura, metricas
from src.tema_dxc import render_card_cascata
from src.ui_comum import (
    CONFIG,
    DESTAQUE_LARANJA,
    DESTAQUE_ROXO,
    LOG,
    LOG_SIM,
    estilizar_grafico,
    fila_base,
    formatar_data_hora,
    traduzir_leitura,
)


def _rotulos_dia(dias_iso: list[str], lang: str) -> tuple[list[str], list[str]]:
    """Formata datas ISO YYYY-MM-DD para eixo horizontal e tooltip."""
    anos = {d[:4] for d in dias_iso if len(d) >= 4}
    incluir_ano = len(anos) > 1
    curtos, completos = [], []
    for d in dias_iso:
        try:
            dt = date.fromisoformat(d)
        except ValueError:
            curtos.append(d)
            completos.append(d)
            continue
        if lang == "EN":
            curtos.append(dt.strftime("%y-%m-%d") if incluir_ano else dt.strftime("%m-%d"))
            completos.append(dt.strftime("%Y-%m-%d"))
        else:
            curtos.append(dt.strftime("%d/%m/%y") if incluir_ano else dt.strftime("%d/%m"))
            completos.append(dt.strftime("%d/%m/%Y"))
    return curtos, completos


def _aba_visao_geral(m: dict, txt: dict, escuro: bool) -> None:
    niveis, decisoes = txt["niveis"], txt["decisoes"]
    lang = txt.get("lang_code", "PT")
    ordem_decisao = [decisoes["aprovou"], decisoes["editou"], decisoes["rejeitou"]]
    ordem_nivel = [niveis["alta"], niveis["media"], niveis["baixa"]]
    escala = alt.Scale(domain=ordem_decisao, range=["#10B981", "#7C3AED", "#F43F5E"])

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown(f"#### {txt['chart_decisions']}")
        df = pd.DataFrame([{"decisao": decisoes[k], "chamados": v} for k, v in m["decisoes"].items()])
        grafico = (
            alt.Chart(df).mark_bar(cornerRadiusEnd=4)
            .encode(
                x=alt.X("chamados:Q", axis=alt.Axis(tickMinStep=1), title=txt["col_tickets"]),
                y=alt.Y("decisao:N", sort=ordem_decisao, title=None),
                color=alt.Color("decisao:N", scale=escala, legend=None),
                tooltip=[
                    alt.Tooltip("decisao:N", title=txt["col_decision"]),
                    alt.Tooltip("chamados:Q", title=txt["col_tickets"]),
                ],
            )
            .properties(height=190)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
    with dir_, st.container(border=True):
        st.markdown(f"#### {txt['chart_by_urgency']}")
        linhas = [
            {"urgencia": niveis[u], "decisao": decisoes[d], "chamados": qtd}
            for u in ("alta", "media", "baixa")
            for d, qtd in m["por_urgencia"][u].items()
        ]
        grafico = (
            alt.Chart(pd.DataFrame(linhas)).mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("chamados:Q", axis=alt.Axis(tickMinStep=1), title=txt["col_tickets"]),
                y=alt.Y("urgencia:N", sort=ordem_nivel, title=None),
                color=alt.Color(
                    "decisao:N",
                    scale=escala,
                    legend=alt.Legend(
                        orient="bottom", title=None, labelLimit=240, labelOverlap="greedy"
                    ),
                ),
                tooltip=[
                    alt.Tooltip("urgencia:N", title=txt["col_urgency"]),
                    alt.Tooltip("decisao:N", title=txt["col_decision"]),
                    alt.Tooltip("chamados:Q", title=txt["col_tickets"]),
                ],
            )
            .properties(height=190)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown(f"#### {txt['chart_per_day']}")
        dias_iso = list(m["por_dia"].keys())
        curtos, completos = _rotulos_dia(dias_iso, lang)
        df = pd.DataFrame([
            {"dia_curto": curto, "dia_completo": completo, "atendimentos": m["por_dia"][iso]}
            for iso, curto, completo in zip(dias_iso, curtos, completos)
        ])
        grafico = (
            alt.Chart(df).mark_line(point=True, color=DESTAQUE_LARANJA, strokeWidth=2.5)
            .encode(
                x=alt.X(
                    "dia_curto:N",
                    sort=curtos,
                    axis=alt.Axis(labelAngle=0, labelOverlap="greedy", labelPadding=6),
                    title=None,
                ),
                y=alt.Y("atendimentos:Q", axis=alt.Axis(tickMinStep=1), title=txt["col_handled"]),
                tooltip=[
                    alt.Tooltip("dia_completo:N", title=txt["col_day"]),
                    alt.Tooltip("atendimentos:Q", title=txt["col_handled"]),
                ],
            )
            .properties(height=210)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
    with dir_, st.container(border=True):
        st.markdown(f"#### {txt['chart_readings']}")
        if m["leituras"]:
            df = pd.DataFrame([
                {"interpretacao": traduzir_leitura(k, txt), "vezes": v}
                for k, v in m["leituras"].items()
            ])
            grafico = (
                alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
                .encode(
                    x=alt.X("vezes:Q", axis=alt.Axis(tickMinStep=1), title=txt["col_times"]),
                    y=alt.Y("interpretacao:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                    tooltip=[
                        alt.Tooltip("interpretacao:N", title=txt["col_reading"]),
                        alt.Tooltip("vezes:Q", title=txt["col_times"]),
                    ],
                )
                .properties(height=210)
            )
            st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
            st.caption(txt["readings_custom_count"].format(n=m["leituras_livres"]))
        else:
            st.caption(txt["readings_none_yet"])
    st.caption(txt["overview_caution"])


def _aba_interpretacoes(eventos: list, usar_sim: bool, txt: dict, escuro: bool) -> None:
    config = carregar_config(CONFIG)
    a = avaliar(eventos, config["ativas"])
    st.progress(
        min(1.0, a["respostas"] / MIN_DECISOES),
        text=txt["cal_progress"].format(respostas=a["respostas"], minimo=MIN_DECISOES),
    )
    if a["respostas"]:
        df = pd.DataFrame([
            {"interpretacao": traduzir_leitura(k, txt), "uso": v}
            for k, v in a["uso"].items()
        ])
        grafico = (
            alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
            .encode(
                x=alt.X("uso:Q", axis=alt.Axis(format="%"), title=txt["cal_share_axis"]),
                y=alt.Y("interpretacao:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                tooltip=[
                    alt.Tooltip("interpretacao:N", title=txt["col_reading"]),
                    alt.Tooltip("uso:Q", format=".1%", title=txt["col_share"]),
                ],
            )
            .properties(height=220)
        )
        st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
        st.caption(
            txt["cal_caption"].format(
                livre=f"{a['share_livre']:.0%}",
                lim_livre=f"{LIMIAR_LIVRE:.0%}",
                lim_rara=f"{LIMIAR_RARA:.0%}",
            )
        )
    propostas, _ = propor_reducao(eventos, config)
    if not a["suficiente"]:
        explicacao_ui = txt["cal_exp_insufficient"].format(
            respostas=a["respostas"], minimo=MIN_DECISOES, faltam=a["faltam"],
        )
    elif a["share_livre"] > LIMIAR_LIVRE:
        explicacao_ui = txt["cal_exp_high_custom"].format(
            share=f"{a['share_livre']:.0%}", lim_livre=f"{LIMIAR_LIVRE:.0%}",
        )
    elif len(config["ativas"]) <= MIN_ATIVAS:
        explicacao_ui = txt["cal_exp_min_active"].format(min_ativas=MIN_ATIVAS)
    elif propostas:
        explicacao_ui = txt["cal_exp_candidate"]
    else:
        explicacao_ui = txt["cal_exp_none"]
    st.info(explicacao_ui)
    for p in propostas:
        motivo_ui = txt["cal_prop_reason"].format(
            uso=f"{a['uso'].get(p.leitura, 0.0):.0%}",
            respostas=a["respostas"],
            lim_rara=f"{LIMIAR_RARA:.0%}",
        )
        st.markdown(txt["cal_proposal_line"].format(leitura=traduzir_leitura(p.leitura, txt), motivo=motivo_ui))
        if usar_sim:
            st.button(txt["cal_approve_sim"], disabled=True, key="ap_sim")
        elif st.button(txt["cal_approve_btn"], key=f"ap_{p.leitura}", type="primary"):
            aprovar_reducao(CONFIG, p.leitura, "Rafael", LOG)
            st.rerun()
    st.caption(txt["cal_active_today"] + ", ".join(traduzir_leitura(k, txt) for k in config["ativas"]))


def _aba_urgencia(eventos: list, txt: dict, escuro: bool) -> None:
    niveis = txt["niveis"]
    ct = calibracao_triagem(eventos)
    if ct["n"] == 0:
        st.info(txt["urg_cal_empty"])
        return
    k = st.columns(3)
    k[0].metric(txt["urg_cal_agree"], f"{ct['concordancia']:.0%}")
    k[1].metric(txt["urg_cal_higher"], ct["subiu"], help=txt["urg_cal_higher_help"])
    k[2].metric(txt["urg_cal_lower"], ct["desceu"])
    if ct["n"] < MIN_DECISOES:
        st.info(txt["urg_cal_insufficient"].format(n=ct["n"], minimo=MIN_DECISOES))

    esq, dir_ = st.columns(2, gap="large")
    with esq, st.container(border=True):
        st.markdown(f"#### {txt['urg_cal_by_conf']}")
        linhas = [
            {
                "confianca": niveis[n],
                "respostas": ct["por_confianca"][n]["n"],
                "concordou": ct["por_confianca"][n]["concordou"],
                "taxa": ct["por_confianca"][n]["taxa"],
            }
            for n in ("baixa", "media", "alta") if n in ct["por_confianca"]
        ]
        df = pd.DataFrame(linhas)
        if not df.empty:
            grafico = (
                alt.Chart(df).mark_bar(cornerRadiusEnd=4, color=DESTAQUE_LARANJA)
                .encode(
                    x=alt.X(
                        "taxa:Q",
                        scale=alt.Scale(domain=[0, 1]),
                        axis=alt.Axis(format="%"),
                        title=txt["urg_cal_axis"],
                    ),
                    y=alt.Y(
                        "confianca:N",
                        sort=[niveis["alta"], niveis["media"], niveis["baixa"]],
                        title=None,
                    ),
                    tooltip=[
                        alt.Tooltip("confianca:N", title=txt["confidence"]),
                        alt.Tooltip("respostas:Q", title=txt["col_responses"]),
                        alt.Tooltip("concordou:Q", title=txt["col_agreed"]),
                        alt.Tooltip("taxa:Q", format=".1%", title=txt["urg_cal_axis"]),
                    ],
                )
                .properties(height=190)
            )
            st.altair_chart(estilizar_grafico(grafico, escuro), width="stretch")
            tabela = pd.DataFrame([
                {
                    txt["confidence"]: r["confianca"],
                    txt["col_responses"]: r["respostas"],
                    txt["col_agreed"]: r["concordou"],
                    txt["col_rate"]: f"{r['taxa']:.1%}",
                }
                for r in linhas
            ])
            st.table(tabela, hide_index=True, width="stretch")
    with dir_, st.container(border=True):
        st.markdown(f"#### {txt['urg_cal_matrix_title']}")
        matriz = pd.DataFrame(ct["matriz"]).T
        matriz.index = [niveis[i] for i in matriz.index]
        matriz.columns = [niveis[c] for c in matriz.columns]
        matriz.index.name = txt["urg_cal_matrix_index"]
        st.table(matriz, width="stretch")
        st.caption(txt["urg_cal_caption"])


def _expander_auditoria(txt: dict) -> None:
    lang = txt.get("lang_code", "PT")
    acoes = txt.get("acoes", {})
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
                cid: f"{cid} · {tk['resolvido_por']} · {formatar_data_hora(tk.get('resolvido_em'), lang=lang)}"
                for cid, tk in finalizados.items()
            }
            alvo = st.selectbox(txt["db_reopen_select"], list(rotulos), format_func=rotulos.get, key="db_reopen_alvo")
            if st.button(txt["db_reopen_btn"], key="db_reopen_confirmar"):
                repositorio.reabrir(alvo, "Rafael")
                st.toast(txt["db_reopen_done"])
                st.rerun()
        eventos_db = repositorio.eventos()
        if eventos_db:
            itens_ev_db = [
                {
                    "titulo": f"{ev['chamado_id']} · {acoes.get(ev['acao'], ev['acao'])}",
                    "badge": ev["agente"],
                    "detalhe": formatar_data_hora(ev["criado_em"], lang=lang),
                }
                for ev in reversed(eventos_db[-10:])
            ]
            render_card_cascata(
                txt["db_events"],
                itens_ev_db,
                chave_unica="rafael_auditoria_eventos",
                envolver_card=False,
            )


def _marcadores_reabertura() -> list[dict]:
    """Reaberturas do SQLite no formato de evento analítico do painel.

    O Rafael registra a reabertura só no banco; o JSONL fica com as duas
    decisões. Os marcadores delimitam qual decisão é a vigente sem apagar
    nada da trilha e sem exigir migração dos dados já registrados.
    """
    return [
        marcador_reabertura(ev["chamado_id"], ev["criado_em"])
        for ev in repositorio.eventos()
        if ev["acao"] == "reabriu"
    ]


def tela_rafael(provider: str, escuro: bool, txt: dict) -> None:
    st.markdown(f'<span class="hpd-eyebrow">{txt["eyebrow_rafael"]}</span>', unsafe_allow_html=True)
    st.title(txt["title_rafael"])
    st.caption(txt["sub_rafael"])

    col_toggle, col_botao = st.columns([2, 1])
    with col_toggle:
        usar_sim = st.toggle(txt["sim_toggle"], value=not LOG.exists(), key="sim_toggle_ui")
    with col_botao:
        if usar_sim and st.button(txt["sim_btn"], width="stretch"):
            gerar_simulado(LOG_SIM, fila_base(provider, os.getenv("GEMINI_MODEL", ""), txt=txt))

    if usar_sim:
        st.warning(txt["sim_warn"])
    eventos = auditoria.ler(LOG_SIM if usar_sim else LOG)
    if not usar_sim:
        eventos = eventos + _marcadores_reabertura()

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
            _aba_interpretacoes(eventos, usar_sim, txt, escuro)
        with aba_urgencia:
            _aba_urgencia(eventos, txt, escuro)

    st.divider()
    _expander_auditoria(txt)

    st.divider()
    with st.expander(txt["autonomy_title"]):
        st.info(txt["autonomy_info"])
