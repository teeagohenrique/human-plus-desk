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
    assert t is not None
    agora = datetime(2026, 11, 24, 15, 0)
    e = acervo.estimar(t, 0, agora)
    assert e.previsto_de.isoformat() == "2026-11-24T15:45:00-03:00"
    assert e.minutos_min == 45 and e.previsto_ate.isoformat() == "2026-11-24T16:50:00-03:00"


def test_estimar_considera_horario_comercial_ao_virar_o_expediente():
    t = acervo.obter_topico("M01-T01")
    assert t is not None
    agora = datetime(2026, 11, 24, 17, 30)

    e = acervo.estimar(t, 0, agora)

    assert e.previsto_de.isoformat() == "2026-11-25T09:15:00-03:00"
    assert e.previsto_ate.isoformat() == "2026-11-25T10:20:00-03:00"


def test_estimar_pula_fim_de_semana_em_minutos_uteis():
    t = acervo.obter_topico("M01-T01")
    assert t is not None
    agora = datetime(2026, 11, 27, 17, 30)

    e = acervo.estimar(t, 1, agora)

    assert e.previsto_de.isoformat() == "2026-11-30T10:20:00-03:00"
    assert e.previsto_ate.isoformat() == "2026-11-30T11:30:00-03:00"


def test_revisao_tem_20_topicos_com_faixas_nao_decrescentes():
    topicos = acervo.todos_topicos()
    assert len(topicos) == 20
    for topico in topicos:
        faixas = topico.tabela_tempo
        assert [f.min for f in faixas] == sorted(f.min for f in faixas), topico.id
        assert [f.max for f in faixas] == sorted(f.max for f in faixas), topico.id


def test_acervo_bilingue_tem_traducao_completa_dos_20_topicos():
    for topico in acervo.todos_topicos():
        assert acervo.texto_topico(topico, "titulo", "EN")
        assert acervo.texto_topico(topico, "problema", "EN")
        assert acervo.texto_topico(topico, "solucao_provisoria", "EN")
        assert len(acervo.texto_topico(topico, "passos", "EN")) == len(topico.passos)
        assert len(acervo.cenarios_topico(topico, "EN")) == len(topico.tabela_tempo)


def test_traducao_ingles_material_e_topico():
    topico = acervo.obter_topico("M01-T01")
    assert topico is not None
    assert acervo.texto_material(topico.material_id, "titulo", "EN") == "Corporate Systems: Instability and Outages"
    assert acervo.texto_topico(topico, "titulo", "EN") == "Billing system freezing or unavailable"


def test_traducoes_ingles_cobrem_exatamente_materiais_topicos_e_campos():
    traducoes = acervo._carregar_traducoes_en()
    materiais = acervo.carregar()
    assert set(traducoes["materials"]) == {material.id for material in materiais}
    assert set(traducoes["topics"]) == {
        topico.id for material in materiais for topico in material.topicos
    }
    for material in materiais:
        traducao = traducoes["materials"][material.id]
        assert traducao["title"] and traducao["summary"]
        for topico in material.topicos:
            texto = traducoes["topics"][topico.id]
            assert texto["title"] and texto["problem"] and texto["solution"]
            assert len(texto["steps"]) == len(topico.passos)
            assert len(texto["scenarios"]) == len(topico.tabela_tempo)


def test_buscar_liga_chamado_ao_topico_com_palavras():
    r = acervo.buscar('O sistema de faturamento travou e preciso fechar o mês até o meio-dia.', 'falha_sistema')
    assert r is not None and r.topico.id == 'M01-T01'
    assert 'faturamento' in r.palavras and 'travou' in r.palavras


def test_buscar_sem_palavra_chave_nao_inventa():
    assert acervo.buscar('Obrigado pelo atendimento de ontem, deu tudo certo!', 'indefinida') is None


def test_buscar_ignora_acentos():
    r = acervo.buscar('A IMPRESSORA do 3o andar parou, temos auditoria hoje', 'falha_sistema')
    assert r is not None and r.topico.id == 'M04-T01'
