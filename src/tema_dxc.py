"""Identidade visual e textos da interface Human + Desk.

Camada de apresentação: traduções PT/EN, tema DXC (Claro/Escuro), logotipo
e seletor de idioma. Nenhuma regra de negócio, persistência ou chamada de
modelo vive aqui.
"""
import html

import streamlit as st

from src.textos import I18N  # noqa: F401  (reexportado: fonte unica dos rotulos)


def get_text(key: str) -> str:
    """Retorna o texto traduzido conforme o idioma ativo no session_state."""
    lang = st.session_state.get("lang", "PT")
    texto: str = I18N.get(lang, I18N["PT"]).get(key, key)
    return texto


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
        bg_active = "rgba(124, 58, 237, 0.38)"
        bd_active = "#A78BFA"
        ring_active = "rgba(167, 139, 250, 0.28)"
        fg_active = "#FFFFFF"
        radio_off_bg = "#1A1E2B"
        radio_off_bd = "#475569"
        icon_muted = "#CBD5E1"
        hover_pill_bg = "#252B3D"
        step_cta_bg = "linear-gradient(90deg, #4F2D7F 0%, #B82968 50%, #FF6B00 100%)"
        bg_cascata_1 = "#212638"
        bg_cascata_2 = "#151822"
        bd_cascata_1 = "rgba(124, 58, 237, 0.45)"
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
        bg_active = "#EDE9FE"
        bd_active = "#7C3AED"
        ring_active = "rgba(124, 58, 237, 0.20)"
        fg_active = "#4C1D95"
        radio_off_bg = "#FFFFFF"
        radio_off_bd = "#94A3B8"
        icon_muted = "#64748B"
        hover_pill_bg = "#F1F5F9"
        step_cta_bg = "#4F2D7F"
        bg_cascata_1 = "#F8F6FC"
        bg_cascata_2 = "#F8FAFC"
        bd_cascata_1 = "rgba(91, 44, 152, 0.28)"
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
        div[data-testid="stButtonGroup"] button:not([data-selected]):not([aria-checked="true"]):not([aria-pressed="true"]):hover,
        div[data-testid="stButtonGroup"] button:not([data-selected]):not([aria-checked="true"]):not([aria-pressed="true"])[data-hovered] {{
            background-color: {hover_pill_bg} !important;
            border-color: {bd_active} !important;
        }}
        div[data-testid="stButtonGroup"] button[data-selected],
        div[data-testid="stButtonGroup"] button[aria-checked="true"],
        div[data-testid="stButtonGroup"] button[aria-pressed="true"],
        div[data-testid="stButtonGroup"] button[data-testid*="Active"],
        button[kind="segmented_controlActive"],
        button[kind="pillsActive"],
        div[class*="st-key-btn_usar_ativo"] button {{
            background-color: {bg_active} !important;
            color: {fg_active} !important;
            border: 2px solid {bd_active} !important;
            box-shadow: 0 0 0 2px {ring_active} !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stButtonGroup"] button[data-selected] *,
        div[data-testid="stButtonGroup"] button[aria-checked="true"] *,
        div[data-testid="stButtonGroup"] button[aria-pressed="true"] *,
        div[data-testid="stButtonGroup"] button[data-testid*="Active"] *,
        button[kind="segmented_controlActive"] *,
        button[kind="pillsActive"] *,
        div[class*="st-key-btn_usar_ativo"] button * {{
            color: {fg_active} !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stPopover"] button {{
            min-width: 82px !important;
            white-space: nowrap !important;
        }}
        div[data-testid="stSelectbox"] div:has(> input),
        div[data-testid="stSelectbox"] div:has(> button[aria-label="Open"]) {{
            background-color: {bg_widget} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-testid="stSelectbox"] input {{
            background-color: transparent !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stSelectbox"] button[aria-label="Open"],
        div[data-testid="stSelectbox"] button[aria-label="Clear value"] {{
            background-color: transparent !important;
            color: {icon_muted} !important;
        }}
        div[data-testid="stSelectbox"] button[aria-label="Open"]:hover,
        div[data-testid="stSelectbox"] button[aria-label="Clear value"]:hover {{
            color: #7C3AED !important;
        }}
        div[data-testid="stSelectbox"] button[aria-label="Open"] svg,
        div[data-testid="stSelectbox"] button[aria-label="Clear value"] svg,
        div[data-testid="stSelectbox"] [data-testid="stSelectboxIcon"] svg {{
            fill: currentColor !important;
            color: inherit !important;
        }}
        [data-testid="stTooltipIcon"] svg,
        [data-testid="stTooltipHoverTarget"] svg {{
            fill: none !important;
            stroke: {icon_muted} !important;
            color: {icon_muted} !important;
        }}
        [data-testid="stTooltipIcon"]:hover svg,
        [data-testid="stTooltipHoverTarget"]:hover svg {{
            stroke: #7C3AED !important;
            color: #7C3AED !important;
        }}
        div[data-testid="stSelectboxVirtualDropdown"],
        div[data-testid="stSelectboxVirtualDropdown"] ul,
        div[data-testid="stSelectboxVirtualDropdown"] li,
        div[data-testid="stSelectboxVirtualDropdown"] [role="listbox"],
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"] {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-testid="stSelectboxVirtualDropdown"] [data-hovered] [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] [data-focused] [data-item-hl] {{
            background-color: {bg_active} !important;
            color: {fg_active} !important;
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
            fill: {icon_muted} !important;
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
        /* Bolinhas de radio harmonizadas nos modos Claro e Escuro */
        label[data-testid="stRadioOption"]:not([data-selected]):not(:has(input:checked)) > div > div:first-child,
        div[role="radiogroup"] label:not([data-selected]):not(:has(input:checked)) > div:first-child {{
            background-color: {radio_off_bg} !important;
            border: 1.5px solid {radio_off_bd} !important;
        }}
        label[data-testid="stRadioOption"]:not([data-selected]):not(:has(input:checked)):hover > div > div:first-child {{
            background-color: {hover_pill_bg} !important;
            border-color: {bd_active} !important;
        }}
        label[data-testid="stRadioOption"][data-selected] > div > div:first-child,
        label[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child,
        div[role="radiogroup"] label:has(input:checked) > div:first-child {{
            background-color: #7C3AED !important;
            border: 1.5px solid #7C3AED !important;
        }}
        label[data-testid="stRadioOption"][data-selected] > div > div:first-child > div,
        label[data-testid="stRadioOption"]:has(input:checked) > div > div:first-child > div,
        div[role="radiogroup"] label:has(input:checked) > div:first-child > div {{
            background-color: #FFFFFF !important;
        }}
        /* Alinhamento simétrico da fila + micro-feedback (deslocamento + seta) no item ativo */
        .st-key-fila_bento_card {{
            min-height: 440px;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label {{
            padding: 5px 10px;
            border-radius: 8px;
            border-left: 3px solid transparent;
            transition: padding-left 0.15s ease, background-color 0.15s ease;
            width: 100%;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label:has(input:checked),
        .st-key-fila_bento_card div[role="radiogroup"] label[data-selected] {{
            background-color: {bg_active} !important;
            border-left: 3px solid #7C3AED !important;
            padding-left: 15px !important;
            font-weight: 600 !important;
        }}
        .st-key-fila_bento_card div[role="radiogroup"] label:has(input:checked)::after,
        .st-key-fila_bento_card div[role="radiogroup"] label[data-selected]::after {{
            content: "→";
            margin-left: auto;
            color: {bd_active};
            font-weight: 700;
        }}
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        ul[role="listbox"],
        li[role="option"] {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stExpander"],
        div[data-testid="stExpander"] details,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary:focus,
        div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-testid="stExpander"] summary * {{
            color: {txt_main} !important;
        }}
        div[data-testid="stExpander"] summary:hover {{
            background-color: {bg_alert} !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stExpander"] summary svg {{
            color: {icon_muted} !important;
            fill: currentColor !important;
        }}
        div[data-testid="stTable"] > div {{
            border-color: {border_card} !important;
            background-color: {bg_card} !important;
        }}
        div[data-testid="stTable"] table {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
        }}
        div[data-testid="stTable"] thead th {{
            background-color: {bg_alert} !important;
            color: {txt_muted} !important;
            border-color: {border_card} !important;
            font-weight: 600 !important;
        }}
        div[data-testid="stTable"] tbody th,
        div[data-testid="stTable"] tbody td {{
            background-color: {bg_card} !important;
            color: {txt_main} !important;
            border-color: {border_card} !important;
        }}
        div[data-testid="stTable"] tbody th {{
            font-weight: 600 !important;
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
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }}
        @keyframes hpdPulse {{
            0%, 100% {{
                box-shadow: 0 0 0 0 rgba(217, 43, 107, 0.38), {shadow};
                border-color: rgba(217, 43, 107, 0.68);
            }}
            50% {{
                box-shadow: 0 0 0 5px rgba(255, 107, 0, 0.10), 0 0 18px rgba(217, 43, 107, 0.34);
                border-color: rgba(255, 107, 0, 0.85);
            }}
        }}
        .bento-kpi.pulse-alert {{
            animation: hpdPulse 2.2s ease-in-out infinite;
        }}
        .bento-kpi.kpi-selected {{
            border: 2px solid #7C3AED !important;
            box-shadow: 0 0 16px rgba(124, 58, 237, 0.24);
        }}
        .kpi-dot-new {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #FF6B00;
            box-shadow: 0 0 8px rgba(255, 107, 0, 0.85);
            margin-left: 6px;
            vertical-align: middle;
        }}
        .msg-sent-box {{
            background: {bg_quote};
            border-left: 3px solid #10B981 !important;
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 0 10px 10px 0;
            padding: 14px 16px;
            color: {txt_main};
            line-height: 1.55;
            white-space: pre-wrap;
        }}
        .st-key-caixa_resposta > div[data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-caixa_resposta"] {{
            border-color: rgba(124, 58, 237, 0.48) !important;
            box-shadow: 0 0 18px rgba(124, 58, 237, 0.14);
        }}
        .cascata-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .cascata-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 0.96rem;
            color: {txt_main};
        }}
        .cascata-counter {{
            font-size: 0.72rem;
            font-weight: 600;
            padding: 2px 9px;
            border-radius: 999px;
            background: {eyebrow_bg};
            color: {eyebrow_fg};
            border: 1px solid {eyebrow_bd};
            white-space: nowrap;
        }}
        .cascata-primary {{
            background: {bg_cascata_1};
            border: 1px solid {bd_cascata_1};
            border-left: 3px solid #7C3AED;
            border-radius: 10px;
            padding: 11px 14px;
            margin-bottom: 8px;
        }}
        .cascata-secondary {{
            background: {bg_cascata_2};
            border: 1px solid {border_card};
            border-left: 2px solid {txt_sub};
            border-radius: 8px;
            padding: 9px 12px;
            margin-bottom: 6px;
            margin-left: 8px;
        }}
        div[class*="st-key-cascata_box_"] {{
            background: {bg_cascata_1};
            border: 1px solid {bd_cascata_1} !important;
            border-left: 3px solid #7C3AED !important;
            border-radius: 10px !important;
            padding: 11px 14px !important;
            margin-bottom: 8px !important;
        }}
        div[class*="st-key-cascata_box_"] .cascata-box-inner {{
            margin-bottom: 8px;
        }}
        .cascata-item-top {{
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            justify-content: space-between;
            gap: 8px;
        }}
        .cascata-item-title {{
            font-weight: 600;
            font-size: 0.90rem;
            color: {txt_main};
            line-height: 1.4;
        }}
        .cascata-item-detail {{
            font-size: 0.82rem;
            color: {txt_muted};
            margin-top: 4px;
            line-height: 1.45;
        }}
        .cascata-badge {{
            font-size: 0.70rem;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 999px;
            background: {chip_bg};
            border: 1px solid {border_card};
            color: {txt_muted};
            white-space: nowrap;
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


def _definir_idioma(novo: str) -> None:
    """Atualiza o idioma e gira `_lang_seq` para fechar o popover no rerun."""
    st.session_state["lang"] = novo
    st.session_state["_lang_seq"] = int(st.session_state.get("_lang_seq", 0)) + 1


def render_language_selector() -> str:
    """Renderiza o seletor PT/EN e devolve o idioma ativo."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = "PT"
    idioma_antes = st.session_state["lang"]
    with st.popover(f"🌐 {idioma_antes}"):
        if st.button(
            "Português (PT)",
            width="stretch",
            key="set_lang_pt",
            on_click=_definir_idioma,
            args=("PT",),
        ):
            st.session_state["lang"] = "PT"
            if idioma_antes != "PT":
                st.session_state["_lang_seq"] = int(st.session_state.get("_lang_seq", 0)) + 1
                st.rerun()
        if st.button(
            "English (EN)",
            width="stretch",
            key="set_lang_en",
            on_click=_definir_idioma,
            args=("EN",),
        ):
            st.session_state["lang"] = "EN"
            if idioma_antes != "EN":
                st.session_state["_lang_seq"] = int(st.session_state.get("_lang_seq", 0)) + 1
                st.rerun()
    lang: str = st.session_state["lang"]
    return lang


def _avancar_cascata(state_key: str, total: int) -> None:
    """Revela o próximo item da lista progressiva até o limite total."""
    atual = int(st.session_state.get(state_key, 1))
    st.session_state[state_key] = min(atual + 1, total)


def _recolher_cascata(state_key: str) -> None:
    """Recolhe os níveis secundários, mantendo apenas o destaque principal."""
    st.session_state[state_key] = 1


def render_card_cascata(
    titulo: str,
    itens: list[dict],
    chave_unica: str,
    vazio: str = "Nenhum item disponível.",
    subtitulo: str | None = None,
    envolver_card: bool = True,
) -> None:
    """Renderiza um bloco com exibição progressiva em cascata (Design System DXC).

    Exibe cabeçalho com contador, nível 1 em destaque e revelação progressiva sob
    demanda dos itens secundários. Cada dict aceita `titulo`, `detalhe`, `badge`
    e `alerta` (todos opcionais exceto `titulo`).
    """
    state_key = f"cascata_visiveis_{chave_unica}"
    total = len(itens)
    lang = st.session_state.get("lang", "PT")
    min_visiveis = max([1] + [i + 1 for i, it in enumerate(itens) if it.get("button")]) if total > 0 else 0
    visiveis = min(max(int(st.session_state.get(state_key, min_visiveis)), min_visiveis), total) if total > 0 else 0
    if total > 0:
        contador = f"{visiveis} de {total}" if lang == "PT" else f"{visiveis} of {total}"
    else:
        contador = "Total: 0"

    def _render_corpo() -> None:
        st.markdown(
            f'<div class="cascata-header">'
            f'<span class="cascata-title">{html.escape(titulo)}</span>'
            f'<span class="cascata-counter">{html.escape(contador)}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        if subtitulo:
            st.caption(subtitulo)
        if total == 0:
            st.caption(vazio)
            return

        for idx, item in enumerate(itens[:visiveis]):
            classe = "cascata-primary" if idx == 0 else "cascata-secondary"
            item_titulo = html.escape(str(item.get("titulo", "")))
            item_badge = str(item.get("badge") or "").strip()
            item_detalhe = str(item.get("detalhe") or "").strip()
            badge_html = f'<span class="cascata-badge">{html.escape(item_badge)}</span>' if item_badge else ""
            detalhe_html = (
                f'<div class="cascata-item-detail">{html.escape(item_detalhe)}</div>'
                if item_detalhe
                else ""
            )
            _render_btn = item.get("button")
            if _render_btn:
                with st.container(key=f"cascata_box_{chave_unica}_{idx}"):
                    st.markdown(
                        f'<div class="cascata-box-inner">'
                        f'<div class="cascata-item-top">'
                        f'<span class="cascata-item-title">{item_titulo}</span>'
                        f"{badge_html}"
                        f"</div>"
                        f"{detalhe_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if item.get("alerta"):
                        st.warning(item["alerta"])
                    ativo_btn = bool(_render_btn.get("active"))
                    lbl_btn = _render_btn["label"]
                    if ativo_btn and not lbl_btn.startswith("✓"):
                        lbl_btn = f"✓ {lbl_btn}"
                    cnt_key = (
                        f"btn_usar_ativo_{_render_btn['key']}"
                        if ativo_btn
                        else f"btn_usar_padrao_{_render_btn['key']}"
                    )
                    with st.container(key=cnt_key):
                        st.button(
                            lbl_btn,
                            key=_render_btn["key"],
                            width="stretch",
                            on_click=_render_btn["on_click"],
                            args=_render_btn.get("args", ()),
                        )
            else:
                st.markdown(
                    f'<div class="{classe}">'
                    f'<div class="cascata-item-top">'
                    f'<span class="cascata-item-title">{item_titulo}</span>'
                    f"{badge_html}"
                    f"</div>"
                    f"{detalhe_html}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if item.get("alerta"):
                    st.warning(item["alerta"])

        if total > 1:
            lbl_next = "Mostrar próximo (+1) ↓" if lang == "PT" else "Show next (+1) ↓"
            lbl_reset = "Recolher ↑" if lang == "PT" else "Collapse ↑"
            if visiveis < total and visiveis > 1:
                with st.container(horizontal=True):
                    st.button(
                        lbl_next,
                        key=f"cascata_next_{chave_unica}",
                        width="stretch",
                        on_click=_avancar_cascata,
                        args=(state_key, total),
                    )
                    st.button(
                        lbl_reset,
                        key=f"cascata_reset_{chave_unica}",
                        width="stretch",
                        on_click=_recolher_cascata,
                        args=(state_key,),
                    )
            elif visiveis < total:
                st.button(
                    lbl_next,
                    key=f"cascata_next_{chave_unica}",
                    width="stretch",
                    on_click=_avancar_cascata,
                    args=(state_key, total),
                )
            else:
                st.button(
                    lbl_reset,
                    key=f"cascata_reset_{chave_unica}",
                    width="stretch",
                    on_click=_recolher_cascata,
                    args=(state_key,),
                )

    if envolver_card:
        with st.container(border=True):
            _render_corpo()
    else:
        _render_corpo()
