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

from src import acervo, auditoria, repositorio
from src.calibracao import carregar_config
from src.painel import (
    classificar_resposta,
    detalhes_supervisao,
    leituras_do_item,
    payload_decisao,
    rascunho_adaptado,
)
from src.percepcao import trechos_da_leitura
from src.redator import (
    _PLACEHOLDER,
    PEND_PRAZO,
    PEND_PRAZO_EN,
    formatar_sugestao_acervo,
    pendencias_abertas,
)
from src.tema_dxc import render_card_cascata
from src.ui_comum import (
    CONFIG,
    COR,
    LOG,
    fila_base,
    formatar_data_hora,
    linha_acervo,
    nome_sinal,
    topico_do_item,
    traduzir_hipotese_salva,
    traduzir_leitura,
    traduzir_palpite,
)

LEITURA_PROPRIA = "__propria__"
VISOES = ("fila", "critica", "finalizados")


# ---------------------------------------------------------------- estado e callbacks

def _ir_para_etapa(item_id: str, destino: str) -> None:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id in estados:
        estados[item_id]["viu_chamado"] = True
        estados[item_id]["camada"] = destino
        estados[item_id]["aba_acervo_aberta"] = False
    st.session_state[f"camada_{item_id}"] = destino


def _ao_trocar_camada(item_id: str) -> None:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id in estados:
        estados[item_id]["aba_acervo_aberta"] = False


def _aplicar_acervo_na_sugestao(
    item,
    estado: dict,
    topico: acervo.Topico,
    solucao_override: str | None = None,
    prazo_override: str | None = None,
) -> str:
    """Injeta a solução provisória (e o prazo simulado, se clicado) na sugestão OARS."""
    idioma = str(st.session_state.get("lang", "PT"))
    solucao = (
        solucao_override
        if solucao_override is not None
        else (estado.get("solucao_simulada") or acervo.texto_topico(topico, "solucao_provisoria", idioma))
    )
    texto_estruturado = str(
        formatar_sugestao_acervo(
            item.triagem, solucao, idioma=idioma, chamado_mascarado=item.texto_mascarado
        )
    )
    prazo_efetivo = prazo_override if prazo_override is not None else estado.get(f"prazo_sim_{item.id}")
    if prazo_efetivo:
        texto_estruturado = texto_estruturado.replace(PEND_PRAZO, f"[{prazo_efetivo}]").replace(
            PEND_PRAZO_EN, f"[{prazo_efetivo}]"
        )
    estado["acervo_topico_id"] = topico.id
    estado["sugestao_acervo"] = texto_estruturado
    leitura_reg, _ = _leitura_para_registro(estado)
    for sufixo in {leitura_reg or "base", "base"}:
        st.session_state[f"sug_ui_{item.id}_{sufixo}"] = texto_estruturado
    return texto_estruturado


def _abrir_acervo(item, origem: str) -> None:
    """Abre a aba do Acervo a partir da Análise Contextual ou do Registro e atualiza a sugestão OARS."""
    estado = _estado_item(item)
    topico, _ = topico_do_item(item)
    estado["viu_chamado"] = True
    estado["camada_origem_acervo"] = origem
    estado["aba_acervo_aberta"] = True
    if topico is not None:
        _aplicar_acervo_na_sugestao(item, estado, topico)


def _voltar_do_acervo(item_id: str) -> None:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id in estados:
        origem = estados[item_id].get("camada_origem_acervo") or "chamado"
        estados[item_id]["aba_acervo_aberta"] = False
        estados[item_id]["camada"] = origem
        st.session_state[f"camada_{item_id}"] = origem


def _ir_para_resposta_do_acervo(item) -> None:
    estado = _estado_item(item)
    topico, _ = topico_do_item(item)
    if topico is not None:
        _aplicar_acervo_na_sugestao(item, estado, topico)
    _ir_para_etapa(item.id, "resposta")


def _registrar_urgencia_ui(item_id: str, agente: str) -> None:
    """Grava a urgência escolhida, com agente e horário, assim que ela é marcada."""
    urgencia = st.session_state.get(f"urg_ui_{item_id}")
    if urgencia:
        repositorio.registrar_urgencia(item_id, urgencia, agente)


def _selecionar_indicador(visao: str, quantidade: int) -> None:
    """Abre/fecha a visão do indicador e marca como visto (interrompe o pulso)."""
    st.session_state.setdefault("kpi_vistos", {})[visao] = quantidade
    st.session_state["visao_marina"] = None if st.session_state.get("visao_marina") == visao else visao


def _usar_sugestao(chave_sugestao: str, chave_resposta: str, item_id: str | None = None) -> None:
    """Leva a sugestão para a resposta ao cliente e sinaliza o botão como ativo."""
    sugestao = st.session_state.get(chave_sugestao, "")
    atual = st.session_state.get(chave_resposta, "")
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id and item_id in estados:
        estados[item_id]["usou_sugestao"] = True
        if estados[item_id].get("acervo_topico_id"):
            st.session_state[chave_resposta] = sugestao
            estados[item_id]["resposta"] = sugestao
            return
    novo = f"{atual.rstrip()}\n\n{sugestao}".strip() if atual.strip() else sugestao
    st.session_state[chave_resposta] = novo
    if item_id and item_id in estados:
        estados[item_id]["resposta"] = novo


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
            "aba_acervo_aberta": False,
            "camada_origem_acervo": "chamado",
            "acervo_topico_id": None,
            "sugestao_acervo": None,
            "usou_sugestao": False,
            "cenario_tempo_idx": 0,
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

def _render_supervisao(
    txt: dict,
    d: dict,
    chave_unica: str,
    subtitulo: str | None = None,
    item=None,
    origem: str | None = None,
) -> None:
    """Registro de supervisão (somente leitura) com exibição em cascata.

    Recebe o mesmo pacote gravado por `detalhes_supervisao`; campos ausentes em
    registros antigos são tratados sem erro.
    """
    niveis = txt["niveis"]
    ia = niveis.get(d.get("urgencia_ia"), "—")
    humano = d.get("urgencia_analista")
    if d.get("leitura"):
        leitura_desc = traduzir_leitura(d["leitura"], txt)
    elif d.get("leitura_livre"):
        leitura_desc = f"✎ {d['leitura_livre']}"
    else:
        leitura_desc = txt["sup_reading_none"]

    titulo_urg = (
        txt["sup_urg_set"].format(ia=ia, humano=niveis.get(humano, humano))
        if humano
        else txt["sup_urg_pending"].format(ia=ia)
    )
    itens_sup = [
        {
            "titulo": titulo_urg,
            "badge": txt["triage"],
            "detalhe": f"{txt['sup_reading']}: {leitura_desc}",
        }
    ]
    for indice, h in enumerate(d.get("hipoteses") or []):
        ev_texto = " | ".join(
            f"{nome_sinal(e['sinal'], txt)}: “{e['trecho']}”"
            for e in h.get("evidencias", [])
        )
        extra = linha_acervo(h.get("acervo_topico_id"), h.get("acervo_palavras"), txt)
        if extra:
            ev_texto = f"{ev_texto} | {extra}" if ev_texto else extra
        itens_sup.append(
            {
                "titulo": traduzir_hipotese_salva(h["hipotese"], len(h.get("evidencias", [])), txt),
                "badge": niveis.get(h["confianca"], h["confianca"]),
                "detalhe": ev_texto,
            }
        )
        # Botão "Consultar solução do Acervo" dentro da caixa, junto à hipótese.
        if item is not None and origem:
            itens_sup.append(
                {
                    "titulo": txt["acervo_open_btn_sup"],
                    "badge": "",
                    "detalhe": "",
                    "button": {
                        "label": txt["acervo_open_btn_sup"],
                        "key": f"abrir_acerto_sup_{item.id}_{indice}",
                        "on_click": _abrir_acervo,
                        "args": (item, origem),
                    },
                }
            )

    render_card_cascata(
        txt["box_supervision"],
        itens_sup,
        chave_unica=chave_unica,
        vazio=txt["sup_no_hyp"],
        subtitulo=subtitulo,
    )


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

    esquerda, direita = st.columns([1.0, 2.1], gap="large")
    with esquerda, st.container(border=True, key="fila_bento_card"):
        st.markdown(f"##### {txt['kpi_done']} ({len(ids)})")
        ativo = st.session_state.get("chamado_concluido_ativo")
        if ativo not in ids:
            ativo = ids[0]
        # Reatribuição explícita força set_value=True no frontend (bolinha sempre marcada).
        st.session_state["chamado_concluido_ativo"] = ativo
        rotulos = {}
        for cid in ids:
            ref = por_id.get(cid)
            categoria = intencoes.get(ref.triagem.intencao, ref.triagem.intencao) if ref else "—"
            rotulos[cid] = f"✓ {cid} · {categoria}"
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
    quando = formatar_data_hora(tk.get("resolvido_em"), lang=txt.get("lang_code", "PT"))
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
            resposta_exibida = tk.get("resposta_final") or d.get("resposta_anterior")
            if resposta_exibida:
                st.markdown(f'<div class="msg-sent-box">{html.escape(resposta_exibida)}</div>', unsafe_allow_html=True)
            else:
                st.info(txt["fin_no_reply"])

        with st.container(border=True):
            st.markdown(f'<span class="hpd-eyebrow">{txt["lgpd_badge"]}</span>', unsafe_allow_html=True)
            st.markdown(f"**{txt['fin_customer_msg']}**")
            st.markdown(f"> {tk.get('texto_mascarado') or '—'}")

        if d:
            _render_supervisao(txt, d, chave_unica=f"sup_fin_{escolhido}")
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
                txt["filter_label"], options=["todas", "alta", "media", "baixa"], default="todas",
                format_func=lambda k: txt["all"] if k == "todas" else f"{COR[k]} {niveis[k]}",
                label_visibility="collapsed", key="filtro_urgencia",
            )
            if filtro not in (None, "todas"):
                fila = [i for i in base if urgencia_efetiva(i) == filtro]
        if not fila:
            st.info(txt["empty_filter"])
            return None
        ids_fila = [i.id for i in fila]
        ativo = st.session_state.get("chamado_ativo_fila")
        if ativo not in ids_fila:
            ativo = ids_fila[0]
        # Reatribuição explícita força set_value=True no frontend (bolinha sempre marcada)
        # e mantém o rótulo estável (a seta → é desenhada pelo CSS no item selecionado).
        st.session_state["chamado_ativo_fila"] = ativo
        rotulos = {
            i.id: f"{COR[urgencia_efetiva(i)]} {i.id} · "
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
    motivos = t.motivos_urgencia + t.motivos_intencao
    itens_ev = [
        {"titulo": f"“{m.trecho}”", "badge": nome_sinal(m.sinal, txt)}
        for m in motivos
    ]
    with col_trechos:
        render_card_cascata(
            txt["evidences"],
            itens_ev,
            chave_unica=f"evidencias_{item.id}",
            vazio=txt["no_evidences"],
        )

    itens_hip = []
    for p in item.palpites:
        hip_txt, perg_txt = traduzir_palpite(p, txt)
        detalhe = f"{txt['confirm_q']} {perg_txt}"
        extra = linha_acervo(p.acervo_topico_id, p.acervo_palavras, txt)
        if extra:
            detalhe = f"{detalhe} | {extra}"
        itens_hip.append(
            {
                "titulo": hip_txt,
                "detalhe": detalhe,
                "badge": niveis.get(p.confianca, p.confianca),
                "alerta": txt["raise_warn"] if p.sugere_subir_urgencia else "",
            }
        )
    with col_analise:
        render_card_cascata(
            txt["perception"],
            itens_hip,
            chave_unica=f"analise_{item.id}",
            vazio=txt["no_guesses"],
        )
        topico_ac, _ = topico_do_item(item)
        if topico_ac is not None:
            st.button(
                txt["acervo_open_btn"].format(titulo=topico_ac.titulo),
                key=f"abrir_acervo_1_{item.id}",
                width="stretch",
                on_click=_abrir_acervo,
                args=(item, "chamado"),
            )

    with st.container(key="cta_step_1"):
        st.button(txt["go_2"], type="primary", width="stretch", key=f"go2_{item.id}",
                  on_click=_ir_para_etapa, args=(item.id, "decisao"))




def gerar_texto_com_passos_marcados(topico, passos, passos_marcados, idioma="PT", txt=None):
    """Gera o texto do 'Simular melhor resposta' a partir dos passos marcados.

    Usa SOMENTE os passos marcados, respeitando as regras de cada passo:
      - passo 1: as quedas também afetam outros usuários;
      - passo 2: acesso pelo portal web seguro, sem VPN;
      - passo 3: rede alternativa só se permitido pela política; nunca credenciais;
      - passo 4: encaminhado à equipe de redes com os horários das quedas.
    """
    pt = {
        1: "Identificamos que as quedas também afetam outros usuários.",
        2: "Como medida alternativa, orientamos o acesso aos sistemas pelo portal web seguro, sem utilização de VPN.",
        3: "Sugerimos uma rede alternativa, se permitido pela política da organização.",
        4: "O problema já foi encaminhado à equipe de redes, juntamente com os horários das interrupções, para análise.",
    }
    en = {
        1: "We identified that the outages also affect other users.",
        2: "As an alternative measure, we guided access to the systems via the secure web portal, without using VPN.",
        3: "We suggest an alternative network, if permitted by the organization's policy.",
        4: "The issue has already been forwarded to the network team, along with the outage times, for analysis.",
    }
    idioma_norm = idioma.upper()
    labels = pt if idioma_norm == "PT" else en
    marcacoes = (
        passos_marcados.get(topico.id, {})
        if isinstance(passos_marcados, dict) and topico.id in passos_marcados
        else (passos_marcados or {})
    )
    partes = []
    for indice in range(1, len(passos) + 1):
        if marcacoes.get(indice, False):
            frase = labels.get(indice, "")
            if frase:
                partes.append(frase)
    partes.append(
        "No momento, recomendamos aguardar o retorno da equipe técnica."
        if idioma_norm == "PT"
        else "For now, we recommend awaiting the technical team's response."
    )
    return " ".join(partes)

def _etapa_acervo(item, estado: dict, txt: dict) -> None:
    """Aba do Acervo: material descritivo, simulador de tempo, voltar e ir para resposta."""
    topico, palavras = topico_do_item(item)
    if topico is None:
        st.button(txt["acervo_back_btn"], key=f"voltar_acervo_{item.id}",
                  on_click=_voltar_do_acervo, args=(item.id,))
        return

    idioma = txt.get("lang_code", "PT")
    titulo = acervo.texto_topico(topico, "titulo", idioma)
    titulo_material = acervo.texto_material(topico.material_id, "titulo", idioma)
    problema = acervo.texto_topico(topico, "problema", idioma)
    solucao = acervo.texto_topico(topico, "solucao_provisoria", idioma)
    passos = acervo.texto_topico(topico, "passos", idioma)
    cenarios = acervo.cenarios_topico(topico, idioma)
    with st.container(border=True):
        st.markdown(f'<span class="hpd-eyebrow">{txt["acervo_tab_title"]}</span>', unsafe_allow_html=True)
        st.caption(txt["acervo_fictional_notice"])
        st.markdown(f"#### `{topico.id}` · {titulo}")
        st.caption(f"**{txt['acervo_material_lbl']}:** {topico.material_id} — {titulo_material}")
        if palavras:
            st.caption(f"**{txt['acervo_words'].capitalize()}:** {', '.join(palavras)}")
        st.markdown(f"**{txt['acervo_problem_lbl']}**\n\n{problema}")
        st.info(f"**{txt['acervo_workaround_lbl']}:** `[{solucao}]`")
        st.markdown(f"**{txt['acervo_steps_lbl']}**")
        estado.setdefault("passos_marcados", {})
        estado["passos_marcados"].setdefault(topico.id, {})
        for indice, passo in enumerate(passos, start=1):
            chave = f"passo_{topico.id}_{indice}"
            estado["passos_marcados"][topico.id][indice] = st.checkbox(
                passo, key=chave, value=estado["passos_marcados"][topico.id].get(indice, False)
            )

        # --- botão de simulação dos passos marcados (Etapa 4) ---
        st.button(
            txt.get("acervo_sim_btn_simular", "Simular melhor resposta com os passos marcados"),
            key=f"simular_melhor_resposta_{item.id}",
            width="stretch",
            on_click=_simular_melhor_resposta,
            args=(item, estado, txt),
        )

    with st.container(border=True):
        st.markdown(f"**{txt['acervo_sim_title']}**")
        linhas_tempo = [
            {
                txt["acervo_sim_scenario"]: cenario,
                txt["acervo_sim_range"]: f"{faixa.min}–{faixa.max} min",
            }
            for faixa, cenario in zip(topico.tabela_tempo, cenarios)
        ]
        st.table(linhas_tempo)

        opcoes_idx = list(range(len(topico.tabela_tempo)))
        idx_padrao = estado.get("cenario_tempo_idx", 0)
        if idx_padrao not in opcoes_idx:
            idx_padrao = 0
        escolhido_idx = st.pills(
            txt["acervo_sim_choose"],
            options=opcoes_idx,
            default=idx_padrao,
            format_func=lambda idx: f"{cenarios[idx]} ({topico.tabela_tempo[idx].min}–{topico.tabela_tempo[idx].max} min)",
            key=f"sim_cenario_{item.id}",
        )
        if escolhido_idx is None:
            escolhido_idx = 0
        estado["cenario_tempo_idx"] = escolhido_idx
        est = acervo.estimar(topico, escolhido_idx)
        lang = txt.get("lang_code", "PT")
        de_str = formatar_data_hora(est.previsto_de.isoformat(), lang=lang)
        ate_str = formatar_data_hora(est.previsto_ate.isoformat(), lang=lang)
        janela_lbl = txt["acervo_sim_result"].format(
            de=de_str, ate=ate_str, min=est.minutos_min, max=est.minutos_max
        )
        # Botão clicável (Etapa 5): ao clicar, preenche o SEGUNDO [ ] (PEND_PRAZO) na sugestão OARS.
        st.button(
            f"{txt['acervo_sim_btn_prazo']} · {janela_lbl.replace('**', '')}",
            key=f"prazo_sim_{item.id}",
            width="stretch",
            on_click=_usar_prazo_sim,
            args=(item, estado, txt),
        )
        st.caption(txt["acervo_sim_caveat"])

    col_voltar, col_aplicar = st.columns(2, gap="medium")
    with col_voltar:
        st.button(
            txt["acervo_back_btn"],
            key=f"voltar_acervo_{item.id}",
            width="stretch",
            on_click=_voltar_do_acervo,
            args=(item.id,),
        )
    with col_aplicar, st.container(key="cta_step_3_acervo"):
        st.button(
            txt["acervo_apply_btn"],
            type="primary",
            key=f"ir_resp_acervo_{item.id}",
            width="stretch",
            on_click=_ir_para_resposta_do_acervo,
            args=(item,),
        )






def _usar_prazo_sim(item, estado: dict, txt: dict) -> None:
    """Preenche o segundo [ ] (PEND_PRAZO) na sugestão OARS com a janela simulada."""
    topico, _ = topico_do_item(item)
    if topico is None:
        return
    lang = txt.get("lang_code", "PT")
    cenario = estado.get("cenario_tempo_idx", 0)
    est = acervo.estimar(topico, cenario)
    de_str = formatar_data_hora(est.previsto_de.isoformat(), lang=lang)
    ate_str = formatar_data_hora(est.previsto_ate.isoformat(), lang=lang)
    if lang.upper() == "EN":
        janela = f"{de_str} to {ate_str} ({est.minutos_min} to {est.minutos_max} min)"
    else:
        janela = f"{de_str} até {ate_str} ({est.minutos_min} a {est.minutos_max} min)"
    estado[f"prazo_sim_{item.id}"] = janela
    _aplicar_acervo_na_sugestao(item, estado, topico, prazo_override=janela)


def _simular_melhor_resposta(item, estado: dict, txt: dict) -> None:
    """Gera a solução a partir dos passos marcados e atualiza a sugestão OARS."""
    topico, _ = topico_do_item(item)
    if topico is None:
        return
    idioma = txt.get("lang_code", "PT")
    passos = acervo.texto_topico(topico, "passos", idioma)
    marcacoes = estado.get("passos_marcados", {}).get(topico.id, {})
    solucao_simulada = gerar_texto_com_passos_marcados(
        topico, passos, marcacoes, idioma=idioma, txt=txt
    )
    estado["solucao_simulada"] = solucao_simulada
    _aplicar_acervo_na_sugestao(item, estado, topico, solucao_override=solucao_simulada)

def _etapa_decisao(item, estado: dict, txt: dict, agente: str) -> None:
    t, niveis = item.triagem, txt["niveis"]
    with st.container(border=True):
        opcoes = leituras_do_item(item, auditoria.ler(LOG), carregar_config(CONFIG)) + [LEITURA_PROPRIA]
        leitura = st.pills(
            txt["reading_lbl"], options=opcoes,
            default=estado["leitura"] if estado["leitura"] in opcoes else None,
            format_func=lambda k: txt["reading_custom"] if k == LEITURA_PROPRIA else traduzir_leitura(k, txt),
            key=f"leit_ui_{item.id}",
        )
        estado["leitura"] = leitura
        if leitura == LEITURA_PROPRIA:
            estado["leitura_livre"] = st.text_input(
                txt["free_reading"], value=estado["leitura_livre"], key=f"livre_ui_{item.id}",
            )
        elif leitura:
            trechos = trechos_da_leitura(leitura, t, item.palpites)
            itens_tr = [
                {"titulo": f"“{m.trecho}”", "badge": nome_sinal(m.sinal, txt)}
                for m in trechos
            ]
            render_card_cascata(
                txt["reading_evidence_title"],
                itens_tr,
                chave_unica=f"ev_leitura_{item.id}_{leitura}",
                vazio=txt["reading_no_evidence"],
                envolver_card=False,
            )

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
    texto_sugestao_ia = estado.get("sugestao_acervo") or rascunho.texto
    chave_sugestao = f"sug_ui_{item.id}_{leitura_registro or 'base'}"
    chave_resposta = f"resp_ui_{item.id}"
    # Valores iniciais definidos antes de criar os campos (sem `value=`, para a
    # sugestão poder ser copiada por callback sem conflito de estado).
    st.session_state.setdefault(chave_sugestao, texto_sugestao_ia)
    st.session_state.setdefault(chave_resposta, estado["resposta"])

    col_sugestao, col_supervisao = st.columns(2, gap="medium")
    with col_sugestao, st.container(border=True):
        st.markdown(f"**{txt['box_suggestion']}**")
        st.caption(f"{txt['box_suggestion_hint']} · {txt['origens'].get(origem, origem)}")
        if estado.get("acervo_topico_id"):
            st.caption(txt["acervo_applied_badge"])
        st.text_area(txt["box_suggestion"], key=chave_sugestao, height=230, label_visibility="collapsed")
        rotulo_usar = (
            f"✓ {txt['btn_use_suggestion']}"
            if estado.get("usou_sugestao")
            else txt["btn_use_suggestion"]
        )
        chave_cnt_usar = f"btn_usar_ativo_{item.id}" if estado.get("usou_sugestao") else f"btn_usar_padrao_{item.id}"
        with st.container(key=chave_cnt_usar):
            st.button(
                rotulo_usar,
                key=f"usar_{item.id}",
                width="stretch",
                on_click=_usar_sugestao,
                args=(chave_sugestao, chave_resposta, item.id),
            )
    pacote = detalhes_supervisao(item, leitura_registro, leitura_livre, estado["urgencia"], texto_sugestao_ia, origem)
    with col_supervisao:
        _render_supervisao(
            txt,
            pacote,
            chave_unica=f"sup_resp_{item.id}",
            subtitulo=txt["box_supervision_hint"],
            item=item,
            origem=origem,
        )
        topico_ac, _ = topico_do_item(item)
        if topico_ac is not None:
            st.button(
                txt["acervo_open_btn"].format(titulo=topico_ac.titulo),
                key=f"abrir_acervo_3_{item.id}",
                width="stretch",
                on_click=_abrir_acervo,
                args=(item, "resposta"),
            )

    with st.container(border=True, key="caixa_resposta"):
        st.markdown(f"**{txt['box_reply']}**")
        st.caption(txt["box_reply_hint"])
        resposta = st.text_area(
            txt["box_reply"], key=chave_resposta, height=220,
            placeholder=txt["reply_placeholder"], label_visibility="collapsed",
        )
        estado["resposta"] = resposta

        marcadores = pendencias_abertas(resposta)
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
            decisao = classificar_resposta(texto_sugestao_ia, resposta)
            payload = payload_decisao(
                item, decisao, resposta, leitura=leitura_registro,
                leitura_livre=leitura_livre, urgencia_analista=estado["urgencia"],
                origem_triagem=item.origem_triagem, origem_rascunho=origem,
            )
            repositorio.registrar_decisao(
                item.id, decisao, resposta, agente, detalhes=pacote,
                payload_auditoria=payload,
            )
            if not repositorio.exportar_auditoria_pendente(LOG):
                st.warning(txt.get("audit_sync_pending", "Decisão salva; a auditoria será sincronizada depois."))
            st.session_state["estado_chamados"].pop(item.id, None)
            st.toast(txt["toast_registered"].format(id=item.id))
            st.rerun()


# ---------------------------------------------------------------- tela

def tela_marina(provider: str, txt: dict, agente: str = "Marina") -> None:
    itens = fila_base(provider, os.getenv("GEMINI_MODEL", ""), txt=txt)
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

    esquerda, direita = st.columns([1.0, 2.1], gap="large")
    with esquerda:
        item = _render_fila(base, visao, txt, urgencia_efetiva)
    if item is None:
        return

    t, niveis, intencoes = item.triagem, txt["niveis"], txt["intencoes"]
    estado = _estado_item(item)
    # Valores dos campos já atualizados nesta execução (os campos só existem na etapa ativa).
    urgencia = st.session_state.get(f"urg_ui_{item.id}", estado["urgencia"])
    resposta = st.session_state.get(f"resp_ui_{item.id}", estado["resposta"])
    pronta = urgencia is not None and bool(_PLACEHOLDER.sub("", resposta or "").strip()) and not pendencias_abertas(resposta or "")
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
        # O widget é desmontado ao trocar de tela e o Streamlit limpa a chave;
        # restaura-se o valor persistido antes de renderizar o controle.
        st.session_state.setdefault(f"camada_{item.id}", estado["camada"])
        escolhida = st.segmented_control(
            txt["steps_label"], options=list(etapas), format_func=lambda k: f"{etapas[k][1]} {etapas[k][0]}",
            label_visibility="collapsed", key=f"camada_{item.id}",
            on_change=_ao_trocar_camada, args=(item.id,),
        )
        if escolhida is not None:
            estado["camada"] = escolhida

        if estado.get("aba_acervo_aberta"):
            _etapa_acervo(item, estado, txt)
        elif estado["camada"] == "chamado":
            _etapa_analise(item, txt)
        elif estado["camada"] == "decisao":
            estado["viu_chamado"] = True
            _etapa_decisao(item, estado, txt, agente)
        else:
            estado["viu_chamado"] = True
            _etapa_resposta(item, estado, txt, agente, provider)
