import pytest

from src.llm import (rascunho_com_llm, resolver_provider, triagem_com_llm, validar_trechos,
                     validar_triagem_trechos)
from src.mascara import mascarar
from src.percepcao import perceber
from src.triagem import triar

CHAMADO = (
    "Bom dia, aqui é o [NOME], CPF [CPF]. O sistema de faturamento travou pela "
    "terceira vez essa semana e eu preciso fechar o mês até o meio-dia."
)


def test_resolver_provider_padrao_e_regras(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert resolver_provider() == "regras"


def test_resolver_provider_gemini_sem_chave_cai_silenciosamente_para_regras(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert resolver_provider() == "regras"
    assert resolver_provider("gemini") == "regras"


def test_resolver_provider_rejeita_provedor_desconhecido():
    with pytest.raises(ValueError):
        resolver_provider("desconhecido")


def test_validar_trechos_aceita_evidencia_literal_com_espacos_normalizados():
    texto = "O sistema   de faturamento\ntravou pela terceira vez."
    ok, invalidos = validar_trechos(["sistema de faturamento travou", "terceira vez"], texto)
    assert ok and invalidos == []


def test_validar_trechos_rejeita_citacao_inventada_capitalizacao_alterada_e_pii_vazado():
    original = "CPF 123.456.789-09. O sistema travou hoje."
    mascarado = mascarar(original).texto
    ok_inv, inv = validar_trechos(["travou ontem"], mascarado)
    assert not ok_inv and inv == ["travou ontem"]

    ok_cap, cap = validar_trechos(["Sistema Travou"], mascarado)
    assert not ok_cap and cap == ["Sistema Travou"]

    ok_pii, pii = validar_trechos(["123.456.789-09"], mascarado)
    assert not ok_pii and pii == ["123.456.789-09"]


def test_triagem_com_llm_padrao_regras_bate_com_triar_e_valida_trechos(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    t_llm = triagem_com_llm(CHAMADO)
    t_regras = triar(CHAMADO)
    assert t_llm == t_regras
    ok, invalidos = validar_triagem_trechos(t_llm, CHAMADO)
    assert ok and invalidos == []


def test_rascunho_com_llm_fallback_regras_passa_no_guardrail(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    t = triagem_com_llm(CHAMADO)
    p = perceber(CHAMADO, t)
    r = rascunho_com_llm(CHAMADO, t, palpites=p, leitura="pressa_prazo")
    assert r.passou_guardrail, r.feedback_guardrail
    assert "caminho provisório" in r.texto


def test_main_padrao_continua_regras_e_aceita_flag_provider(monkeypatch):
    from src import main
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    args_padrao = main._parse_args(["--avaliar"])
    assert args_padrao.provider is None
    assert resolver_provider(args_padrao.provider) == "regras"

    res = main.avaliar(main.DADOS)
    assert res["provider"] == "regras"
    assert res["acertos_intencao"] == res["n"]
    assert res["acertos_urgencia"] == res["n"]

    out = main.processar("TEST-1", "Bom dia, aqui é o Carlos. O sistema travou até as 12h.", log=None)
    assert "[NOME]" in out["mascara"].texto
    assert out["rascunho"].passou_guardrail


class _ErroAPI(Exception):
    def __init__(self, code: int, retry_delay: str | None = None):
        self.code = code
        detalhes = []
        if retry_delay is not None:
            detalhes.append({
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                "retryDelay": retry_delay,
            })
        self.details = {"error": {"details": detalhes}}
        super().__init__(f"erro {code}")


class _ClienteFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.chamadas += 1
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _preparar_sem_pausa(monkeypatch):
    from src import llm

    monkeypatch.setattr(llm, "_ULTIMA_CHAMADA_GEMINI", None)
    monkeypatch.setattr(llm.time, "sleep", lambda segundos: None)
    monkeypatch.setattr(llm.time, "monotonic", lambda: 0.0)


def test_pausa_entre_chamadas_respeita_intervalo(monkeypatch):
    from src import llm

    monkeypatch.setattr(llm, "_ULTIMA_CHAMADA_GEMINI", None)
    relogio = [0.0]
    dormidas = []

    def dormir(segundos):
        dormidas.append(segundos)
        relogio[0] += segundos

    monkeypatch.setattr(llm.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(llm.time, "sleep", dormir)

    llm._pausar_entre_chamadas()
    relogio[0] = 1.0
    llm._pausar_entre_chamadas()
    assert dormidas == [pytest.approx(llm.INTERVALO_MINIMO_GEMINI - 1.0)]

    relogio[0] = 10.0
    llm._pausar_entre_chamadas()
    assert len(dormidas) == 1


def test_backoff_429_respeita_retry_delay_da_api(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    dormidas = []
    relogio = [0.0]

    def dormir(segundos):
        dormidas.append(segundos)
        relogio[0] += segundos

    monkeypatch.setattr(llm.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(llm.time, "sleep", dormir)
    cliente = _ClienteFalso([_ErroAPI(429, "9.099506196s"), "resposta"])

    assert llm._chamar_api_gemini(cliente, "modelo", "prompt", None) == "resposta"
    assert cliente.chamadas == 2
    assert dormidas == [pytest.approx(9.099506196 + 0.2)]


def test_backoff_503_tambem_tenta_de_novo(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    cliente = _ClienteFalso([_ErroAPI(503), "resposta"])

    assert llm._chamar_api_gemini(cliente, "modelo", "prompt", None) == "resposta"
    assert cliente.chamadas == 2


def test_backoff_tem_limite_de_tres_tentativas(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    cliente = _ClienteFalso([_ErroAPI(429, "1s")] * 5)

    with pytest.raises(_ErroAPI):
        llm._chamar_api_gemini(cliente, "modelo", "prompt", None)
    assert cliente.chamadas == llm.MAX_TENTATIVAS_API


def test_erro_400_nao_e_repetido(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    cliente = _ClienteFalso([_ErroAPI(400)])

    with pytest.raises(_ErroAPI):
        llm._chamar_api_gemini(cliente, "modelo", "prompt", None)
    assert cliente.chamadas == 1
