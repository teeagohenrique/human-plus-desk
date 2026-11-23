"""Identidade visual e textos da interface Human + Desk.

Camada de apresentação: traduções PT/EN, tema DXC (Claro/Escuro), logotipo
e seletor de idioma. Nenhuma regra de negócio, persistência ou chamada de
modelo vive aqui.
"""
import streamlit as st


I18N = {
    "PT": {
        "nav_label": "Navegação",
        "nav_marina": "Painel da Marina",
        "nav_rafael": "Painel do Rafael",
        "appearance": "Aparência",
        "dark": "Escuro",
        "light": "Claro",
        "adapter": "Adaptador de IA",
        "rules_opt": "Regras (offline)",
        "gemini_opt": "Gemini (API)",
        "eyebrow_marina": "Human+ · Console de Atendimento",
        "eyebrow_rafael": "Human+ · Observabilidade e Calibração",
        "title_marina": "Painel da Marina",
        "title_rafael": "Painel do Rafael (gestor)",
        "sub_rafael": "Acompanhamento de qualidade, calibração passiva e transparência das decisões humanas.",
        "kpi_pending": "Pendentes",
        "kpi_of_queue": "de {n} na fila",
        "kpi_high": "Urgência Alta",
        "kpi_priority": "prioridade imediata",
        "kpi_done": "Concluído",
        "kpi_registered": "{n} registrados",
        "db_title": "Persistência e auditoria",
        "db_caption": "Estado salvo em human_desk.db: sobrevive a F5 e ao reinício do Streamlit.",
        "db_reopen_select": "Chamado concluído",
        "db_reopen_btn": "Reabrir chamado (registra Rafael)",
        "db_reopen_done": "Chamado reaberto e registrado no banco.",
        "db_empty": "Nenhum chamado concluído no banco.",
        "db_events": "Últimos eventos registrados",
        "queue": "Fila",
        "all": "Todas",
        "empty_filter": "Sem chamados nesse filtro.",
        "queue_done": "Fila zerada! Todas as decisões foram registradas na auditoria.",
        "niveis": {"alta": "Alta", "media": "Média", "baixa": "Baixa"},
        "decisoes": {"aprovou": "Aprovou", "editou": "Editou", "rejeitou": "Rejeitou"},
        "intencoes": {
            "falha_sistema": "Falha no sistema", "acesso": "Acesso", "reclamacao": "Reclamação",
            "solicitacao": "Solicitação", "duvida": "Dúvida", "indefinida": "Indefinida",
        },
        "sinais": {
            "prazo": "Prazo", "recorrencia": "Recorrência", "processo_critico": "Processo crítico",
            "muitos_afetados": "Muitos afetados", "bloqueio": "Bloqueio",
            "risco_saida": "Risco de cancelamento", "palavra_chave": "Termo-chave",
        },
        "origens": {"gemini": "Gemini (API)", "regras": "Regras (offline)", "fallback": "Fallback por regras"},
        "triage": "Triagem",
        "draft": "Rascunho",
        "confidence": "Confiança",
        "chip_1_done": "1 · Chamado visto",
        "chip_1_alert": "1 · Chamado · alerta de prioridade",
        "chip_1_pend": "1 · Revisar chamado",
        "chip_2_done": "2 · Urgência definida",
        "chip_2_pend": "2 · Definir urgência",
        "chip_3_done": "3 · Resposta pronta",
        "chip_3_pend": "3 · Preencher [colchetes]",
        "layer_1": "1 · Chamado",
        "layer_2": "2 · Decisão",
        "layer_3": "3 · Resposta",
        "lgpd_badge": "LGPD · Dados pessoais mascarados",
        "evidences": "Evidências literais",
        "no_evidences": "Sem sinais literais encontrados.",
        "perception": "Percepção",
        "hyp_one": "hipótese",
        "hyp_many": "hipóteses",
        "no_guesses": "Sem evidência, sem palpite.",
        "confirm_q": "Confirmar:",
        "raise_warn": "Sugestão: avaliar subir prioridade.",
        "go_2": "Avançar para 2 · Decisão →",
        "back_1": "← Voltar ao Chamado",
        "go_3": "Avançar para 3 · Resposta →",
        "reading_lbl": "Leitura do chamado (ajusta o rascunho na Camada 3)",
        "none_opt": "Nenhuma delas",
        "free_reading": "Sua leitura (opcional)",
        "urg_lbl": "Urgência real — IA sugeriu {sug} (escolha explicitamente):",
        "urg_hint": "Escolha a urgência acima para marcar esta camada como concluída.",
        "draft_lbl": "Rascunho OARS (edite antes de aprovar)",
        "need_urg": "defina a **urgência** na camada `2 · Decisão`",
        "need_brack": "preencha ou remova: ",
        "pending_banner": "Pendente para liberar: ",
        "ready_banner": "Tudo validado — pronto para registrar (nenhum envio automático).",
        "btn_approve": "Aprovar / salvar edição",
        "btn_reject": "Rejeitar (escrevo a minha)",
        "sim_toggle": "Usar dados SIMULADOS (demonstração)",
        "sim_btn": "Gerar / atualizar simulados",
        "sim_warn": "Dados INVENTADOS apenas para demonstração visual. Não representam resultados reais.",
        "no_decisions": "Ainda não há decisões registradas. Decida alguns chamados no Painel da Marina ou ative os dados simulados.",
        "tab_overview": "Visão geral",
        "tab_readings": "Calibração das leituras",
        "tab_urgency": "Calibração da urgência",
        "footer": "Human + Desk v2 · Enterprise Adaptive · humano no controle",
    },
    "EN": {
        "nav_label": "Navigation",
        "nav_marina": "Marina's Dashboard",
        "nav_rafael": "Rafael's Dashboard",
        "appearance": "Appearance",
        "dark": "Dark",
        "light": "Light",
        "adapter": "AI Adapter",
        "rules_opt": "Rules (offline)",
        "gemini_opt": "Gemini (API)",
        "eyebrow_marina": "Human+ · AI-Assisted Service Desk",
        "eyebrow_rafael": "Human+ · Observability & Calibration",
        "title_marina": "Marina's Dashboard",
        "title_rafael": "Rafael's Dashboard (Manager)",
        "sub_rafael": "Quality tracking, passive calibration, and transparency of human decisions.",
        "kpi_pending": "Pending",
        "kpi_of_queue": "of {n} in queue",
        "kpi_high": "High Urgency",
        "kpi_priority": "immediate priority",
        "kpi_done": "Completed",
        "kpi_registered": "{n} logged",
        "db_title": "Persistence and audit",
        "db_caption": "State saved in human_desk.db: survives F5 and a Streamlit restart.",
        "db_reopen_select": "Completed ticket",
        "db_reopen_btn": "Reopen ticket (logged as Rafael)",
        "db_reopen_done": "Ticket reopened and logged in the database.",
        "db_empty": "No completed tickets in the database.",
        "db_events": "Latest logged events",
        "queue": "Queue",
        "all": "All",
        "empty_filter": "No tickets in this filter.",
        "queue_done": "Queue cleared! All decisions have been recorded in the audit log.",
        "niveis": {"alta": "High", "media": "Medium", "baixa": "Low"},
        "decisoes": {"aprovou": "Approved", "editou": "Edited", "rejeitou": "Rejected"},
        "intencoes": {
            "falha_sistema": "System Failure", "acesso": "Access", "reclamacao": "Complaint",
            "solicitacao": "Request", "duvida": "Question", "indefinida": "Undefined",
        },
        "sinais": {
            "prazo": "Deadline", "recorrencia": "Recurrence", "processo_critico": "Critical process",
            "muitos_afetados": "Many affected", "bloqueio": "Blocker",
            "risco_saida": "Churn risk", "palavra_chave": "Keyword",
        },
        "origens": {"gemini": "Gemini (API)", "regras": "Rules (offline)", "fallback": "Rules fallback"},
        "triage": "Triage",
        "draft": "Draft",
        "confidence": "Confidence",
        "chip_1_done": "1 · Ticket reviewed",
        "chip_1_alert": "1 · Ticket · priority alert",
        "chip_1_pend": "1 · Review ticket",
        "chip_2_done": "2 · Urgency set",
        "chip_2_pend": "2 · Set urgency",
        "chip_3_done": "3 · Reply ready",
        "chip_3_pend": "3 · Fill [brackets]",
        "layer_1": "1 · Ticket",
        "layer_2": "2 · Decision",
        "layer_3": "3 · Reply",
        "lgpd_badge": "LGPD / GDPR · Personal data masked",
        "evidences": "Literal evidence",
        "no_evidences": "No literal signals found.",
        "perception": "Perception",
        "hyp_one": "hypothesis",
        "hyp_many": "hypotheses",
        "no_guesses": "No evidence, no hypothesis.",
        "confirm_q": "Confirm:",
        "raise_warn": "Suggestion: consider raising priority.",
        "go_2": "Continue to 2 · Decision →",
        "back_1": "← Back to Ticket",
        "go_3": "Continue to 3 · Reply →",
        "reading_lbl": "Ticket reading (adapts the draft in Layer 3)",
        "none_opt": "None of these",
        "free_reading": "Your reading (optional)",
        "urg_lbl": "Actual urgency — AI suggested {sug} (choose explicitly):",
        "urg_hint": "Select urgency above to mark this layer complete.",
        "draft_lbl": "OARS Draft (edit before approving)",
        "need_urg": "set **urgency** in layer `2 · Decision`",
        "need_brack": "fill or remove: ",
        "pending_banner": "Required to unlock: ",
        "ready_banner": "Validated — ready to log (no automatic send).",
        "btn_approve": "Approve / save edit",
        "btn_reject": "Reject (write my own)",
        "sim_toggle": "Use SIMULATED data (demo)",
        "sim_btn": "Generate / refresh simulated",
        "sim_warn": "INVENTED demo data only. Does not represent real operational results.",
        "no_decisions": "No decisions logged yet. Decide a few tickets in Marina's Dashboard or enable simulated data.",
        "tab_overview": "Overview",
        "tab_readings": "Reading calibration",
        "tab_urgency": "Urgency calibration",
        "footer": "Human + Desk v2 · Enterprise Adaptive · human-in-the-loop",
    },
}


def get_text(key: str) -> str:
    """Retorna o texto traduzido conforme o idioma ativo no session_state."""
    lang = st.session_state.get("lang", "PT")
    return I18N.get(lang, I18N["PT"]).get(key, key)


def render_dxc_theme(dark_mode: bool = False) -> None:
    """Injeta a fonte Space Grotesk e a paleta DXC (Claro/Escuro)."""
    escuro = dark_mode
    if escuro:
        bg_app = (
            "radial-gradient(circle at 12% 0%, rgba(91, 44, 152, 0.16), transparent 40%), "
            "radial-gradient(circle at 88% 6%, rgba(255, 107, 0, 0.08), transparent 36%), #0E1017"
        )
        bg_side = "#151822"
        bg_card = "#1A1E2B"
        bg_quote = "#0E1017"
        border_card = "#2D3348"
        shadow = "0 6px 24px rgba(0, 0, 0, 0.28)"
        txt_main = "#F8FAFC"
        txt_muted = "#94A3B8"
        txt_sub = "#64748B"
        eyebrow_bg = "rgba(91, 44, 152, 0.18)"
        eyebrow_fg = "#E9D5FF"
        eyebrow_bd = "rgba(217, 43, 107, 0.42)"
        chip_bg = "#151822"
        bg_widget = "#1A1E2B"
        bg_header = "rgba(14, 16, 23, 0.88)"
        bg_alert = "#151822"
        bg_active = "rgba(124, 58, 237, 0.32)"
        fg_active = "#FFFFFF"
        radio_off_bg = "#1A1E2B"
        step_cta_bg = "linear-gradient(90deg, #4F2D7F 0%, #B82968 50%, #FF6B00 100%)"
        pend_fg, alert_fg, done_fg = "#FDE68A", "#FDA4AF", "#A7F3D0"
        btn_dis_bg, btn_dis_fg = "#252A3D", "#64748B"
    else:
        bg_app = (
            "radial-gradient(circle at 12% 0%, rgba(91, 44, 152, 0.06), transparent 40%), "
            "radial-gradient(circle at 88% 6%, rgba(255, 107, 0, 0.05), transparent 36%), #F8FAFC"
        )
        bg_side = "#F1F5F9"
        bg_card = "#FFFFFF"
        bg_quote = "#F8FAFC"
        border_card = "#CBD5E1"
        shadow = "0 4px 18px rgba(15, 23, 42, 0.06)"
        txt_main = "#0F172A"
        txt_muted = "#475569"
        txt_sub = "#64748B"
        eyebrow_bg = "rgba(91, 44, 152, 0.08)"
        eyebrow_fg = "#5B2C98"
        eyebrow_bd = "rgba(91, 44, 152, 0.26)"
        chip_bg = "#FFFFFF"
        bg_widget = "#FFFFFF"
        bg_header = "rgba(248, 250, 252, 0.92)"
        bg_alert = "#F1F5F9"
        bg_active = "rgba(91, 44, 152, 0.16)"
        fg_active = "#3B1C6E"
        radio_off_bg = "#FFFFFF"
        step_cta_bg = "#4F2D7F"
        pend_fg, alert_fg, done_fg = "#B45309", "#BE123C", "#047857"
        btn_dis_bg, btn_dis_fg = "#E2E8F0", "#94A3B8"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap');

        .stApp {{
            background: {bg_app};
            color: {txt_main};
            font-family: 'Inter', sans-serif;
        }}
        header[data-testid="stHeader"] {{
            background: {bg_header} !important;
            backdrop-filter: blur(6px);
        }}
        header[data-testid="stHeader"] * {{
            color: {txt_main} !important;
        }}
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{
            font-family: 'Space Grotesk', sans-serif !important;
            letter-spacing: -0.02em;
            color: {txt_main};
        }}
        .stApp p, .stApp label, .stApp span {{ color: {txt_main}; }}
        .stApp [data-testid="stCaptionContainer"] p {{ color: {txt_muted} !important; }}
        section[data-testid="stSidebar"] {{
            background-color: {bg_side};
            border-right: 1px solid {border_card};
        }}
        section[data-testid="stSidebar"] * {{ color: {txt_main}; }}

        /* Widgets nativos adaptados ao modo Claro e Escuro (Streamlit 1.67+) */
        div[data-testid="stButtonGroup"] button,
        div[data-testid="stPopover"] button,
        button[kind="secondary"],
        button[kind="segmented_control"],
        button[kind="pills"] {{
            background-color: {bg_widget} !important;
            color: {txt_main} !important;
            border: 1px solid {border_card} !important;
        }}
        div[data-testid="stButtonGroup"] button *,
        div[data-testid="stPopover"] button *,
        button[kind="secondary"] *,
        button[kind="segmented_control"] *,
        button[kind="pills"] * {{
            color: {txt_main} !important;
        }}
        button[kind="secondary"]:disabled {{
            background-color: {btn_dis_bg} !important;
            color: {btn_dis_fg} !important;
            opacity: 0.55 !important;
            cursor: not-allowed !important;
        }}
        button[kind="secondary"]:disabled * {{
            color: {btn_dis_fg} !important;
        }}
        div[data-testid="stButtonGroup"] button[aria-pressed="true"],
        div[data-testid="stButtonGroup"] button[data-testid*="Active"],
        button[kind="segmented_controlActive"],
        button[kind="pillsActive"] {{
            background-color: {bg_active} !important;
            color: {fg_active} !important;
            border: 2px solid #7C3AED !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
        div[data-testid="stButtonGroup"] button[data-testid*="Active"] *,
        button[kind="segmented_controlActive"] *,
        button[kind="pillsActive"] * {{
            color: {fg_active} !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stPopover"] button {{
            min-width: 82px !important;
            white-space: nowrap !important;
        }}
        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"],
        textarea,
        input {{
            background-color: {bg_widget} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-baseweb="select"] *,
        div[data-baseweb="select"] button {{
            background-color: transparent !important;
        }}
        div[data-baseweb="select"] > div {{
            background-color: {bg_widget} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-baseweb="select"] svg {{
            fill: {txt_main} !important;
        }}
        /* Alertas (st.info / st.warning / st.success) legíveis no Claro e Escuro */
        div[data-testid="stAlert"],
        div[data-testid="stAlert"] > div,
        div[data-testid="stAlert"] > div > div,
        div[data-testid="stAlertContainer"],
        div[data-testid="stNotification"],
        div[data-testid="stNotification"] > div,
        div[role="alert"],
        div[role="alert"] > div {{
            background-color: {bg_alert} !important;
            color: {txt_main} !important;
            border-radius: 10px !important;
        }}
        div[data-testid="stAlert"],
        div[data-testid="stNotification"] {{
            border: 1px solid {border_card} !important;
        }}
        div[data-testid="stAlert"] *,
        div[data-testid="stNotification"] *,
        div[role="alert"] * {{
            color: {txt_main} !important;
        }}
        /* Bolinhas de radio não selecionadas no modo Claro */
        div[role="radiogroup"] label > div:first-child {{
            background-color: {radio_off_bg} !important;
            border-color: {border_card} !important;
        }}
        /* Alinhamento simétrico da fila + micro-feedback (deslocamento + seta) no item ativo */
        .st-key-fila_bento_card {{
            min-height: 460px;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label {{
            padding: 5px 10px;
            border-radius: 8px;
            border-left: 3px solid transparent;
            transition: padding-left 0.15s ease, background-color 0.15s ease;
            width: 100%;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label:has(input:checked) {{
            background-color: {bg_active} !important;
            border-left: 3px solid #7C3AED !important;
            padding-left: 15px !important;
            font-weight: 600 !important;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label:has(input:checked)::after {{
            content: "→";
            margin-left: auto;
            color: #7C3AED;
            font-weight: 700;
        }}
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        ul[role="listbox"],
        li[role="option"] {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stExpander"] {{
            background-color: {bg_card} !important;
            border-color: {border_card} !important;
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {bg_card};
            border: 1px solid {border_card} !important;
            border-radius: 12px !important;
            box-shadow: {shadow};
        }}
        .bento-kpi {{
            background: {bg_card};
            border: 1px solid {border_card};
            border-radius: 10px;
            padding: 14px 18px;
            min-height: 92px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            box-shadow: {shadow};
        }}
        .bento-kpi::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, #5B2C98 0%, #D92B6B 50%, #FF6B00 100%);
        }}
        .bento-kpi-label {{
            font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em;
            text-transform: uppercase; color: {txt_muted}; margin-bottom: 4px;
        }}
        .bento-kpi-val {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.65rem; font-weight: 700; color: {txt_main}; line-height: 1.15;
        }}
        .bento-kpi-sub {{ font-size: 0.78rem; color: {txt_sub}; margin-top: 2px; }}
        .layer-strip {{ display: flex; gap: 8px; margin: 8px 0 10px 0; flex-wrap: wrap; }}
        .layer-chip {{
            display: inline-flex; align-items: center; gap: 7px;
            font-size: 0.76rem; font-weight: 600; padding: 4px 11px; border-radius: 999px;
            background: {chip_bg}; border: 1px solid {border_card}; color: {txt_muted};
        }}
        .layer-chip.pending {{ border-color: rgba(245, 158, 11, 0.48); color: {pend_fg}; }}
        .layer-chip.alert   {{ border-color: rgba(217, 43, 107, 0.55); color: {alert_fg}; }}
        .layer-chip.done    {{ border-color: rgba(16, 185, 129, 0.45); color: {done_fg}; }}
        .dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
        .dot-pending {{ background: #F59E0B; box-shadow: 0 0 8px rgba(245, 158, 11, 0.7); }}
        .dot-alert   {{ background: #D92B6B; box-shadow: 0 0 8px rgba(217, 43, 107, 0.75); }}
        .dot-done    {{ background: #10B981; box-shadow: 0 0 8px rgba(16, 185, 129, 0.7); }}
        blockquote {{
            background: {bg_quote};
            border-left: 3px solid #D92B6B !important;
            border-radius: 0 10px 10px 0;
            padding: 12px 16px !important;
            color: {txt_main} !important;
        }}
        button[kind="primary"] {{
            background: linear-gradient(90deg, #4F2D7F 0%, #B82968 50%, #FF6B00 100%) !important;
            border: none !important;
            border-radius: 24px !important;
            color: #FFFFFF !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 600 !important;
        }}
        /* Passos intermediários (1 e 2): roxo sólido #4F2D7F no Claro; degradê completo reservado ao Passo 3 */
        div[class*="st-key-go2_"] button[kind="primary"],
        div[class*="st-key-go3_"] button[kind="primary"],
        .st-key-cta_step_1 button[kind="primary"],
        .st-key-cta_step_2 button[kind="primary"] {{
            background: {step_cta_bg} !important;
        }}
        button[kind="primary"] * {{ color: #FFFFFF !important; }}
        button[kind="primary"]:disabled {{
            background: {btn_dis_bg} !important;
            color: {btn_dis_fg} !important;
        }}
        button[kind="primary"]:disabled * {{ color: {btn_dis_fg} !important; }}
        .hpd-eyebrow {{
            display: inline-block; font-size: 0.70rem; letter-spacing: 0.12em;
            text-transform: uppercase; color: {eyebrow_fg} !important;
            background: {eyebrow_bg}; border: 1px solid {eyebrow_bd};
            border-radius: 999px; padding: 3px 10px; margin-bottom: 6px; font-weight: 600;
        }}
        #MainMenu {{ visibility: hidden; }}
        [data-testid="stAppDeployButton"] {{ display: none; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_dxc_logo(dark_mode: bool = False) -> None:
    """Renderiza o logotipo Human [+] Desk com a cruz geométrica DXC."""
    logo_color = "#F8FAFC" if dark_mode else "#0F172A"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:12px;margin:6px 0 20px 0;">
            <div style="font-family:'Space Grotesk',sans-serif;font-size:1.65rem;font-weight:700;line-height:1.05;color:{logo_color};">
                Human<br>Desk
            </div>
            <svg width="34" height="34" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="dxcGrad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stop-color="#3B2371"/>
                        <stop offset="50%" stop-color="#D92B6B"/>
                        <stop offset="100%" stop-color="#FF6B00"/>
                    </linearGradient>
                </defs>
                <path d="M14 4H26V14H36V26H26V36H14V26H4V14H14V4Z" fill="url(#dxcGrad)"/>
            </svg>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_language_selector() -> str:
    """Renderiza o seletor PT/EN e devolve o idioma ativo."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = "PT"
    with st.popover(f"🌐 {st.session_state['lang']}"):
        if st.button("Português (PT)", width="stretch", key="set_lang_pt"):
            st.session_state["lang"] = "PT"
            st.rerun()
        if st.button("English (EN)", width="stretch", key="set_lang_en"):
            st.session_state["lang"] = "EN"
            st.rerun()
    return st.session_state["lang"]
