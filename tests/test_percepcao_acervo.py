"""Liga a hipótese de prazo (Análise Contextual) ao tópico do acervo."""
from src.percepcao import perceber
from src.triagem import triar


def test_hipotese_de_prazo_carrega_o_topico_do_acervo():
    texto = 'A VPN caiu de novo e preciso entregar o relatório até as 17h.'
    palpites = perceber(texto, triar(texto))
    nd = [p for p in palpites if p.tipo == 'necessidade_nao_dita']
    assert nd and nd[0].acervo_topico_id == 'M03-T01'
    assert 'vpn' in nd[0].acervo_palavras
