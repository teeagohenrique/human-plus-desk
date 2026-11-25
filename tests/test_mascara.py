from src.mascara import mascarar


def test_mascara_cpf_formatado():
    r = mascarar("Meu CPF é 123.456.789-09, obrigado")
    assert "123.456.789-09" not in r.texto
    assert "[CPF]" in r.texto


def test_mascara_cpf_sem_pontuacao():
    r = mascarar("cpf 12345678909")
    assert "12345678909" not in r.texto


def test_mascara_cnpj():
    r = mascarar("CNPJ 12.345.678/0001-95")
    assert "[CNPJ]" in r.texto and "12.345.678" not in r.texto


def test_mascara_email():
    r = mascarar("escreva para ana.souza@empresa.com.br")
    assert "[EMAIL]" in r.texto and "ana.souza" not in r.texto


def test_mascara_telefones():
    for tel in ["(11) 98765-4321", "11 98765-4321", "+55 11 98765-4321", "(11) 3456-7890"]:
        r = mascarar(f"ligue {tel} por favor")
        assert tel not in r.texto, tel
        assert "[TELEFONE]" in r.texto, tel


def test_nao_mascara_numeros_comuns():
    texto = "Chamado 4521, 3º andar, às 17h, terceira vez"
    assert mascarar(texto).texto == texto


def test_registra_tipos_encontrados():
    r = mascarar("CPF 123.456.789-09 e e-mail a@b.com")
    assert sorted(r.tipos_encontrados) == ["CPF", "EMAIL"]


def test_mascara_nomes_em_apresentacao_tratamento_e_atribuicao():
    casos = [
        ("Bom dia, aqui é o Carlos. O sistema travou.", "Carlos"),
        ("Meu nome é Maria Clara da Silva e preciso de acesso.", "Maria Clara da Silva"),
        ("Favor verificar o chamado do Sr. João Pereira.", "João Pereira"),
        ("Liberar acesso à pasta do RH para a Júlia.", "Júlia"),
        ("Instalar o software na máquina da Paula.", "Paula"),
    ]
    for texto, nome in casos:
        r = mascarar(texto)
        assert nome not in r.texto, (texto, r.texto)
        assert "[NOME]" in r.texto, (texto, r.texto)
        assert "NOME" in r.tipos_encontrados


def test_nao_mascara_siglas_sistemas_ou_dias_como_nome():
    texto = "Liberar acesso para o Excel, verificar o VPN no RH até Sexta e preparar para a reunião das 14h."
    r = mascarar(texto)
    assert "[NOME]" not in r.texto
    assert "Excel" in r.texto and "VPN" in r.texto and "RH" in r.texto and "reunião das 14h" in r.texto


def test_ner_indisponivel_na_execucao_e_reportado_na_mascara():
    from unittest.mock import patch

    class _FalhaAnalise:
        def analyze(self, **kwargs):
            raise RuntimeError("falha simulada")

    with patch("src.ner_local._analisador", return_value=_FalhaAnalise()):
        resultado = mascarar("Texto de chamado com Beatriz Lima")

    assert resultado.ner_disponivel is False


def test_mascara_nome_fora_dos_prefixos_com_ner_local():
    texto = "O relatório foi revisado por Beatriz Lima antes do envio."
    r = mascarar(texto)
    assert "Beatriz Lima" not in r.texto
    assert r.texto == "O relatório foi revisado por [NOME] antes do envio."
    assert "NOME" in r.tipos_encontrados


def test_ner_nao_transforma_verbos_e_saudacoes_em_nome():
    for texto in [
        "Procurei no menu e não achei.",
        "Abri dois chamados semana passada.",
        "CNPJ 12.345.678/0001-95",
        "Olá, tudo bem?",
    ]:
        assert "[NOME]" not in mascarar(texto).texto, texto
    r = mascarar("Favor verificar o chamado do Sr. João Pereira.")
    assert "Favor" in r.texto
    assert "João Pereira" not in r.texto
