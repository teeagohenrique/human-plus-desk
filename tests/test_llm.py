from types import SimpleNamespace

import pytest

from src.llm import (
    obter_contador_fallback,
    obter_contador_triagem,
    rascunho_com_llm,
    rascunho_com_origem,
    resolver_provider,
    triagem_com_llm,
    triagem_com_origem,
    validar_trechos,
    validar_triagem_trechos,
    zerar_contador_triagem,
    zerar_contadores,
)
from src.mascara import mascarar
from src.percepcao import perceber
from src.triagem import Triagem, triar

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


def test_backoff_503_tem_limite_de_cinco_tentativas(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    dormidas = []
    relogio = [0.0]

    def dormir(segundos):
        dormidas.append(segundos)
        relogio[0] += segundos

    monkeypatch.setattr(llm.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(llm.time, "sleep", dormir)
    cliente = _ClienteFalso([_ErroAPI(503)] * 6)

    with pytest.raises(_ErroAPI):
        llm._chamar_api_gemini(cliente, "modelo", "prompt", None)
    assert cliente.chamadas == llm.MAX_TENTATIVAS_503
    assert dormidas == [10.0, 20.0, 40.0, 60.0]


def test_backoff_503_respeita_retry_delay_quando_presente(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    dormidas = []
    relogio = [0.0]

    def dormir(segundos):
        dormidas.append(segundos)
        relogio[0] += segundos

    monkeypatch.setattr(llm.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(llm.time, "sleep", dormir)
    cliente = _ClienteFalso([_ErroAPI(503, "7s"), "resposta"])

    assert llm._chamar_api_gemini(cliente, "modelo", "prompt", None) == "resposta"
    assert dormidas == [pytest.approx(7.2)]


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


def _resposta_valida():
    return SimpleNamespace(parsed=triar(CHAMADO))


def _resposta_invalida():
    t = triar(CHAMADO).model_copy(deep=True)
    t.motivos_intencao[0].trecho = "trecho_inventado"
    return SimpleNamespace(parsed=t)


def _preparar_gemini_falso(monkeypatch, resposta):
    from src import llm

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")
    monkeypatch.setattr(llm, "_chamar_api_gemini", lambda *args, **kwargs: resposta)
    zerar_contador_triagem()


def test_contador_registra_triagem_gemini(monkeypatch):
    from src import llm

    _preparar_gemini_falso(monkeypatch, _resposta_valida())
    triagem_com_llm(CHAMADO, provider="gemini")
    assert obter_contador_triagem() == {"gemini": 1, "regras": 0, "fallback": 0}
    assert llm.CONTADOR_TRIAGEM is not obter_contador_triagem()


def test_contador_registra_fallback_por_trecho_invalido(monkeypatch):
    _preparar_gemini_falso(monkeypatch, _resposta_invalida())
    triagem_com_llm(CHAMADO, provider="gemini")
    assert obter_contador_triagem() == {"gemini": 0, "regras": 0, "fallback": 1}


def test_contador_registra_triagem_por_regras(monkeypatch):

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    zerar_contador_triagem()
    triagem_com_llm(CHAMADO, provider="regras")
    assert obter_contador_triagem() == {"gemini": 0, "regras": 1, "fallback": 0}


def test_avaliar_expoe_origem_das_respostas(monkeypatch):
    from src import main

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = main.avaliar(main.DADOS)
    assert res["origem"] == {"gemini": 0, "regras": res["n"], "fallback": 0}


def test_backoff_misto_503_depois_429_para_no_limite_do_429(monkeypatch):
    from src import llm

    _preparar_sem_pausa(monkeypatch)
    # 3 erros 503 (tentativas 0, 1, 2) seguidos de 429 na tentativa 3 (>= MAX_TENTATIVAS_API - 1)
    cliente = _ClienteFalso([_ErroAPI(503), _ErroAPI(503), _ErroAPI(503), _ErroAPI(429, "1s"), "nao_alcanca"])
    with pytest.raises(_ErroAPI) as exc_info:
        llm._chamar_api_gemini(cliente, "modelo", "prompt", None)
    assert exc_info.value.code == 429
    assert cliente.chamadas == 4


def test_validar_trechos_rejeita_fragmento_de_palavra_e_aceita_palavra_inteira():
    texto = "O sistema caiu hoje. CPF [CPF]."
    ok_frag, inv_frag = validar_trechos(["cai"], texto)
    assert not ok_frag and inv_frag == ["cai"]

    ok_full, inv_full = validar_trechos(["caiu", "[CPF]"], texto)
    assert ok_full and inv_full == []


def test_triagem_com_origem_devolve_gemini_e_regras(monkeypatch):
    _preparar_gemini_falso(monkeypatch, _resposta_valida())
    t, origem = triagem_com_origem(CHAMADO, provider="gemini")
    assert origem == "gemini" and isinstance(t, Triagem)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    t2, origem2 = triagem_com_origem(CHAMADO, provider="regras")
    assert origem2 == "regras" and isinstance(t2, Triagem)


def test_rascunho_gemini_exige_os_dois_marcadores_no_retry(monkeypatch):
    from src import llm
    from src.redator import PEND_PRAZO, PEND_PROVISORIA

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")
    respostas = iter([
        SimpleNamespace(text="Olá! Entendi o problema e vamos verificar."),
        SimpleNamespace(text=f"Olá! Entendi o problema. {PEND_PRAZO} {PEND_PROVISORIA}"),
    ])
    prompts_vistos = []

    def chamar_falso(_cliente, _modelo, contents, _config):
        prompts_vistos.append(contents)
        return next(respostas)

    monkeypatch.setattr(llm, "_chamar_api_gemini", chamar_falso)
    r, origem = rascunho_com_origem(CHAMADO, triar(CHAMADO), provider="gemini")
    assert origem == "gemini"
    assert r.passou_guardrail
    assert PEND_PRAZO in r.pendencias and PEND_PROVISORIA in r.pendencias
    assert len(prompts_vistos) == 2
    assert "Faltam os marcadores" in prompts_vistos[1]


def test_rascunho_gemini_sem_os_dois_marcadores_cai_em_fallback(monkeypatch):
    from src import llm
    from src.redator import PEND_PRAZO

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")
    monkeypatch.setattr(
        llm, "_chamar_api_gemini",
        lambda *a, **k: SimpleNamespace(text=f"Olá! Entendi o problema. {PEND_PRAZO}"),
    )
    r, origem = rascunho_com_origem(CHAMADO, triar(CHAMADO), provider="gemini")
    assert origem == "fallback"
    assert r.passou_guardrail


def test_triagem_gemini_com_excecao_de_api_cai_em_fallback(monkeypatch):
    from src import llm

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")

    def falhar(*_args, **_kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(llm, "_chamar_api_gemini", falhar)
    t, origem = triagem_com_origem(CHAMADO, provider="gemini")
    assert origem == "fallback" and isinstance(t, Triagem)


def test_rascunho_gemini_com_excecao_de_api_cai_em_fallback(monkeypatch):
    from src import llm

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")

    def falhar(*_args, **_kwargs):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(llm, "_chamar_api_gemini", falhar)
    r, origem = rascunho_com_origem(CHAMADO, triar(CHAMADO), provider="gemini")
    assert origem == "fallback" and r.passou_guardrail


def test_fallback_por_trecho_invalido_e_registrado_com_motivo(monkeypatch):
    _preparar_gemini_falso(monkeypatch, _resposta_invalida())
    zerar_contadores()
    triagem_com_origem(CHAMADO, provider="gemini")
    motivos = obter_contador_fallback()
    assert motivos["trecho_invalido"] == 1
    assert sum(motivos.values()) == 1


def test_fallback_por_schema_invalido_e_registrado_com_motivo(monkeypatch):
    _preparar_gemini_falso(monkeypatch, SimpleNamespace(parsed={"nao": "e uma Triagem"}))
    zerar_contadores()
    triagem_com_origem(CHAMADO, provider="gemini")
    assert obter_contador_fallback()["schema_invalido"] == 1


@pytest.mark.parametrize("status,motivo", [(429, "erro_api_429"), (503, "erro_api_503")])
def test_fallback_por_erro_api_e_classificado_por_status(monkeypatch, status, motivo):
    from src import llm

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")

    def falhar(*_args, **_kwargs):
        raise _ErroAPI(status)

    monkeypatch.setattr(llm, "_chamar_api_gemini", falhar)
    zerar_contadores()
    triagem_com_origem(CHAMADO, provider="gemini")
    motivos = obter_contador_fallback()
    assert motivos[motivo] == 1
    assert sum(motivos.values()) == 1


def test_fallback_por_guardrail_e_marcadores_sao_distintos(monkeypatch):
    from src import llm
    from src.redator import PEND_PRAZO

    monkeypatch.setenv("GEMINI_API_KEY", "chave_teste")
    monkeypatch.setenv("GEMINI_MODEL", "modelo_teste")
    zerar_contadores()

    monkeypatch.setattr(
        llm, "_chamar_api_gemini",
        lambda *_a, **_k: SimpleNamespace(text="Você está nervoso; resolvo até amanhã às 10h."),
    )
    rascunho_com_origem(CHAMADO, triar(CHAMADO), provider="gemini")
    assert obter_contador_fallback()["guardrail"] == 1

    monkeypatch.setattr(
        llm, "_chamar_api_gemini",
        lambda *_a, **_k: SimpleNamespace(text=f"Olá, entendi o problema. {PEND_PRAZO}"),
    )
    rascunho_com_origem(CHAMADO, triar(CHAMADO), provider="gemini")
    motivos = obter_contador_fallback()
    assert motivos["guardrail"] == 1
    assert motivos["marcadores_faltantes"] == 1


def test_zerar_contadores_limpa_origem_e_motivos(monkeypatch):
    _preparar_gemini_falso(monkeypatch, _resposta_invalida())
    triagem_com_origem(CHAMADO, provider="gemini")
    assert any(obter_contador_fallback().values())

    zerar_contadores()
    assert obter_contador_triagem() == {"gemini": 0, "regras": 0, "fallback": 0}
    assert not any(obter_contador_fallback().values())


def test_avaliar_expoe_motivos_dos_fallbacks(monkeypatch):
    from src import llm, main

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    original = main.triagem_com_llm
    vistos = []

    def triagem_com_um_fallback(texto, provider=None):
        vistos.append(1)
        if len(vistos) == 1:
            llm._registrar_fallback("erro_api_503")
            llm._registrar_triagem("fallback")
        return original(texto, provider=provider)

    monkeypatch.setattr(main, "triagem_com_llm", triagem_com_um_fallback)
    res = main.avaliar(main.DADOS)
    assert res["fallback_motivos"]["erro_api_503"] == 1
    assert res["origem"]["fallback"] == 1


def test_pausa_reserva_slots_distintos_sem_espera_duplicada(monkeypatch):
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
    llm._pausar_entre_chamadas()
    llm._pausar_entre_chamadas()

    assert dormidas == [pytest.approx(llm.INTERVALO_MINIMO_GEMINI)] * 2


def test_usar_contadores_isola_metricas_e_respeita_aninhamento(monkeypatch):
    from src import llm

    monkeypatch.setattr(llm, "CONTADOR_TRIAGEM", {"gemini": 0, "regras": 0, "fallback": 0})
    monkeypatch.setattr(llm, "CONTADOR_FALLBACK", {m: 0 for m in llm.MOTIVOS_FALLBACK})

    with llm.usar_contadores() as contexto:
        llm._registrar_triagem("gemini")
        llm._registrar_fallback("erro_api_503")
        assert obter_contador_triagem()["gemini"] == 1

        with llm.usar_contadores():
            zerar_contadores()
            assert not any(obter_contador_triagem().values())

        assert obter_contador_triagem()["gemini"] == 1
        assert obter_contador_fallback()["erro_api_503"] == 1

    assert contexto.triagem["gemini"] == 1
    assert not any(llm.CONTADOR_TRIAGEM.values())
    assert not any(llm.CONTADOR_FALLBACK.values())


def test_avaliar_nao_suja_contador_global(monkeypatch):
    from src import llm, main

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "CONTADOR_TRIAGEM", {"gemini": 0, "regras": 0, "fallback": 0})
    monkeypatch.setattr(llm, "CONTADOR_FALLBACK", {m: 0 for m in llm.MOTIVOS_FALLBACK})

    res = main.avaliar(main.DADOS, provider="regras")

    assert res["origem"]["regras"] == res["n"]
    assert not any(llm.CONTADOR_TRIAGEM.values())
