"""Central de Atendimento (analista): fila, análise, decisão e resposta ao cliente.

Fluxo em três etapas por chamado:
  1. Análise  - texto mascarado, trechos-chave e Análise Contextual (hipóteses de apoio);
  2. Decisão  - interpretação do caso (com os trechos que a sustentam) e urgência real;
  3. Resposta - sugestão OARS (referência), registro de supervisão (somente leitura)
                e a resposta ao cliente, escrita pela analista.

A IA só sugere. Nada é enviado: a decisão e a resposta ficam registradas na auditoria.
"""
import html
import os

import streamlit as st

from src import auditoria, repositorio
from src.calibracao import carregar_config
from src.painel import (
    classificar_resposta,
    detalhes_supervisao,
    leituras_do_item,
    rascunho_adaptado,
    registrar_decisao,
)
from src.percepcao import LEITURAS, trechos_da_leitura
from src.redator import _PLACEHOLDER
from src.ui_comum import CONFIG, COR, LOG, fila_base, formatar_data_hora, nome_sinal

LEITURA_PROPRIA = "__propria__"
VISOES = ("fila", "critica", "finalizados")


# ---------------------------------------------------------------- estado e callbacks

def _ir_para_etapa(item_id: str, destino: str) -> None:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id in estados:
        estados[item_id]["viu_chamado"] = True
        estados[item_id]["camada"] = destino
    st.session_state[f"camada_{item_id}"] = destino


def _registrar_urgencia_ui(item_id: str, agente: str) -> None:
    """Grava a urgência escolhida, com agente e horário, assim que ela é marcada."""
    urgencia = st.session_state.get(f"urg_ui_{item_id}")
    if urgencia:
        repositorio.registrar_urgencia(item_id, urgencia, agente)


def _selecionar_indicador(visao: str, quantidade: int) -> None:
    """Abre/fecha a visão do indicador e marca como visto (interrompe o pulso)."""
    st.session_state.setdefault("kpi_vistos", {})[visao] = quantidade
    st.session_state["visao_marina"] = None if st.session_state.get("visao_marina") == visao else visao


def _usar_sugestao(chave_sugestao: str, chave_resposta: str) -> None:
    """Leva a sugestão para a resposta ao cliente sem apagar o que já foi escrito."""
    sugestao = st.session_state.get(chave_sugestao, "")
    atual = st.session_state.get(chave_resposta, "")
    st.session_state[chave_resposta] = f"{atual.rstrip()}\n\n{sugestao}".strip() if atual.strip() else sugestao


def _estado_item(item) -> dict:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item.id not in estados:
        opcoes = leituras_do_item(item, auditoria.ler(LOG), carregar_config(CONFIG))
        estados[item.id] = {
            "camada": "chamado",
            "viu_chamado": False,
            "leitura": opcoes[0] if opcoes else None,
            "leitura_livre": "",
            "urgencia": None,
            "resposta": "",
        }
        st.session_state.setdefault(f"camada_{item.id}", "chamado")
    return estados[item.id]


def _leitura_para_registro(estado: dict) -> tuple[str | None, str | None]:
    """(interpretação padronizada, interpretação livre) como serão gravadas."""
    if estado["leitura"] == LEITURA_PROPRIA:
        return None, estado["leitura_livre"] or None
    return estado["leitura"], None


# ---------------------------------------------------------------- indicadores

def _render_indicadores(txt: dict, total: int, qtd_fila: int, qtd_critica: int, qtd_final: int) -> str | None:
    """Três blocos clicáveis; o que tem novidade pulsa suavemente até ser aberto."""
    visao = st.session_state.get("visao_marina")
    if visao not in VISOES:
        visao = None
    vistos = st.session_state.setdefault("kpi_vistos", {})
    pct = round(qtd_final / total * 100) if total else 0

    blocos = (
        ("fila", txt["kpi_pending"], qtd_fila, str(qtd_fila),
         txt["kpi_of_queue"].format(n=total), "btn_open_queue", "btn_hide_queue"),
        ("critica", txt["kpi_high"], qtd_critica, str(qtd_critica),
         txt["kpi_priority"], "btn_open_critical", "btn_hide_critical"),
        ("finalizados", txt["kpi_done"], qtd_final, f"{pct}%",
         txt["kpi_registered"].format(n=qtd_final), "btn_open_resolved", "btn_hide_resolved"),
    )

    coluna_titulo, *colunas = st.columns([2.0, 1.05, 1.05, 1.05], gap="medium")
    with coluna_titulo:
        st.markdown(f'<span class="hpd-eyebrow">{txt["eyebrow_marina"]}</span>', unsafe_allow_html=True)
        st.title(txt["title_marina"])

    for coluna, (chave, rotulo, qtd, valor, sub, abrir, ocultar) in zip(colunas, blocos):
        pulsa = qtd > 0 and vistos.get(chave) != qtd
        classes = "bento-kpi" + (" pulse-alert" if pulsa else "") + (" kpi-selected" if visao == chave else "")
        ponto = '<span class="kpi-dot-new"></span>' if pulsa else ""
        with coluna:
            st.markdown(
                f'<div class="{classes}"><div class="bento-kpi-label">{rotulo}{ponto}</div>'
                f'<div class="bento-kpi-val">{valor}</div>'
                f'<div class="bento-kpi-sub">{sub}</div></div>',
                unsafe_allow_html=True,
            )
            st.button(
                txt[ocultar] if visao == chave else txt[abrir],
                key=f"btn_kpi_{chave}", width="stretch",
                on_click=_selecionar_indicador, args=(chave, qtd),
            )
    return visao


# ---------------------------------------------------------------- blocos reutilizáveis

def _render_supervisao(txt: dict, d: dict) -> None:
    """Registro de supervisão (somente leitura): o que foi apresentado e como foi decidido.

    Recebe o mesmo pacote gravado por `detalhes_supervisao`; campos ausentes em
    registros antigos são tratados sem erro.
    """
    niveis = txt["niveis"]
    st.markdown(f"**{txt['sup_analysis']}**")
    hipoteses = d.get("hipoteses") or []
    if hipoteses:
        for h in hipoteses:
            st.markdown(f"- {h['hipotese']} *({niveis.get(h['confianca'], h['confianca'])})*")
            for e in h.get("evidencias", []):
                st.caption(f"{nome_sinal(e['sinal'], txt)}: “{e['trecho']}”")
    else:
        st.caption(txt["sup_no_hyp"])

    st.markdown(f"**{txt['sup_reading']}**")
    if d.get("leitura"):
        st.markdown(LEITURAS.get(d["leitura"], d["leitura"]))
    elif d.get("leitura_livre"):
        st.markdown(f"✎ {d['leitura_livre']}")
    else:
        st.caption(txt["sup_reading_none"])

    ia = niveis.get(d.get("urgencia_ia"), "—")
    humano = d.get("urgencia_analista")
    if humano:
        st.markdown(txt["sup_urgency"].format(ia=ia, humano=niveis.get(humano, humano)))
    else:
        st.markdown(txt["sup_urgency_pending"].format(ia=ia))


# ---------------------------------------------------------------- finalizados

def _render_finalizados(itens: list, estado_db: dict, txt: dict) -> None:
    """Chamados finalizados: como a mensagem chegou ao cliente, com data, hora e supervisão."""
    niveis, intencoes, decisoes = txt["niveis"], txt["intencoes"], txt["decisoes"]
    por_id = {i.id: i for i in itens}
    ids = [
        cid for cid, tk in sorted(estado_db.items(), key=lambda par: par[1].get("resolvido_em") or "", reverse=True)
        if tk.get("status") == "concluido"
    ]
    if not ids:
        st.info(txt["fin_empty"])
        return

    esquerda, direita = st.columns([1.0, 2.3], gap="large")
    with esquerda, st.container(border=True, key="fila_bento_card"):
        st.markdown(f"##### {txt['kpi_done']} ({len(ids)})")
        ativo = st.session_state.get("chamado_concluido_ativo")
        if ativo not in ids:
            ativo = ids[0]
        rotulos = {}
        for cid in ids:
            ref = por_id.get(cid)
            categoria = intencoes.get(ref.triagem.intencao, ref.triagem.intencao) if ref else "—"
            rotulos[cid] = f"{'→  ' if cid == ativo else ''}✓ {cid} · {categoria}"
        escolhido = st.radio(
            txt["kpi_done"], ids, format_func=rotulos.get,
            label_visibility="collapsed", key="chamado_concluido_ativo",
        )

    tk = estado_db.get(escolhido, {})
    ref = por_id.get(escolhido)
    decisao_evento = next(
        (e for e in reversed(repositorio.eventos(chamado_id=escolhido)) if e["acao"] == "decisao"), None
    )
    d = (decisao_evento or {}).get("detalhes", {})
    quando = formatar_data_hora(tk.get("resolvido_em"))
    urgencia = tk.get("urgencia_confirmada") or d.get("urgencia_analista") or (ref.triagem.urgencia if ref else "baixa")
    decisao = decisoes.get(d.get("decisao"), "—")
    categoria = intencoes.get(ref.triagem.intencao, ref.triagem.intencao) if ref else "—"

    with direita:
        st.markdown(f"#### `{escolhido}` · {categoria} &nbsp;·&nbsp; ✓ **{txt['kpi_done']}**")
        st.caption(txt["fin_meta"].format(
            quando=quando, analista=tk.get("resolvido_por") or "—",
            urgencia=f"{COR.get(urgencia, '')} {niveis.get(urgencia, urgencia)}", decisao=decisao,
        ))

        with st.container(border=True, key="caixa_resposta"):
            st.markdown(f"**{txt['fin_delivered']}**")
            st.caption(f"{txt['fin_logged']}: **{quando}**")
            if tk.get("resposta_final"):
                st.markdown(f'<div class="msg-sent-box">{html.escape(tk["resposta_final"])}</div>', unsafe_allow_html=True)
            else:
                st.info(txt["fin_no_reply"])

        with st.container(border=True):
            st.markdown(f'<span class="hpd-eyebrow">{txt["lgpd_badge"]}</span>', unsafe_allow_html=True)
            st.markdown(f"**{txt['fin_customer_msg']}**")
            st.markdown(f"> {tk.get('texto_mascarado') or '—'}")

        if d:
            with st.container(border=True):
                st.markdown(f"**{txt['box_supervision']}**")
                _render_supervisao(txt, d)
                if d.get("rascunho_ia"):
                    with st.expander(txt["fin_suggestion_ia"]):
                        st.write(d["rascunho_ia"])


# ---------------------------------------------------------------- fila

def _render_fila(base: list, visao: str, txt: dict, urgencia_efetiva):
    """Coluna da fila. Devolve o chamado selecionado, ou None se não houver itens."""
    niveis, intencoes = txt["niveis"], txt["intencoes"]
    with st.container(border=True, key="fila_bento_card"):
        titulo = txt["kpi_high"] if visao == "critica" else txt["kpi_pending"]
        st.markdown(f"##### {txt['queue']} · {titulo}")
        fila = base
        if visao == "fila":
            filtro = st.pills(
                "Filtrar", options=["todas", "alta", "media", "baixa"], default="todas",
                format_func=lambda k: txt["all"] if k == "todas" else f"{COR[k]} {niveis[k]}",
                label_visibility="collapsed", key="filtro_urgencia",
            )
            if filtro not in (None, "todas"):
                fila = [i for i in base if urgencia_efetiva(i) == filtro]
        if not fila:
            st.info(txt["empty_filter"])
            return None
        ativo = st.session_state.get("chamado_ativo_fila")
        if ativo not in [i.id for i in fila]:
            ativo = fila[0].id
        rotulos = {
            i.id: f"{'→  ' if i.id == ativo else ''}{COR[urgencia_efetiva(i)]} {i.id} · "
                  f"{intencoes.get(i.triagem.intencao, i.triagem.intencao)}"
            for i in fila
        }
        escolhido = st.radio(
            txt["queue"], list(rotulos), format_func=rotulos.get,
            label_visibility="collapsed", key="chamado_ativo_fila",
        )
    return next(i for i in fila if i.id == escolhido)


# ---------------------------------------------------------------- etapas

def _etapa_analise(item, txt: dict) -> None:
    t, niveis = item.triagem, txt["niveis"]
    with st.container(border=True):
        st.markdown(f'<span class="hpd-eyebrow">{txt["lgpd_badge"]}</span>', unsafe_allow_html=True)
        st.markdown(f"> {item.texto_mascarado}")

    col_trechos, col_analise = st.columns(2, gap="medium")
    with col_trechos, st.container(border=True):
        st.markdown(f"**{txt['evidences']}**")
        motivos = t.motivos_urgencia + t.motivos_intencao
        if motivos:
            for m in motivos:
                st.markdown(f"- **{nome_sinal(m.sinal, txt)}:** “{m.trecho}”")
        else:
            st.caption(txt["no_evidences"])
    with col_analise, st.container(border=True):
        qtd = len(item.palpites)
        st.markdown(f"**{txt['perception']} ({qtd} {txt['hyp_one'] if qtd == 1 else txt['hyp_many']})**")
        if not item.palpites:
            st.caption(txt["no_guesses"])
        for p in item.palpites:
            st.markdown(f"- {p.hipotese} *({niveis.get(p.confianca, p.confianca)})*")
            st.caption(f"{txt['confirm_q']} {p.pergunta_confirmacao}")
            if p.sugere_subir_urgencia:
                st.warning(txt["raise_warn"])

    with st.container(key="cta_step_1"):
        st.button(txt["go_2"], type="primary", width="stretch", key=f"go2_{item.id}",
                  on_click=_ir_para_etapa, args=(item.id, "decisao"))


def _etapa_decisao(item, estado: dict, txt: dict, agente: str) -> None:
    t, niveis = item.triagem, txt["niveis"]
    with st.container(border=True):
        opcoes = leituras_do_item(item, auditoria.ler(LOG), carregar_config(CONFIG)) + [LEITURA_PROPRIA]
        leitura = st.pills(
            txt["reading_lbl"], options=opcoes,
            default=estado["leitura"] if estado["leitura"] in opcoes else None,
            format_func=lambda k: txt["reading_custom"] if k == LEITURA_PROPRIA else LEITURAS.get(k, k),
            key=f"leit_ui_{item.id}",
        )
        estado["leitura"] = leitura
        if leitura == LEITURA_PROPRIA:
            estado["leitura_livre"] = st.text_input(
                txt["free_reading"], value=estado["leitura_livre"], key=f"livre_ui_{item.id}",
            )
        elif leitura:
            st.markdown(f"**{txt['reading_evidence_title']}**")
            trechos = trechos_da_leitura(leitura, t, item.palpites)
            if trechos:
                for m in trechos:
                    st.markdown(f"- **{nome_sinal(m.sinal, txt)}:** “{m.trecho}”")
            else:
                st.caption(txt["reading_no_evidence"])

        estado["urgencia"] = st.pills(
            txt["urg_lbl"].format(sug=niveis[t.urgencia]),
            options=["alta", "media", "baixa"], default=estado["urgencia"],
            format_func=lambda k: f"{COR[k]} {niveis[k]}",
            key=f"urg_ui_{item.id}", on_change=_registrar_urgencia_ui, args=(item.id, agente),
        )
        if estado["urgencia"] is None:
            st.info(txt["urg_hint"])

        voltar, avancar = st.columns(2)
        voltar.button(txt["back_1"], width="stretch", key=f"back1_{item.id}",
                      on_click=_ir_para_etapa, args=(item.id, "chamado"))
        with avancar, st.container(key="cta_step_2"):
            st.button(txt["go_3"], type="primary", width="stretch", key=f"go3_{item.id}",
                      on_click=_ir_para_etapa, args=(item.id, "resposta"))


def _etapa_resposta(item, estado: dict, txt: dict, agente: str, provider: str) -> None:
    leitura_registro, leitura_livre = _leitura_para_registro(estado)
    st.session_state.setdefault("cache_rascunhos", {})
    rascunho, origem = rascunho_adaptado(
        item, leitura_registro, provider, os.getenv("GEMINI_MODEL", ""), st.session_state["cache_rascunhos"],
    )
    chave_sugestao = f"sug_ui_{item.id}_{leitura_registro or 'base'}"
    chave_resposta = f"resp_ui_{item.id}"
    # Valores iniciais definidos antes de criar os campos (sem `value=`, para a
    # sugestão poder ser copiada por callback sem conflito de estado).
    st.session_state.setdefault(chave_sugestao, rascunho.texto)
    st.session_state.setdefault(chave_resposta, estado["resposta"])

    col_sugestao, col_supervisao = st.columns(2, gap="medium")
    with col_sugestao, st.container(border=True):
        st.markdown(f"**{txt['box_suggestion']}**")
        st.caption(f"{txt['box_suggestion_hint']} · {txt['origens'].get(origem, origem)}")
        st.text_area(txt["box_suggestion"], key=chave_sugestao, height=230, label_visibility="collapsed")
        st.button(txt["btn_use_suggestion"], key=f"usar_{item.id}", width="stretch",
                  on_click=_usar_sugestao, args=(chave_sugestao, chave_resposta))
    pacote = detalhes_supervisao(item, leitura_registro, leitura_livre, estado["urgencia"], rascunho.texto, origem)
    with col_supervisao, st.container(border=True):
        st.markdown(f"**{txt['box_supervision']}**")
        st.caption(txt["box_supervision_hint"])
        _render_supervisao(txt, pacote)

    with st.container(border=True, key="caixa_resposta"):
        st.markdown(f"**{txt['box_reply']}**")
        st.caption(txt["box_reply_hint"])
        resposta = st.text_area(
            txt["box_reply"], key=chave_resposta, height=220,
            placeholder=txt["reply_placeholder"], label_visibility="collapsed",
        )
        estado["resposta"] = resposta

        marcadores = _PLACEHOLDER.findall(resposta)
        corpo = _PLACEHOLDER.sub("", resposta).strip()
        faltas = []
        if estado["urgencia"] is None:
            faltas.append(txt["need_urg"])
        if not corpo:
            faltas.append(txt["need_reply"])
        if marcadores:
            faltas.append(txt["need_brack"] + "; ".join(marcadores))
        if faltas:
            st.warning(txt["pending_banner"] + " | ".join(faltas) + ".")
        else:
            st.success(txt["ready_banner"])

        if st.button(txt["btn_register"], type="primary", width="stretch", key=f"ok_{item.id}", disabled=bool(faltas)):
            decisao = classificar_resposta(rascunho.texto, resposta)
            registrar_decisao(
                LOG, item, decisao, resposta, leitura_registro, leitura_livre, estado["urgencia"], False,
                origem_triagem=item.origem_triagem, origem_rascunho=origem,
            )
            repositorio.registrar_decisao(item.id, decisao, resposta, agente, detalhes=pacote)
            st.session_state["estado_chamados"].pop(item.id, None)
            st.toast(txt["toast_registered"].format(id=item.id))
            st.rerun()


# ---------------------------------------------------------------- tela

def tela_marina(provider: str, txt: dict, agente: str = "Marina") -> None:
    itens = fila_base(provider, os.getenv("GEMINI_MODEL", ""))
    estado_db = repositorio.estado(repositorio.DATASET_FILA)
    feitos = repositorio.ids_concluidos(repositorio.DATASET_FILA)
    fila_completa = [i for i in itens if i.id not in feitos]

    def urgencia_efetiva(item) -> str:
        """Urgência confirmada pela analista prevalece sobre a sugestão da IA."""
        return estado_db.get(item.id, {}).get("urgencia_confirmada") or item.triagem.urgencia

    fila_critica = [i for i in fila_completa if urgencia_efetiva(i) == "alta"]
    visao = _render_indicadores(txt, len(itens), len(fila_completa), len(fila_critica), len(feitos))

    if visao is None:
        with st.container(border=True):
            st.markdown(txt["welcome_md"])
        return
    if visao == "finalizados":
        _render_finalizados(itens, estado_db, txt)
        return

    base = fila_critica if visao == "critica" else fila_completa
    if not base:
        st.success(txt["queue_done"] if visao == "fila" else txt["empty_filter"])
        return

    esquerda, direita = st.columns([1.0, 2.3], gap="large")
    with esquerda:
        item = _render_fila(base, visao, txt, urgencia_efetiva)
    if item is None:
        return

    t, niveis, intencoes = item.triagem, txt["niveis"], txt["intencoes"]
    estado = _estado_item(item)
    # Valores dos campos já atualizados nesta execução (os campos só existem na etapa ativa).
    urgencia = st.session_state.get(f"urg_ui_{item.id}", estado["urgencia"])
    resposta = st.session_state.get(f"resp_ui_{item.id}", estado["resposta"])
    pronta = urgencia is not None and bool(_PLACEHOLDER.sub("", resposta or "").strip()) and not _PLACEHOLDER.search(resposta or "")
    alerta = any(p.sugere_subir_urgencia for p in item.palpites)

    etapas = {
        "chamado": ("✓" if estado["viu_chamado"] else ("!" if alerta else "●"), txt["layer_1"]),
        "decisao": ("✓" if urgencia is not None else "●", txt["layer_2"]),
        "resposta": ("✓" if pronta else "●", txt["layer_3"]),
    }
    chips = (
        ("done", txt["chip_1_done"]) if estado["viu_chamado"]
        else (("alert", txt["chip_1_alert"]) if alerta else ("pending", txt["chip_1_pend"])),
        ("done", txt["chip_2_done"]) if urgencia is not None else ("pending", txt["chip_2_pend"]),
        ("done", txt["chip_3_done"]) if pronta else ("pending", txt["chip_3_pend"]),
    )

    with direita:
        st.markdown(
            f"#### `{item.id}` · {intencoes.get(t.intencao, t.intencao)}  "
            f"&nbsp;·&nbsp; {COR[t.urgencia]} **{niveis[t.urgencia]}** ({t.pontuacao_urgencia} pts)"
        )
        st.caption(
            f"{txt['triage']}: **{txt['origens'].get(item.origem_triagem, item.origem_triagem)}** · "
            f"{txt['confidence']}: **{niveis.get(t.confianca, t.confianca)}**"
        )
        st.markdown(
            '<div class="layer-strip">'
            + "".join(
                f'<span class="layer-chip {estilo}"><span class="dot dot-{estilo}"></span>{rotulo}</span>'
                for estilo, rotulo in chips
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        escolhida = st.segmented_control(
            "Etapas", options=list(etapas), format_func=lambda k: f"{etapas[k][1]} {etapas[k][0]}",
            label_visibility="collapsed", key=f"camada_{item.id}",
        )
        if escolhida is not None:
            estado["camada"] = escolhida

        if estado["camada"] == "chamado":
            _etapa_analise(item, txt)
        elif estado["camada"] == "decisao":
            estado["viu_chamado"] = True
            _etapa_decisao(item, estado, txt, agente)
        else:
            estado["viu_chamado"] = True
            _etapa_resposta(item, estado, txt, agente, provider)
