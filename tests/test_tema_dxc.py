"""Testes do módulo de apresentação DXC, sem subir servidor Streamlit."""
from unittest.mock import MagicMock, patch

from src import tema_dxc
from src.percepcao import LEITURAS

ANINHADOS = (
    "niveis",
    "decisoes",
    "intencoes",
    "sinais",
    "origens",
    "leituras",
    "hipoteses",
    "perguntas_hipotese",
    "acoes",
)


def _verificar_valores(bloco: dict, origem: str) -> None:
    """Valida recursivamente os blocos aninhados e as strings simples."""
    for chave, valor in bloco.items():
        caminho = f"{origem}.{chave}"
        if chave in ANINHADOS:
            assert isinstance(valor, dict) and valor, f"Bloco aninhado inválido em {caminho}"
            for subchave, texto in valor.items():
                assert isinstance(texto, str) and texto.strip(), f"Valor inválido em {caminho}.{subchave}"
        else:
            assert isinstance(valor, str) and valor.strip(), f"Valor inválido em {caminho}"


def test_paridade_chaves_pt_en():
    """Garante que todas as chaves existem em PT e EN, inclusive as aninhadas."""
    chaves_pt = set(tema_dxc.I18N["PT"])
    chaves_en = set(tema_dxc.I18N["EN"])

    assert chaves_pt, "Dicionário PT vazio"
    assert chaves_pt == chaves_en, f"Diferença entre chaves PT e EN: {chaves_pt ^ chaves_en}"

    for idioma in ("PT", "EN"):
        bloco = tema_dxc.I18N[idioma]
        for chave in ANINHADOS:
            assert set(bloco[chave]) == set(tema_dxc.I18N["PT"][chave]), f"Subchaves divergentes em {idioma}.{chave}"
        _verificar_valores(bloco, idioma)


def test_get_text_traducao_e_fallback():
    """Valida PT, EN, chave desconhecida e idioma ainda não inicializado."""
    with patch.object(tema_dxc.st, "session_state", {"lang": "PT"}):
        assert tema_dxc.get_text("nav_marina") == "Central de Atendimento"
        assert tema_dxc.get_text("chave_inexistente") == "chave_inexistente"

    with patch.object(tema_dxc.st, "session_state", {"lang": "EN"}):
        assert tema_dxc.get_text("nav_marina") == "Service Console"

    with patch.object(tema_dxc.st, "session_state", {}):
        assert tema_dxc.get_text("nav_rafael") == "Gestão e Qualidade"


def test_vocabulario_elegante_sem_termos_antigos():
    """Os rótulos visíveis usam o vocabulário aprovado, não os nomes técnicos antigos."""
    pt = tema_dxc.I18N["PT"]
    assert pt["perception"] == "Análise Contextual"
    assert pt["kpi_pending"] == "Em Fila"
    assert pt["kpi_high"] == "Prioridade Crítica"
    assert pt["kpi_done"] == "Finalizados"
    assert pt["queue"] == "Fila de Atendimento"
    textos_visiveis = " ".join(v for v in pt.values() if isinstance(v, str))
    for antigo in ("Camada", "Palpites", "Nenhuma delas", "Pendentes"):
        assert antigo not in textos_visiveis, f"Termo antigo ainda exibido: {antigo}"


def test_render_dxc_theme_claro_e_escuro():
    """Verifica a fonte Space Grotesk e as paletas DXC nos dois modos."""
    with patch.object(tema_dxc.st, "markdown") as mock_markdown:
        tema_dxc.render_dxc_theme(dark_mode=False)
        css_claro = mock_markdown.call_args[0][0]
        assert "Space Grotesk" in css_claro
        assert "fonts.googleapis.com/css2?family=Inter" in css_claro
        assert "#F8FAFC" in css_claro

        tema_dxc.render_dxc_theme(dark_mode=True)
        css_escuro = mock_markdown.call_args[0][0]
        assert "#0E1017" in css_escuro
        assert mock_markdown.call_args[1]["unsafe_allow_html"] is True


def test_render_dxc_theme_destaque_pills_e_controles_claro():
    """Garante seletores ativos de pills/radio/selectbox e contraste no Modo Claro."""
    with patch.object(tema_dxc.st, "markdown") as mock_markdown:
        tema_dxc.render_dxc_theme(dark_mode=False)
        css_claro = mock_markdown.call_args[0][0]
        for trecho in (
            "button[data-selected]",
            'button[aria-checked="true"]',
            'label[data-testid="stRadioOption"]:not([data-selected])',
            "#FFFFFF",
            "#94A3B8",
            'div[data-testid="stSelectbox"]',
            'button[aria-label="Open"]',
            "stSelectboxVirtualDropdown",
            "#64748B",
            'div[data-testid="stExpander"] summary',
            '[data-testid="stTooltipIcon"] svg',
            '[data-testid="stTooltipHoverTarget"] svg',
            "fill: none !important;",
            "stroke:",
            'div[data-testid="stTable"]',
        ):
            assert trecho in css_claro, f"Esperado no CSS claro: {trecho}"

        tema_dxc.render_dxc_theme(dark_mode=True)
        css_escuro = mock_markdown.call_args[0][0]
        for trecho in (
            "button[data-selected]",
            'button[aria-checked="true"]',
            "#A78BFA",
            'div[data-testid="stSelectbox"]',
            "stSelectboxVirtualDropdown",
            '[data-testid="stTooltipIcon"] svg',
            '[data-testid="stTooltipHoverTarget"] svg',
            "fill: none !important;",
            "stroke:",
            'div[data-testid="stTable"]',
        ):
            assert trecho in css_escuro, f"Esperado no CSS escuro: {trecho}"


def test_render_dxc_logo():
    """Garante o logotipo Human Desk e o SVG com o gradiente DXC."""
    with patch.object(tema_dxc.st, "markdown") as mock_markdown:
        tema_dxc.render_dxc_logo(dark_mode=True)
        html_logo = mock_markdown.call_args[0][0]
        assert "Human<br>Desk" in html_logo
        assert "<svg" in html_logo
        assert "dxcGrad" in html_logo
        assert mock_markdown.call_args[1]["unsafe_allow_html"] is True


def test_render_language_selector_alterna_idioma():
    """Simula o clique em EN e confirma a troca no session_state com rerun."""
    fake_state = {"lang": "PT"}
    mock_popover_ctx = MagicMock()
    mock_popover_ctx.__enter__.return_value = None
    mock_popover_ctx.__exit__.return_value = None

    with (
        patch.object(tema_dxc.st, "session_state", fake_state),
        patch.object(tema_dxc.st, "popover", return_value=mock_popover_ctx) as mock_popover,
        patch.object(tema_dxc.st, "button", side_effect=[False, True]),
        patch.object(tema_dxc.st, "rerun") as mock_rerun,
    ):
        idioma = tema_dxc.render_language_selector()

        mock_popover.assert_called_once_with("🌐 PT")
        assert fake_state["lang"] == "EN"
        assert idioma == "EN"
        mock_rerun.assert_called_once()


def _ctx_falso():
    ctx = MagicMock()
    ctx.__enter__.return_value = None
    ctx.__exit__.return_value = None
    return ctx


def test_render_card_cascata_vazio_e_item_unico():
    """Lista vazia mostra Total: 0; item único mostra 1 de 1 sem botões de cascata."""
    fake_state = {"lang": "PT"}
    with (
        patch.object(tema_dxc.st, "session_state", fake_state),
        patch.object(tema_dxc.st, "container", return_value=_ctx_falso()),
        patch.object(tema_dxc.st, "markdown") as mock_md,
        patch.object(tema_dxc.st, "caption") as mock_cap,
        patch.object(tema_dxc.st, "button") as mock_btn,
    ):
        tema_dxc.render_card_cascata("Histórico", [], "teste_vazio", vazio="Nada ainda.")
        assert "Total: 0" in mock_md.call_args[0][0]
        mock_cap.assert_called_with("Nada ainda.")
        mock_btn.assert_not_called()

        mock_md.reset_mock()
        mock_btn.reset_mock()
        tema_dxc.render_card_cascata(
            "Supervisão",
            [{"titulo": "Principal", "detalhe": "Detalhe", "badge": "Alta"}],
            "teste_unico",
        )
        html_saida = " ".join(c[0][0] for c in mock_md.call_args_list)
        assert "1 de 1" in html_saida
        assert "cascata-primary" in html_saida
        assert "Principal" in html_saida
        mock_btn.assert_not_called()


def test_render_card_cascata_revelacao_progressiva_e_recolhimento():
    """Avança nível a nível (1 -> 2 -> 3) e recolhe de volta para o destaque."""
    fake_state = {"lang": "PT"}
    itens = [
        {"titulo": "Item 1", "badge": "N1"},
        {"titulo": "Item 2", "detalhe": "Secundário"},
        {"titulo": "Item 3"},
    ]
    col1, col2 = _ctx_falso(), _ctx_falso()

    with (
        patch.object(tema_dxc.st, "session_state", fake_state),
        patch.object(tema_dxc.st, "container", return_value=_ctx_falso()),
        patch.object(tema_dxc.st, "columns", return_value=[col1, col2]),
        patch.object(tema_dxc.st, "markdown") as mock_md,
        patch.object(tema_dxc.st, "button") as mock_btn,
    ):
        # Estado inicial: 1 de 3 visível
        tema_dxc.render_card_cascata("Evidências", itens, "k3")
        html_1 = " ".join(c[0][0] for c in mock_md.call_args_list)
        assert "1 de 3" in html_1
        assert "Item 1" in html_1
        assert "Item 2" not in html_1 and "Item 3" not in html_1
        assert mock_btn.call_args[0][0] == "Mostrar próximo (+1) ↓"
        assert mock_btn.call_args[1]["key"] == "cascata_next_k3"

        # Avança para 2 de 3
        tema_dxc._avancar_cascata("cascata_visiveis_k3", 3)
        assert fake_state["cascata_visiveis_k3"] == 2
        mock_md.reset_mock()
        col1.button.reset_mock()
        col2.button.reset_mock()
        tema_dxc.render_card_cascata("Evidências", itens, "k3")
        html_2 = " ".join(c[0][0] for c in mock_md.call_args_list)
        assert "2 de 3" in html_2
        assert "cascata-secondary" in html_2
        assert "Item 2" in html_2 and "Item 3" not in html_2
        assert col1.button.call_args[0][0] == "Mostrar próximo (+1) ↓"
        assert col2.button.call_args[0][0] == "Recolher ↑"

        # Avança para 3 de 3
        tema_dxc._avancar_cascata("cascata_visiveis_k3", 3)
        assert fake_state["cascata_visiveis_k3"] == 3
        mock_md.reset_mock()
        mock_btn.reset_mock()
        tema_dxc.render_card_cascata("Evidências", itens, "k3")
        html_3 = " ".join(c[0][0] for c in mock_md.call_args_list)
        assert "3 de 3" in html_3 and "Item 3" in html_3
        assert mock_btn.call_args[0][0] == "Recolher ↑"
        assert mock_btn.call_args[1]["key"] == "cascata_reset_k3"

        # Recolhe de volta para 1
        tema_dxc._recolher_cascata("cascata_visiveis_k3")
        assert fake_state["cascata_visiveis_k3"] == 1


def test_render_card_cascata_escapa_html():
    """Garante escape de HTML malicioso em título, detalhe e badge."""
    fake_state = {"lang": "PT"}
    itens = [{"titulo": "<script>alert(1)</script>", "detalhe": "<b>x</b>", "badge": "<img src=x>"}]
    with (
        patch.object(tema_dxc.st, "session_state", fake_state),
        patch.object(tema_dxc.st, "markdown") as mock_md,
    ):
        tema_dxc.render_card_cascata("Segurança", itens, "xss", envolver_card=False)
        html_saida = " ".join(c[0][0] for c in mock_md.call_args_list)
        assert "<script>" not in html_saida
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_saida
        assert "&lt;b&gt;x&lt;/b&gt;" in html_saida
        assert "&lt;img src=x&gt;" in html_saida


def test_cobertura_blocos_traduzidos_percepcao_e_acoes():
    """Garante paridade entre LEITURAS, tipos de Palpite e ações de auditoria."""
    tipos_palpite = {"necessidade_nao_dita", "padrao", "risco_recorrencia"}
    acoes_db = {"urgencia_alterada", "decisao", "reabriu"}
    for idioma in ("PT", "EN"):
        bloco = tema_dxc.I18N[idioma]
        assert set(bloco["leituras"]) == set(LEITURAS)
        assert set(bloco["hipoteses"]) == tipos_palpite
        assert set(bloco["perguntas_hipotese"]) == tipos_palpite
        assert set(bloco["acoes"]) == acoes_db
