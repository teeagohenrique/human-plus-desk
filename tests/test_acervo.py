from datetime import datetime

from src import acervo
from src.redator import _PROMESSA


def test_acervo_tem_5_materiais_com_3_a_5_topicos():
    materiais = acervo.carregar()
    assert len(materiais) == 5
    for m in materiais:
        assert 3 <= len(m.topicos) <= 5, m.id


def test_ids_de_topicos_sao_unicos():
    ids = [t.id for t in acervo.todos_topicos()]
    assert len(ids) == len(set(ids))


def test_topico_tem_campos_essenciais():
    for t in acervo.todos_topicos():
        assert t.palavras_chave, t.id
        assert t.solucao_provisoria.strip(), t.id
        assert len(t.passos) >= 3, t.id
        assert t.material_id and t.material_titulo, t.id


def test_tabela_de_tempo_coerente():
    for t in acervo.todos_topicos():
        assert len(t.tabela_tempo) >= 3, t.id
        for f in t.tabela_tempo:
            assert 0 < f.min <= f.max, (t.id, f.cenario)


def test_solucao_provisoria_nao_promete_prazo():
    # Alinhado ao guardrail do redator: prazo é só da analista.
    for t in acervo.todos_topicos():
        assert not _PROMESSA.search(t.solucao_provisoria), t.id
        assert "[" not in t.solucao_provisoria, t.id


def test_obter_topico():
    assert acervo.obter_topico("M01-T01").titulo.startswith("Faturamento")
    assert acervo.obter_topico("inexistente") is None


def test_estimar_converte_faixa_em_hora_e_data():
    t = acervo.obter_topico("M01-T01")
    agora = datetime(2026, 11, 24, 15, 0)
    e = acervo.estimar(t, 0, agora)
    assert e.previsto_de == datetime(2026, 11, 24, 15, 45)
    assert e.minutos_min == 45 and e.previsto_ate > e.previsto_de


def test_buscar_liga_chamado_ao_topico_com_palavras():
    r = acervo.buscar('O sistema de faturamento travou e preciso fechar o mês até o meio-dia.', 'falha_sistema')
    assert r is not None and r.topico.id == 'M01-T01'
    assert 'faturamento' in r.palavras and 'travou' in r.palavras


def test_buscar_sem_palavra_chave_nao_inventa():
    assert acervo.buscar('Obrigado pelo atendimento de ontem, deu tudo certo!', 'indefinida') is None


def test_buscar_ignora_acentos():
    r = acervo.buscar('A IMPRESSORA do 3o andar parou, temos auditoria hoje', 'falha_sistema')
    assert r is not None and r.topico.id == 'M04-T01'
