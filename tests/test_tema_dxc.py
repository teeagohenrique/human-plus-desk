"""Testes do módulo de apresentação DXC, sem subir servidor Streamlit."""
from unittest.mock import MagicMock, patch

from src import tema_dxc


ANINHADOS = ("niveis", "decisoes", "intencoes", "sinais", "origens")


def _verificar_valores(bloco: dict, origem: str) -> None:
    """Valida recursivamente os 5 blocos aninhados e as strings simples."""
    for chave, valor in bloco.items():
        caminho = f"{origem}.{chave}"
        if chave in ANINHADOS:
            assert isinstance(valor, dict) and valor, f"Bloco aninhado inválido em {caminho}"
            for subchave, texto in valor.items():
                assert isinstance(texto, str) and texto.strip(), f"Valor inválido em {caminho}.{subchave}"
        else:
            assert isinstance(valor, str) and valor.strip(), f"Valor inválido em {caminho}"


def test_paridade_chaves_pt_en():
    """Garante que todas as 81 chaves existem em PT e EN, inclusive as aninhadas."""
    chaves_pt = set(tema_dxc.I18N["PT"])
    chaves_en = set(tema_dxc.I18N["EN"])

    assert len(chaves_pt) == 81
    assert chaves_pt == chaves_en, f"Diferença entre chaves PT e EN: {chaves_pt ^ chaves_en}"

    for idioma in ("PT", "EN"):
        bloco = tema_dxc.I18N[idioma]
        for chave in ANINHADOS:
            assert set(bloco[chave]) == set(tema_dxc.I18N["PT"][chave]), f"Subchaves divergentes em {idioma}.{chave}"
        _verificar_valores(bloco, idioma)


def test_get_text_traducao_e_fallback():
    """Valida PT, EN, chave desconhecida e idioma ainda não inicializado."""
    with patch.object(tema_dxc.st, "session_state", {"lang": "PT"}):
        assert tema_dxc.get_text("nav_marina") == "Painel da Marina"
        assert tema_dxc.get_text("chave_inexistente") == "chave_inexistente"

    with patch.object(tema_dxc.st, "session_state", {"lang": "EN"}):
        assert tema_dxc.get_text("nav_marina") == "Marina's Dashboard"

    with patch.object(tema_dxc.st, "session_state", {}):
        assert tema_dxc.get_text("nav_rafael") == "Painel do Rafael"


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
