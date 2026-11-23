"""Painel Human + Desk (Streamlit). Rodar:  streamlit run app.py

Identidade visual inspirada na DXC (Space Grotesk, degradê roxo/magenta/laranja,
modo Claro/Escuro adaptativo, logotipo Human [+] Desk e seletor PT/EN).
A IA só sugere; aqui nada é enviado de verdade: toda decisão fica registrada na auditoria.
"""
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src import auditoria, repositorio
from src.calibracao import (LIMIAR_LIVRE, LIMIAR_RARA, MIN_DECISOES, aprovar_reducao, avaliar,
                            carregar_config, propor_reducao)
from src.config import carregar_env
from src.painel import (calibracao_triagem, carregar_historico, decisao_por_texto, gerar_simulado,
                        ids_decididos, leituras_do_item, metricas, montar_fila, rascunho_adaptado,
                        registrar_decisao)
from src.percepcao import LEITURAS
from src.redator import _PLACEHOLDER

RAIZ = Path(__file__).resolve().parent
LOG = RAIZ / "data" / "painel_log.jsonl"
LOG_SIM = RAIZ / "data" / "painel_simulado.jsonl"
CONFIG = RAIZ / "data" / "calibracao_config.json"

# Cria human_desk.db na raiz do projeto e reconcilia decisões antigas do JSONL.
repositorio.init_db(concluidos=ids_decididos(auditoria.ler(LOG)))

COR = {"alta": "🔴", "media": "🟠", "baixa": "🟢"}
CORES_DECISAO = alt.Scale(
    domain=["Aprovou", "Editou", "Rejeitou", "Approved", "Edited", "Rejected"],
    range=["#10B981", "#7C3AED", "#F43F5E", "#10B981", "#7C3AED", "#F43F5E"],
)
DESTAQUE_ROXO = "#7C3AED"
DESTAQUE_LARANJA = "#FF6B00"

UI = {
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

carregar_env(RAIZ / ".env")
st.set_page_config(page_title="Human + Desk", page_icon="💠", layout="wide", initial_sidebar_state="expanded")


def _aplicar_tema(escuro: bool) -> None:
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
        bg_active = "rgba(124, 58, 237, 0.25)"
        fg_active = "#F8FAFC"
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
        bg_active = "rgba(91, 44, 152, 0.12)"
        fg_active = "#4F2D7F"
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
            background: transparent !important;
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
        div[data-testid="stButtonGroup"] button[aria-pressed="true"],
        button[kind="segmented_controlActive"],
        button[kind="pillsActive"] {{
            background-color: {bg_active} !important;
            color: {fg_active} !important;
            border: 1px solid #7C3AED !important;
        }}
        div[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
        button[kind="segmented_controlActive"] *,
        button[kind="pillsActive"] * {{
            color: {fg_active} !important;
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
        div[data-baseweb="select"] * {{
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
        div[data-testid="stAlert"] {{
            background-color: {bg_side} !important;
            border: 1px solid {border_card} !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stAlert"] * {{
            color: {txt_main} !important;
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
            min-height: 82px;
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def _estilizar_grafico(chart: alt.Chart, escuro: bool = True) -> alt.Chart:
    lbl = "#CBD5E1" if escuro else "#334155"
    tit = "#94A3B8" if escuro else "#475569"
    grd = "rgba(148, 163, 184, 0.12)" if escuro else "rgba(15, 23, 42, 0.08)"
    dom = "rgba(148, 163, 184, 0.25)" if escuro else "rgba(15, 23, 42, 0.18)"
    return (
        chart.configure_view(strokeWidth=0, fill="transparent")
        .configure(background="transparent")
        .configure_axis(labelColor=lbl, titleColor=tit, gridColor=grd, domainColor=dom)
        .configure_legend(labelColor=lbl, titleColor=tit)
    )


def _nome_sinal(sinal: str, txt: dict) -> str:
    if sinal.startswith("historico:"):
        return f"Histórico ({sinal.split(':', 1)[1]})"
    return txt["sinais"].get(sinal, sinal.replace("_", " ").capitalize())


@st.cache_data(show_spinner="Montando a fila com o adaptador escolhido…")
def fila_base(provider: str = "regras", model: str = ""):
    chamados = json.loads((RAIZ / "data" / "chamados_simulados.json").read_text(encoding="utf-8"))["chamados"]
    hist = carregar_historico(RAIZ / "data" / "historico_simulado.json")
    return montar_fila(chamados, hist, provider=provider, model=model or None)


def _ir_para_camada(item_id: str, destino: str) -> None:
    estados = st.session_state.setdefault("estado_chamados", {})
    if item_id in estados:
        estados[item_id]["viu_chamado"] = True
        estados[item_id]["camada"] = destino
    st.session_state[f"camada_{item_id}"] = destino


def _registrar_urgencia_ui(item_id: str, agente: str) -> None:
    """Callback do Passo 2: grava urgência, agente e timestamp na hora."""
    urgencia = st.session_state.get(f"urg_ui_{item_id}")
    if urgencia:
        repositorio.registrar_urgencia(item_id, urgencia, agente)


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
            "textos": {},
        }
        st.session_state.setdefault(f"camada_{item.id}", estados[item.id]["camada"])
    return estados[item.id]


def _barra_idioma() -> str:
    if "lang" not in st.session_state:
        st.session_state.lang = "PT"
    _, col_lang = st.columns([9.4, 1.6])
    with col_lang:
        with st.popover(f"🌐 {st.session_state.lang}"):
            if st.button("Português (PT)", width="stretch", key="set_lang_pt"):
                st.session_state.lang = "PT"
                st.rerun()
            if st.button("English (EN)", width="stretch", key="set_lang_en"):
                st.session_state.lang = "EN"
                st.rerun()
    return st.session_state.lang


def tela_marina(provider: str, txt: dict, agente: str = "Marina"):
    itens = fila_base(provider, os.getenv("GEMINI_MODEL", ""))
    estado_db = repositorio.estado(repositorio.DATASET_FILA)
    feitos = repositorio.ids_concluidos(repositorio.DATASET_FILA)
    fila_completa = [i for i in itens if i.id not in feitos]

    def _urgencia_efetiva(item) -> str:
        """Urgência confirmada pela analista prevalece sobre a sugestão da IA."""
        return estado_db.get(item.id, {}).get("urgencia_confirmada") or item.triagem.urgencia

    qtd_alta = sum(1 for i in fila_completa if _urgencia_efetiva(i) == "alta")
    pct_prog = int(round((len(feitos) / len(itens)) * 100)) if itens else 0

    h_tit, k1, k2, k3 = st.columns([2.2, 1, 1, 1], gap="medium")
    with h_tit:
        st.markdown(f'<span class="hpd-eyebrow">{txt["eyebrow_marina"]}</span>', unsafe_allow_html=True)
        st.title(txt["title_marina"])
    with k1:
        st.markdown(
            f'<div class="bento-kpi"><div class="bento-kpi-label">{txt["kpi_pending"]}</div>'
            f'<div class="bento-kpi-val">{len(fila_completa)}</div>'
            f'<div class="bento-kpi-sub">{txt["kpi_of_queue"].format(n=len(itens))}</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="bento-kpi"><div class="bento-kpi-label">{txt["kpi_high"]}</div>'
            f'<div class="bento-kpi-val">{qtd_alta}</div>'
            f'<div class="bento-kpi-sub">{txt["kpi_priority"]}</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f'<div class="bento-kpi"><div class="bento-kpi-label">{txt["kpi_done"]}</div>'
            f'<div class="bento-kpi-val">{pct_prog}%</div>'
            f'<div class="bento-kpi-sub">{txt["kpi_registered"].format(n=len(feitos))}</div></div>',
            unsafe_allow_html=True,
        )

    if not fila_completa:
        st.success(txt["queue_done"])
        return

    niveis_txt = txt["niveis"]
    int_txt = txt["intencoes"]
    orig_txt = txt["origens"]

    esq, dir_ = st.columns([1.0, 2.3], gap="large")

    with esq:
        with st.container(border=True):
            st.markdown(f"##### {txt['queue']}")
            filtro = st.pills(
                "Filtrar",
                options=["todas", "alta", "media", "baixa"],
                default="todas",
                format_func=lambda k: txt["all"] if k == "todas" else f"{COR[k]} {niveis_txt[k]}",
                label_visibility="collapsed",
                key="filtro_urgencia",
            )
            fila = fila_completa if filtro in (None, "todas") else [i for i in fila_completa if _urgencia_efetiva(i) == filtro]
            if not fila:
                st.info(txt["empty_filter"])
                return
            rotulos = {
                i.id: f"{COR[_urgencia_efetiva(i)]} {i.id} · {int_txt.get(i.triagem.intencao, i.triagem.intencao)}"
                for i in fila
            }
            escolhido = st.radio(
                "Chamado",
                list(rotulos),
                format_func=rotulos.get,
                label_visibility="collapsed",
            )

    item = next(i for i in fila if i.id == escolhido)
    t = item.triagem
    modelo_atual = os.getenv("GEMINI_MODEL", "")
    estado = _estado_item(item)

    if "cache_rascunhos" not in st.session_state:
        st.session_state.cache_rascunhos = {}
    leitura_atual = estado["leitura"]
    rascunho_atual, origem_rascunho = rascunho_adaptado(
        item, leitura_atual, provider, modelo_atual, st.session_state.cache_rascunhos,
    )
    chave_txt = leitura_atual or "nenhuma"
    texto_atual = estado["textos"].get(chave_txt, rascunho_atual.texto)
    pend = _PLACEHOLDER.findall(texto_atual)
    urgencia_atual = estado["urgencia"]

    tem_alerta = any(p.sugere_subir_urgencia for p in item.palpites)
    st_chamado = "✓" if estado["viu_chamado"] else ("!" if tem_alerta else "●")
    st_decisao = "✓" if urgencia_atual is not None else "●"
    st_resposta = "✓" if (urgencia_atual is not None and not pend) else "●"

    rotulos_camada = {
        "chamado": f"{txt['layer_1']} {st_chamado}",
        "decisao": f"{txt['layer_2']} {st_decisao}",
        "resposta": f"{txt['layer_3']} {st_resposta}",
    }

    with dir_:
        st.markdown(
            f"#### `{item.id}` · {int_txt.get(t.intencao, t.intencao)}  "
            f"&nbsp;·&nbsp; {COR[t.urgencia]} **{niveis_txt[t.urgencia]}** ({t.pontuacao_urgencia} pts)"
        )
        st.caption(
            f"{txt['triage']}: **{orig_txt.get(item.origem_triagem, item.origem_triagem)}** · "
            f"{txt['draft']}: **{orig_txt.get(origem_rascunho, origem_rascunho)}** · "
            f"{txt['confidence']}: **{niveis_txt.get(t.confianca, t.confianca)}**"
        )

        cls_1, dot_1, txt_1 = (
            ("done", "dot-done", txt["chip_1_done"]) if estado["viu_chamado"]
            else (("alert", "dot-alert", txt["chip_1_alert"]) if tem_alerta
                  else ("pending", "dot-pending", txt["chip_1_pend"]))
        )
        cls_2, dot_2, txt_2 = (
            ("done", "dot-done", txt["chip_2_done"]) if urgencia_atual is not None
            else ("pending", "dot-pending", txt["chip_2_pend"])
        )
        cls_3, dot_3, txt_3 = (
            ("done", "dot-done", txt["chip_3_done"]) if (urgencia_atual is not None and not pend)
            else ("pending", "dot-pending", txt["chip_3_pend"])
        )
        st.markdown(
            f'<div class="layer-strip">'
            f'<span class="layer-chip {cls_1}"><span class="dot {dot_1}"></span>{txt_1}</span>'
            f'<span class="layer-chip {cls_2}"><span class="dot {dot_2}"></span>{txt_2}</span>'
            f'<span class="layer-chip {cls_3}"><span class="dot {dot_3}"></span>{txt_3}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        camada_sel = st.segmented_control(
            "Camadas",
            options=["chamado", "decisao", "resposta"],
            format_func=rotulos_camada.get,
            label_visibility="collapsed",
            key=f"camada_{item.id}",
        )
        if camada_sel is not None:
            estado["camada"] = camada_sel
        camada = estado["camada"]

        if camada == "chamado":
            with st.container(border=True):
                st.markdown(f'<span class="hpd-eyebrow">{txt["lgpd_badge"]}</span>', unsafe_allow_html=True)
                st.markdown(f"> {item.texto_mascarado}")

            c_ev, c_pa = st.columns(2, gap="medium")
            with c_ev:
                with st.container(border=True):
                    st.markdown(f"**{txt['evidences']}**")
                    motivos = t.motivos_urgencia + t.motivos_intencao
                    if motivos:
                        for m in motivos:
                            st.markdown(f"- **{_nome_sinal(m.sinal, txt)}:** “{m.trecho}”")
                    else:
                        st.caption(txt["no_evidences"])
            with c_pa:
                with st.container(border=True):
                    qtd_p = len(item.palpites)
                    rotulo_p = txt["hyp_one"] if qtd_p == 1 else txt["hyp_many"]
                    st.markdown(f"**{txt['perception']} ({qtd_p} {rotulo_p})**")
                    if not item.palpites:
                        st.caption(txt["no_guesses"])
                    for p in item.palpites:
                        st.markdown(f"- {p.hipotese} *({niveis_txt.get(p.confianca, p.confianca)})*")
                        st.caption(f"{txt['confirm_q']} {p.pergunta_confirmacao}")
                        if p.sugere_subir_urgencia:
                            st.warning(txt["raise_warn"])

            st.button(
                txt["go_2"],
                type="primary",
                width="stretch",
                key=f"go2_{item.id}",
                on_click=_ir_para_camada,
                args=(item.id, "decisao"),
            )

        elif camada == "decisao":
            estado["viu_chamado"] = True
            with st.container(border=True):
                if item.palpites:
                    opcoes = leituras_do_item(item, auditoria.ler(LOG), carregar_config(CONFIG)) + ["nenhuma"]
                    default_l = leitura_atual if leitura_atual in opcoes else "nenhuma"
                    leitura_sel = st.pills(
                        txt["reading_lbl"],
                        options=opcoes,
                        default=default_l,
                        format_func=lambda k: LEITURAS.get(k, txt["none_opt"]),
                        key=f"leit_ui_{item.id}",
                    )
                    if leitura_sel == "nenhuma":
                        estado["leitura"] = None
                        estado["leitura_livre"] = st.text_input(
                            txt["free_reading"],
                            value=estado["leitura_livre"],
                            key=f"livre_ui_{item.id}",
                        )
                    else:
                        estado["leitura"] = leitura_sel
                        estado["leitura_livre"] = ""

                urg_sel = st.pills(
                    txt["urg_lbl"].format(sug=niveis_txt[t.urgencia]),
                    options=["alta", "media", "baixa"],
                    default=urgencia_atual,
                    format_func=lambda k: f"{COR[k]} {niveis_txt[k]}",
                    key=f"urg_ui_{item.id}",
                    on_change=_registrar_urgencia_ui,
                    args=(item.id, agente),
                )
                estado["urgencia"] = urg_sel

                if urg_sel is None:
                    st.info(txt["urg_hint"])

                b1, b2 = st.columns(2)
                b1.button(
                    txt["back_1"],
                    width="stretch",
                    key=f"back1_{item.id}",
                    on_click=_ir_para_camada,
                    args=(item.id, "chamado"),
                )
                b2.button(
                    txt["go_3"],
                    type="primary",
                    width="stretch",
                    key=f"go3_{item.id}",
                    on_click=_ir_para_camada,
                    args=(item.id, "resposta"),
                )

        else:
            estado["viu_chamado"] = True
            with st.container(border=True):
                texto = st.text_area(
                    txt["draft_lbl"],
                    value=texto_atual,
                    height=180,
                    key=f"txt_ui_{item.id}_{chave_txt}",
                )
                estado["textos"][chave_txt] = texto
                pend = _PLACEHOLDER.findall(texto)

                faltas = []
                if estado["urgencia"] is None:
                    faltas.append(txt["need_urg"])
                if pend:
                    faltas.append(txt["need_brack"] + "; ".join(pend))

                if faltas:
                    st.warning(txt["pending_banner"] + " | ".join(faltas) + ".")
                else:
                    st.success(txt["ready_banner"])

                c1, c2 = st.columns(2)
                if c1.button(
                    txt["btn_approve"],
                    disabled=bool(pend) or estado["urgencia"] is None,
                    type="primary",
                    width="stretch",
                    key=f"ok_{item.id}",
                ):
                    decisao = decisao_por_texto(rascunho_atual.texto, texto)
                    registrar_decisao(
                        LOG, item, decisao, texto,
                        estado["leitura"], estado["leitura_livre"] or None, estado["urgencia"], False,
                        origem_triagem=item.origem_triagem, origem_rascunho=origem_rascunho,
                    )
                    repositorio.registrar_decisao(
                        item.id, decisao, texto, agente,
                        detalhes={"origem_triagem": item.origem_triagem,
                                  "origem_rascunho": origem_rascunho,
                                  "urgencia_analista": estado["urgencia"]},
                    )
                    st.session_state["estado_chamados"].pop(item.id, None)
                    st.rerun()
                if c2.button(
                    txt["btn_reject"],
                    disabled=estado["urgencia"] is None,
                    width="stretch",
                    key=f"rej_{item.id}",
                ):
                    registrar_decisao(
                        LOG, item, "rejeitou", None,
                        estado["leitura"], estado["leitura_livre"] or None, estado["urgencia"], False,
                        origem_triagem=item.origem_triagem, origem_rascunho=origem_rascunho,
                    )
                    repositorio.registrar_decisao(
                        item.id, "rejeitou", None, agente,
                        detalhes={"origem_triagem": item.origem_triagem,
                                  "origem_rascunho": origem_rascunho,
                                  "urgencia_analista": estado["urgencia"]},
                    )
                    st.session_state["estado_chamados"].pop(item.id, None)
                    st.rerun()


def tela_rafael(provider: str, escuro: bool, txt: dict):
    niveis_txt = txt["niveis"]
    dec_txt = txt["decisoes"]

    st.markdown(f'<span class="hpd-eyebrow">{txt["eyebrow_rafael"]}</span>', unsafe_allow_html=True)
    st.title(txt["title_rafael"])
    st.caption(txt["sub_rafael"])

    t1, t2 = st.columns([2, 1])
    with t1:
        usar_sim = st.toggle(txt["sim_toggle"], value=not LOG.exists())
    with t2:
        if usar_sim and st.button(txt["sim_btn"], width="stretch"):
            gerar_simulado(LOG_SIM, fila_base(provider, os.getenv("GEMINI_MODEL", "")))

    if usar_sim:
        st.warning(txt["sim_warn"])
        eventos = auditoria.ler(LOG_SIM)
    else:
        eventos = auditoria.ler(LOG)

    with st.container(border=True):
        st.subheader(txt["db_title"])
        st.caption(txt["db_caption"])
        concluidos_db = {
            cid: tk for cid, tk in repositorio.estado(repositorio.DATASET_FILA).items()
            if tk["status"] == "concluido"
        }
        if not concluidos_db:
            st.info(txt["db_empty"])
        else:
            rotulos_db = {
                cid: f"{cid} · {tk['resolvido_por']} · {(tk['resolvido_em'] or '')[:16]}"
                for cid, tk in concluidos_db.items()
            }
            alvo = st.selectbox(
                txt["db_reopen_select"], list(rotulos_db),
                format_func=rotulos_db.get, key="db_reopen_alvo",
            )
            if st.button(txt["db_reopen_btn"], key="db_reopen_confirmar"):
                repositorio.reabrir(alvo, "Rafael")
                st.toast(txt["db_reopen_done"])
                st.rerun()
        eventos_db = repositorio.eventos()
        if eventos_db:
            st.caption(txt["db_events"])
            for ev in eventos_db[-5:]:
                st.markdown(
                    f"`{ev['criado_em'][:19]}` · **{ev['chamado_id']}** · "
                    f"{ev['acao']} · {ev['agente']}"
                )

    m = metricas(eventos)
    if m["total"] == 0:
        st.info(txt["no_decisions"])
        return

    c = st.columns(4)
    c[0].metric("Decisões", m["total"])
    c[1].metric("Editadas", f"{m['taxa_edicao']:.0%}")
    c[2].metric("Rejeitadas", f"{m['taxa_rejeicao']:.0%}")
    c[3].metric("Recorrentes", m["recorrentes"])

    aba_geral, aba_leituras, aba_urgencia = st.tabs([
        txt["tab_overview"],
        txt["tab_readings"],
        txt["tab_urgency"],
    ])

    ordem_dec = [dec_txt["aprovou"], dec_txt["editou"], dec_txt["rejeitou"]]
    ordem_niv = [niveis_txt["alta"], niveis_txt["media"], niveis_txt["baixa"]]

    with aba_geral:
        g1, g2 = st.columns(2, gap="large")
        with g1:
            with st.container(border=True):
                st.markdown("#### Decisões da analista")
                df_dec = pd.DataFrame([{"Decisão": dec_txt[k], "Chamados": v} for k, v in m["decisoes"].items()])
                chart_dec = (
                    alt.Chart(df_dec)
                    .mark_bar(cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("Chamados:Q", title="Chamados"),
                        y=alt.Y("Decisão:N", sort=ordem_dec, title=None),
                        color=alt.Color("Decisão:N", scale=CORES_DECISAO, legend=None),
                        tooltip=["Decisão", "Chamados"],
                    )
                    .properties(height=180)
                )
                st.altair_chart(_estilizar_grafico(chart_dec, escuro), width="stretch")

        with g2:
            with st.container(border=True):
                st.markdown("#### Decisão por urgência")
                linhas_u = [
                    {"Urgência": niveis_txt[u], "Decisão": dec_txt[d], "Chamados": qtd}
                    for u in ("alta", "media", "baixa")
                    for d, qtd in m["por_urgencia"][u].items()
                ]
                chart_u = (
                    alt.Chart(pd.DataFrame(linhas_u))
                    .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .encode(
                        x=alt.X("Urgência:N", sort=ordem_niv, axis=alt.Axis(labelAngle=0), title=None),
                        y=alt.Y("Chamados:Q", title="Chamados"),
                        color=alt.Color("Decisão:N", scale=CORES_DECISAO),
                        tooltip=["Urgência", "Decisão", "Chamados"],
                    )
                    .properties(height=180)
                )
                st.altair_chart(_estilizar_grafico(chart_u, escuro), width="stretch")

        g3, g4 = st.columns(2, gap="large")
        with g3:
            with st.container(border=True):
                st.markdown("#### Decisões por dia")
                df_dia = pd.DataFrame([{"Dia": k, "Decisões": v} for k, v in m["por_dia"].items()])
                chart_dia = (
                    alt.Chart(df_dia)
                    .mark_line(point=True, color=DESTAQUE_LARANJA, strokeWidth=2.5)
                    .encode(
                        x=alt.X("Dia:N", axis=alt.Axis(labelAngle=-25), title=None),
                        y=alt.Y("Decisões:Q", title="Decisões"),
                        tooltip=["Dia", "Decisões"],
                    )
                    .properties(height=210)
                )
                st.altair_chart(_estilizar_grafico(chart_dia, escuro), width="stretch")

        with g4:
            with st.container(border=True):
                st.markdown("#### Leituras escolhidas")
                if m["leituras"]:
                    df_l = pd.DataFrame([{"Leitura": LEITURAS[k], "Vezes": v} for k, v in m["leituras"].items()])
                    chart_l = (
                        alt.Chart(df_l)
                        .mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
                        .encode(
                            x=alt.X("Vezes:Q", title="Vezes"),
                            y=alt.Y("Leitura:N", sort="-x", title=None, axis=alt.Axis(labelLimit=240)),
                            tooltip=["Leitura", "Vezes"],
                        )
                        .properties(height=210)
                    )
                    st.altair_chart(_estilizar_grafico(chart_l, escuro), width="stretch")
                    st.caption(f"{m['leituras_livres']} vez(es) a analista escreveu a própria leitura.")
                else:
                    st.caption("Nenhuma leitura registrada ainda.")

        st.caption("Poucas decisões = poucos dados: leia estes gráficos como indícios, não como conclusões.")

    with aba_leituras:
        config = carregar_config(CONFIG)
        a = avaliar(eventos, config["ativas"])
        st.progress(
            min(1.0, a["respostas"] / MIN_DECISOES),
            text=f"{a['respostas']} de {MIN_DECISOES} respostas necessárias para propor mudanças na lista",
        )
        if a["respostas"]:
            df_cal = pd.DataFrame([{"Leitura": LEITURAS[k], "Uso": v} for k, v in a["uso"].items()])
            chart_cal = (
                alt.Chart(df_cal)
                .mark_bar(cornerRadiusEnd=4, color=DESTAQUE_ROXO)
                .encode(
                    x=alt.X("Uso:Q", axis=alt.Axis(format="%"), title="Participação nas respostas"),
                    y=alt.Y("Leitura:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                    tooltip=[alt.Tooltip("Leitura:N"), alt.Tooltip("Uso:Q", format=".1%")],
                )
                .properties(height=220)
            )
            st.altair_chart(_estilizar_grafico(chart_cal, escuro), width="stretch")
            st.caption(
                f"Leitura própria escrita pela analista: {a['share_livre']:.0%} "
                f"(acima de {LIMIAR_LIVRE:.0%} a lista não é reduzida). "
                f"Uma leitura só é proposta para sair se ficar abaixo de {LIMIAR_RARA:.0%}."
            )
        props, explicacao = propor_reducao(eventos, config)
        st.info(explicacao)
        for pr in props:
            st.markdown(f"**Proposta:** retirar “{LEITURAS[pr.leitura]}”. {pr.motivo}")
            if usar_sim:
                st.button("Aprovar (indisponível com dados simulados)", disabled=True, key="ap_sim")
            elif st.button("Aprovar a retirada (gestor)", key=f"ap_{pr.leitura}", type="primary"):
                aprovar_reducao(CONFIG, pr.leitura, "Rafael", LOG)
                st.rerun()
        st.caption("Leituras ativas hoje: " + ", ".join(LEITURAS[k] for k in config["ativas"]))

    with aba_urgencia:
        ct = calibracao_triagem(eventos)
        if ct["n"] == 0:
            st.info("Ainda não há urgências confirmadas pela analista.")
        else:
            k = st.columns(3)
            k[0].metric("Concordância IA × analista", f"{ct['concordancia']:.0%}")
            k[1].metric("Analista achou MAIS urgente", ct["subiu"], help="Erro mais crítico: a IA subestimou.")
            k[2].metric("Analista achou MENOS urgente", ct["desceu"])
            if ct["n"] < MIN_DECISOES:
                st.info(f"Informação insuficiente para concluir: {ct['n']} de {MIN_DECISOES} respostas.")

            u1, u2 = st.columns(2, gap="large")
            with u1:
                with st.container(border=True):
                    st.markdown("#### Concordância por confiança da IA")
                    linhas_c = [
                        {
                            "Confiança": niveis_txt[nivel],
                            "Respostas": ct["por_confianca"][nivel]["n"],
                            "Concordou": ct["por_confianca"][nivel]["concordou"],
                            "Taxa": ct["por_confianca"][nivel]["taxa"],
                        }
                        for nivel in ("baixa", "media", "alta")
                        if nivel in ct["por_confianca"]
                    ]
                    df_c = pd.DataFrame(linhas_c)
                    if not df_c.empty:
                        chart_c = (
                            alt.Chart(df_c)
                            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=DESTAQUE_LARANJA)
                            .encode(
                                x=alt.X("Confiança:N", sort=[niveis_txt["baixa"], niveis_txt["media"], niveis_txt["alta"]],
                                        axis=alt.Axis(labelAngle=0), title=None),
                                y=alt.Y("Taxa:Q", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%"), title="Concordância"),
                                tooltip=["Confiança", "Respostas", "Concordou", alt.Tooltip("Taxa:Q", format=".1%")],
                            )
                            .properties(height=190)
                        )
                        st.altair_chart(_estilizar_grafico(chart_c, escuro), width="stretch")
                        df_tab = df_c.copy()
                        df_tab["Taxa"] = df_tab["Taxa"].map(lambda x: f"{x:.1%}")
                        st.dataframe(df_tab, hide_index=True, width="stretch")

            with u2:
                with st.container(border=True):
                    st.markdown("#### Matriz (IA sugeriu × Analista decidiu)")
                    df_m = pd.DataFrame(ct["matriz"]).T
                    df_m.index = [niveis_txt[i] for i in df_m.index]
                    df_m.columns = [niveis_txt[c_] for c_ in df_m.columns]
                    df_m.index.name = "IA sugeriu"
                    st.dataframe(df_m, width="stretch")
                    st.caption("A analista escolhe a urgência explicitamente (sem pré-seleção) para evitar concordância automática.")

    st.divider()
    with st.expander("Visão futura (desligado no MVP): Portão de Autonomia"):
        st.info(
            "No MVP (v2), todas as decisões permanecem 100% humanas. O módulo `src/autonomia.py` "
            "(portão estatístico Clopper-Pearson) permanece guardado no repositório para fases futuras, "
            "quando houver volume real de chamados e modelos treinados."
        )


lang = _barra_idioma()
txt = UI[lang]

with st.sidebar:
    tema_sel = st.segmented_control(
        txt["appearance"],
        options=["Escuro", "Claro"],
        default="Escuro",
        format_func=lambda k: txt["dark"] if k == "Escuro" else txt["light"],
        key="tema_ui",
    )
    modo_escuro = tema_sel != "Claro"
    _aplicar_tema(modo_escuro)

    logo_color = "#F8FAFC" if modo_escuro else "#0F172A"
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

    pagina = st.radio(
        txt["nav_label"],
        ["marina", "rafael"],
        format_func=lambda k: txt["nav_marina"] if k == "marina" else txt["nav_rafael"],
    )
    st.divider()
    provider = st.selectbox(
        txt["adapter"],
        ["regras", "gemini"],
        index=0,
        format_func=lambda k: txt["rules_opt"] if k == "regras" else txt["gemini_opt"],
        help="Regras é determinístico e funciona offline. Gemini envia o texto já mascarado à API.",
    )
    if provider == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            st.warning("Sem GEMINI_API_KEY no .env: o painel usará regras.")
        if not os.getenv("GEMINI_MODEL"):
            st.warning("Defina GEMINI_MODEL no .env para escolher o modelo.")
        st.caption("Modelo lido do .env; para trocar, edite o arquivo e recarregue.")

    st.divider()
    st.caption(txt["footer"])

if pagina == "marina":
    tela_marina(provider, txt, agente="Marina")
else:
    tela_rafael(provider, escuro=modo_escuro, txt=txt)
